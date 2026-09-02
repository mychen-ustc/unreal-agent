"""UE 5.8 真 MCP client —— 与自研桩不同的真实会话模型。

引擎 MCP(127.0.0.1:8000/mcp, JSON-RPC over HTTP):
- initialize 返回 `Mcp-Session-Id` 头；后续请求须携带该 Id（session 模型）。
- 工具发现走 `tools/call` 调顶层 meta：list_toolsets / describe_toolset(call) list meta tools
  tools/list。
- 执行注册工具走 meta `call_tool`, 参数 {toolset_name, tool_name, arguments}。
(与 orchestrator/mcp_client 的简单 single-method 自研桩不同；本模块服务于 AC-P0 真引擎闭环节点。)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

log = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "http://127.0.0.1:8000/mcp"


def _content_text(result: Any) -> str:
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list):
            return "".join(
                i.get("text", "") for i in content if isinstance(i, dict) and i.get("type") == "text"
            )
        if "content" in result:
            return json.dumps(result["content"], ensure_ascii=False)
        return json.dumps(result, ensure_ascii=False)
    return str(result)


class UeMcpClient:
    """针对 UE 5.8 MCP session 协议的最小只调用客户端。"""

    def __init__(self, endpoint: str = DEFAULT_ENDPOINT, timeout: float = 60.0):
        self.endpoint = endpoint
        self._client = httpx.Client(base_url=endpoint, timeout=timeout)
        self.session_id: Optional[str] = None

    # ---- 请求 ----
    def _headers(self, need_session: bool = True) -> dict:
        h = {"Content-Type": "application/json"}
        if need_session and self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    def request(self, method: str, params: dict, rpc_id: int = 1, need_session: bool = True) -> Any:
        body = {"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params}
        resp = self._client.post("/", headers=self._headers(need_session), json=body)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"MCP error({data['error'].get('code')}): {data['error'].get('message')}")
        return data.get("result")

    def initialize(self) -> str:
        # 需要捕获响应头拿到 session id
        body = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "unreal-orchestrator", "version": "0.1.0"}}}
        with self._client.stream("POST", "/", headers={"Content-Type": "application/json"}, json=body) as r:
            r.raise_for_status()
            sid = r.headers.get("Mcp-Session-Id")
            r.read()
            data = r.json()
        if sid:
            self.session_id = sid
        else:
            raise RuntimeError("initialize 未返回 Mcp-Session-Id")
        return self.session_id

    def ensure_session(self) -> bool:
        if not self.session_id:
            try:
                self.initialize()
                return True
            except Exception as exc:  # noqa: BLE001
                log.warning("无法连 UE MCP: %s", exc)
                return False
        return True

    # ---- 工具 ----
    def ping(self) -> bool:
        try:
            self.ensure_session()
            self.request("ping", {}, need_session=True)
            return True
        except Exception:  # noqa: BLE001
            return False

    # top meta 工具也是通过 tools/call 提交（select 表单类似单层）
    def call_top(self, top_name: str, arguments: dict | None = None) -> str:
        self.ensure_session()
        result = self.request(
            "tools/call",
            {"name": top_name, "arguments": arguments or {}},
            need_session=True,
        )
        return _content_text(result)

    def call_tool(self, toolset_name: str, tool_name: str, arguments: dict | None = None) -> str:
        """经过 meta `call_tool` 调用某个 toolset 内的真实工具，返回解析后的文本。"""
        self.ensure_session()
        inner = {"toolset_name": toolset_name, "tool_name": tool_name,
                 "arguments": arguments or {}}
        result = self.request("tools/call", {"name": "call_tool", "arguments": inner},
                              need_session=True)
        return _content_text(result)

    def list_toolsets_text(self) -> str:
        return self.call_top("list_toolsets")

    def describe_toolset(self, toolset_name: str) -> str:
        return self.call_top("describe_toolset", {"toolset_name": toolset_name})

    def tools_list(self) -> str:  # 顶层（session）工具清单，用于确认 meta tools 存在
        self.ensure_session()
        result = self.request("tools/list", {}, need_session=True)
        names = []
        for t in (result or {}).get("tools", []):
            names.append(t.get("name"))
        return ",".join(names)

    # ---- 便捷：定位自研 toolset & cube 闭环 ----
    def find_toolset_containing(self, seed: str) -> str:
        """从 list_toolsets 中找名字含 seed 的 toolset。"""
        txt = self.list_toolsets_text()
        for line in txt.splitlines():
            # 形如 "- <ToolsetName>: <desc>"
            if line.lstrip().startswith("- "):
                name = line.split(":", 1)[0].replace("-", "").strip()
                if seed.lower() in name.lower():
                    return name
        return ""

    def close(self) -> None:
        self._client.close()
