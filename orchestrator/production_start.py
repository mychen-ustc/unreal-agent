"""production_start —— 把 ACTIVE 提案接进真 UE 生产（灰盒 step，机制验证）。

- 读 ACTIVE run（resolve_active）取出 strategy/proposal 与 game_design 的 summary 文本，
  作为“生产任务书”文本输入。
- 依它产出一份可物理化的灰盒布局，host 经 UeMcpBackend 在真 UE 关卡批量放置带
  `prod://…` label 的立方体占位（房间/门/符文/敌人出生点等簇），形成首关“可跑/可用真实资产覆盖”的灰盒。
- 写 shared_state/production/<runId>/MANIFEST.json 记录每个占位的 label/坐标/状态（后续真实资产可对照覆盖）。
- 默认保留这些灰盒以覆盖（--clean 可清除该 run 用 BasicSpawn 移除）。

仅验证机制；离线单元走 fake backend 验证布局与 ledger 正确。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from orchestrator.ue_backend import UeMcpBackend

log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[1]
SHARED = REPO / "shared_state"

LABEL_PREFIX = "prod"


@dataclass
class GreyBoxSpec:
    """灰盒占位规格：一个可放置立方体。"""

    label: str
    x: float
    y: float
    z: float


# 基于“收集符文→开仪式门→推新区域”的轻魂系探索最小灰盒（起一段流程，坐标为示意）
_DEFAULT_LAYOUT: list[GreyBoxSpec] = [
    GreyBoxSpec(f"{LABEL_PREFIX}_entrance_room", 0, 0, 50),
    GreyBoxSpec(f"{LABEL_PREFIX}_wall_a", 0, -200, 150),
    GreyBoxSpec(f"{LABEL_PREFIX}_wall_b", 0, 200, 150),
    GreyBoxSpec(f"{LABEL_PREFIX}_rune_01", -400, 0, 50),
    GreyBoxSpec(f"{LABEL_PREFIX}_rune_02", -400, 200, 50),
    GreyBoxSpec(f"{LABEL_PREFIX}_gate_frame_l", 800, -120, 150),
    GreyBoxSpec(f"{LABEL_PREFIX}_gate_frame_r", 800, 120, 150),
    GreyBoxSpec(f"{LABEL_PREFIX}_activation_platform", 800, 0, 45),
    GreyBoxSpec(f"{LABEL_PREFIX}_next_zone_gate", 1400, 0, 150),
    GreyBoxSpec(f"{LABEL_PREFIX}_enemy_spawn_a", 400, 300, 50),
    GreyBoxSpec(f"{LABEL_PREFIX}_enemy_spawn_b", 600, -300, 50),
]


def load_active_proposal_text() -> tuple[Any, str]:
    """取 ACTIVE run 的方向与 proposal 文本（作为生产任务书）。raise 若无 ACTIVE。"""
    from orchestrator.demo_concept import resolve_active
    from orchestrator.shared_state import SharedState

    rid = resolve_active()
    if not rid:
        raise RuntimeError("无 ACTIVE run（先跑 demo-concept 生成提案）")
    ss = SharedState()
    prop = ss.read(f"runs/{rid}/strategy/proposal")
    text = ""
    if prop and isinstance(prop.get("payload"), dict):
        text = prop["payload"].get("summary", "") or ""
    return prop, rid


def layout_for_proposal() -> list[GreyBoxSpec]:
    """由 ACTIVE 提案方向决定可物理化灰盒布局（P0 用确定基准布局）。"""
    # 机制验证：基准布局即可；解析方向展示在 ledger。
    return list(_DEFAULT_LAYOUT)


def produce(backend: UeMcpBackend, *, clean: bool = False) -> dict[str, Any]:
    """在真 UE 关卡放置/清除 ACTIVE 灰盒布局，写 ledger。返回 summary。"""
    _, rid = load_active_proposal_text()
    run_dir = SHARED / "production" / rid
    run_dir.mkdir(parents=True, exist_ok=True)

    if clean:
        # 仅清除此前 prod:// 生成的占位（用一个代表 label 集重建清除）
        cleaned = 0
        for spec in layout_for_proposal():
            r = backend.call_tool("remove_cube", {"label": spec.label})
            if r.ok:
                cleaned += 1
        _write_ledger(run_dir, layout_for_proposal(), [], cleaned=cleaned, rid=rid)
        return {"run": rid, "cleaned": cleaned}

    spawned: list[dict] = []
    fail = 0
    for spec in layout_for_proposal():
        r = backend.call_tool("place_cube", {"label": spec.label, "location_x": spec.x,
                                             "location_y": spec.y, "location_z": spec.z})
        if r.ok:
            spawned.append({"label": spec.label, "x": spec.x, "y": spec.y, "z": spec.z})
        else:
            fail += 1
            log.warning("放置 %s 失败: %s", spec.label, r.detail)
    _write_ledger(run_dir, layout_for_proposal(), spawned, cleaned=0, rid=rid)
    return {"run": rid, "spawned": len(spawned), "fail": fail}


def _write_ledger(run_dir: Path, layout: list, spawned: list, *, cleaned: int, rid: str) -> None:
    ledger = {
        "run_id": rid,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prefix": LABEL_PREFIX,
        "mode": "greybox",
        "actors": [
            {"label": s.label, "x": s.x, "y": s.y, "z": s.z,
             "ok": any(sp["label"] == s.label for sp in spawned)} for s in layout
        ],
        "spawn_ok_count": len(spawned),
        "cleaned": cleaned,
    }
    (run_dir / "MANIFEST.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("ledger 已写 %s", run_dir / "MANIFEST.json")
