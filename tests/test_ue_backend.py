"""UeMcpBackend 解析/路由单测（不连真引擎）：以假 capability 验证 tool 名→(toolset,tool) 调用。"""
from __future__ import annotations

import json

import pytest

from orchestrator.ue_backend import UeMcpBackend


class _FakeUE:
    """模拟 UE5.8 MCP：仅 BasicSpawnTools 与 EditorAppToolsets 的 describe 可反。"""

    TOOLSETS = [
        "basic_spawn.basic_spawn_tools.BasicSpawnTools",
        "EditorToolset.EditorAppToolset",
    ]

    def ensure_session(self) -> bool:
        return True

    def ping(self) -> bool:
        return True

    def list_toolsets_text(self) -> str:
        lines = "".join(f"- {n}: desc\n" for n in self.TOOLSETS)
        return lines

    def describe_toolset(self, ts: str) -> str:
        if ts == "basic_spawn.basic_spawn_tools.BasicSpawnTools":
            obj = {
                "name": ts, "tools": [
                    {"name": "place_cube", "inputSchema": {}},
                    {"name": "list_agent_cubes", "inputSchema": {}},
                    {"name": "remove_cube", "inputSchema": {}},
                ],
            }
        elif ts == "EditorToolset.EditorAppToolset":
            obj = {
                "name": ts, "tools": [
                    {"name": "EditorToolset.EditorAppToolset.GetSelectedAssets", "inputSchema": {}},
                    {"name": "EditorToolset.EditorAppToolset.GetVisibleActors", "inputSchema": {}},
                ],
            }
        else:
            obj = {"name": ts, "tools": []}
        return json.dumps(obj)

    def call_tool(self, toolset: str, tool_name: str, arguments: dict) -> str:
        # 模拟 UE 返回
        if tool_name == "place_cube":
            return '{"returnValue": "{\\"ok\\": true, \\"actor_label\\": \"AgentCube\\"}"}'
        if tool_name == "list_agent_cubes":
            return '{"returnValue": "[{\\"label\\": \\"AgentCube\\", \\"x\\": 0.0}]"}'
        if tool_name == "remove_cube":
            return '{"returnValue": "{\\"ok\\": true, \\"removed\\": 1}"}'
        return '{"returnValue": "{}"}'


def _backend():
    return UeMcpBackend(ue=_FakeUE(), discover=True)


def test_capability_loaded():
    b = _backend()
    assert b._cap_loaded is True
    names = b.ue_tool_names()
    assert "place_cube" in names
    assert "list_agent_cubes" in names


def test_resolve_plain_and_toolset():
    b = _backend()
    assert b.resolve("place_cube") == ("basic_spawn.basic_spawn_tools.BasicSpawnTools", "place_cube")
    # 显式 :: 形态
    assert b.resolve("basic_spawn.basic_spawn_tools.BasicSpawnTools::remove_cube") == \
        ("basic_spawn.basic_spawn_tools.BasicSpawnTools", "remove_cube")


def test_call_tool_ok_and_structured():
    b = _backend()
    r = b.call_tool("place_cube", {"label": "AgentCube"}, risk="mutating")
    assert r.ok is True
    rv = r.data.get("returnValue") if isinstance(r.data, dict) else r.data
    assert "ok" in str(rv)


def test_call_tool_unsupported():
    b = _backend()
    r = b.call_tool("rag_search", {})   # 本地/非 UE 工具，无映射
    assert r.ok is False
    assert r.error_code == "TOOL_UNSUPPORTED"
