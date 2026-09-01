"""MCP Client —— Orchestrator 的「唯一写入者」（TechDesign §2.2 / §6.1）。

职责：
- 作为唯一发起 Tool 写入调用的实体，保证 Game Thread 串行。
- 暴露 list_tools / call_tool / ping。
- 调用前经过风险分级审批门（read_only 自动放行 / mutating 触发 yN / destructive 阻塞人工）。

P0：本模块提供可插入的 Transport。
- `HttpTransport`：走 UE 5.8 MCP Server (127.0.0.1:8000/mcp)。
- `StubTransport`：无 UE 时的本地调用（测试 / 脚手架自检用），不真正写引擎。
"""
from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any, Protocol, runtime_checkable

import httpx

log = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "http://127.0.0.1:8000/mcp"


class RiskLevel(str, Enum):
    READ_ONLY = "read_only"
    MUTATING = "mutating"
    DESTRUCTIVE = "destructive"

    @classmethod
    def classify(cls, tool_name: str) -> "RiskLevel":
        if any(k in tool_name for k in ("delete_", "destroy", "rollback", "clear_")):
            return cls.DESTRUCTIVE
        if any(k in tool_name for k in ("write_", "create_", "update_", "set_", "move_", "rename_", "generate_")):
            return cls.MUTATING
        return cls.READ_ONLY


class ToolResult:
    """与附录 B 对齐的统一返回结构。"""

    def __init__(self, ok: bool, data: Any = None, error_code: str = "", detail: str = "", version: str = "1.2.0"):
        self.ok = ok
        self.data = data
        self.error_code = error_code
        self.detail = detail
        self.version = version

    def as_dict(self) -> dict:
        if self.ok:
            return {"ok": True, "data": self.data, "version": self.version}
        return {"ok": False, "error_code": self.error_code, "detail": self.detail}

    @classmethod
    def from_response(cls, body: Any) -> "ToolResult":
        if isinstance(body, dict) and body.get("ok") is not None:
            return cls(
                ok=body["ok"],
                data=body.get("data"),
                error_code=body.get("error_code", ""),
                detail=body.get("detail", ""),
                version=body.get("version", "1.2.0"),
            )
        return cls(ok=True, data=body)

    def __repr__(self) -> str:  # pragma: no cover
        return f"ToolResult(ok={self.ok}, code={self.error_code or '-'}, data={self.data!r})"


@runtime_checkable
class MCPTransport(Protocol):
    def call(self, method: str, params: dict) -> Any: ...


class HttpTransport:
    """连 UE 5.8 的 MCP Server (HTTP, JSON-RPC over HTTP)。"""

    def __init__(self, endpoint: str = DEFAULT_ENDPOINT, timeout: float = 30.0) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self._client = httpx.Client(base_url=endpoint, timeout=timeout)

    def call(self, method: str, params: dict) -> Any:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        resp = self._client.post("/", json=payload)
        resp.raise_for_status()
        body = resp.json()
        if "error" in body:
            raise RuntimeError(f"MCP error: {body['error']}")
        return body.get("result")

    def close(self) -> None:
        self._client.close()


class StubTransport:
    """无 UE 时的本地桩（脚手架/CI 自检）。只回显 list_tools，写调用抛『需 UE 在线』。"""

    TOOLS = [
        {"name": "pcg_generate_graph", "description": "按 JSON 规格生成/修改 PCG Graph 资产", "risk": "mutating"},
        {"name": "place_actor", "description": "在关卡中放置 Actor", "risk": "mutating"},
        {"name": "list_tools", "description": "列出全部 Tool 及 JSON Schema", "risk": "read_only"},
        {"name": "git_commit", "description": "Agent 改动自动 commit（post-tool hook）", "risk": "mutating"},
    ]

    def __init__(self, require_ue: bool = True) -> None:
        self.require_ue = require_ue
        self.log: list[dict] = []

    def call(self, method: str, params: dict) -> Any:
        if method == "tools/list" or method == "list_tools":
            return {"tools": self.TOOLS}
        if method in ("ping", "initialize"):
            return {"ok": True}
        if self.require_ue:
            raise RuntimeError("UE 编辑器未在线（StubTransport：写操作需连接 UE 5.8 MCP Server）")
        self.log.append({"method": method, "params": params})
        return {"ok": True, "data": {"stubbed": True}}


class McpClient:
    """唯一写入者门面：持有 Transport + 审批回调，串行执行写调用。"""

    def __init__(self, transport: MCPTransport | None = None, approver=None):
        self.transport = transport or StubTransport(require_ue=True)
        self.approver = approver or default_approver
        self._write_lock_held = False

    # ---- 只读 ----
    def list_tools(self) -> list[dict]:
        return (self.transport.call("list_tools", {}) or {}).get("tools", [])

    def ping(self) -> bool:
        try:
            return bool(self.transport.call("ping", {}))
        except Exception:  # noqa: BLE001
            return False

    # ---- 写（唯一写入者串行 + 审批） ----
    def call_tool(
        self,
        tool_name: str,
        arguments: dict,
        risk: RiskLevel | str | None = None,
        metadata: dict | None = None,
    ) -> ToolResult:
        risk_ = RiskLevel(risk) if risk else RiskLevel.classify(tool_name)

        # 审批门
        if not self.approver(tool_name, arguments, risk_, metadata or {}):
            return ToolResult(ok=False, error_code="APPROVAL_DENIED", detail=f"工具 {tool_name} 被拒绝")

        # 唯一写入者：写调用串行执行（P0 单进程内加锁占位）
        if risk_ != RiskLevel.READ_ONLY and self._write_lock_held:
            return ToolResult(ok=False, error_code="BUSY", detail="已有写调用在进行中")
        self._write_lock_held = risk_ != RiskLevel.READ_ONLY

        try:
            body = self.transport.call(
                "tools/call" if risk_ != RiskLevel.READ_ONLY else tool_name,
                {"name": tool_name, "arguments": arguments},
            )
            return ToolResult.from_response(body)
        except Exception as exc:  # noqa: BLE001
            log.warning("Tool %s 调用失败: %s", tool_name, exc)
            return ToolResult(ok=False, error_code="TOOL_CALL_ERROR", detail=str(exc))
        finally:
            self._write_lock_held = False


def default_approver(tool_name: str, arguments: dict, risk: RiskLevel, metadata: dict) -> bool:
    """默认审批：read_only 自动放行；mutating/destructive 走交互 yN（P0 CLI 内联）。"""
    if risk == RiskLevel.READ_ONLY:
        return True
    # 脚手架默认打印风险并请求确认（CI 可用 --auto-approve 覆盖）
    from rich.console import Console

    console = Console()
    console.print(f"[yellow]审批[/] 工具={tool_name} 风险={risk.value} 参数={_shorten(arguments)}")
    ans = input(f"  允许执行? [y/N]: ").strip().lower()
    return ans in ("y", "yes")


def _shorten(d: dict, maxlen: int = 120) -> str:
    s = json.dumps(d, ensure_ascii=False)
    return s if len(s) <= maxlen else s[: maxlen - 3] + "..."
