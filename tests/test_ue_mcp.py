"""UE 真 MCP client 本地测试（不连引擎）：
- _content_text 解析各种 MCP result 文本
- find_toolset_containing 从 list_toolsets 文本找 BasicSpawn
- 连不上时 ensure_session 不 panic（返回 False）
"""
from __future__ import annotations

import json

import pytest

from orchestrator.ue_mcp import UeMcpClient, _content_text


def test_content_text_variants():
    assert _content_text({"content": [{"type": "text", "text": "hello"}]}) == "hello"
    assert "returnValue" in _content_text({"returnValue": []})
    assert _content_text("plain") == "plain"


def test_find_toolset_containing():
    c = UeMcpClient()
    c.listtext = "- BasicSpawnTools.BasicSpawnTools: Minimal spawn/remove of cube."
    c.list_toolsets_text = lambda: c.listtext

    got = c.find_toolset_containing("BasicSpawn")
    assert got == "BasicSpawnTools.BasicSpawnTools"


def test_ensure_session_unreachable_is_false():
    # 默认端口无服务 → 连不上应返回 False、不抛
    c = UeMcpClient(endpoint="http://127.0.0.1:1")
    assert c.ensure_session() is False


def test_call_tool_builds_meta(monkeypatch):
    c = UeMcpClient()
    c.session_id = "sess"
    calls = {}

    def fake_request(method, params, rpc_id=1, need_session=True):
        assert method == "tools/call"
        assert params["arguments"]["toolset_name"] == "BasicSpawnTools.BasicSpawnTools"
        assert params["arguments"]["tool_name"] == "place_cube"
        calls["params"] = params
        return {"content": [{"type": "text", "text": '{"ok": true}'}]}

    monkeypatch.setattr(c, "request", fake_request)
    out = c.call_tool("BasicSpawnTools.BasicSpawnTools", "place_cube", {"label": "AgentCube"})
    assert "ok" in out and '"ok": true' in out
    assert calls
