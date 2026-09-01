"""UnrealAgent Orchestrator —— L4 编排与治理层（P0 地基脚手架）。

对齐 Agent Harness 选型与技术设计 §6（唯一事实源）：自研最小编排核心（dag + scheduler）
+ DurableProvider + LiteLLM；不使用第三方 Agent 图框架（LangGraph 已评估排除）。
入口：`python -m orchestrator ...` 或 `orchestrator ...`（CLI）。
"""
from orchestrator.models import ModelRouter, get_router
from orchestrator.trace import TraceWriter, get_trace

__all__ = ["ModelRouter", "get_router", "TraceWriter", "get_trace", "__version__"]

__version__ = "0.1.0"
