"""Claude Code 宿主 Adapter（Agent Harness §12.4）。

映射规则（§12.4 / §7.0 P0/P1 优先验证 Claude Code）：
- Skill → `.claude/skills/<skill>/SKILL.md`（frontmatter: name/description; 正文=描述 + 工具说明 + 执行步骤注记）
- MCP   → `.mcp.json`（指向 UE 5.8 MCP Server 127.0.0.1:8000/mcp）
- steps → SKILL.md 正文里的「执行步骤」自然语言片段；depends/severity/partition 转成「注意/约束」注记

只消费 Distiller 的蒸馏子集（完整能力包不走此通道）。
"""
from __future__ import annotations

import json
from typing import Iterable

from orchestrator.distiller import DistilledSkill
from orchestrator.importers.base import (
    GeneratedConfigFile,
    GeneratedSkillFile,
    HarnessImporter,
    ImportBundle,
)


class ClaudeCodeImporter(HarnessImporter):
    target = "claude_code"

    def emit_skill(self, skill: DistilledSkill) -> GeneratedSkillFile:
        # frontmatter：Anthropic Skills 规范（name + description）
        frontmatter = (
            "---\n"
            f"name: {skill.name}\n"
            f"description: {_one_line(skill.description)}\n"
            "---\n\n"
        )
        body = [_corpus(skill)]
        # 执行步骤：steps.yaml 拍平为自然语言步骤 + 约束注记
        if skill.steps:
            body.append("## 执行步骤\n")
            for i, st in enumerate(skill.steps, 1):
                extra = ", ".join(f"{k}: {v}" for k, v in st.items() if k != "id")
                line = f"{i}. `{st['id']}`"
                if extra:
                    line += f"（{extra}）"
                body.append(f"- {line}\n")
        # 工具说明
        if skill.distilled_tool_whitelist:
            body.append("\n## 可用工具\n")
            for t in skill.distilled_tool_whitelist:
                body.append(f"- `{t}`\n")
        content = frontmatter + "".join(body)
        return GeneratedSkillFile(
            rel_path=f".claude/skills/{skill.name}/SKILL.md",
            content=content,
        )

    def emit_mcp_config(self, mcp_url: str) -> GeneratedConfigFile:
        mcp = {
            "mcpServers": {
                "unreal-agent": {
                    "url": mcp_url,
                    "transport": "http",
                }
            }
        }
        return GeneratedConfigFile(
            rel_path=".mcp.json",
            content=json.dumps(mcp, indent=2, ensure_ascii=False) + "\n",
        )

    def emit_project_manifest(self, skills: Iterable[DistilledSkill]) -> GeneratedConfigFile:
        entries = [
            {"name": s.name, "path": f".claude/skills/{s.name}/SKILL.md", "tier": s.source_tier}
            for s in skills
        ]
        return GeneratedConfigFile(
            rel_path="MANIFEST.json",
            content=json.dumps({"target": "claude_code", "skills": entries}, indent=2, ensure_ascii=False) + "\n",
        )

    def generate(self, skills: list[DistilledSkill], mcp_url: str) -> ImportBundle:
        return super().generate(skills, mcp_url)


def _one_line(text: str) -> str:
    return (text or "").replace("\n", " ").strip()


def _corpus(skill: DistilledSkill) -> str:
    lines = []
    if skill.description:
        lines.append(f"## 定位\n{skill.description}\n")
    if skill.distilled_input_schema:
        required = skill.distilled_input_schema.get("required", [])
        props = skill.distilled_input_schema.get("properties", {})
        if required:
            lines.append(f"## 输入参数（必填：{', '.join(required)}）\n")
            for name in required:
                prop = props.get(name, {})
                lines.append(f"- `{name}`：{prop.get('description', '')}\n")
    return "".join(lines)
