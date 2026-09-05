"""preproduction：立项后风格/叙事/数值基线产出（离线，假 `_call`，不落盘）。"""
from __future__ import annotations

import json

import orchestrator.preproduction as pp


def test_run_produces_three_blocks(monkeypatch):
    def fake_call(prompt, tier="default"):
        if "concept_artist" in prompt:
            return json.dumps({"identity": "灯塔使者的光语信物", "color_palette": ["深渊蓝黑"],
                               "material_language": ["锈铜"], "lighting_mood": "压抑微光",
                               "landmark_notes": "孤塔举灯"})
        if "writer(W1)" in prompt:
            return json.dumps({"hook_line": "光是废海仅存的语言",
                               "lumina_grammar": ["沉钟记忆要用光读"], "artifact_motifs": ["断桅"],
                               "opening_intro": "潮声，人影，火起。"})
        if "system_designer(ND)" in prompt:
            return json.dumps({"light_pool": "5 格", "tide_axis": "60s",
                               "enemy_lightmatrix": {"影带怪": {"hp": 3}},
                               "gate": {"seq": 2}, "constraints": {"fail_gate": 30}})
        return "{}"

    monkeypatch.setattr(pp, "_call", fake_call)
    res = pp.run(persist=False)
    assert set(res["payloads"]) == {"style_guide", "narrative", "system_baseline"}
    assert isinstance(res["payloads"]["style_guide"], dict)
    assert "identity" in res["payloads"]["style_guide"]
    assert isinstance(res["payloads"]["system_baseline"]["constraints"], dict)
