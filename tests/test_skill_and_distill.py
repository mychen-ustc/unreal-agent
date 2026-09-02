"""Skill 商业分级 + distiller 能力蒸馏 + importers 跨宿主导入测试。

对齐 Agent Harness §11.3（tier 0–4 / distill_visibility）、§12（importers 只消费蒸馏子集）、
SECURITY-LICENSING §3.2（P0 预埋分级字段）。
"""
from __future__ import annotations

import pytest

from orchestrator.skill import SkillSpec, get_registry, _parse_tier, _check_distill


# ---- Skill 商业分级解析 ----

def test_parse_tier_clamps_range():
    assert _parse_tier(0) == 0
    assert _parse_tier(4) == 4
    assert _parse_tier(7) == 4     # 超上限钳制
    assert _parse_tier(-1) == 0    # 负值钳制
    assert _parse_tier("2") == 2   # 字符串兼容


def test_parse_tier_fallback_on_garbage():
    assert _parse_tier(None) == 0
    assert _parse_tier("abc") == 0


def test_check_distill_valid_and_fallback():
    assert _check_distill("full") == "full"
    assert _check_distill("lite") == "lite"
    assert _check_distill("hidden") == "hidden"
    assert _check_distill("illegal") == "full"  # 非法回退 full


def test_scenes_pcg_commercial_tier_loaded():
    """P0 预埋：scenes_pcg 应声明商业 tier/distill（§11.3 / SECURITY-LICENSING §3.2）。"""
    reg = get_registry()
    spec = reg.load("scenes_pcg").spec
    assert spec.tier == 2
    assert spec.distill_visibility == "lite"
    assert spec.default_tier == "default"


# ---- Distiller 能力蒸馏 ----

def test_disto_mvp_subset_includes_low_tier():
    from orchestrator.distiller import Distiller
    from orchestrator.skill import SkillRegistry
    from pathlib import Path
    import tempfile

    # 构造一个临时 skills 目录，含一个 tier=1/lite 和一个 tier=4/hidden 的 Skill
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "low").mkdir()
        (root / "low" / "skill.yaml").write_text(
            "name: low\n" "tier: 1\n" "distill_visibility: lite\n", encoding="utf-8")
        (root / "secret").mkdir()
        (root / "secret" / "skill.yaml").write_text(
            "name: secret\n" "tier: 4\n" "distill_visibility: hidden\n", encoding="utf-8")

        d = Distiller(registry=SkillRegistry(skills_dir=root))
        subset = d.make_mvp_subset()
        names = [s.name for s in subset]
        assert "low" in names     # tier=1,lite 进入
        assert "secret" not in names  # tier=4,hidden 被裁掉


def test_disto_hidden_and_high_tier_excluded():
    from orchestrator.distiller import Distiller

    # 用 scenes_pcg（tier=2, lite）验证：应进入子集
    subset = Distiller().make_mvp_subset()
    assert any(s.name == "scenes_pcg" for s in subset)


# ---- Importers 跨宿主导入 ----

def test_self_hosted_importer_generates_bundle():
    from orchestrator.distiller import Distiller
    from orchestrator.importers.registry import get_importer, list_targets

    assert "self_hosted" in list_targets()
    subset = Distiller().make_mvp_subset()
    imp = get_importer("self_hosted")
    bundle = imp.generate(subset, "http://127.0.0.1:8000/mcp")
    assert bundle.target == "self_hosted"
    rel_paths = [f.rel_path for f in bundle.all_files()]
    # 每个蒸馏 Skill 有一个 skill.yaml + mcp 配置 + manifest
    assert any("skill.yaml" in p for p in rel_paths)
    assert "mcp.config.json" in rel_paths
    assert "MANIFEST.yaml" in rel_paths


def test_unknown_importer_raises():
    from orchestrator.importers.registry import get_importer

    with pytest.raises(KeyError):
        get_importer("codex")  # 尚未实现，应明确报错


def test_claude_code_importer_generates_skill_md():
    """Claude Code Adapter：SKILL.md + .mcp.json + MANIFEST.json（§12.4）。"""
    from orchestrator.distiller import Distiller
    from orchestrator.importers.registry import get_importer, list_targets

    assert "claude_code" in list_targets()
    subset = Distiller().make_mvp_subset(skill_names=["scenes_pcg"])
    bundle = get_importer("claude_code").generate(subset, "http://127.0.0.1:8000/mcp")

    paths = {f.rel_path for f in bundle.all_files()}
    skill_md = next(f for f in bundle.all_files() if f.rel_path.endswith("SKILL.md"))
    mcp_json = next(f for f in bundle.all_files() if f.rel_path == ".mcp.json")

    # SKILL.md：Anthropic frontmatter + 执行步骤注记
    assert skill_md.content.startswith("---\nname: scenes_pcg")
    assert "## 执行步骤" in skill_md.content
    # .mcp.json：指向 UE MCP Server
    assert '"unreal-agent"' in mcp_json.content
    assert "127.0.0.1:8000/mcp" in mcp_json.content
    assert ".mcp.json" in paths and "MANIFEST.json" in paths


# ---- 多 Skill 分组：发现与白名单/工具映射 ----

def test_skill_groups_discovered():
    """P0 代表 Skill（场景/灯光/数据/QA）可被发现且商业分级齐全。"""
    reg = get_registry()
    names = set(reg.discover())
    assert {"scenes_pcg", "lighting_setup", "data_pipeline", "qa_smoke"} <= names
    lighting = reg.load("lighting_setup").spec
    assert lighting.tool_whitelist == ["lighting_place_directional", "lighting_set_postprocess"]
    assert lighting.tier == 2 and lighting.distill_visibility == "lite"


def test_skill_steps_map_to_registered_tools():
    """每个 Skill 的执行步骤声明的 tool 都应在 toolset_registry 登记。"""
    from orchestrator import toolset_registry as reg

    for name in get_registry().discover():
        spec = get_registry().load(name).spec
        for s in spec.steps:
            if s.tool:
                assert reg.get_tool_meta(s.tool) is not None, f"Skill {name} 步骤 {s.id} 的 tool {s.tool} 未在 registry 登记"


def test_lighting_steps_tools_registered():
    from orchestrator import toolset_registry as reg

    spec = get_registry().load("lighting_setup").spec
    step_tools = {s.tool for s in spec.steps if s.tool}
    for t in step_tools:
        assert reg.get_tool_meta(t) is not None
