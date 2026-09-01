"""Agents 子包：汇集领域 Agent 并提供注册表构建。"""
from __future__ import annotations

from orchestrator.agents.base import Agent, AgentTask, Registry
from orchestrator.models import ModelRouter
from orchestrator.shared_state import SharedState

__all__ = ["Agent", "AgentTask", "Registry", "build_registry"]


def build_registry(state: SharedState | None = None, router: ModelRouter | None = None) -> Registry:
    """构建 Agent 注册表（P0：只含 general；后续按里程碑加入 S1~S6 等）。"""
    state = state or SharedState()
    router = router or ModelRouter()
    reg = Registry(state=state, router=router)

    from orchestrator.agents.general_agent import GeneralAgent

    reg.register(GeneralAgent(state=state, router=router))

    # 预留：strategy / gameplay / eval 组成组注册点（P1+ 按 §5.2 展开）
    return reg
