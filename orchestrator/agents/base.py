"""领域 Agent 基类与注册表（TechDesign §5.2 / §5.3）。

每个 Agent：名字 + 档位 + 产出 SharedState 路径 + 依赖路径。
实际实现绕开：Agent 不能直连 MCP，由 Orchestrator 唯一写入者代理调用 Tool。
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Optional

from orchestrator.models import ModelRouter
from orchestrator.shared_state import SharedState, hash_envelope


@dataclass
class AgentTask:
    """单个 Agent 的一次执行任务。"""

    task_id: str
    producer: str
    instruction: str
    tier: str = "default"
    context: dict = field(default_factory=dict)


class Agent(abc.ABC):
    """领域 Agent 抽象基类。"""

    name: str = "agent"
    tier: str = "default"
    reads: list[str] = []       # 读路径（相对 shared_state/）
    writes: list[str] = []      # 写路径

    def __init__(self, state: SharedState | None = None, router: ModelRouter | None = None) -> None:
        self.state = state or SharedState()
        self.router = router or ModelRouter()

    @abc.abstractmethod
    async def run(self, task: AgentTask) -> dict:
        """执行任务，返回 { result, shared_state_delta, next_agents, artifacts }。

        对齐附录 B AgentOutput 契约。
        """

    # ---- 便捷 ----
    def read_envelope(self, rel_path: str) -> dict | None:
        return self.state.read(rel_path)

    def write_envelope(self, rel_path: str, payload: dict, parent_hash: str = "") -> str:
        """写入信封并返回其 parent_hash；供下游作为输入引用。"""
        env = self.state.write(rel_path, producer=self.name, payload=payload, parent_hash=parent_hash)
        return hash_envelope(env)

    def _default_output(self, **kw: Any) -> dict:
        out = {
            "result": {},
            "shared_state_delta": {},
            "next_agents": [],
            "artifacts": [],
        }
        out.update(kw)
        return out


class Registry:
    """Agent 注册表：按名字取实例 / 列全部。"""

    def __init__(self, state: SharedState | None = None, router: ModelRouter | None = None) -> None:
        self.state = state or SharedState()
        self.router = router or ModelRouter()
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> Agent:
        return self._agents[name]

    def names(self) -> list[str]:
        return sorted(self._agents)

    def __contains__(self, name: str) -> bool:
        return name in self._agents
