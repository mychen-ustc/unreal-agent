"""Toolset Registry 与 MCP 桩能力测试（对齐 TechDesign §4.1 / Agent Harness §12）。

验证 12 个自研 Toolset 可被桩态 list_tools 发现，Skill 步骤经 MCP 唯一写入者调工具。
"""
from __future__ import annotations


def test_twelve_toolsets_registered():
    from orchestrator import toolset_registry as reg

    ts = reg.toolset_names()
    expect = {"ProjectToolset", "SafeguardToolset", "PCGToolset", "ArtPipelineToolset",
              "BuildToolset", "LightingToolset", "AudioToolset", "UIToolset",
              "DataToolset", "ProfilerToolset", "PlaytestToolset", "BenchmarkToolset"}
    assert set(ts) == expect
    # 每个关键工具都有元数据
    assert reg.get_tool_meta("pcg_generate_graph").toolset == "PCGToolset"
    assert reg.get_tool_meta("playtest_smoke").toolset == "PlaytestToolset"


def test_stub_transport_lists_all_tools():
    from orchestrator.mcp_client import StubTransport

    stub = StubTransport(require_ue=True)
    tools = stub.call("tools/list", {})["tools"]
    names = {t["name"] for t in tools}
    # 12 个 Toolset 的代表工具 + 通用工具都在
    assert "pcg_generate_graph" in names
    assert "lighting_place_directional" in names
    assert "data_csv_to_datatable" in names
    assert "playtest_smoke" in names
    assert "list_tools" in names


def test_stub_transport_rejects_write_when_ue_required():
    import pytest

    from orchestrator.mcp_client import StubTransport, McpClient

    from orchestrator import toolset_registry as reg

    # mutating 工具在 require_ue=True 时写调用抛出（需连 UE）
    stub = StubTransport(require_ue=True)
    meta = reg.get_tool_meta("pcg_generate_graph")
    assert meta.risk == "mutating"
    # 通过 call 直接触发（tools/call 分支要求 UE 在线）
    with pytest.raises(RuntimeError):
        stub.call("tools/call", {"name": "pcg_generate_graph", "arguments": {}})
