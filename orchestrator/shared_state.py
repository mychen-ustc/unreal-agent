"""SharedState：Git 事实源 + 消息信封（TechDesign §5.3 / 附录 B）。

- 存储：仓库根 `shared_state/` 目录，JSON 按路径组织。
- 信封：{ schema_version, parent_hash, producer, created_at, payload }。
- 提供读写 + parent_hash 计算，供 Orchestrator/Agent 使用。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_VERSION = "1.2.0"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(data: str) -> str:
    return "sha256:" + hashlib.sha256(data.encode("utf-8")).hexdigest()


def make_envelope(
    producer: str,
    payload: dict,
    parent_hash: str = "",
    schema_version: str = _SCHEMA_VERSION,
) -> dict:
    """构造一个 SharedState 信封。"""
    return {
        "schema_version": schema_version,
        "parent_hash": parent_hash,
        "producer": producer,
        "created_at": now_iso(),
        "payload": payload,
    }


def hash_envelope(envelope: dict) -> str:
    """对信封做规范化 SHA-256，作为其 parent_hash。"""
    canonical = json.dumps(envelope, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256(canonical)


class SharedState:
    """Git 事实源 + 信封的读写门面。"""

    def __init__(self, root: Path = _REPO_ROOT) -> None:
        self.root = root
        self.base = root / "shared_state"

    # ---- 路径解析 ----
    def _path_for(self, rel_path: str) -> Path:
        p = (self.base / rel_path).resolve()
        # 禁止路径穿越到 base 之外
        if not (str(p).startswith(str(self.base)) or p == self.base):
            raise ValueError(f"非法 SharedState 路径: {rel_path}")
        return p

    def read(self, rel_path: str) -> dict | None:
        p = self._path_for(rel_path)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def write(self, rel_path: str, producer: str, payload: dict, parent_hash: str = "") -> dict:
        """写入一个信封到 shared_state/<rel_path>.json。返回信封。"""
        envelope = make_envelope(producer=producer, payload=payload, parent_hash=parent_hash)
        p = self._path_for(rel_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        # 统一存为 <rel>.json
        target = p if p.suffix == ".json" else p.with_suffix(".json")
        target.write_text(
            json.dumps(envelope, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return envelope

    def exists(self, rel_path: str) -> bool:
        return self._path_for(rel_path).exists()

    def list(self, subdir: str = "") -> list[str]:
        base = self.base / subdir if subdir else self.base
        if not base.exists():
            return []
        return sorted(str(p.relative_to(self.base)) for p in base.rglob("*.json"))

    def ensure_dirs(self) -> None:
        for sub in ("strategy", "game", "narrative", "character", "art", "level", "data", "eval"):
            (self.base / sub).mkdir(parents=True, exist_ok=True)
