"""Skill 注册与调度接口（Harness §6.1）。

Skill = 领域角色能力的封装。一个 Skill 由以下组成（§6.1）：
- skill.yaml：名称 / 输入输出 schema / 模型档位 / 工具白名单 / 风险分级
- prompt.md：面向宿主 Agent 的调用说明与领域策略
- steps.yaml：Skill 内部步骤（对应 DAG 节点）与依赖 / 回退阈值
- tools/：可调用的 Toolset 白名单声明

宿主 Agent 按任务加载对应 Skill 并用自研 DAG 驱动其内部步骤。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

log = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).resolve().parent / "skills"


@dataclass
class SkillStep:
    """Skill 内部的单个步骤（对应一个 DAG 节点）。"""

    id: str
    dependencies: list[str] = field(default_factory=list)
    shared_state_refs: list[str] = field(default_factory=list)
    severity: str = "read_only"      # read_only | mutating | destructive
    tier: str = "default"            # fast | default | strong
    priority: int = 100
    partition: Optional[str] = None   # 空间分区（可选）


@dataclass
class SkillSpec:
    """从 skill.yaml 加载的技能元数据。

    字段对齐 Agent Harness §11.3 / §12.3（Common Spec）：
    - tier：商业能力等级（0–4），用于 distiller 裁剪（完整能力包分级，P0 即声明）
    - distill_visibility：对外蒸馏可见度（full | lite | hidden），资产保护红线
    - default_tier：模型档位（fast | default | strong），用于模型路由
    - risk：风险分级（read_only | mutating | destructive），走审批门
    """

    name: str
    description: str = ""
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    default_tier: str = "default"          # 模型档位（fast/default/strong）
    tier: int = 0                          # 商业能力等级 0–4（§11.3）
    distill_visibility: str = "full"       # full | lite | hidden（§11.3 / SECURITY-LICENSING）
    tool_whitelist: list[str] = field(default_factory=list)
    risk: str = "read_only"
    steps: list[SkillStep] = field(default_factory=list)


class Skill:
    """一个已装载的 Skill 实例。"""

    def __init__(self, spec: SkillSpec, dir_path: Path | None = None) -> None:
        self.spec = spec
        self.dir = dir_path
        self.prompt: str = ""
        if dir_path is not None:
            self._load_prompt(dir_path)

    def _load_prompt(self, dir_path: Path) -> None:
        p = dir_path / "prompt.md"
        if p.exists():
            self.prompt = p.read_text(encoding="utf-8")

    @property
    def name(self) -> str:
        return self.spec.name


class SkillRegistry:
    """按名称加载/解析 Skill（元数据来自 ./skills/<skill>/skill.yaml）。"""

    def __init__(self, skills_dir: Path = _SKILLS_DIR) -> None:
        self.dir = skills_dir
        self._cache: dict[str, Skill] = {}

    def discover(self) -> list[str]:
        if not self.dir.exists():
            return []
        return sorted(
            p.name for p in self.dir.iterdir()
            if p.is_dir() and (p / "skill.yaml").exists()
        )

    def load(self, name: str) -> Skill:
        if name in self._cache:
            return self._cache[name]
        sdir = self.dir / name
        spec_file = sdir / "skill.yaml"
        if not spec_file.exists():
            raise KeyError(f"Skill 不存在: {name}")
        with open(spec_file, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        spec = SkillSpec(
            name=raw.get("name", name),
            description=raw.get("description", ""),
            input_schema=raw.get("input_schema", {}),
            output_schema=raw.get("output_schema", {}),
            default_tier=raw.get("default_tier", "default"),
            tier=_parse_tier(raw.get("tier", 0)),
            distill_visibility=_check_distill(raw.get("distill_visibility", "full")),
            tool_whitelist=raw.get("tool_whitelist", []),
            risk=raw.get("risk", "read_only"),
        )
        # steps.yaml
        steps_file = sdir / "steps.yaml"
        if steps_file.exists():
            spec.steps = self._load_steps(steps_file)
        skill = Skill(spec, sdir)
        self._cache[name] = skill
        return skill

    @staticmethod
    def _load_steps(path: Path) -> list[SkillStep]:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or []
        steps = []
        for item in raw:
            steps.append(
                SkillStep(
                    id=item.get("id"),
                    dependencies=item.get("dependencies", []),
                    shared_state_refs=item.get("shared_state_refs", []),
                    severity=item.get("severity", "read_only"),
                    tier=item.get("tier", "default"),
                    priority=int(item.get("priority", 100)),
                    partition=item.get("partition"),
                )
            )
        return steps


def _parse_tier(val) -> int:
    """把 tier 解析为 0–4 的 int；兼容字符串/缺省。"""
    try:
        t = int(val)
    except (TypeError, ValueError):
        log.warning("tier 非法值 %r，回退为 0", val)
        return 0
    if t < 0 or t > 4:
        log.warning("tier=%d 超出 0–4，钳制为 %d", t, max(0, min(4, t)))
    return max(0, min(4, t))


_VALID_DISTILL = {"full", "lite", "hidden"}


def _check_distill(visibility: str) -> str:
    v = visibility if visibility in _VALID_DISTILL else "full"
    if v != visibility:
        log.warning("distill_visibility=%r 非法，回退为 full", visibility)
    return v


_default_registry: SkillRegistry | None = None


def get_registry() -> SkillRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = SkillRegistry()
    return _default_registry
