"""UE5.8 真执行后端（UeMcpBackend）—— 可注入 Host.run 作为 mcp 后端，驱动 Skill 步骤真调 UE。

形态对齐 orchestrator.mcp_client.McpClient：暴露 `call_tool(tool_name, arguments, risk=None, metadata=None)`
与 `list_tools()`，使 `Host.run(skill)` 无需改动即可在真 UE 后端上执行。

真实能力面（UE 工具）：
- 用 UE5.8 MCP 会话（ue_mcp.UeMcpClient）动态取 list_toolsets + 对每个 toolset describe_toolset，
  汇聚成 `(toolset_name, plain_tool_name, inputSchema)` 的 UE 工具面 cache。
- Skill 步骤 `step.tool` -> 解析成真实调用：支持
    * "toolset.tool"/(`x::y`) 显式形态；
    * 纯 plain_tool_name 时在 cache 中按名匹配（命中同 tool 名即真调）；
    * 内置常用别名表（place_cube/remove_cube/list_agent_cubes 等自研 BasicSpawn、pcg_validate 等）在 cap 可用时直达。
- 找不到对应 UE 工具时返回明确 unsupported（不伪装 stub）。

routing：Host 默认用原 McpClient；本后端仅在显式 `--backend ue` 或 Host(mcp=UeMcpBackend(...)) 时启用。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from orchestrator.mcp_client import ToolResult
from orchestrator.ue_mcp import UeMcpClient

log = logging.getLogger(__name__)

# 若干 Skill step.tool（我们 own 的 step tool 名）到 UE 工具 plain name 的别名（cap 命中后生效）
_ALIAS: dict[str, str] = {
    "place_cube": "place_cube",
    "remove_cube": "remove_cube",
    "list_agent_cubes": "list_agent_cubes",
    "project_list_directory": "list_project_file_paths",  # 若存在，否则回退 unsupported
    "pcg_validate": "validate",
    "pcg_generate_graph": "generate_graph",
}


def _normalize(raw: Any) -> dict:
    result: list[dict] = []
    if isinstance(raw, list):
        for it in raw:
            if isinstance(it, dict) and it.get("type") == "text":
                try:
                    parsed = json.loads(it["text"])
                except Exception:
                    parsed = None
                if isinstance(parsed, dict):
                    result.append(parsed)
            elif isinstance(it, dict):
                result.append(it)
    elif isinstance(raw, dict):
        result.append(raw)
    return result[0] if result else {}


class UeMcpBackend:
    """真 UE MCP 后端。on-demand 会话，编辑器/8000 在线时才可用。"""

    def __init__(self, endpoint: str = "http://127.0.0.1:8000/mcp",
                 ue: Optional[UeMcpClient] = None, discover: bool = True):
        self.ue = ue or UeMcpClient(endpoint=endpoint)
        self._cap_loaded = False
        self._cap: dict[str, list[dict]] = {}   # toolset -> tools[{name,inputSchema}]
        if discover:
            self.load_capability()

    # --- capability ---
    def load_capability(self) -> bool:
        if not self.ue.ensure_session():
            log.info("Ue 后端不可用（编辑器未在线/8000 未监听），能力面为空。")
            return False
        try:
            text = self.ue.list_toolsets_text()
            toolsets = _extract_meta_names(text) or []
            if not toolsets:
                # tools/call 返回 text 形如 list；退化为对该文本直接按 "- x.y:" 解析
                toolsets = _extract_meta_names_from_plain(text)
            for ts in toolsets:
                try:
                    desc = self.ue.describe_toolset(ts)   # 返回的是 JSON 字符串（toolset 对象）
                    parsed = json.loads(desc) if isinstance(desc, str) else desc
                    if isinstance(parsed, str):
                        parsed = json.loads(parsed)
                    tools = parsed.get("tools", []) if isinstance(parsed, dict) else []
                    # 若工具带 toolset 前缀,保留 plain names
                    self._cap[ts] = tools
                except Exception as exc:  # noqa: BLE001
                    log.warning("describe %s 失败: %s", ts, exc)
            self._cap_loaded = True
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("无法枚举 UE 工具面: %s", exc)
            return False

    def tools_in(self, toolset: str) -> list[str]:
        return [t.get("name", "") for t in self._cap.get(toolset, [])]

    def ue_tool_names(self) -> list[str]:
        out = []
        for tl in self._cap.values():
            for t in tl:
                n = t.get("name", "")
                if n and n not in out:
                    out.append(n)
        return out

    def resolve(self, tool_name: str) -> tuple[str, str] | None:
        """返回 (toolset_name, plain_tool). None=未找到。"""
        if "::" in tool_name:
            ts, t = tool_name.split("::", 1)
            return (ts, t)
        # 显式 toolset.tool
        base = tool_name.split(".")[-1]
        cand = [t for t in base.split(".") if t]
        # 纯 plain name 直接在 cap 所有 toolset 里搜
        for ts, tl in self._cap.items():
            for t in tl:
                n = t.get("name", "")
                plain = n.split(".")[-1] if "." in n else n
                if plain == tool_name or n == tool_name:
                    return (ts, plain)
        # 别名
        alias = _ALIAS.get(tool_name)
        if alias:
            for ts, tl in self._cap.items():
                for t in tl:
                    n = t.get("name", "")
                    plain = n.split(".")[-1] if "." in n else n
                    if plain == alias:
                        return (ts, plain)
        return None

    # --- compat 接口（与 McpClient 一致，供 Host） ---
    def list_tools(self) -> list[dict]:
        out = []
        for ts, tl in self._cap.items():
            for t in tl:
                out.append({"toolset": ts, **t})
        return out

    def call_tool(self, tool_name: str, arguments: dict,
                  risk: Any = None, metadata: dict | None = None) -> ToolResult:
        if not self._cap_loaded:
            ok = self.load_capability()
            if not ok:
                return ToolResult(ok=False, error_code="ENGINE_OFFLINE",
                                  detail="UE MCP 不可用（编辑器未在线/8000 未监听）")
        hit = self.resolve(tool_name)
        if not hit:
            log.warning("后端无 UE 工具对应 %s（可用 UE 工具缺或不匹配）", tool_name)
            return ToolResult(ok=False, error_code="TOOL_UNSUPPORTED",
                              detail=f"UE 工具面中无 {tool_name!r} 的映射；仅列 {sorted(self.ue_tool_names())[:12]}")
        ts, t = hit
        try:
            txt = self.ue.call_tool(ts, t, arguments)
        except Exception as exc:  # noqa: BLE001
            log.exception("真 UE 调用失败 %s::%s", ts, t)
            return ToolResult(ok=False, error_code="TOOL_CALL_ERROR", detail=str(exc))
        # 尝试还原成结构化
        data: Any = txt
        try:
            inner = json.loads(txt) if txt.strip().startswith("{") else None
            if isinstance(inner, dict) and "returnValue" in inner:
                rv = inner["returnValue"]
                if isinstance(rv, str):
                    try:
                        rv = json.loads(rv)
                    except Exception:
                        pass
                data = {"returnValue": rv}
            elif inner is not None:
                data = inner
        except Exception:  # noqa: BLE001
            pass
        return ToolResult(ok=True, data=data)

    def ping(self) -> bool:
        return self.ue.ping()


# ---- capability 文本解析 helpers ----
def _extract_meta_names(text: str) -> list[str]:
    if "--":  # noqa: SIM108 internal no-op keep simple
        pass
    lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("- ")]
    names = []
    for ln in lines:
        head = ln.lstrip("- ").split(":", 1)[0].strip()
        if head and "." in head:
            names.append(head)
    return names


def _extract_meta_names_from_plain(text: str) -> list[str]:
    names = []
    import re
    for m in re.finditer(r'([A-Za-z0-9_]+\.[A-Za-z0-9_]+)\s*:', text):
        n = m.group(1)
        if n not in names:
            names.append(n)
    return names
