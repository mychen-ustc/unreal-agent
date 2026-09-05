"""schema_check.py —— 契约可执行校验（CONTRACTS §3/§5；非手写文档）。

检查（可被 CI / pytest 调用）：
1. 每个 Skill：skill.yaml 的 tier∈0–4, distill∈{full,lite,hidden}, default_tier∈{fast,default,strong}，
   steps.yaml 引用存在；步骤 tool 已注册且在白名单（toolset_registry 全局登记）。
2. shared_state/*.json（runs 信封）：schema_version/parent_hash/producer 必备。

用法：
  python -m orchestrator.scripts.schema_check        # 全量
  python -m orchestrator.scripts.schema_check --quiet
退出码：0=通过；非 0=存在违例。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / "orchestrator" / "skills"
SHARED = REPO / "shared_state"

_ERR = []


def _err(msg: str):
    _ERR.append(msg)


def check_skills() -> None:
    from orchestrator import toolset_registry as TR
    from orchestrator.skill import get_registry

    avail = {t.name for t in TR.ALL_TOOLS}
    reg = get_registry()
    reg._cache.clear()
    for name in sorted(reg.discover()):
        spec = reg.load(name).spec
        if not (0 <= spec.tier <= 4):
            _err(f"{name}: tier={spec.tier} 超出 0–4")
        if spec.distill_visibility not in ("full", "lite", "hidden"):
            _err(f"{name}: distill_visibility={spec.distill_visibility!r} 非法")
        if spec.default_tier not in ("fast", "default", "strong"):
            _err(f"{name}: default_tier={spec.default_tier!r} 非法")
        if not spec.tool_whitelist:
            _err(f"{name}: tool_whitelist 为空")
        for st in spec.steps:
            if st.tool:
                if st.tool not in avail:
                    _err(f"{name}/{st.id}: tool {st.tool!r} 未注册")
                elif st.tool not in spec.tool_whitelist:
                    _err(f"{name}/{st.id}: tool {st.tool!r} 不在白名单")
            for dep in st.dependencies:
                ids = {s.id for s in spec.steps}
                if dep not in ids:
                    _err(f"{name}/{st.id}: 依赖 {dep!r} 未定义")


def check_shared_state() -> None:
    if not SHARED.exists():
        return
    for p in SHARED.rglob("*.json"):
        # 排除非信封元文件（run manifest / production manifest 等）
        if p.name in {"RUNMANIFEST.json", "MANIFEST.json"}:
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            _err(f"{p.relative_to(REPO)}: json 解析失败 {exc}")
            continue
        for f in ("schema_version", "parent_hash", "producer"):
            if f not in d:
                _err(f"{p.relative_to(REPO)}: 缺 {f}")
                break


def run() -> int:
    check_skills()
    check_shared_state()
    return 1 if _ERR else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true", help="仅退出码，不打印")
    args = ap.parse_args()
    code = run()
    if not args.quiet:
        if _ERR:
            print(f"schema_check: 发现 {len(_ERR)} 处违例")
            for m in _ERR:
                print("  -", m)
        else:
            print("schema_check: 全部通过（Skill 契约 + SharedState 信封）")
    sys.exit(code)


if __name__ == "__main__":
    os.chdir(REPO)
    main()
