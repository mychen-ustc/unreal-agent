"""production_start: ACTIVE→真 UE 灰盒生产机制单测（离线：fake backend，写 ledger 到临时目录，不碰网络/repo）。"""
from __future__ import annotations

import json

import pytest

from orchestrator.ue_backend import ToolResult


class _FakeBackend:
    def __init__(self, fail_first: int = 0):
        self.calls = []
        self.fail = fail_first

    def call_tool(self, tool_name: str, arguments: dict):
        self.calls.append((tool_name, arguments))
        if tool_name == "place_cube":
            if self.fail > 0:
                self.fail -= 1
                return ToolResult(ok=False, error_code="TOOL_ERR", detail="模拟失败")
            return ToolResult(ok=True, data={"ok": True})
        if tool_name == "remove_cube":
            return ToolResult(ok=True, data={"removed": 1})
        return ToolResult(ok=False, error_code="TOOL_UNSUPPORTED", detail=f"unknown {tool_name}")


def _patch(monkeypatch, tmp_path):
    import orchestrator.production_start as ps
    monkeypatch.setattr(ps, "SHARED", tmp_path)
    # 用基准布局
    monkeypatch.setattr(ps, "_DEFAULT_LAYOUT", ps._DEFAULT_LAYOUT[:2])  # 缩短
    return ps


def test_produce_places_and_writes_ledger(monkeypatch, tmp_path):
    ps = _patch(monkeypatch, tmp_path)
    backend = _FakeBackend()
    summary = ps.produce(backend)
    assert summary["spawned"] == len(ps._DEFAULT_LAYOUT)
    assert summary["fail"] == 0
    # ledger 落在 production/<runId>/MANIFEST.json（runId 来自仓库 ACTIVE，存在即可）
    man_dir = list((tmp_path / "production").rglob("MANIFEST.json"))
    assert man_dir, "应写 ledger"
    m = json.loads(man_dir[0].read_text())
    assert m["mode"] == "greybox"
    assert m["prefix"] == "prod"
    assert all(a["ok"] for a in m["actors"])


def test_produce_fail_recorded(monkeypatch, tmp_path):
    ps = _patch(monkeypatch, tmp_path)
    backend = _FakeBackend(fail_first=1)
    summary = ps.produce(backend)
    assert summary["spawned"] == len(ps._DEFAULT_LAYOUT) - 1
    assert summary["fail"] == 1


def test_layout_label_prefix():
    from orchestrator.production_start import _DEFAULT_LAYOUT
    assert _DEFAULT_LAYOUT
    assert all(s.label.startswith("prod") for s in _DEFAULT_LAYOUT)
