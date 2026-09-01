"""P0 DurableProvider：SQLite 落盘实现。

进程/编辑器重启后，可按 job_id 重建长时任务并查询 UE 侧状态（§6.2.1）。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .base import DurableProvider, DurableTask

_SCHEMA = """
CREATE TABLE IF NOT EXISTS durable_tasks (
    job_id TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    params TEXT NOT NULL,
    status TEXT NOT NULL,
    result TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class SQLiteDurableProvider(DurableProvider):
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def create(self, job_id: str, tool_name: str, params: dict) -> DurableTask:
        now = datetime.now(timezone.utc).isoformat()
        task = DurableTask(
            job_id=job_id,
            tool_name=tool_name,
            params=params,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO durable_tasks VALUES (?,?,?,?,?,?,?)",
            (
                task.job_id,
                task.tool_name,
                json.dumps(task.params, ensure_ascii=False),
                task.status,
                json.dumps(task.result, ensure_ascii=False),
                task.created_at,
                task.updated_at,
            ),
        )
        self._conn.commit()
        return task

    def get(self, job_id: str) -> DurableTask | None:
        row = self._conn.execute(
            "SELECT * FROM durable_tasks WHERE job_id=?", (job_id,)
        ).fetchone()
        if row is None:
            return None
        return DurableTask(
            job_id=row["job_id"],
            tool_name=row["tool_name"],
            params=json.loads(row["params"]),
            status=row["status"],
            result=json.loads(row["result"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def update(self, job_id: str, *, status: str | None = None, result: dict | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        existing = self.get(job_id)
        if existing is None:
            raise KeyError(f"Unknown job: {job_id}")
        new_status = status or existing.status
        new_result = result if result is not None else existing.result
        self._conn.execute(
            "UPDATE durable_tasks SET status=?, result=?, updated_at=? WHERE job_id=?",
            (new_status, json.dumps(new_result, ensure_ascii=False), now, job_id),
        )
        self._conn.commit()

    def list_pending(self) -> list[DurableTask]:
        rows = self._conn.execute(
            "SELECT * FROM durable_tasks WHERE status IN ('pending','running')"
        ).fetchall()
        return [
            DurableTask(
                job_id=r["job_id"],
                tool_name=r["tool_name"],
                params=json.loads(r["params"]),
                status=r["status"],
                result=json.loads(r["result"]),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()
