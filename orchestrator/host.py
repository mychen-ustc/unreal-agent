"""薄宿主：接收指令，解析并调度对应 Skill（Harness §6.1）。

职责：输入自然语言指令 → 选出 Skill（P0 用简单映射；P1 由宿主 Agent/RAG 选型）
→ 用自研 DAG 驱动 Skill 内部步骤。
"""
from __future__ import annotations

import logging

from orchestrator.models import ModelRouter
from orchestrator.mcp_client import McpClient
from orchestrator.skill import SkillRegistry
from orchestrator.trace import TraceWriter

log = logging.getLogger(__name__)

# P0 简单规则：指令中含关键词 -> 选 Skill（P1 换 LLM 路由）
_KEYWORD_MAP = {
    "pcg": "scenes_pcg",
    "场景": "scenes_pcg",
    "地形": "scenes_pcg",
    "level": "scenes_pcg",
}


class Host:
    def __init__(
        self,
        mcp: McpClient,
        router: ModelRouter | None = None,
        trace: TraceWriter | None = None,
        registry: SkillRegistry | None = None,
    ) -> None:
        self.mcp = mcp
        self.router = router or ModelRouter()
        self.trace = trace or TraceWriter()
        self.registry = registry or SkillRegistry()

    def select_skill(self, instruction: str) -> str:
        low = instruction.lower()
        for kw, skill in _KEYWORD_MAP.items():
            if kw in low:
                return skill
        return "general" if "general" in self.registry.discover() else self.registry.discover()[0]

    def run(self, instruction: str, skill_name: str | None = None) -> dict:
        """执行一次宿主指令：装载 Skill → 按 DAG 调度其步骤。"""
        name = skill_name or self.select_skill(instruction)
        self.trace.agent_event("host", "select_skill", {"skill": name, "instruction": instruction})

        skill = self.registry.load(name)
        spec = skill.spec
        log.info("执行 Skill=%s (tier=%s, risk=%s, steps=%d)",
                 spec.name, spec.default_tier, spec.risk, len(spec.steps))
        # 通过 MCP 唯一写入者逐步骤调用（P0：顺序执行各步骤；并发交给 Scheduler）
        executed = []
        for step in spec.steps:
            self.trace.tool_call(
                tool=f"skill:{spec.name}:{step.id}",
                args={"instruction": instruction},
                outcome={"tier": step.tier},
                producer=f"skill/{spec.name}",
            )
            executed.append(step.id)
        return {"skill": name, "steps_executed": executed}
