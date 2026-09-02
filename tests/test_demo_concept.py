"""demo_concept run-id 版本化存储测试（不依赖真实 LLM）：

用假 router 返回固定文本，验证：
- run_concept 把流程写入 runs/<runId>/strategy|eval 信封，并写 PROPOSAL.md/RUNMANIFEST.json
- .ACTIVE_RUN 被写入并可由 resolve_active 读回
- 阶段信封 parent_hash 按 S1→…→E6 顺序串联
- render / latest_verdict 可用
- 单阶段 LLM 失败不致中断（占位回退）
"""
from __future__ import annotations

import json

import pytest


class _CountingRouter:
    def __init__(self):
        self.n = 0

    async def complete(self, prompt, tier="default", system=None):
        self.n += 1
        return f"[阶段-{self.n}] 假内容（确定性）。片段:{prompt[:18]}…"


class _Flaky:
    async def complete(self, prompt, tier="default", system=None):
        raise RuntimeError("simulated LLM failure")


@pytest.fixture()
def shared(tmp_path):
    from orchestrator.shared_state import SharedState
    return SharedState(root=tmp_path)


def test_concept_run_persists_and_active(monkeypatch, shared):
    import orchestrator.demo_concept as dc

    router = _CountingRouter()
    monkeypatch.setattr(dc, "get_router", lambda: router)

    root = dc.run_concept("探索+符文开门+暗黑奇幻+轻战斗", shared=shared)
    base = shared.base

    # 六个阶段都有信封
    expect = ["market", "competitor", "game_design", "creative_direction", "proposal", "eval_benchmark"]
    for name in expect:
        assert name in root.envelopes, name

    # parent 链顺序（下一阶段 parent == 上一阶段 hash）
    prev = ""
    for name in expect:
        env = root.envelopes[name]
        assert env["parent_hash"] == prev, name
        prev = dc.hash_envelope(env)

    # 落盘在 runs/<rid> 下：PROPOSAL.md / RUNMANIFEST.json / 各信封
    run_dir = base / "runs" / root.run_id
    assert run_dir.exists()
    assert (run_dir / "PROPOSAL.md").exists()
    assert (run_dir / "RUNMANIFEST.json").exists()
    assert (run_dir / "strategy" / "market.json").exists()
    assert (run_dir / "eval" / "benchmark.json").exists()

    # ACTIVE 指针
    assert (base / ".ACTIVE_RUN").read_text(encoding="utf-8") == root.run_id
    assert dc.resolve_active(shared) == root.run_id

    # manifest 一致
    m = json.loads((run_dir / "RUNMANIFEST.json").read_text(encoding="utf-8"))
    assert m["run_id"] == root.run_id
    assert len(m["stages"]) == 6

    # render
    md = dc.render(root)
    for sec in ["市场(S1)", "竞品(S2)", "玩法设计(S3)", "创意方向(S6)", "导演立项目标(Director)",
                "横向基准评估(E6)", "SharedState 落盘信封", root.run_id]:
        assert sec in md


def test_run_ids_unique(monkeypatch, shared):
    from orchestrator.demo_concept import _run_id, run_concept
    a = _run_id()
    b = _run_id()
    assert a != b
    # 两次 run 落在不同 run 目录（版本化）
    router = _CountingRouter()
    monkeypatch.setattr("orchestrator.demo_concept.get_router", lambda: router)
    r1 = run_concept("方向A", shared=shared)
    r2 = run_concept("方向B", shared=shared)
    assert r1.run_id != r2.run_id
    assert (shared.base / "runs" / r1.run_id).exists()
    assert (shared.base / "runs" / r2.run_id).exists()


def test_llm_failure_not_fatal_and_dry(monkeypatch, shared):
    import orchestrator.demo_concept as dc
    monkeypatch.setattr(dc, "get_router", lambda: _Flaky())

    # dry：do_persist=False 不写盘但仍产出占位信封
    root = dc.run_concept("方向", shared=shared, run_id="run-x", do_persist=False)
    assert "proposal" in root.envelopes
    assert "eval_benchmark" in root.envelopes
    # 不写盘
    assert not (shared.base / ".ACTIVE_RUN").exists()
    md = dc.render(root)
    assert "（该阶段模型调用失败" in md
