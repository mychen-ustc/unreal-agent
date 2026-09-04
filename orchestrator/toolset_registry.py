"""Toolset Registry：12 个自研 Toolset 的结构化注册（对齐 TechDesign §4.1）。

本模块是「能力包 → 工具」在编码侧的事实源：它登记每个自研 Toolset 及其代表性工具
（name / description / risk / 所属 toolset / 输入提示）。

用途：
- MCP StubTransport 以此为桩：`list_tools` 返回全量工具（可在无 UE 时验证工具发现与 schema）。
- Skill 的 `tool_whitelist` / `steps[].tool` 引用这里登记的工具名，供执行前静态校验。
- 将来升级为真 UE 时，这里与 UE 侧 `ToolsetRegistry` 插件的反射 schema 对齐（可 diff）。

P0 每 Toolset 先登记最关键的「代表性工具」；完整工具面随 Skill / 关卡推进补全。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# 风险分级与 mcp_client.RiskLevel 一致
READ_ONLY = "read_only"
MUTATING = "mutating"
DESTRUCTIVE = "destructive"


@dataclass(frozen=True)
class ToolMeta:
    """一个 MCP 工具的定义。"""

    name: str
    description: str
    risk: str                    # read_only | mutating | destructive
    toolset: str                 # 所属 toolset 名，如 "PCGToolset"
    schema: dict = field(default_factory=dict)   # JSON Schema 输入提示（可空）

    def as_dict(self) -> dict:
        d: dict[str, Any] = {"name": self.name, "description": self.description, "risk": self.risk, "toolset": self.toolset}
        if self.schema:
            d["inputSchema"] = self.schema
        return d


# ---- 各 Toolset 的工具定义（对齐 TechDesign §4.1 关键工具） ----

_PROJECT_TOOLS = [
    ToolMeta("project_check_naming", "校验目录/资产命名是否符合项目规范", READ_ONLY, "ProjectToolset"),
    ToolMeta("project_list_directory", "列出指定目录内容（只读）", READ_ONLY, "ProjectToolset"),
]
_SAFEGUARD_TOOLS = [
    ToolMeta("safeguard_check_path", "检查路径是否允许写入（沙箱白名单）", READ_ONLY, "SafeguardToolset"),
    ToolMeta("safeguard_request_approval", "为破坏性操作请求人工审批", MUTATING, "SafeguardToolset"),
]
_PCG_TOOLS = [
    ToolMeta("pcg_generate_graph", "按 JSON 规格生成/修改 PCG Graph 资产", MUTATING, "PCGToolset",
             {"type": "object", "properties": {"biome": {"type": "string"}, "graph_path": {"type": "string"}}}),
    ToolMeta("pcg_validate", "校验 PCG 图合法性", READ_ONLY, "PCGToolset"),
    ToolMeta("pcg_run_async", "异步触发生成并返回 job_id（长任务）", MUTATING, "PCGToolset"),
]
_ARTPIPELINE_TOOLS = [
    ToolMeta("art_import_mesh", "导入外部生成的 mesh 到 /Game/Generated/Assets/", MUTATING, "ArtPipelineToolset"),
    ToolMeta("art_configure_nanite", "为网格开启 Nanite 虚拟几何体", MUTATING, "ArtPipelineToolset"),
]
_BUILD_TOOLS = [
    ToolMeta("build_live_coding", "编译代码（Live Coding）", MUTATING, "BuildToolset"),
    ToolMeta("build_run_pie_tests", "启动 PIE 跑自动化测试，返回通过/失败+截图", MUTATING, "BuildToolset"),
    ToolMeta("build_cook_run", "打平台包（UBT cook/run，destructive 人工审批）", DESTRUCTIVE, "BuildToolset"),
]
_LIGHTING_TOOLS = [
    ToolMeta("lighting_place_directional", "放置 Directional Light", MUTATING, "LightingToolset"),
    ToolMeta("lighting_set_postprocess", "配置 PostProcess Volume", MUTATING, "LightingToolset"),
]
_AUDIO_TOOLS = [
    ToolMeta("audio_place_ambient", "放置环境音", MUTATING, "AudioToolset"),
    ToolMeta("audio_create_sound_cue", "创建 Sound Cue", MUTATING, "AudioToolset"),
]
_UI_TOOLS = [
    ToolMeta("ui_create_umg_widget", "生成/修改 UMG Widget", MUTATING, "UIToolset"),
]
_DATA_TOOLS = [
    ToolMeta("data_csv_to_datatable", "导入 CSV 生成 DataTable", MUTATING, "DataToolset"),
    ToolMeta("data_validate_rows", "校验 DataTable 行", READ_ONLY, "DataToolset"),
]
_PROFILER_TOOLS = [
    ToolMeta("profiler_report", "生成性能超标报告", READ_ONLY, "ProfilerToolset"),
]
_PLAYTEST_TOOLS = [
    ToolMeta("playtest_smoke", "自动走通 spawn→collect→open 最小路径（可玩性冒烟）", MUTATING, "PlaytestToolset"),
]
_BENCHMARK_TOOLS = [
    ToolMeta("benchmark_align", "把本游产物与竞品某维度对齐打分", READ_ONLY, "BenchmarkToolset"),
]


# 内容生产 / 分析 / 评估 类工具（供策略 S1–S6、预生产 W1/ND、评估 E1–E6 等非引擎执行型 Skill 步骤落点）
_ANALYSIS_GENERATION_TOOLS = [
    ToolMeta("rag_search", "检索 UE 文档/项目规范/已验证产物（RAG getrounding）", READ_ONLY, "AnalysisToolset"),
    ToolMeta("rag_ingest", "把已验证片段/决策写入长期记忆（LanceDB）", MUTATING, "AnalysisToolset"),
    ToolMeta("report_write", "把结构化方案/提案/报告写入 shared_state/（如 /strategy/）", MUTATING, "AnalysisToolset"),
    ToolMeta("eval_submit", "把评估结论写入 /eval/*（评估 Skill 的唯一写口）", MUTATING, "AnalysisToolset"),
    ToolMeta("image_concept", "生成概念/参考图（图像 API，供概念/角色/敌人方向）", MUTATING, "AnalysisToolset"),
    ToolMeta("asset_generate_3d", "外部 3D/纹理生成入口（风格约束下）", MUTATING, "AnalysisToolset"),
    ToolMeta("table_design", "产出数值/经济/Datatable 规格草稿（System Designer 用）", MUTATING, "AnalysisToolset"),
]


# 通用（不做 Toolset 归属，供脚手架）：
_GENERIC_TOOLS = [
    ToolMeta("list_tools", "列出全部工具及 JSON Schema", READ_ONLY, "Registry"),
    ToolMeta("git_commit", "mutating 后自动 commit（post-tool hook）", MUTATING, "Registry"),
    ToolMeta("place_actor", "在关卡中放置一个 Actor（AC-P0-06 最小闭环）", MUTATING, "Registry"),
    # UE BasicSpawnToolset 别名（真调用仅经 UeMcpBackend 到 UE；offline 时由 Stub 占位）
    ToolMeta("place_cube", "[UE alias→BasicSpawn.place_cube] 放置底层立方体", MUTATING, "Registry"),
    ToolMeta("list_agent_cubes", "[UE alias→BasicSpawn.list_agent_cubes] 列出 agent 立方体", READ_ONLY, "Registry"),
    ToolMeta("remove_cube", "[UE alias→BasicSpawn.remove_cube] 移除按 label 立方体", MUTATING, "Registry"),
]


# ---- 聚合与查询 ----

# 12 个自研 Toolset 的工具（不含通用）
TWELVE_TOOLSET_TOOLS: list[ToolMeta] = (
    _PROJECT_TOOLS + _SAFEGUARD_TOOLS + _PCG_TOOLS + _ARTPIPELINE_TOOLS
    + _BUILD_TOOLS + _LIGHTING_TOOLS + _AUDIO_TOOLS + _UI_TOOLS
    + _DATA_TOOLS + _PROFILER_TOOLS + _PLAYTEST_TOOLS + _BENCHMARK_TOOLS
)

# 完整工具清单（12 个自研 Toolset + 内容生产/分析类 + 通用脚手架工具）
ALL_TOOLS: list[ToolMeta] = (
    TWELVE_TOOLSET_TOOLS + _ANALYSIS_GENERATION_TOOLS + _GENERIC_TOOLS
)

_TOOLS_BY_NAME: dict[str, ToolMeta] = {t.name: t for t in ALL_TOOLS}


def get_tool_meta(name: str) -> Optional[ToolMeta]:
    """按工具名取元数据；未知返回 None。"""
    return _TOOLS_BY_NAME.get(name)


def toolset_names() -> list[str]:
    """12 个自研 Toolset 名。"""
    names = []
    for t in TWELVE_TOOLSET_TOOLS:
        if t.toolset not in names:
            names.append(t.toolset)
    return sorted(names)


def list_tools_dict() -> list[dict]:
    """供 MCP list_tools 返回的结构化清单。"""
    return [t.as_dict() for t in ALL_TOOLS]
