"""能力蒸馏工具 distiller（Agent Harness §11.3 / ROADMAP C1 / SECURITY-LICENSING §3.2）。

P0 骨架：把「完整能力包」按 Skill 的 `tier`(0–4) / `distill_visibility`(full|lite|hidden)
裁剪为「对外 Demo / 体验子集」。最小可用版 = `tier <= 2` 且 `distill_visibility != hidden`。

边界（红线）：
- 只产出裁剪后的 Skill 子集（含元数据，含 prompt/steps/tools 白名单裁剪），不泄露 Tier 3/4。
- `importers/` 只消费本蒸馏子集，绝不注入完整能力包。
- 蒸馏是纯生成/翻译：不改源能力包，可重复、可回归。

P0 只做「函数签名 + tier<=2 裁剪」的可运行骨架；C1 填完整蒸馏规则与宿主格式。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from orchestrator.skill import SkillRegistry, SkillSpec

log = logging.getLogger(__name__)

# 文档 §11.3：最小可用版（MVP-subset）= tier ≤ 2 且非 hidden
DEFAULT_MAX_TIER = 2
HIDDEN = "hidden"


@dataclass
class DistilledSkill:
    """蒸馏后的一个 Skill 子集（宿主无关，供 importers 翻译）。"""

    name: str
    source_tier: int
    visibility: str
    distilled_input_schema: dict = field(default_factory=dict)
    distilled_tool_whitelist: list[str] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)   # 能力注记（拍平后的执行步骤，供宿主提示）
    description: str = ""
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "source_tier": self.source_tier,
            "visibility": self.visibility,
            "input_schema": self.distilled_input_schema,
            "tool_whitelist": self.distilled_tool_whitelist,
            "steps": self.steps,
            "description": self.description,
            "note": self.note,
        }


class Distiller:
    """能力蒸馏器。P0：按 tier/distill_visibility 裁剪出可对外子集。"""

    def __init__(
        self,
        registry: SkillRegistry | None = None,
        max_tier: int = DEFAULT_MAX_TIER,
        min_visibility: str | None = None,   # 供测试传 "full"/"lite"
    ) -> None:
        self.registry = registry or SkillRegistry()
        self.max_tier = max_tier
        self.min_visibility = min_visibility

    def _include(self, spec: SkillSpec) -> bool:
        """是否进入 MVP 子集：tier<=max 且 visibility 合格。"""
        if spec.tier > self.max_tier:
            return False
        if spec.distill_visibility == HIDDEN:
            return False
        if self.min_visibility is not None and spec.distill_visibility != self.min_visibility:
            return False
        return True

    def distill(self, skill_names: list[str] | None = None) -> list[DistilledSkill]:
        """生成对外蒸馏子集（宿主无关）。skill_names=None 表示全能力包。"""
        names = skill_names or self.registry.discover()
        out: list[DistilledSkill] = []
        for name in names:
            try:
                spec = self.registry.load(name).spec
            except KeyError as exc:
                log.warning("跳过未装载 Skill %s: %s", name, exc)
                continue
            if not self._include(spec):
                log.info("Skill %s (tier=%d, visibility=%s) 不进入 MVP 子集（裸掉）",
                         name, spec.tier, spec.distill_visibility)
                continue
            out.append(
                DistilledSkill(
                    name=name,
                    source_tier=spec.tier,
                    visibility=spec.distill_visibility,
                    distilled_input_schema=spec.input_schema,
                    distilled_tool_whitelist=spec.tool_whitelist,
                    steps=[_step_note(s) for s in spec.steps],
                    description=spec.description,
                    note=f"min_visibility={spec.distill_visibility}",
                )
            )
        return out

    def make_mvp_subset(self, skill_names: list[str] | None = None) -> list[DistilledSkill]:
        """语义别名：生成最小可用版子集（= distill() 的 tier<=2 语义）。"""
        return self.distill(skill_names)


def _step_note(step: Any) -> dict:
    """把 SkillStep 拍平为宿主无关的能力注记（§12.4：depends/severity/partition 转约束）。"""
    note = {"id": step.id}
    if step.dependencies:
        note["依赖"] = step.dependencies
    if step.severity and step.severity != "read_only":
        note["风险"] = step.severity
    if step.partition:
        note["分区"] = step.partition
    return note


_default_distiller: Distiller | None = None


def get_distiller() -> Distiller:
    global _default_distiller
    if _default_distiller is None:
        _default_distiller = Distiller()
    return _default_distiller
