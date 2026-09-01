"""DurableProvider 抽象（TechDesign §6.2.1 长时任务持久化）。

职责：把『挂起的长时任务状态』落盘，进程/编辑器重启后能按 job_id 重建。
P0 用 local_sqlite；生产级可换 temporal_adapter / prefect_adapter（同接口）。
"""
from __future__ import annotations

import abc
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class DurableTask:
    """一条被持久化的长时任务记录。"""

    job_id: str
    tool_name: str
    params: dict = field(default_factory=dict)
    status: str = "pending"          # pending | running | done | failed
    result: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "tool_name": self.tool_name,
            "params": self.params,
            "status": self.status,
            "result": self.result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class DurableProvider(abc.ABC):
    """长时任务持久化接口。"""

    @abc.abstractmethod
    def create(self, job_id: str, tool_name: str, params: dict) -> DurableTask: ...

    @abc.abstractmethod
    def get(self, job_id: str) -> DurableTask | None: ...

    @abc.abstractmethod
    def update(self, job_id: str, *, status: str | None = None, result: dict | None = None) -> None: ...

    @abc.abstractmethod
    def list_pending(self) -> list[DurableTask]: ...
