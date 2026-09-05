"""preproduction —— 立项后预生产设定（风格/叙事/数值基线）产出。

从 ACTIVE run（已采用方向）产出三块预生产输入，供 C（vertical-slice build 的真实生产/UE）前置对齐：
- style_guide       概念美术方向（identity / color_palette / material / lighting / landmark）
- narrative         灯语语义与开场（hook_line / lumina_grammar / artifact_motifs / opening_intro）
- system_baseline   竖切片可用数值草（light_pool / tide_axis / enemy_lightmatrix / gate / constraints）

信封落 shared_state/preproduction/<runId>/。可被 CLI/import/测试复用（假 router）。
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Optional

from orchestrator.models import get_router
from orchestrator.shared_state import SharedState

_PREPROD = "preproduction"


def _direction_text() -> str:
    """基于 ACTIVE run 的立项世界上下文（human short）。"""
    from orchestrator.demo_concept import resolve_active

    ss = SharedState()
    rid = resolve_active()
    txt = ""
    if rid:
        prop = ss.read(f"runs/{rid}/strategy/proposal")
        if prop and isinstance(prop.get("payload"), dict):
            txt = prop["payload"].get("summary", "") or ""
    tail = "首个竖直切片为沉塔-灯塔：验证控光（光=武器/盾/导航）、灯语收集、逐塔点亮以变潮汐/机"
    "关开航道；敌人影带怪畏光；失败率≤30%且无文字教学。"
    return f"立项[{rid}]：\n{txt}\n约定：\n{tail}"


def _call(prompt: str, tier: str = "default") -> str:
    return asyncio.run(get_router().complete(prompt, tier="default"))


def _as_json(text: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None


def _style_prompt(world: str) -> str:
    return (
        "你是《废海灯语》(TidalLight) 的 concept_artist，为海洋废土/灯塔制定美术方向。立项世界：\n"
        + world + (
            "\n请只输出 JSON 对象，字段：identity、color_palette(数组)、material_language(数组)、"
            "lighting_mood、landmark_notes（沉塔/灯塔一层视觉简述）。拿捏压抑深海克苏鲁 + 灯塔希望。"
        )
    )


def _narrative_prompt(world: str) -> str:
    return (
        "你是《废海灯语》的 narrative_writer(W1)，给灯语语义与开场定调。立项世界：\n"
        + world + (
            "\n只输出 JSON 对象：hook_line、lumina_grammar(数组条目)、artifact_motifs(数组)、"
            "opening_intro(碎片电影感 2-4 句)。原创、无既有 IP。"
        )
    )


def _system_prompt(world: str) -> str:
    return (
        "你是《废海灯语》的 system_designer(ND)，为首竖切沉塔-灯塔(3 战 + 1 光闸门→点灯塔)出可用数值草。立项世界：\n"
        + world + (
            "\n只输出 JSON 对象：light_pool(存量节奏说明)、tide_axis(潮汐轴简述)、"
            "enemy_lightmatrix(影带怪等 灯光系/生命/行为)、gate(光闸门参数)、"
            "constraints(fail_gate=30 等阈值，无文字教学起点)。"
        )
    )


def run(*, persist: bool = True) -> dict[str, Any]:
    """为 ACTIVE run 产出三块预生产设定（texts + payloads；persist 时落信封）。"""
    world = _direction_text()
    builders = {
        "style_guide": _style_prompt,
        "narrative": _narrative_prompt,
        "system_baseline": _system_prompt,
    }
    texts: dict[str, str] = {}
    payloads: dict[str, Any] = {}
    for name, b in builders.items():
        t = _call(b(world))
        texts[name] = t
        data = _as_json(t)
        payloads[name] = data if data is not None else {"raw": t}
    envs: dict[str, Any] = {}
    if persist:
        envs = _persist(payloads)
    return {"texts": texts, "payloads": payloads, "envelopes": envs}


def _persist(payloads: dict[str, Any]) -> dict[str, Any]:
    from orchestrator.demo_concept import resolve_active
    from orchestrator.shared_state import hash_envelope

    ss = SharedState()
    rid = resolve_active() or "unknown"
    parent = ""
    out: dict[str, Any] = {}
    for name, pl in payloads.items():
        env = ss.write(f"{_PREPROD}/{rid}/{name}", producer=f"pre{name}",
                       payload=pl, parent_hash=parent)
        out[name] = env
        parent = hash_envelope(env)
    return out
