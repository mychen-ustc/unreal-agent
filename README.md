# 项目文档索引

> **项目**：AI Agent 驱动的高品质游戏开发  
> **引擎**：Unreal Engine 5.8 LTS

---

## 文档清单

> 文档按「**为何做 → 做什么 → 怎么实现 → 何时做 → 交付形态**」组织。`ROADMAP.md` 是阶段划分与里程碑的单一事实源。

| 类别 | 文档 | 说明 | 读者 |
|---|---|---|---|
| **方向/为何做** | [project-background-and-tech-selection.md](./docs/project-background-and-tech-selection.md) | 项目背景、引擎选型决策（UE 5.8）、商业生态、AI 整合对比。供 PRD 继承上下文。 | 全员（产品、技术、商务） |
| **产品/做什么** | [ai-agent-game-dev-prd.md](./docs/ai-agent-game-dev-prd.md) | **产品需求文档**：AI 多 Agent 开发系统（产品本体）的功能需求、非功能需求、验收标准、里程碑、风险登记册。 | 产品、技术、测试 |
| **架构/结构** | [ai-agent-toolchain-architecture-unreal.md](./docs/ai-agent-toolchain-architecture-unreal.md) | **核心架构**：四层金字塔、33 个领域与评估 Agent、MCP 工具平面（12 Toolset）、PCG 策略、编排层、变更传播 DAG。编排细节与路线图指向 Harness 与 ROADMAP。 | AI 技术专家、引擎工程师 |
| **底座/运行时** | [agent-harness-selection-and-design.md](./docs/agent-harness-selection-and-design.md) | **Agent Harness/运行时底座**：能力包（MCP Server + Toolset + Common Spec Skill）为第一公民、编排核心为可选宿主；含跨宿主导入（§12）、商业交付与资产保护（§11：SaaS/私有化黑盒/引流蒸馏、Skill 分级）。 | AI 技术专家、后端工程师 |
| **实现/怎么做** | [ai-agent-game-dev-tech-design.md](./docs/ai-agent-game-dev-tech-design.md) | **技术设计**：模块划分、接口契约、数据结构、并发模型、构建/部署、可观测性、可测试性、TDR。 | 工程师（AI、UE） |
| **验证载体** | [reference-game.md](./docs/reference-game.md) | **参考游戏（验证载体）**：品类/规格/受众/内容需求/性能/验收/决策，端到端验证工具链能力。 | 产品、技术、测试 |
| **阶段规划/何时做** | [ROADMAP.md](./docs/ROADMAP.md) | **项目路线图（单一事实源）**：工程里程碑 P0–P6（主时间轴）+ 商业/资产保护里程碑 C0–C3（并行）+ UE6 远瞻 + 联动评审。 | 全员（阶段 gate） |
| **环境/启动** | [environment-setup.md](./docs/environment-setup.md) | 研发/运行环境搭建（Xcode、UE 5.8 源码版、Conda、Redis、模型凭据、Git）与本机核验清单。**启动研发前完成。** | 全员（接管环境者先读） |

> 说明：`docs/game_ideas.md` 的灵感草稿已移至 [ideas/game-ideas.md](./ideas/game-ideas.md) 归档，不作为正式设计文档。

### 启动/运维/安全/契约（`docs/ops/`）

> 这组文档是「从设计走向正式启动」的工程底座，P0 启动前逐份启用（见 [STARTUP-GATE](./docs/ops/STARTUP-GATE.md) Gate 清单）。

| 文档 | 说明 | 读者 |
|---|---|---|
| [STARTUP-GATE.md](./docs/ops/STARTUP-GATE.md) | **启动前置条件 Gate**：满足什么 = 可正式启动 P0；含「代码实现 ↔ PRD AC 现状对照」与首次提交约定。 | AI 技术专家 |
| [GOVERNANCE-OPS.md](./docs/ops/GOVERNANCE-OPS.md) | **治理运行规程**：审批 SOP、回滚 SOP、数据/备份口径、负责人矩阵。 | 全员（审批人） |
| [SECURITY-LICENSING.md](./docs/ops/SECURITY-LICENSING.md) | **安全·审计·授权计量**：审计 vs RAG 分离、License/计量标签、P0 预埋的商业钩子。 | 技术 + 产品/商务 |
| [UE-ENGINE-WORKFLOW.md](./docs/ops/UE-ENGINE-WORKFLOW.md) | **UE 引擎工作流**：UE 源码分支、引擎级定制目录、构建/发布约定。 | 引擎工程师 |
| [CONTRACTS.md](./docs/ops/CONTRACTS.md) | **契约与版本管理**：schema 版本化、破坏性变更、契约校验脚本、错误码管理。 | 工程师（AI、UE） |

---

## 阅读顺序建议

1. **方向**：[项目背景与选型](./docs/project-background-and-tech-selection.md) — 理解「为什么选 UE 5.8、要解决什么」
2. **阶段**：[项目路线图](./docs/ROADMAP.md) — 先看「分几期、每期做什么、何时到哪」
3. **产品**：[PRD](./docs/ai-agent-game-dev-prd.md) — 理解「做到什么标准」
4. **架构**：[工具链架构方案](./docs/ai-agent-toolchain-architecture-unreal.md) — 理解「系统怎么搭」
5. **底座**：[Agent Harness 选型与设计](./docs/agent-harness-selection-and-design.md) — 理解「运行时底座怎么选、怎么跨宿主、怎么商业化交付」
6. **实现**：[技术设计](./docs/ai-agent-game-dev-tech-design.md) — 理解「具体怎么实现」
7. **验证**：[参考游戏](./docs/reference-game.md) — 理解「用什么验证这套系统能做出什么」
8. **启动**：[环境准备](./docs/environment-setup.md) — 开发环境就绪后进入 P0 地基

## 当前代码进展（P0 地基 · Orchestrator 脚手架）

位于 `orchestrator/`，对齐 **Agent Harness 选型与设计 §6**（自研最小编排核心 + DurableProvider + LiteLLM，不使用第三方图框架）。

```text
orchestrator/
├── cli.py            # Typer 入口：run / plan / skills / import / approve / rollback
├── host.py           # 薄宿主：LLM/Skill 选型 + 用 DAG/调度器驱动步骤并调 MCP 工具
├── toolset_registry.py# ★ 12 个自研 Toolset 的工具注册（list_tools 事实源，能力包执行端）
├── skill.py + skills/# Common Spec Skill（scenes_pcg/lighting_setup/data_pipeline/qa_smoke 等）
├── distiller.py      # ★ 能力蒸馏（§11.3）：完整能力包 → 对外 MVP 子集（tier<=2 裁剪）
├── importers/        # ★ 跨宿主导入（§12）：蒸馏子集 → claude_code / self_hosted（codex/openclaw 待补）
├── dag.py            # ★ 自研 DAG 状态机（依赖传播/stale/回退 ≤3）
├── scheduler.py      # asyncio 调度器（拓扑 + 优先级 + 并发）
├── task_queue.py     # 优先级任务队列
├── durable/          # DurableProvider（base + local_sqlite）
├── models.py         # LiteLLM 封装 + fast/default/strong 三档路由
├── config/models.yaml# 模型映射（读 .env 的 base_url/model_name）
├── mcp_client.py     # MCP Client（唯一写入者 + 审批门 approval=prompt|auto|read_only）
├── shared_state.py   # SharedState（Git 事实源 + 信封）
├── rag.py + memory/  # LanceDB 检索骨架
└── trace.py          # JSON Lines trace（.logs/trace.jsonl）
```

**快速自检**（用已建好的 conda 环境）：
```bash
conda activate unreal-agent
python -m orchestrator --help                       # 看命令
python -m orchestrator skills                       # 列 Skill（含商业 tier/distill）
python -m orchestrator plan --task "搭玩法" --dry-run
python -m orchestrator run --task "用 PCG 生成森林"   # 选 Skill + DAG 调度其步骤 + trace
python -m orchestrator import --target self_hosted --skills scenes_pcg   # 蒸馏子集注入宿主
# 多 Skill 端到端 demo（需 .env 模型凭据、真实 LLM 约 6 次调用；共享状态写 shared_state/）：
python -m orchestrator demo-concept --direction "探索驱动、收集符文开门、暗黑奇幻、轻战斗"
# 模型路由实测（需 .env）：python -c "import asyncio; from orchestrator.models import get_router; print(asyncio.run(get_router().complete('hi', tier='fast')))"
```

**已实现（实测自检通过）**：模型路由（DeepSeek 连通）、DAG/拓扑/stale/回退、Skill 装载 + **Scheduler 按依赖驱动步骤**、Skill 商业分级（tier/distill）、**LLM/Skill 选型（失败回退关键词）**、**distiller 能力蒸馏（tier<=2）**、**importers 跨宿主导入（claude_code + self_hosted）**、**MCP Toolset Registry（12 自研 Toolset + 内容分析类，32 工具桩态可调）**、Skill 步骤->Tool 真实映射执行 + 审批门、**33 个领域/评估 Skill 全量端到端闭环自检**、SQLite Durable、SharedState 信封、CLI + trace、**真 UE5.8 MCP 会话已跑通：AC-P0-01（插件+8000+initialize/session/tools/call）与 AC-P0-06（自研 BasicSpawnToolset place→list→remove）**、**host→UeMcpBackend 真调用（ue-run）**。
**已建 Skill（33/33）**：策略组 `s1_market_research`~`s6_creative_direction` / 预生产 `director`·`concept_artist`·`level_designer`·`narrative_writer`·`data_pipeline`·`system_designer` / 生产 `scenes_pcg`·`lighting_setup`·`audio_setup`·`ui_setup`·`asset_retriever`·`asset3d_generator`·`gameplay_dev`·`technical_artist`·`player_character_design`·`enemy_boss_design`·`animation_design` / 验证 `profiler_skill`·`qa_smoke`·`build_agent` / 评估 `eval_*`×6 + `playtest_researcher`——均含 Common Spec（skill.yaml 商业 tier/distill + steps.yaml 工具映射 + prompt.md），全部可被 host 装载执行并跑端到端闭环。
**真引擎命令**（需编辑器在线）：`python -m orchestrator ue-p0`（AC-P0-06 place→list→remove）；`ue-run --skill ue_basicspawn_smoke`（host→UeMcpBackend 真调 UE）；详见 docs/ops/UE-ENGINE-WORKFLOW §3.1。
**待后续（完整游戏开发前置）**：真引擎审批/回滚/沙箱（AC-P0-03/04/05）、LanceDB 真实检索、importers 补 codex/openclaw/hermes。说明：全部 33 个 Skill 的 prompt.md 已细化为领域质量中文 prompt，供第三方宿主注入与 debug 使用。

---

## 文档规范

- 所有文档使用 **Markdown** 格式（`.md`），便于 Git 版本管理和 diff
- 架构图使用 **Mermaid** 语法，支持 GitHub / 多数 Markdown 渲染器
- 中文为主，关键术语保留英文缩写（见架构文档术语表）
- 文件名使用 **kebab-case**，不含空格（历史文件保留 Pascal_Snake 命名，新增文件统一 kebab-case）
- **docs 根目录**放「方向/产品/架构/底座/实现/验证/阶段/环境」八份主文档；**docs/ops/** 放「启动/运维/安全/契约/UE 协作」这批工程底座文档；`ideas/` 为灵感归档（不纳入 git，见 `.gitignore`）

---

*维护者：AI 技术专家 · 最后更新：2026*