"""Skills 子包：领域能力封装（技能 = 角色能力的可执行单元）。"""
from orchestrator.skill import Skill, SkillRegistry, SkillSpec, SkillStep, get_registry

__all__ = ["Skill", "SkillRegistry", "SkillSpec", "SkillStep", "get_registry", "discover_skills"]


def discover_skills() -> list[str]:
    return get_registry().discover()
