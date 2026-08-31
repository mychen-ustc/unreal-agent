# 项目文档索引

> **项目**：AI Agent 驱动的高品质游戏开发  
> **引擎**：Unreal Engine 5.8 LTS

---

## 文档清单

| 文档 | 说明 | 读者 |
|---|---|---|
| [project-background-and-tech-selection.md](./docs/project-background-and-tech-selection.md) | 项目背景、引擎选型决策、商业生态分析、AI 整合对比。供 PRD 继承上下文。 | 全员（产品、技术、商务） |
| [AI_Agent_Toolchain_Architecture-unreal.md](./docs/AI_Agent_Toolchain_Architecture-unreal.md) | **核心架构文档**：四层金字塔设计、33 个领域与评估 Agent、MCP 工具平面（12 Toolset）、PCG 策略、编排层、变更传播 DAG、落地路线图。 | AI 技术专家、引擎工程师 |
| [agent-harness-selection-and-design.md](./docs/agent-harness-selection-and-design.md) | **Agent Harness（编排/运行时底座）选型与技术设计**：剔除 LangGraph，自研最小编排核心 + Durable Execution 外挂 + LiteLLM；含 SaaS/多租户长期演进路线。TechDesign 编排选型的唯一事实源。 | AI 技术专家、后端工程师 |
| [environment-setup.md](./docs/environment-setup.md) | **环境准备指南**：研发/运行环境搭建（Xcode、UE 5.8、Conda+依赖、Redis、模型凭据、Git）与本机差异核验清单。**启动研发前完成。** | 全员（接管环境者先读） |
| [AI_Agent_Game_Dev_PRD.md](./docs/AI_Agent_Game_Dev_PRD.md) | **产品需求文档**：AI 多 Agent 开发系统（产品本体）的功能需求、非功能性需求、验收标准、里程碑、风险登记册；聚焦多 Agent 系统本身，参考游戏详情报单独文档。 | 全员（产品、技术、测试） |
| [reference-game.md](./docs/reference-game.md) | **参考游戏文档（验证载体）**：参考游戏的品类选型、规格、受众、内容需求、性能与验收标准、相关产品决策。由 PRD 引用维护，避免稀释产品本体聚焦。 | 产品、技术、测试 |
| [AI_Agent_Game_Dev_TechDesign.md](./docs/AI_Agent_Game_Dev_TechDesign.md) | **技术设计文档**：PRD 的技术落地层——模块划分、接口契约、数据结构、并发模型、构建/部署、可观测性、可测试性、TDR。 | 工程师（AI、UE） |

---

## 阅读顺序建议

1. **先读** [项目背景与选型](./docs/project-background-and-tech-selection.md) — 理解「为什么选 UE 5.8」
2. **再读** [工具链架构方案](./docs/AI_Agent_Toolchain_Architecture-unreal.md) — 理解「怎么做」
3. **然后读** [PRD](./docs/AI_Agent_Game_Dev_PRD.md) — 理解「做到什么标准」
4. **接着读** [技术设计](./docs/AI_Agent_Game_Dev_TechDesign.md) — 理解「具体怎么实现」
5. **最后读** [Agent Harness 选型与技术设计](./docs/agent-harness-selection-and-design.md) — 理解「编排/运行时底座怎么选、怎么落地、如何演进 SaaS/多租户」

## 当前代码进展（P0 地基 · Orchestrator 脚手架）

位于 `orchestrator/`，对齐 **Agent Harness 选型与设计 §6**（自研最小编排核心 + DurableProvider + LiteLLM，不使用第三方图框架）。

```text
orchestrator/
├── cli.py            # Typer 入口：run / plan / approve / rollback / skills
├── host.py           # 薄宿主：选 Skill 并调度
├── skill.py + skills/# Skill 封装（scenes_pcg 为示例）
├── dag.py            # ★ 自研 DAG 状态机（依赖传播/stale/回退 ≤3）
├── scheduler.py      # asyncio 调度器（拓扑 + 优先级）
├── task_queue.py     # 优先级任务队列
├── durable/          # DurableProvider（base + local_sqlite）
├── models.py         # LiteLLM 封装 + fast/default/strong 三档路由
├── config/models.yaml# 模型映射（读 .env 的 base_url/model_name）
├── mcp_client.py     # MCP Client（唯一写入者 + 审批门）
├── shared_state.py   # SharedState（Git 事实源 + 信封）
├── rag.py + memory/  # LanceDB 检索骨架
└── trace.py          # JSON Lines trace（.logs/trace.jsonl）
```

**快速自检**（用已建好的 conda 环境）：
```bash
conda activate unreal-agent
python -m orchestrator --help                       # 看命令
python -m orchestrator skills                       # 列 Skill
python -m orchestrator plan --task "搭玩法" --dry-run
python -m orchestrator run --task "用 PCG 生成森林"   # 自动选 Skill + DAG 步骤 + trace
# 模型路由实测（需 .env）：python -c "import asyncio; from orchestrator.models import get_router; print(asyncio.run(get_router().complete('hi', tier='fast')))"
```

**已实现（实测自检通过）**：模型路由（DeepSeek 连通）、DAG/拓扑/stale/回退、Skill 装载与步骤调度、MCP 桩 + 审批门、SQLite Durable、SharedState 信封、CLI + trace。
**待后续**：连真 UE 的 MCP（`--no-stub` + `--endpoint`）、Skill 自动选型上 LLM/RAG、scheduler 并发接入、其余 32 个 Skill、LanceDB 真实检索。

---

## 文档规范

- 所有文档使用 **Markdown** 格式（`.md`），便于 Git 版本管理和 diff
- 架构图使用 **Mermaid** 语法，支持 GitHub / 多数 Markdown 渲染器
- 中文为主，关键术语保留英文缩写（见架构文档术语表）
- 文件名使用 **kebab-case**，不含空格（历史文件保留 Pascal_Snake 命名，新增文件统一 kebab-case）

---

*维护者：AI 技术专家 · 最后更新：2026*