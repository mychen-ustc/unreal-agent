"""RAG Grounding：LanceDB 检索 + 注入（TechDesign §6.3 / §6.4）。

P0：嵌入式 LanceDB 索引；文档带 source/version/chunk_type 元数据；
支持写入 + 语义检索 + 作为 Agent context 注入。默认目录 ./memory/lancedb（gitignored）。

注意：LanceDB 表 schema 由首次写入数据推断（不固定嵌入维度），
以便接不同的编码器（all-MiniLM-L6-v2 384 / e5 1024 等）。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import lancedb

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_DIR = _REPO_ROOT / "orchestrator" / "memory" / "lancedb"


class RagStore:
    """嵌入式向量检索库。"""

    def __init__(self, dir_path: Path = DEFAULT_DB_DIR) -> None:
        self.dir = dir_path
        self.dir.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self.dir))

    @property
    def _name(self) -> str:
        return "corpus"

    @property
    def table(self):
        names = self._db.table_names()
        return self._db.open_table(self._name) if self._name in names else None

    def _ensure_table(self, vector: list[float]):
        if self.table is None:
            self._db.create_table(self._name, data=[self._row("", "", "", "", vector)])
        return self.table

    @staticmethod
    def _row(rid: str, text: str, source: str, version: str, vector: list) -> dict:
        return {
            "id": rid,
            "text": text,
            "source": source,
            "version": version,
            "chunk_type": "",
            "vector": vector,
        }

    # ---- 写入 ----
    def upsert(
        self,
        *,
        text: str,
        source: str,
        version: str = "",
        chunk_type: str = "code",
        vector: list[float],
        embedding_id: str = "",
    ) -> None:
        import uuid

        rid = embedding_id or str(uuid.uuid4())
        idx = _EmbeddingIndex(self)
        tbl = idx._ensure_version(vector)
        row = self._row(rid, text, source, version, vector)
        row["chunk_type"] = chunk_type
        tbl.add([row])

    # ---- 检索 ----
    def search(self, embedding: list[float], limit: int = 5) -> list[dict]:
        tbl = self.table
        if tbl is None:
            return []
        try:
            return tbl.search(embedding).limit(int(limit)).to_list()
        except Exception as exc:  # noqa: BLE001
            log.warning("LanceDB 检索失败: %s", exc)
            return []


class _EmbeddingIndex:
    """懒创建表并做 schema 版本兼容的辅助。"""

    def __init__(self, store: RagStore) -> None:
        self.store = store

    def _ensure_version(self, vector: list[float]):
        if self.store.table is None:
            self.store._db.create_table(
                self.store._name,
                data=[self.store._row("x", "x", "x", "x", vector)],
            )
        return self.store.table
