"""通用 Agent：直接调用 LLM（按档位路由）产出一段结构化结果。

用于 P0 最小闭环验证：证明 LLM 路由 + SharedState 信封 + Tool 门 全链路可跑。
实际领域 Agent（S1~S6/生产/评估）在后续按需成组加入。
"""
from __future__ import annotations

from orchestrator.agents.base import Agent, AgentTask


class GeneralAgent(Agent):
    name = "general"
    tier = "default"

    async def run(self, task: AgentTask) -> dict:
        instruction = task.instruction
        # 简单夹具：让 LLM 产出一个 JSON 对象
        prompt = (
            "你是 UE 研发管线里的一个领域 Agent。\n"
            f"任务：{instruction}\n"
            "请只输出一个 JSON 对象，至少包含字段 { \"summary\": string, \"flags\": [string] }。\n"
        )
        text = await self.router.complete(prompt, tier=task.tier)
        return {
            "result": {"summary": text, "task_id": task.task_id},
            "shared_state_delta": {"summary": text},
            "next_agents": [],
            "artifacts": [],
        }
