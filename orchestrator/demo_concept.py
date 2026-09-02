"""demo_concept：把「策略→评估」多 Skill 协同串成一个可观测、可复现、可持久化的核心玩法判断 demo。

说明（演示/验证「多 Skill 内容生产 + SharedState 沉淀 + 跨 Skill 状态链」）：
- 复用能力包里的 33 个 Common Spec Skill（此处取策略组 s1/s2/s3/s6 + 预生产 director + 评估 E6）
  的领域定位，调用真实 LLM（DeepSeek，读 .env）逐个产出可读领域产物。
- 存储按「run-id 版本化 + ACTIVE 指针」：
    shared_state/runs/<runId>/strategy/{market,competitor,game_design,creative_direction,proposal}.json
    shared_state/runs/<runId>/eval/benchmark.json
    shared_state/runs/<runId>/PROPOSAL.md        # 人类可读提案快照（合并 6 段）
    shared_state/runs/<runId>/RUNMANIFEST.json   # 运行元信息（direction / 时间 / 各阶段 producer / 落盘路径）
    shared_state/.ACTIVE_RUN                      # 内容=当前采用的 runId（文本，非信封）
  每次运行独立 run-id，历史保留在 git；`.ACTIVE_RUN` 指认"当前立项事实源"，后续策略/生产/评估流程读它定位输入。
- 阶段的 SharedState 信封携带 parent_hash 链，体现多 Skill 间的状态传递与 provenance。
- 这与「生产引擎 Skill 步骤 → MCP 桩调用」正交；此 driver 展示内容生产型 Skill 的 LLM 编排与
  SharedState 沉淀的端到端形态，产物可被后续生产 / 评估 / 存档持续引用。

用法：
  python -m orchestrator demo-concept --direction "想做探索驱动、收集符文开门、暗黑奇幻、轻战斗的动作冒险"
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from orchestrator.models import get_router
from orchestrator.shared_state import SharedState, hash_envelope


# 每阶段的 SharedState 相对 key（不含 .json；写入 runs/<runId>/<分组>/<name>）
# 同时用于 render / manifest / 上层读取本 run 特定节。
_STAGES = [
    ("market", "strategy/market", "s1_market_research"),
    ("competitor", "strategy/competitor", "s2_competitive_intel"),
    ("game_design", "strategy/game_design", "s3_game_design"),
    ("creative_direction", "strategy/creative_direction", "s6_creative_direction"),
    ("proposal", "strategy/proposal", "director"),
    ("eval_benchmark", "eval/benchmark", "eval_benchmark"),
]
_STAGE_NAME2REL = {name: rel for name, rel, _ in _STAGES}


@dataclass
class ConceptRoot:
    """一次概念的产物句柄。artifacts[name]=(md_text)；envelopes[name]=信封。"""

    direction: str
    run_id: str = ""
    artifacts: dict = field(default_factory=dict)     # name -> 可读文本（md）
    envelopes: dict = field(default_factory=dict)     # name -> SharedState 信封 dict

    @property
    def latest_verdict(self) -> str:
        e = self.envelopes.get("eval_benchmark")
        if not e:
            return ""
        txt = self.artifacts.get("eval_benchmark", "")
        # 尽力提取 GO/NO-GO/PIVOT
        for w in ("GO", "NO-GO", "PIVOT"):
            if w in txt:
                return w
        return "?(未解析)"


def _run_id(now: Optional[datetime] = None) -> str:
    """生成唯一 run-id：run-<UTC YYYYmmdd-HHMMSS>-<8hex>。"""
    now = now or datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d-%H%M%S")
    h = hashlib.sha1((now.isoformat()).encode("utf-8")).hexdigest()[:8]
    return f"run-{ts}-{h}"


def _s(prompt: str, tier: str = "default", system: str | None = None) -> str:
    """同步调 router.complete（内部 asyncio.to_thread）。tier 固定走 default(flash) 防强档超时（demo）。

    鲁棒：调用失败/空返回时以占位符回退，不让管线中断。
    """
    try:
        out = asyncio.run(get_router().complete(prompt, tier="default", system=system))
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] LLM 调用失败，占位回退：{type(exc).__name__}: {exc}", flush=True)
        return "（该阶段模型调用失败，已跳过）——建议重跑或检查 .env / 网络。"
    out = (out or "").strip()
    if not out:
        print("  [warn] LLM 返回为空，占位回退。", flush=True)
        out = "（该阶段返回为空，已占位）"
    return out


def _phase_contract():
    return (
        "\n请按以下格式输出：\n"
        "### 结论\n<一句话结论>\n"
        "### 要点\n- <要点1>\n- <要点2>（不超过 6 条，每条 ≤ 40 字）\n"
    )


# ---- 一次性 prompt 构造（各阶段对接对应 Skill） ----
def _q_market(direction):
    return ("你是 UE 独立游戏研发的市场分析师(S1)。\n"
            f"用户想做的方向：{direction}\n"
            "任务：一句话定位它是哪个细分赛道（dark fantasy action/adventure 类）、目标用户画像、"
            "以及这个空位上最有吸引力的点；不编造具体营收/销量数字。\n" + _phase_contract())


def _q_competitor(mkt):
    return ("你是 UE 动作冒险的竞品情报(S2)。\n参考市场定位：\n" + mkt +
            "\n任务：列出 2-3 个最有参考价值的对标/竞品，各给一句它证明了什么 + 一个本作可差异化空位。\n"
            + _phase_contract())


def _q_game_design(mkt, comp):
    return ("你是动作冒险核心玩法设计(S3)。\n市场：" + mkt + "\n竞品：" + comp +
            "\n任务：给出【核心循环】一句(秒→分钟→十分钟)与最核心的 First-hour 目标、"
            "以及一个『可证伪的最小验切口』假设。\n" + _phase_contract())


def _q_creative(direction, gd):
    return ("你是暗黑奇幻世界观与基调(S6)。\n设计方向：" + direction + "\n玩法：" + gd +
            "\n任务：给一句概念钩子（文明被自然吞没后玩家探索/收集/发现真相的原创转写）、一个核心意象、"
            "一个 Tone 色板情绪方向。\n" + _phase_contract())


def _q_director(mkt, comp, gd, cr):
    return ("你是项目导演(Director)。把下面策略拼成一个 3 行的可评估 Goal(目标 + 成功判据引用玩法假设)。\n"
            "市场:\n" + mkt + "\n竞品:\n" + comp + "\n玩法:\n" + gd + "\n创意:\n" + cr)


def _q_e6(dir_, mkt, gd):
    return ("你是面向投资/立项的横向基准评估(E6)。结合下面市场/玩法与提案给：受欢迎度分(0-100)+一句理由、"
            "三个最强差异化 axis、综合裁决 GO / NO-GO / PIVOT（并一句为什么）。\n"
            "提案:\n" + dir_ + "\n市场:\n" + mkt + "\n玩法:\n" + gd)


# ---- 核心：跑一次概念管线并写入 runs/<runId> + ACTIVE -----
def run_concept(direction: str,
                *,
                shared: SharedState | None = None,
                run_id: str | None = None,
                do_persist: bool = True) -> ConceptRoot:
    """按给定方向跑 S1→S2→S3→S6→Director→E6，持久化到 runId，并设 ACTIVE。

    do_persist=False 时不落盘（仅内存），供测试/预览。do_persist 时写 PROPOSAL.md + RUNMANIFEST +
    .ACTIVE_RUN。
    """
    shared = shared or SharedState()
    root = ConceptRoot(direction=direction, run_id=run_id or _run_id())
    run_dir = shared.base / "runs" / root.run_id
    parent = ""

    txt: dict[str, str] = {}

    print(f"[demo] run_id={root.run_id}", flush=True)

    mkt = _s(_q_market(direction));        txt["market"] = mkt
    print("[demo] S1 市场 ✓", flush=True)
    comp = _s(_q_competitor(mkt));         txt["competitor"] = comp
    print("[demo] S2 竞品 ✓", flush=True)
    gd = _s(_q_game_design(mkt, comp));    txt["game_design"] = gd
    print("[demo] S3 玩法 ✓", flush=True)
    crt = _s(_q_creative(direction, gd));  txt["creative_direction"] = crt
    print("[demo] S6 创意 ✓", flush=True)
    dir_txt = _s(_q_director(mkt, comp, gd, crt)); txt["proposal"] = dir_txt
    print("[demo] Director 立项目标 ✓", flush=True)
    e6 = _s(_q_e6(dir_txt, mkt, gd));      txt["eval_benchmark"] = e6
    print("[demo] E6 评估 ✓（裁决占位）", flush=True)
    root.artifacts = dict(txt)

    # 写信封到 runs/<runId>/...（含 parent_hash 跨阶段链），同时登记在 root.envelopes
    for name, rel, producer in _STAGES:
        env = shared.write(f"runs/{root.run_id}/{rel}", producer=producer,
                           payload={"summary": txt[name]}, parent_hash=parent)
        root.envelopes[name] = env
        parent = hash_envelope(env)

    if not do_persist:
        return root

    # 额外持久化（不用 SharedState.write，避免被强制 .json 后缀）
    run_dir.mkdir(parents=True, exist_ok=True)
    # PROPOSAL.md：人类可读提案快照
    proposal_md = _render_md(root)
    (run_dir / "PROPOSAL.md").write_text(proposal_md, encoding="utf-8")
    # RUNMANIFEST.json：运行元信息
    manifest = {
        "run_id": root.run_id,
        "direction": direction,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stages": [
            {"name": name, "producer": prod, "path": f"runs/{root.run_id}/{rel}"}
            for name, rel, prod in _STAGES
        ],
        "active": True,
    }
    (run_dir / "RUNMANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    # ACTIVE 指针
    active_p = shared.base / ".ACTIVE_RUN"
    active_p.write_text(root.run_id, encoding="utf-8")
    print(f"[demo] 持久化到 {run_dir.relative_to(shared.base)} 并设为 ACTIVE（.ACTIVE_RUN）", flush=True)
    return root


def resolve_active(shared: SharedState | None = None) -> str | None:
    """读取当前 ACTIVE run-id；无则 None。下游可用它作为“当前提案事实源”入口。"""
    shared = shared or SharedState()
    p = shared.base / ".ACTIVE_RUN"
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return None


def _run_rel(name: str) -> str:
    """把 stage name 映射到它在 run 下的信封相对路径（不含 .json）。"""
    rel = _STAGE_NAME2REL.get(name)
    return rel or f"strategy/{name}"


def _render_md(root: ConceptRoot) -> str:
    sec = [
        ("1. 市场(S1)", "market"),
        ("2. 竞品(S2)", "competitor"),
        ("3. 玩法设计(S3)", "game_design"),
        ("4. 创意方向(S6)", "creative_direction"),
        ("5. 导演立项目标(Director)", "proposal"),
        ("6. 横向基准评估(E6)", "eval_benchmark"),
    ]
    lines = [f"# 核心玩法提案（run_id: {root.run_id or '(内存/dry)'}）", "", f"> 方向：{root.direction}", ""]
    for title, name in sec:
        lines += [f"## {title}", "", (root.artifacts.get(name) or "（空）"), ""]
    lines += ["---", "## SharedState 落盘信封", ""]
    for name in ("market","competitor","game_design","creative_direction","proposal","eval_benchmark"):
        env = root.envelopes.get(name)
        rel = _run_rel(name)
        if env:
            lines.append(f"`runs/{root.run_id}/{rel}.json`  producer={env['producer']}  hash={hash_envelope(env)[:20]}…  parent={env['parent_hash'][:16]}…")
    return "\n".join(lines)


def render(root: ConceptRoot) -> str:
    """返回整个提案的可读 markdown（含 run_id 与信封路径）。"""
    return _render_md(root)


def show_envelope_map(root: ConceptRoot) -> str:
    """返回每阶段信封落盘相对路径的清单（CLI/人工查看用）。"""
    lines = []
    for name in ("market","competitor","game_design","creative_direction","proposal","eval_benchmark"):
        env = root.envelopes.get(name)
        rel = _run_rel(name)
        if env:
            lines.append(f"- runs/{root.run_id}/{rel}.json  [{env['producer']}]  parent={env['parent_hash'][:14]}…")
    return "\n".join(lines)
