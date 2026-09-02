"""demo_concept：把「策略→评估」多 Skill 协同串成一个可观测的核心玩法判断 demo。

说明（演示用途，非生产编排核心）：
- 复用能力包里的 33 个 Common Spec Skill（此处取策略组 s1/s2/s3/s6 + 预生产 director + 评估 E6）
  的领域定位，调用真实 LLM（DeepSeek，读 .env）逐个产出可读领域产物。
- 每一步把结果以 SharedState 信封写入 shared_state/<...>.json（含 parent_hash 链），
  下游 Skill 读取上游信封作为上下文——体现多 Skill 间的状态传递。
- 这与「生产引擎 Skill 步骤 → MCP 桩调用」正交；此 driver 展示的是“内容生产型 Skill 的 LLM
  编排与 SharedState 沉淀”的端到端可能，产物可被 eval / 存档 / 后续人工用。

用法：
  python -m orchestrator demo-concept --direction "想做一个探索驱动、收集符文开门、暗黑奇幻的动作游戏"
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from orchestrator.models import get_router
from orchestrator.shared_state import SharedState, hash_envelope, make_envelope


@dataclass
class ConceptRoot:
    direction: str
    # 收集每个 phase 的 envelope + 人类可读产物
    artifacts: dict  # key: "%s/json"→ dict envelope; key "%s/md"→ text (可选)


def _s(prompt: str, tier: str = "default", system: str | None = None) -> str:
    """同步调 router.complete（内部 asyncio.to_thread）。tier 固定走 default(flash) 防强档超时（demo）。

    鲁棒：调用失败/空返回时以占位符回退，不让 6 步管线中断。
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


def _phase_contract(marker: str):
    """给每个阶段一个明确的输出格式约束，便于后续解析与呈现。"""
    return (
        "\n请按以下格式输出：\n"
        "### 结论\n<一句话结论>\n"
        "### 要点\n- <要点1>\n- <要点2>（不超过 6 条，每条 ≤ 40 字）\n"
    )


def run_concept(direction: str, *, shared: SharedState | None = None) -> ConceptRoot:
    shared = shared or SharedState()
    parent = ""
    root = ConceptRoot(direction=direction, artifacts={})

    # --- Phase A 策略组 ---
    # S1 市场：给定方向 → 细分类目 + 潜在受众 / 吸引点
    mkt_prompt = (
        "你是 UE 独立游戏研发的市场分析师(S1)。\n"
        f"用户想做的方向：{direction}\n"
        "任务：一句话定位它是哪个细分赛道（dark fantasy action/adventure 类）、\
        目标用户画像、以及这个空位上最有吸引力的点；不编造具体营收/销量数字。\n"
        + _phase_contract("")
    )
    mkt_txt = _s(mkt_prompt, tier="default")
    env = shared.write("strategy/market", producer="s1_market_research",
                       payload={"market": mkt_txt}, parent_hash=parent)
    parent = hash_envelope(env)
    root.artifacts["market/json"] = env
    # --- S2 竞品（对齐市场结论）---
    comp_prompt = (
        "你是 UE 动作冒险的竞品情报(S2)。\n参考市场定位：\n" + mkt_txt +
        "\n任务：列出 2-3 个最有参考价值的对标/竞品（如 Hades2/ Tunic / God of War(2018)），\
        各给一句它证明了什么 + 一个本作可差异化空位。\n" + _phase_contract("")
    )
    comp_txt = _s(comp_prompt, tier="default")
    env = shared.write("strategy/competitor", producer="s2_competitive_intel",
                       payload={"competitor": comp_txt}, parent_hash=parent)
    parent = hash_envelope(env)
    root.artifacts["competitor/json"] = env
    # --- S3 玩法（吃掉市场+竞品）---
    gd_prompt = (
        "你是动作冒险核心玩法设计(S3)。\n市场：" + mkt_txt + "\n竞品：" + comp_txt +
        "\n任务：给出【核心循环】的一句(秒→分钟→十分钟)与一个最核心的 First-hour 目标、\
        以及一个『可证伪的最小验切口』假设。\n" + _phase_contract("")
    )
    gd_txt = _s(gd_prompt, tier="strong")
    parent_e = shared.write("strategy/game_design", producer="s3_game_design",
                            payload={"design": gd_txt}, parent_hash=parent)
    parent = hash_envelope(parent_e)
    root.artifacts["game_design/json"] = parent_e
    # --- S6 创意方向（世界观/基调）---
    cr_prompt = (
        "你是暗黑奇幻世界观与基调(S6)。设计方向：" + direction +
        "\n玩法：" + gd_txt +
        "\n任务：给一句概念钩子(一个文明被自然吞没后玩家探索/收集符文开门/发现真相，但用你自己的原创转写)、一个核心意象、一个 Tone 色板情绪方向。\n" + _phase_contract("")
    )
    cr_txt = _s(cr_prompt, tier="default")
    env = shared.write("strategy/creative_direction", producer="s6_creative_direction",
                       payload={"creative": cr_txt}, parent_hash=parent)
    parent = hash_envelope(env)
    root.artifacts["creative_direction/json"] = env
    # --- director 轻整合 成一个可评估“立项目标”摘要 ---
    dir_prompt = (
        "你是项目导演(Director)。把下面策略拼成一个 3 行的可评估 Goal(目标 + 成功判据引用玩法假设)。\n市场:\n" + mkt_txt +
        "\n竞品:\n" + comp_txt + "\n玩法:\n" + gd_txt + "\n创意:\n" + cr_txt + "\n"
    )
    dir_txt = _s(dir_prompt, tier="strong")
    env = shared.write("strategy/proposal", producer="director",
                       payload={"proposal": dir_txt, "direction": direction}, parent_hash=parent)
    parent = hash_envelope(env)
    root.artifacts["proposal/json"] = env
    # --- E6 横向基准 评估：市场可行 + 受欢迎度 + GO/NO-GO/PIVOT ---
    e6_prompt = (
        "你是面向投资/立项的横向基准评估(E6)。结合上述市场/竞品/玩法与提案，给出：\n"
        "- 受欢迎度分(0-100) 与一句话理由\n"
        "- 三个最强的差异化 axis\n"
        "- 综合裁决：GO / NO-GO / PIVOT（并一句为什么）\n"
        "提案：\n" + dir_txt +
        "\n市场:\n" + mkt_txt + "\n玩法:\n" + gd_txt
    )
    e6_txt = _s(e6_prompt, tier="strong")
    env = shared.write("eval/benchmark", producer="eval_benchmark",
                       payload={"benchmark": e6_txt}, parent_hash=parent)
    parent = hash_envelope(env)
    root.artifacts["eval/benchmark/json"] = env

    # 记录可读文本便于 CLI 输出
    root.artifacts["market/md"] = mkt_txt
    root.artifacts["competitor/md"] = comp_txt
    root.artifacts["game_design/md"] = gd_txt
    root.artifacts["creative_direction/md"] = cr_txt
    root.artifacts["proposal/md"] = dir_txt
    root.artifacts["eval/benchmark/md"] = e6_txt
    return root


def render(root: ConceptRoot) -> str:
    out = [
        f"# 核心玩法提案（方向：{root.direction}）",
        "",
        "## 1. 市场(S1)",
        root.artifacts["market/md"],
        "## 2. 竞品(S2)",
        root.artifacts["competitor/md"],
        "## 3. 玩法设计(S3)",
        root.artifacts["game_design/md"],
        "## 4. 创意方向(S6)",
        root.artifacts["creative_direction/md"],
        "## 5. 导演立项目标(Director)",
        root.artifacts["proposal/md"],
        "## 6. 横向基准评估(E6)",
        root.artifacts["eval/benchmark/md"],
        "",
        "## SharedState 落盘信封",
    ]
    for k in ("market","competitor","game_design","creative_direction","proposal","eval/benchmark"):
        env = root.artifacts[f"{k}/json"]
        out.append(f"- shared_state/{k}.json  producer={env['producer']}  hash={hash_envelope(env)[:22]}…  parent={env['parent_hash'][:18]}…")
    return "\n".join(out)
