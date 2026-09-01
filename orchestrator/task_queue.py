"""优先级任务队列（Harness §6.1）。"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(order=True)
class PriorityItem:
    priority: int
    seq: int
    task: Any = field(compare=False)


class TaskQueue:
    """最小堆优先队列（低值优先执行）。"""

    def __init__(self) -> None:
        self._heap: list[PriorityItem] = []
        self._seq = 0

    def push(self, task: Any, priority: int = 100) -> None:
        heapq.heappush(self._heap, PriorityItem(priority, self._seq, task))
        self._seq += 1

    def pop(self) -> Optional[Any]:
        if not self._heap:
            return None
        return heapq.heappop(self._heap).task

    def peek(self) -> Optional[Any]:
        return self._heap[0].task if self._heap else None

    def __len__(self) -> int:
        return len(self._heap)

    def clear(self) -> None:
        self._heap.clear()
