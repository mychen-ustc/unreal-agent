"""结构化追踪日志（JSON Lines → .logs/trace.jsonl）。

对齐 TechDesign §6.5：每条 Tool/Agent 事件以 JSON Lines 落盘，既给人看也喂回 RAG。
"""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_DIR = _REPO_ROOT / ".logs"
TRACE_FILE = "trace.jsonl"


class TraceWriter:
    def __init__(self, path: Path = DEFAULT_LOG_DIR / TRACE_FILE) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = None

    def _open(self):
        if self._fh is None or self._fh.closed:
            self._fh = open(self.path, "a", encoding="utf-8")
        return self._fh

    def emit(self, event: str, **fields) -> None:
        record = {
            "event": event,
            "ts": datetime.now(timezone.utc).isoformat(),
            **fields,
        }
        self._open().write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        self._open().flush()

    def tool_call(self, tool: str, args: dict, outcome: dict, producer: str = "") -> None:
        self.emit(
            "tool_call",
            tool=tool,
            arguments=args,
            outcome=outcome,
            producer=producer,
        )

    def agent_event(self, agent: str, action: str, detail: dict | None = None) -> None:
        self.emit("agent", agent=agent, action=action, detail=detail or {})

    def close(self) -> None:
        if self._fh and not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> "TraceWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


@contextmanager
def trace(path: Path = DEFAULT_LOG_DIR / TRACE_FILE) -> Iterator[TraceWriter]:
    w = TraceWriter(path)
    try:
        yield w
    finally:
        w.close()


_default_writer: TraceWriter | None = None


def get_trace() -> TraceWriter:
    global _default_writer
    if _default_writer is None:
        _default_writer = TraceWriter()
    return _default_writer
