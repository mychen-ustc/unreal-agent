"""asyncio 任务调度器：拓扑 + 优先级 + 并行就绪分支（TechDesign §6.2）。

职责：把 DAG 的 ready 节点按优先级调度执行；同一层可并发。
挂起长任务（未来）经 DurableProvider 交给收割协程，实现让出协程、不阻塞无关分支。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional

from orchestrator.dag import DagEngine

log = logging.getLogger(__name__)

_TIER_PRIORITY = {"strong": 0, "default": 1, "fast": 2}
_TASK_PRIORITY_OVERRIDE = {
    "build_cook_run": -10,     # 阻塞清单项优先
    "git_push": -10,
}


class Scheduler:
    def __init__(
        self,
        dag: DagEngine,
        runner: Callable[[str], Awaitable[None]],
        *,
        executor: Optional[asyncio.AbstractEventLoop] = None,
        max_concurrent: int = 4,
    ) -> None:
        self.dag = dag
        self.runner = runner          # run(task_id) -> None
        self.max_concurrent = max_concurrent
        self._sem = asyncio.Semaphore(max_concurrent)

    def _priority(self, task_id: str) -> tuple[int, int]:
        node = self.dag.nodes[task_id]
        base = _TIER_PRIORITY.get(node.tier, 50)
        base = _TASK_PRIORITY_OVERRIDE.get(task_id, base)
        return (base, 0)

    async def run(self) -> int:
        """按拓扑 + 优先级调度全部 ready 节点，直到无新就绪。返回执行节点数。"""
        executed = 0
        while True:
            ready = self.dag.ready_nodes()
            if not ready:
                break
            ready.sort(key=self._priority)
            log.info("本轮就绪 %d 个：%s", len(ready), ready)
            # 并发执行就绪分支（受空间分区锁约束 → P0 简化为并发上限）
            await asyncio.gather(*(self._run_one(t) for t in ready))
            executed += len(ready)
        return executed

    async def _run_one(self, task_id: str) -> None:
        async with self._sem:
            node = self.dag.nodes[task_id]
            node.state = "running"
            try:
                await self.runner(task_id)
                node.state = "done"
            except Exception as exc:  # noqa: BLE001
                node.state = "failed"
                log.exception("任务 %s 失败: %s", task_id, exc)
