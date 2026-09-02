"""调度器 + MCP 审批门 + Host 集成测试（对齐 TechDesign §6.2 / §3.3 单写入者）。

验证：
- Scheduler 按拓扑 + 依赖执行 Skill 步骤（ready_nodes 判定）。
- McpClient 审批门：read_only 自动放行 / mutating 需批准。
- Host.run 把 Skill 的 steps 构造成 DAG，由 Scheduler 按依赖顺序驱动。
"""
from __future__ import annotations

import asyncio

from orchestrator.dag import DagEngine, DagNode
from orchestrator.scheduler import Scheduler


def _node(task_id, deps=()):
    return DagNode(task_id=task_id, producer="general", tier="default", deps=list(deps))


def test_scheduler_executes_in_topo_order():
    d = DagEngine()
    d.add_node(_node("a"))
    d.add_node(_node("b", deps=["a"]))
    d.add_edge("a", "b")
    order: list[str] = []

    async def runner(task_id):
        order.append(task_id)

    sched = Scheduler(dag=d, runner=runner, max_concurrent=2)
    asyncio.run(sched.run())
    assert order.index("a") < order.index("b")


def test_scheduler_marks_done():
    d = DagEngine()
    d.add_node(_node("a"))

    async def runner(task_id):
        pass

    sched = Scheduler(dag=d, runner=runner)
    asyncio.run(sched.run())
    assert d.nodes["a"].state == "done"


def test_mcp_risk_classification():
    from orchestrator.mcp_client import RiskLevel

    assert RiskLevel.classify("list_tools") == RiskLevel.READ_ONLY
    assert RiskLevel.classify("generate_tree") == RiskLevel.MUTATING
    assert RiskLevel.classify("delete_asset") == RiskLevel.DESTRUCTIVE


def test_mcp_approval_gate_rejects_by_default():
    """非只读工具默认需交互批准：提供一个总拒绝的 approver 验证门生效。"""
    from orchestrator.mcp_client import McpClient, StubTransport, RiskLevel

    def deny_all(tool, args, risk, meta):
        return False

    mcp = McpClient(transport=StubTransport(require_ue=False), approver=deny_all)
    res = mcp.call_tool("generate_tree", {}, risk=RiskLevel.MUTATING)
    assert res.ok is False
    assert res.error_code == "APPROVAL_DENIED"


def test_host_run_drives_skill_steps_via_scheduler():
    """Host.run 用 Scheduler 按依赖驱动 scenes_pcg 步骤。"""
    from orchestrator.host import Host
    from orchestrator.mcp_client import StubTransport, McpClient

    mcp = McpClient(transport=StubTransport(require_ue=False))

    class _DummyTrace:
        def tool_call(self, *a, **k):
            pass

        def agent_event(self, *a, **k):
            pass

    host = Host(mcp=mcp, trace=_DummyTrace())
    result = host.run("用 PCG 生成森林")
    assert result["skill"] == "scenes_pcg"
    assert set(result["steps"]) == {"plan_spec", "generate_graph", "validate"}
    assert result["steps_executed"] == 3
