"""schema_check.py 契约校验冒烟（无真实共他副作用安全）。"""
from __future__ import annotations

from orchestrator.scripts import schema_check


def test_clean_passes():
    # 当前仓库 Skill 契约 + SharedState 信封应无违例
    assert schema_check.run() == 0


def test_manifest_exempt_not_flag():
    # RUNMANIFEST.json 等非信封元文件应被跳过
    # 直接构造检查：其 head 不是信封也未必被计入
    schema_check._ERR.clear()
    schema_check.check_shared_state()
    errs_manifest_only = all(not m.startswith("shared_state/runs/") or 'RUNMANIFEST' not in m for m in schema_check._ERR)
    assert errs_manifest_only
