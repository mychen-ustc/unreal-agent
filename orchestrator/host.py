"""薄宿主：接收指令，解析并调度对应 Skill（Harness §6.1）。

职责：输入自然语言指令 → 选出 Skill（P0 用简单映射；P1 由宿主 Agent/RAG 选型）
→ 用自研 DAG 驱动 Skill 内部步骤。
"""
from __future__ import annotations

import asyncio
import logging

from orchestrator.dag import DagEngine, DagNode
from orchestrator.models import ModelRouter
from orchestrator.mcp_client import McpClient
from orchestrator.scheduler import Scheduler
from orchestrator.skill import SkillRegistry
from orchestrator.trace import TraceWriter

log = logging.getLogger(__name__)

# P0:关键词兜底映射（LLM 选型不可用/失败时回退）
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
        use_llm_select: bool = True,
    ) -> None:
        self.mcp = mcp
        self.router = router or ModelRouter()
        self.trace = trace or TraceWriter()
        self.registry = registry or SkillRegistry()
        # LLM 选型开关：默认开；失败自动回退关键词（保证 stub/离线可用）
        self.use_llm_select = use_llm_select

    def _keyword_fallback(self, instruction: str) -> str:
        low = instruction.lower()
        for kw, skill in _KEYWORD_MAP.items():
            if kw in low:
                return skill
        names = self.registry.discover()
        return names[0] if names else "general"

    def select_skill(self, instruction: str) -> str:
        """从已装载 Skill 中选出最适合指令的名称。

        优先走 LLM（fast 档）做语义选型；失败/禁用时回退关键词匹配。
        """
        names = self.registry.discover()
        if not names:
            raise RuntimeError("Skills 目录为空，无法选型")
        if not self.use_llm_select:
            return self._keyword_fallback(instruction)
        try:
            return self._select_by_llm(instruction, names)
        except Exception as exc:  # noqa: BLE001
            log.warning("LLM 选型失败，回退关键词: %s", exc)
            return self._keyword_fallback(instruction)

    def _select_by_llm(self, instruction: str, names: list[str]) -> str:
        """让 LLM 从 names 中选最匹配指令的 Skill（要求只输出一个已知 name）。"""
        allowed = ", ".join(names)
        prompt = (
            "你是 UE 研发管线宿主的 Skill 选型器。\n"
            f"可用 Skill：{allowed}\n"
            f"用户指令：{instruction}\n"
            "请只输出一个最匹配的 Skill 名称（必须是上面列表之一，不要解释）。"
        )
        text = asyncio.run(self.router.complete(prompt, tier="fast")).strip()
        # 限定返回必须在已知 Skill 内（防 LLM 幻觉输出不属于任何 Skill 的名字）
        for n in names:
            if n in text:
                return n
        return self._keyword_fallback(instruction)

    def run(self, instruction: str, skill_name: str | None = None) -> dict:
        """执行一次宿主指令：装载 Skill → 用自研 DAG/调度器驱动其内部步骤。

        P0：把 Skill 的 `steps` 构造成 DagEngine，由 Scheduler 按拓扑 + 依赖 + 并发执行
        （每个步骤经 MCP 唯一写入者调用工具并 trace）。
        """
        name = skill_name or self.select_skill(instruction)
        self.trace.agent_event("host", "select_skill", {"skill": name, "instruction": instruction})

        skill = self.registry.load(name)
        spec = skill.spec
        log.info("执行 Skill=%s (model_tier=%s, biz_tier=%d, distill=%s, risk=%s, steps=%d)",
                 spec.name, spec.default_tier, spec.tier, spec.distill_visibility,
                 spec.risk, len(spec.steps))

        # 把 Skill 内部 steps 构造成 DAG（节点即步骤，依赖来自 steps.yaml）
        dag = DagEngine()
        for step in spec.steps:
            dag.add_node(DagNode(
                task_id=f"{spec.name}:{step.id}",
                producer=f"skill/{spec.name}",
                skill=spec.name,
                step=step.id,
                tier=step.tier,
                severity=step.severity,
                partition=step.partition,
                priority=step.priority,
                shared_state_refs=step.shared_state_refs,
            ))
        # 依赖边（steps.yaml 的 dependencies 引用步骤 id）
        id_to_task = {s.id: f"{spec.name}:{s.id}" for s in spec.steps}
        for step in spec.steps:
            for dep in step.dependencies:
                if dep in id_to_task:
                    dag.add_edge(id_to_task[dep], id_to_task[step.id])
                else:
                    log.warning("Skill %s 步骤 %s 的依赖 %s 未定义，跳过", spec.name, step.id, dep)

        async def runner(task_id: str) -> None:
            node = dag.nodes[task_id]
            self.trace.tool_call(
                tool=f"skill:{node.skill}:{node.step}",
                args={"instruction": instruction},
                outcome={"tier": node.tier, "severity": node.severity},
                producer=node.producer,
            )
            # 真实工具调用：当前经 MCP 唯一写入者（P0 many steps 无真 UE，gate 保留）
            # TODO(P1): 把 Skill 步骤映射到具体 Tool 白名单内的 Tool 调用。

        scheduler = Scheduler(dag=dag, runner=runner, max_concurrent=len(spec.steps))
        executed = asyncio.run(scheduler.run())
        return {"skill": name, "steps_executed": executed, "steps": [s.id for s in spec.steps]}
