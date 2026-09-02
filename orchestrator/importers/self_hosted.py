"""self_hosted 宿主 Adapter：把蒸馏子集导出为「自有宿主可加载的 skills 包」。

P0 示例实现：直接按 Common Spec 重新导出（skill.yaml + prompt + steps），
作为导入管线的「最小可行参考」，供后续 claude_code / codex 等 adapter 对齐。
"""
from __future__ import annotations

import yaml

from orchestrator.distiller import DistilledSkill
from orchestrator.importers.base import (
    GeneratedConfigFile,
    GeneratedSkillFile,
    HarnessImporter,
    ImportBundle,
)


class SelfHostedImporter(HarnessImporter):
    target = "self_hosted"

    def emit_skill(self, skill: DistilledSkill) -> GeneratedSkillFile:
        # 蒸馏子集 → skills/<name>/skill.yaml（宿主无关 Common Spec）
        payload = {
            "name": skill.name,
            "source_tier": skill.source_tier,
            "distill_visibility": skill.visibility,
            "input_schema": skill.distilled_input_schema,
            "tool_whitelist": skill.distilled_tool_whitelist,
            "note": skill.note,
        }
        return GeneratedSkillFile(
            rel_path=f"skills/{skill.name}/skill.yaml",
            content=yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        )

    def emit_mcp_config(self, mcp_url: str) -> GeneratedConfigFile:
        return GeneratedConfigFile(
            rel_path="mcp.config.json",
            content=f'{{"mcpServer": {{"url": "{mcp_url}", "transport": "http"}}}}\n',
        )

    def emit_project_manifest(self, skills: list[DistilledSkill]) -> GeneratedConfigFile:
        names = [s.name for s in skills]
        return GeneratedConfigFile(
            rel_path="MANIFEST.yaml",
            content=yaml.safe_dump({"target": "self_hosted", "skills": names}, allow_unicode=True, sort_keys=False),
        )

    def generate(self, skills: list[DistilledSkill], mcp_url: str) -> ImportBundle:
        return super().generate(skills, mcp_url)
