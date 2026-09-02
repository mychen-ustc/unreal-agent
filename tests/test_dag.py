"""DAG 引擎单元测试：拓扑 / stale 传播 / 回退循环（对齐 TechDesign §6.2）。

对齐 PRD §4.1.3 与 Agent Harness §6.2。
"""
from __future__ import annotations

import pytest

from orchestrator.dag import DagEngine, DagNode


def _node(task_id, deps=(), **kw):
    return DagNode(task_id=task_id, producer="general", tier="default", deps=list(deps), **kw)


def test_topological_order():
    d = DagEngine()
    d.add_node(_node("a"))
    d.add_node(_node("b", deps=["a"]))
    d.add_node(_node("c", deps=["b"]))
    d.add_edge("a", "b")
    d.add_edge("b", "c")
    assert d.topological_order() == ["a", "b", "c"]


def test_cycle_detected():
    d = DagEngine()
    d.add_node(_node("a"))
    d.add_node(_node("b", deps=["a"]))
    d.add_edge("a", "b")
    d.add_edge("b", "a")
    with pytest.raises(RuntimeError):
        d.topological_order()


def test_stale_propagation_depth_limited():
    d = DagEngine(max_stale_depth=2)
    d.add_node(_node("a"))
    d.add_node(_node("b", deps=["a"]))
    d.add_node(_node("c", deps=["b"]))
    d.add_node(_node("d", deps=["c"]))
    d.add_edge("a", "b")
    d.add_edge("b", "c")
    d.add_edge("c", "d")
    affected = d.mark_stale("a")
    # 深度 2：只影响 b、c；d 不受影响
    assert set(affected) == {"b", "c"}
    assert d.nodes["b"].stale and d.nodes["c"].stale
    assert not d.nodes["d"].stale


def test_rollback_loop_escalates_after_max():
    d = DagEngine(max_loop=2)
    d.add_node(_node("gen"))
    # 连续失败 -> 超过 max_loop 后升级人工
    first = d.rollback("gen", "gen", "score<70")
    second = d.rollback("gen", "gen", "score<70")
    third = d.rollback("gen", "gen", "score<70")
    assert first.startswith("gen#redo")
    assert second.startswith("gen#redo")
    assert third == "ESCALATE:gen"


def test_should_rework_on_low_score():
    d = DagEngine()
    ok, _ = d.should_rework(85.0)
    assert ok is False
    ok, reason = d.should_rework(65.0)
    assert ok is True
    assert "65" in reason


def test_should_rework_on_verdict_fix():
    d = DagEngine()
    ok, _ = d.should_rework(None, verdict="FIX")
    assert ok is True
    ok, _ = d.should_rework(None, verdict="GO")
    assert ok is False  # GO 是裁决，不是回退
