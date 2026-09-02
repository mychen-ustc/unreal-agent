"""薄宿主：接收指令，解析并调度对应 Skill（Harness §6.1）。

职责：输入自然语言指令 → 选出 Skill（P0 用简单映射；P1 由宿主 Agent/RAG 选型）
→ 用自研 DAG 驱动 Skill 内部步骤。
"""
from __future__ import annotations

import asyncio
import logging

from orchestrator.dag import DagEngine, DagNode
from orchestrator.models import ModelRouter
from orchestrator.mcp_client import McpClient
from orchestrator.scheduler import Scheduler
from orchestrator.skill import SkillRegistry
from orchestrator.trace import TraceWriter

log = logging.getLogger(__name__)

# P0:关键词兜底映射（LLM 选型不可用/失败时回退）
_KEYWORD_MAP = {
    # 场景/PCG
    "pcg": "scenes_pcg", "场景": "scenes_pcg", "地形": "scenes_pcg", "森林": "scenes_pcg", "level": "scenes_pcg",
    "生成地图": "scenes_pcg",
    # 灯光
    "灯光": "lighting_setup", "光照": "lighting_setup", "布光": "lighting_setup", "postprocess": "lighting_setup",
    # 数据/数值落地
    "csv": "data_pipeline", "datatable": "data_pipeline", "data": "data_pipeline",
    # QA 冒烟
    "冒烟": "qa_smoke", "smoke": "qa_smoke", "可玩性测试": "qa_smoke",
    # 策略：市场调研
    "market": "s1_market_research", "市场 ": "s1_market_research", "市场调研": "s1_market_research", "受众": "s1_market_research",
    # 竞品
    "竞品": "s2_competitive_intel", "competitor": "s2_competitive_intel",
    # 玩法设计
    "玩法": "s3_game_design", "核心玩法": "s3_game_design", "game design": "s3_game_design",
    # 商业
    "商业": "s4_business_strategy", "定价": "s4_business_strategy", "monetization": "s4_business_strategy",
    # 技术可行性
    "可行性": "s5_tech_feasibility", "tech 评估": "s5_tech_feasibility",
    # 创意/世界观
    "世界观": "s6_creative_direction", "创意方向": "s6_creative_direction", "情绪板": "s6_creative_direction",
    # 预生产
    "gdd": "director", "导演": "director",
    "风格指南": "concept_artist", "concept": "concept_artist",
    "关卡设计": "level_designer", "动线": "level_designer", "blockout": "level_designer",
    "叙事": "narrative_writer", "剧情": "narrative_writer", "对白": "narrative_writer", "文案": "narrative_writer",
    "数值设计": "system_designer", "系统设计": "system_designer", "经济": "system_designer",
    # 生产
    "资产": "asset_retriever", "fab": "asset_retriever", "检索": "asset_retriever",
    "生成3d": "asset3d_generator", "生成纹理": "asset3d_generator", "模型生成": "asset3d_generator",
    "玩法实现": "gameplay_dev", "代码": "gameplay_dev", "verse": "gameplay_dev", "cpp": "gameplay_dev",
    "音效": "audio_setup", "音频": "audio_setup", "环境音": "audio_setup",
    "ui": "ui_setup", "hud": "ui_setup", "界面": "ui_setup",
    "材质": "technical_artist", "渲染": "technical_artist", "技术美术": "technical_artist",
    "角色": "player_character_design", "手感": "player_character_design",
    "敌人": "enemy_boss_design", "boss": "enemy_boss_design", "怪物": "enemy_boss_design",
    "动画": "animation_design", "动作": "animation_design",
    # 验证
    "性能": "profiler_skill", "帧率": "profiler_skill", "profiler": "profiler_skill",
    "打包": "build_agent", "cook": "build_agent",
    # 评估
    "体验评估": "eval_experience", "节奏批判": "eval_experience",
    "美术评估": "eval_content",
    "可玩评估": "eval_gameplay_fun", "手感评估": "eval_gameplay_fun",
    "经济批判": "eval_design_economy",
    "商业化评估": "eval_monetization",
    "横评": "eval_benchmark", "对比评测": "eval_benchmark", "竞品对比": "eval_benchmark",
    "横向对比": "eval_benchmark", "横向": "eval_benchmark", "对拍": "eval_benchmark",
    "玩家研究": "playtest_researcher",
}


class Host:
    def __init__(
        self,
        mcp: McpClient,
        router: ModelRouter | None = None,
        trace: TraceWriter | None = None,
        registry: SkillRegistry | None = None,
        use_llm_select: bool = True,
        step_param_provider=None,
    ) -> None:
        self.mcp = mcp
        self.router = router or ModelRouter()
        self.trace = trace or TraceWriter()
        self.registry = registry or SkillRegistry()
        # LLM 选型开关：默认开；失败自动回退关键词（保证 stub/离线可用）
        self.use_llm_select = use_llm_select
        # step_param_provider(node, base_args) -> dict：可选，为 Skill 步骤注入动态工具参数
        self.step_param_provider = step_param_provider

    def _keyword_fallback(self, instruction: str) -> str:
        low = instruction.lower()
        for kw, skill in _KEYWORD_MAP.items():
            if kw in low:
                return skill
        names = self.registry.discover()
        # 未命中明确领域：优先落到综合入口 director（能把任务细分），其次取第一个可用 skill
        return "director" if "director" in names else (names[0] if names else "general")

    def select_skill(self, instruction: str) -> str:
        """从已装载 Skill 中选出最适合指令的名称。

        优先走 LLM（fast 档）做语义选型；失败/禁用时回退关键词匹配。
        """
        names = self.registry.discover()
        if not names:
            raise RuntimeError("Skills 目录为空，无法选型")
        if not self.use_llm_select:
            return self._keyword_fallback(instruction)
        try:
            return self._select_by_llm(instruction, names)
        except Exception as exc:  # noqa: BLE001
            log.warning("LLM 选型失败，回退关键词: %s", exc)
            return self._keyword_fallback(instruction)

    def _select_by_llm(self, instruction: str, names: list[str]) -> str:
        """让 LLM 从 names 中选最匹配指令的 Skill（要求只输出一个已知 name）。"""
        allowed = ", ".join(names)
        prompt = (
            "你是 UE 研发管线宿主的 Skill 选型器。\n"
            f"可用 Skill：{allowed}\n"
            f"用户指令：{instruction}\n"
            "请只输出一个最匹配的 Skill 名称（必须是上面列表之一，不要解释）。"
        )
        text = asyncio.run(self.router.complete(prompt, tier="fast")).strip()
        # 限定返回必须在已知 Skill 内（防 LLM 幻觉输出不属于任何 Skill 的名字）
        for n in names:
            if n in text:
                return n
        return self._keyword_fallback(instruction)

    def run(self, instruction: str, skill_name: str | None = None) -> dict:
        """执行一次宿主指令：装载 Skill → 用自研 DAG/调度器驱动其内部步骤。

        P0：把 Skill 的 `steps` 构造成 DagEngine，由 Scheduler 按拓扑 + 依赖 + 并发执行
        （每个步骤经 MCP 唯一写入者调用工具并 trace）。
        """
        name = skill_name or self.select_skill(instruction)
        self.trace.agent_event("host", "select_skill", {"skill": name, "instruction": instruction})

        skill = self.registry.load(name)
        spec = skill.spec
        log.info("执行 Skill=%s (model_tier=%s, biz_tier=%d, distill=%s, risk=%s, steps=%d)",
                 spec.name, spec.default_tier, spec.tier, spec.distill_visibility,
                 spec.risk, len(spec.steps))

        # 把 Skill 内部 steps 构造成 DAG（节点即步骤，依赖来自 steps.yaml）
        dag = DagEngine()
        for step in spec.steps:
            dag.add_node(DagNode(
                task_id=f"{spec.name}:{step.id}",
                producer=f"skill/{spec.name}",
                skill=spec.name,
                step=step.id,
                tier=step.tier,
                severity=step.severity,
                partition=step.partition,
                priority=step.priority,
                shared_state_refs=step.shared_state_refs,
            ))
        # 依赖边（steps.yaml 的 dependencies 引用步骤 id）
        id_to_task = {s.id: f"{spec.name}:{s.id}" for s in spec.steps}
        for step in spec.steps:
            for dep in step.dependencies:
                if dep in id_to_task:
                    dag.add_edge(id_to_task[dep], id_to_task[step.id])
                else:
                    log.warning("Skill %s 步骤 %s 的依赖 %s 未定义，跳过", spec.name, step.id, dep)

        async def runner(task_id: str) -> None:
            node = dag.nodes[task_id]
            step = _find_step(spec.steps, node.step)
            tool_name = (step.tool if step else "") or _first_whitelist_tool(spec)
            self.trace.tool_call(
                tool=f"skill:{node.skill}:{node.step}",
                args={"instruction": instruction, "tool": tool_name},
                outcome={"tier": node.tier, "severity": node.severity},
                producer=node.producer,
            )
            if tool_name:
                # 经 MCP 唯一写入者真实调用工具（桩态记录 + 审批门；真 UE 走 HTTP）
                args = dict(step.tool_args) if step else {}
                if self.step_param_provider:
                    args = {**args, **(self.step_param_provider(node, args) or {})}
                res = self.mcp.call_tool(tool_name, args, risk=node.severity,
                                         metadata={"skill": node.skill, "step": node.step})
                log.info("步骤 %s → tool %s: ok=%s code=%s", node.step, tool_name, res.ok, res.error_code)
                if not res.ok:
                    raise RuntimeError(f"tool {tool_name} 失败: {res.error_code} {res.detail}")
            else:
                log.warning("步骤 %s 未声明 tool 且无白名单工具，跳过真实调用", node.step)

        scheduler = Scheduler(dag=dag, runner=runner, max_concurrent=len(spec.steps))
        executed = asyncio.run(scheduler.run())
        return {"skill": name, "steps_executed": executed, "steps": [s.id for s in spec.steps]}


def _find_step(steps, step_id):
    """在 SkillSpec.steps 里按 id 找步骤；找不到返回 None。"""
    for s in steps:
        if s.id == step_id:
            return s
    return None


def _first_whitelist_tool(spec) -> str:
    """取 tool_whitelist 的第一个工具（供未声明 tool 的步骤兜底）。"""
    return spec.tool_whitelist[0] if spec.tool_whitelist else ""
