"""importers 基础：HarnessImporter 抽象接口（Agent Harness §12.2）。

每个宿主一个 Adapter（claude_code / codex / openclaw / hermes / self_hosted），
实现 `emit_skill` / `emit_mcp_config` / `emit_project_manifest`，`generate` 汇总为
可写入目标目录的 bundle。P0 提供接口与一个最小示例（self_hosted）；宿主格式后续按需补。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from orchestrator.distiller import DistilledSkill


@dataclass
class GeneratedSkillFile:
    """一次生成的目标宿主文件（供 importers 写入）。"""

    rel_path: str
    content: str


@dataclass
class GeneratedConfigFile:
    """一个生成的宿主配置文件。"""

    rel_path: str
    content: str


@dataclass
class ImportBundle:
    """一次 import 的可写入结果集。"""

    target: str
    generated_files: list[GeneratedSkillFile] = field(default_factory=list)
    mcp_configs: list[GeneratedConfigFile] = field(default_factory=list)
    manifest: GeneratedConfigFile | None = None

    def all_files(self) -> list[GeneratedConfigFile | GeneratedSkillFile]:
        return [*self.generated_files, *self.mcp_configs] + ([self.manifest] if self.manifest else [])


class HarnessImporter(ABC):
    """宿主无关 Skill 子集 → 目标宿主文件的翻译器。"""

    target: str  # 宿主标识，如 "claude_code" / "codex" / "self_hosted"

    @abstractmethod
    def emit_skill(self, skill: DistilledSkill) -> GeneratedSkillFile:
        """翻译单个蒸馏 Skill 为目标宿主可加载文件。"""

    @abstractmethod
    def emit_mcp_config(self, mcp_url: str) -> GeneratedConfigFile:
        """生成目标宿主的 MCP 接入配置（指向本项目 UE MCP Server）。"""

    @abstractmethod
    def emit_project_manifest(self, skills: list[DistilledSkill]) -> GeneratedConfigFile:
        """生成 skills 索引 / 菜单清单。"""

    def generate(self, skills: list[DistilledSkill], mcp_url: str) -> ImportBundle:
        """默认流程：逐 Skill 翻译 + MCP 配置 + 项目清单。子类可覆盖。"""
        bundle = ImportBundle(target=self.target)
        for s in skills:
            bundle.generated_files.append(self.emit_skill(s))
        bundle.mcp_configs.append(self.emit_mcp_config(mcp_url))
        bundle.manifest = self.emit_project_manifest(skills)
        return bundle
