"""demo_concept 管线确定性测试（不依赖真实 LLM）：

用假 router 返回固定文本，验证「策略→生产(Director)→评估(E6)」多 Skill 协同：
- 六个产物阶段均产生 SharedState 信封（market/competitor/game_design/creative_direction/proposal/eval.benchmark）
- parent_hash 链按顺序串起（每信封 parent 指向上一个信封 hash）
- run_concept 输出可渲染（含六节与 SharedState 落盘清单）。
"""
from __future__ import annotations

import asyncio

import pytest


class _FakeRouter:
    def __init__(self, tag):
        self.tag = tag

    async def complete(self, prompt, tier="default", system=None):
        # 抛出一个能反映“是哪个阶段被调用”的可读片段
        return f"[{self.tag or 'stage'}]\n实际内容为假生成但结构完整。" + prompt[:20]


def _install(monkeypatch, tmp_path):
    import orchestrator.demo_concept as dc
    from orchestrator.shared_state import SharedState

    # 用假 router 避免真实网络/模型
    calls = {}
    class Counting:
        def __init__(self): self.n = 0
        async def complete(self, prompt, tier="default", system=None):
            self.n += 1
            return f"[阶段-{self.n}]\n假产物内容（用于确定性验证结构）。\n第一行提示: {prompt[:24]}…"
    counting = Counting()
    monkeypatch.setattr(dc, "get_router", lambda: counting)
    # SharedState 写到临时目录，避免污染仓库 shared_state/
    def fake_factory():
        return SharedState(root=tmp_path)
    monkeypatch.setattr(dc, "SharedState", fake_factory)
    # 禁默认（tier 已固定 default）无关
    return dc, counting


@pytest.fixture(params=["demo_concept"])
def _module(request):
    return request.param


def test_concept_pipeline_envelope_chain(monkeypatch, tmp_path):
    dc, counting = _install(monkeypatch, tmp_path)
    root = dc.run_concept("探索驱动+收集符文开门+暗黑奇幻+轻战斗")
    # 六阶段都产生信封
    for k in ("market", "competitor", "game_design", "creative_direction", "proposal", "eval/benchmark"):
        assert f"{k}/json" in root.artifacts, f"缺少 {k} 信封"

    # parent_hash 链按顺序串联（后一个 parent == 前一个 hash）
    order = ["market", "competitor", "game_design", "creative_direction", "proposal", "eval/benchmark"]
    prev_hash = ""
    for k in order:
        env = root.artifacts[f"{k}/json"]
        assert env["parent_hash"] == prev_hash, f"{k} 的 parent 与上一阶段 hash 不一致"
        prev_hash = dc.hash_envelope(env)

    # 可渲染（含每一节与 SharedState 落盘清单）
    md = dc.render(root)
    for k_sect in ["市场(S1)", "竞品(S2)", "玩法设计(S3)", "创意方向(S6)", "导演立项目标", "横向基准评估(E6)", "SharedState 落盘信封"]:
        assert k_sect in md


def test_concept_llm_failure_not_fatal(monkeypatch, tmp_path):
    """某个阶段 LLM 失败不应中断整个管线（占位回退）。"""
    import orchestrator.demo_concept as dc
    from orchestrator.shared_state import SharedState

    class Flaky:
        async def complete(self, prompt, tier="default", system=None):
            raise RuntimeError("simulated failure")
    monkeypatch.setattr(dc, "get_router", lambda: Flaky())
    def ff():
        return SharedState(root=tmp_path)
    monkeypatch.setattr(dc, "SharedState", ff)

    root = dc.run_concept("方向")
    # 占位文本不会中断；六阶段信封与父链仍在（占位也写 envelope）
    assert "eval/benchmark/json" in root.artifacts
    md = dc.render(root)
    assert "（该阶段模型调用失败" in md
