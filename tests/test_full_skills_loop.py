"""全量 Skill 端到端闭环回归（P0 验收：从 Skill 装载 → Scheduler 驱动 → MCP 工具执行）。

遍历 toolset_registry 登记的可用工具可支撑的全部已建 Skill，用 stub+approve_all 跑通：
每 Skill 应能 load 且所有步骤经 Scheduler 按依赖执行、工具可调。
"""
from __future__ import annotations


def test_all_skills_load_and_strict():
    """每个 Skill 可装载，且其步骤主工具都在 toolset_registry 且在白名单内。"""
    from orchestrator import toolset_registry as reg
    from orchestrator.skill import get_registry

    avail = {t.name for t in reg.ALL_TOOLS}
    for name in get_registry().discover():
        spec = get_registry().load(name).spec
        assert spec.tool_whitelist, name
        for st in spec.steps:
            if st.tool:
                assert st.tool in avail, f"{name} 步骤 {st.id} 工具 {st.tool} 未登记"
                assert st.tool in spec.tool_whitelist, f"{name} 工具 {st.tool} 不在白名单"
        # 商业字段齐全
        assert 0 <= spec.tier <= 4, name
        assert spec.distill_visibility in ("full", "lite", "hidden"), name


def test_all_skills_full_loop_executes():
    """每个已建 Skill 通过 Host(stub+approve_all) 跑通完整闭环（含真实工具调用）。"""
    from orchestrator.host import Host
    from orchestrator.mcp_client import StubTransport, McpClient, approve_all
    from orchestrator.skill import get_registry

    class _DT:
        def tool_call(self, *a, **k):
            pass

        def agent_event(self, *a, **k):
            pass

    mcp = McpClient(transport=StubTransport(require_ue=False), approver=approve_all)
    host = Host(mcp=mcp, trace=_DT(), use_llm_select=False)
    names = get_registry().discover()
    assert names, "Skills 为空"
    for name in names:
        result = host.run("执行", skill_name=name)
        n_steps = len(get_registry().load(name).spec.steps)
        # 每 Skill 所有步骤都被执行且成功
        assert result["skill"] == name
        assert result["steps_executed"] == n_steps, f"{name}: 预期 {n_steps} 步，实际 {result['steps_executed']}"
