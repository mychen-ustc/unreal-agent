# Agent Harness（Agent 运行时底座）选型与技术设计

项目代号：AI Agent 驱动的高品质游戏开发
关联 PRD：[AI_Agent_Game_Dev_PRD.md](./AI_Agent_Game_Dev_PRD.md)（v0.2）
关联技术设计：[AI_Agent_Game_Dev_TechDesign.md](./AI_Agent_Game_Dev_TechDesign.md)（§2.3 / §6 / §13）
关联架构：[AI_Agent_Toolchain_Architecture-unreal.md](./AI_Agent_Toolchain_Architecture-unreal.md)（§1 四层 · §6 编排层）
状态：**定稿（v1.1）**

> **本文档的定位**：**Agent Harness（编排 / Agent 运行时）选型的权威依据与落地文档**。面向本项目「框架可替换 + 源码可控 + 单写入者 + 支撑 SaaS / 多租户长期演进」的约束，规定：
> - **范式**：核心能力封装为 **Skill / 插件**（与 Claude Code / Codex / DeepSeek Harness 等业界主流同构），由宿主 Agent 调度，而非常驻 sub-agent 网络（§1.1）；
> - **底座**：**自研最小编排核心**（作为 Skill 的执行引擎）+ **可选 Durable Execution 外挂** + **LiteLLM**；
> - **商业化**：支持「Skill 注入第三方宿主」与「薄宿主托管 SaaS / 多租户」双路径（§9）。
> 本文档是**该选型的唯一事实源**（Single Source of Truth），TechDesign 相关章节以其为准并交叉引用。

---

## 目录

- [1. 背景与决策结论](#1-背景与决策结论)
- [2. 本项目对 Agent 底座的真实约束](#2-本项目对-agent-底座的真实约束)
- [3. 编排框架候选评估与排除依据](#3-编排框架候选评估与排除依据)
- [4. 候选底座调研与对比](#4-候选底座调研与对比)
- [5. 定稿选型：自研最小编排核心 + 可选 Durable Execution 引擎](#5-定稿选型自研最小编排核心--可选-durable-execution-引擎)
- [6. 技术设计：自研 Harness 的架构与模块](#6-技术设计自研-harness-的架构与模块)
- [7. 任务执行模型（同步 / 长任务两阶段）](#7-任务执行模型同步--长任务两阶段)
- [8. 与现有栈的对齐（SharedState / MCP / 记忆 / 模型）](#8-与现有栈的对齐sharedstatemcp--记忆--模型)
- [9. SaaS 化与多租户（对标 Manus 等业界 Agent 平台）](#9-saas-化与多租户对标-manus-等业界-agent-平台)
- [10. 演进路线与替换策略](#10-演进路线与替换策略)
- [11. 技术决策记录（TDR-Harness）](#11-技术决策记录tdr-harness)
- [参考依据](#参考依据)

---

## 1. 背景与决策结论

本项目 Agent Harness 的编排与运行时底座定义为：

> **定稿底座 = 自研「最小编排核心」（Minimal Orchestration Core）+ 可选的 Durable Execution 引擎（Temporal / 轻量版 Prefect）作为外挂长任务恢复层 + LiteLLM 统一模型接口 + asyncio 运行时。**

设计原则：**不把「Agent 图」绑定在某个第三方图框架上，而是把「图/状态机/回退」这层自研（为核心 IP），把「长任务能否断点续跑」这层交给成熟引擎。**

| 维度 | 定稿 |
|---|---|
| Agent 运行时 | **Python 3.11+，asyncio** |
| **编排/图（核心）** | **自研** `orchestrator/dag.py` 状态机 + 依赖传播 + stale + 回退 |
| **长任务恢复** | **可选外挂 Durable Execution 引擎**（默认 Temporal；轻量单机场景可退化为 Prefect 或内置 SQLite checkpoint） |
| **模型路由** | **LiteLLM**（统一三档模型，`fast/default/strong`） |
| **MCP 客户端** | `mcp` Python SDK（官方，唯一写入者） |

> **选型边界**：本项目不采用任何「Agent 图框架」（如 OpenAI AgentKit / Claude Agent SDK / LangGraph）作为编排底座——原因见 §4 候选对比。此类框架要么长任务持久化能力不足，要么引入供应商锁定，均不符合本项目「框架可替换 + 源码可控 + 单写入者 + 多租户演进」的约束。正确设计是把"图编排"收归自研、把"持久化"外挂成熟引擎。

### 1.1 范式定位：Skill / 插件体系（与主流 Agent Harness 同构）

本项目 Agent 的构成遵循业界主流 Agent Harness（Claude Code / Codex / DeepSeek Harness 等）的范式：**核心能力封装为 Skill / 插件，由宿主 Agent 按需调用，而不是做成常驻的 sub-agent 网络。**

| 范式维度 | 业界主流（Claude Code / Codex / DeepSeek Harness） | 本项目 |
|---|---|---|
| **交互单位** | 宿主 Agent（用户直接对话）+ Skill 库 | 宿主 Agent（用户自有的 Harness 或本项目薄宿主）+ Skill 库 |
| **领域能力** | 封装成 Skill / 插件（输入 schema + 提示词策略 + 工具集） | 封装成 Skill / 插件（领域 Agent 的能力沉淀为可复用 Skill） |
| **子 Agent** | 一般不暴露常驻 sub-agent；需要时做临时角色/工具 | 不暴露常驻 sub-agent 网络；领域职能以 Skill 形式提供 |
| **编排** | 宿主自主决策 + Skill 内部多步骤 | 宿主决策调度 Skill；**Skill 内部的步骤/回退由自研最小编排核心驱动（§5/§6）** |

**关键澄清**：项目文档中的 **33 个领域 / 评估"Agent"在本范式中对应"33 个领域 Skill"**——它们在概念上仍是"某领域由谁负责"的角色，但**调用模型不是"33 个平级 sub-agent 互相调 tool"，而是"宿主 Agent 按任务调度对应 Skill"**。SharedState 路径仍按领域组织（`shared_state/<skill>/...`），语义不变。

这对底座选型有两个直接推论：
1. **编排核心的真实角色是"Skill 的执行引擎"**：驱动一个 Skill 内部的多步骤、依赖、回退与长任务，而非在 33 个 sub-agent 间做全局总编排。这让自研最小编排核心更加合理——它是每个 Skill 的轻量运行器，薄、全掌控。
2. **产品形态支持双路径**：底层能力沉淀为 Skill 库后，(a) 可被用户自有的 Claude Code / Codex / DeepSeek Harness 直接调用（Skill 注入 / MCP 服务），或 (b) 由本项目提供轻量宿主 + 托管 UE 执行服务，支持独立 SaaS / 多租户化（§9）。两者共用同一套 Skill 与编排核心。

> 本节确立**Skill / 插件范式为主范本**；以下 §2–§11 的约束、选型、技术设计均在此范式下展开。

---

## 2. 本项目对 Agent 底座的真实约束

在选型前，先把约束说透——这些是本项目与"聊天式多 Agent demo"的本质差异：

| 约束 | 说明 | 对底座的影响 |
|---|---|---|
| **C1 单写入者 + 空间分区** | 唯一 MCP 写入者，多 Agent 按坐标分区 | 不需要框架内置的"协作协议/tool-use 自动分发"；**需要的只有串行调度 + 资源归属锁**，自研即可 |
| **C2 长任务很多且带外部副作用** | PCG 生成（<60s~几分钟）、全量编译（50–70min）、PIE 测试 | 底座必须解决**断点续跑 / 崩溃后恢复 / 不重复触发外部副作用**（durable execution）——这是 LangGraph 的短板 |
| **C3 图语义（依赖传播/stale/回退≤3）是核心 IP** | 自研 DAG 引擎定义好了 | 框架 layer 越厚越碍事；**薄**才好 |
| **C4 模型/框架/向量库全可替换** | TDR-009/010、TechDesign §12 | 底座不能引入强厂商锁定 |
| **C5 源码可控 + 小团队 + UE6 迁移** | 长期演进、复用 ≥80% | 底座应稳定、API 不频繁破坏、可本地化 |
| **C6 Python 单机优先** | Python 3.11+，asyncio | 分布式是远期扩展，底座须先满足单机可跑通 |
| **C7 支撑 SaaS / 多租户 / 订阅长期演进** | 未来以 SaaS 订阅 + 多租户协作商业化（对标 Manus 等） | 底座不能绑定厂商 Agent 平台；需支持多租户隔离、配额计费、弹性扩展的长远路径（详见 §9） |

**结论**：本项目需要的底座**不是"Agents framework"**（那解决"让 agent 互相聊天/自动调 tool"），而是**一个薄的状态机编排核心 + 一个靠得住的持久化执行引擎**。业界 2025–2026 的趋势也印证这一点：图框架（LangGraph）的短板正由 **durable execution 引擎（Temporal 等）以 plugin 形式补上**（见参考依据）。与其在 LangGraph 上蹭 Temporal 的 plugin，不如直接自研薄层 + 直连 durable 引擎。

---

## 3. 编排框架候选评估与排除依据

对 LangGraph 作为本项目编排底座的适配性评估如下。针对本项目约束（§2 C1–C7），LangGraph 有四个不满足项，故不采用：

### 3.1 长任务持久化能力不足，需在框架之外重造执行恢复层

LangGraph 的 Checkpoint 语义无法覆盖 UE 长任务场景（PCG 生成 / 全量编译 / PIE 测试，耗时数十秒至数十分钟）。其单次图推演本质是同步步进，对"一个节点阻塞再返回"的恢复依靠 Checkpoint + 程序重放；而 UE 长任务带真实外部副作用（资产已生成），重放会产生重复副作用，需额外引入「两阶段节点 + 外部任务句柄 + AsyncJobRegistry」自行实现恢复——即需要在框架之上重造一层执行恢复能力，且仅覆盖部分场景。这不符合 §2 C2/C5 对"成熟、不重复触发、经得起长周期"的要求。

### 3.2 API 稳定性是长期最大风险

LangGraph 2022 年发布后，`langgraph` 包在 2024–2025 经历多次非向后兼容重构。对本项目"小团队 + 跑多年 + UE6 迁移"的长周期，**框架频繁 breaking change 会让维护成本持续漏血**。虽然文档把编排语义封在 `dag.py`（正确），但该适配层的维护成本明显高于更稳的框架。

### 3.3 厂商引力与生态重心

LangGraph 商业重心明显倾向 **LangGraph Platform / LangSmith**，分布式 Checkpoint 依赖 LangSmith key。与本项目"本地化、源码掌控、单写入者"持续摩擦。

### 3.4 与"自研 DAG 语义是核心 IP"冲突

本项目 90% 的编排价值在自研的依赖传播/stale/回退/空间分区，LangGraph 只提供 StateGraph 原语——**它带来的加速度明显小于其 3.1–3.3 的成本**。用更薄的方案获取等价的图编排能力，代价更可控。

> **评估结论**：LangGraph 作为竞品框架在偏对话式、需快速 Demo 的场景具有竞争力，但**不满足本项目编排底座的约束**。本项目不采用，属针对本项目约束的正式裁决。

---

## 4. 候选底座调研与对比

对业界主流的 Agent 底座/编排方案进行调研与横向对比（2025–2026 现状）。评估维度贴合 §2 的约束 C1–C6；C7（SaaS / 多租户维度）的专项评估见 §9。

### 4.1 候选池与一句话定性

| 候选 | 类型 | 一句话定性 | 是否入选对比 |
|---|---|---|---|
| **LangGraph / LangChain** | Agent 图框架 | 图式多 Agent 编排，生态大，但长任务持久化弱、API 不稳定、厂商引力强（详见 §3 排除依据） | 否（已评估排除） |
| **自研最小编排核心** | 自研状态机 + asyncio | 薄、全掌控、贴合 C1/C3/C5，是本项目核心 IP 的归属 | **是（首选）** |
| **Temporal** | Durable Execution 引擎 | 生产级（MIT/YAML 开源），断点续跑/恢复/retry 成熟，非"agent 框架"但正是长任务底座 | **是（外挂）** |
| **Prefect**（多取 Pydantic-AI 配套） | Workflow 编排 + durable | 轻量、Python 原生、agent durable execution 支持正在变好 | **是（外挂备选/单机降级）** |
| **Pydantic-AI** | Python Agent 框架 | 类型安全的 agent 定义，已支持接 Temporal/Prefect 做 durable | **是（Agent 层备选，不自研 agent 协议时可用）** |
| **OpenAI AgentKit / Agents SDK** | 厂商 Agent/编排 SDK | 生态好，但偏 benchmark/快速原型，定位厂商生态 + beta | **否（锁定 & 平台向）** |
| **Claude Agent SDK** | 厂商 Agent SDK | 与 MCP/Claude 契合，但平台锁定，与 C4 冲突 | **否（观察不采用）** |
| **AutoGen / Microsoft Agent Framework** | Agent 协作框架 | actor-model，并入微软更大版图，方向变数大 | 否（变数大） |
| **CrewAI / Mastra / AgentFlow** | 协作/确定性编排库 | 偏高层对话式或某专业向，与"结构化的 SharedState DAG 流水线"范式不同 | 否（范式不匹配） |
| **Airflow / Dagster** | 通用 DAG 调度 | 成熟批处理，但为"数据管道"设计，agent 状态机/回退/模型路由支持弱 | 否（太重/不贴合） |

### 4.2 关键候选详细对比表（针对 C1–C6）

| 维度 | 自研最小编排核心 | Temporal（外挂长任务） | Prefect（外挂备选） | Pydantic-AI（Agent 层备选） | OpenAI AgentKit | Claude Agent SDK |
|---|---|---|---|---|---|---|
| **C1 单写入者/空间分区** | 内建，全掌控 | 不相关（只管执行） | 不相关 | 不相关 | 协作式（不符） | 协作式（不符） |
| **C2 长任务 durable** | 需自写（弱） | **强**（断点续跑核心能力） | 中（agent durable 支持见好） | 通过接 Temporal/Prefect 获得 | 弱/发展中 | 弱 |
| **C3 自研图语义为核心** | **完美**（本来就自研） | 外挂，不干扰 | 外挂 | 需封装 | 平台自带（覆盖自研） | 平台自带 |
| **C4 不锁定** | **完美** | 开源（MIT/YAML）可自托管 | 开源 | 开源但生态向 Pydantic | **平台锁定** | **平台锁定** |
| **C5 长期稳定/源码可控/UE6** | **完美** | 成熟稳定 | 较稳 | 较新但活跃 | beta，API 变数大 | 厂商演进 |
| **C6 Python 单机优先** | **完美**（asyncio） | 需本地起 temporal service（有 dev server） | **浅**（API 好，单进程） | **浅** | 浅 | 浅 |

### 4.3 结论性判断

1. **没有任何现成的"Agent 图框架"适合作本项目底座**——要么长任务弱（LangGraph/AgentKit/Claude SDK），要么强锁定（厂商 SDK），要么范式不匹配（CrewAI/通用 DAG）。这印证了"图编排应自研"的方向。
2. **真正缺的是一层 durable execution**（长任务断点续跑），这正是业界已用 Temporal 这类引擎补在 LangGraph 之上的能力。
3. **最优组合**：**自研最小编排核心（图/状态机/回退，核心 IP） + Temporal 外挂（长任务持久化）**。单机轻量场景（solo dev、无独立服务许可顾虑）可用 Prefect 或内置 SQLite checkpoint 降级，保持同一接口。

---

## 5. 定稿选型：自研最小编排核心 + 可选 Durable Execution 引擎

### 5.1 两层分工

编排核心是**领域 Skill 的执行引擎**（§1.1 范式）：宿主 Agent 调度某个 Skill 时，由它驱动该 Skill 内部的多步骤、依赖、回退与长任务。

```
┌──────────────────────────────────────────────────────────────┐
│  L4 自研最小编排核心 = 领域 Skill 执行引擎（核心 IP，薄）        │
│   · DAG 状态机 / 依赖传播 / stale 标记 / 回退(≤3)              │
│   · 任务队列(优先级) / 空间分区锁 / 单写入者调度               │
│   · 模型路由(LiteLLM) / 记忆分层(RAG) 注入                    │
│   ┌────────────────────────────────────────────────────┐      │
│  │  Durable Execution 适配层（薄）                       │      │
│  │   · 长任务(job) 注册/句柄/恢复  <─可选─> Temporal      │      │
│  │   · 单机降级：Prefect / 内置 SQLite checkpoint         │      │
│  └────────────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────────────┘
         │ MCP Client（唯一写入者）
         ▼
   UE 5.8 MCP Server (127.0.0.1:8000)
```

- **核心层**：自研 `orchestrator/`（dag.py / scheduler.py / partition.py / task_queue.py），**不依赖任何 Agent 图框架**。
- **外挂层**：`orchestrator/durable/`（`temporal_adapter.py` / `prefect_adapter.py` / `local_sqlite.py`），统一 `DurableProvider` 接口，**可替换、可关闭**。

### 5.2 为什么是"外挂"而不是"内置 Temporal"

- **降级友好**：单机 solo 场景不需要跑一个 Temporal 服务；P0 用本地 SQLite checkpoint 就能跑通闭环，Temporal 作为 P1+ 生产级选项。
- **不引入重基础设施**：Temporal 需要 worker + server（或有 dev server），P0 不引第三方常驻服务，符合"最小可行 + 可演进"。
- **接口单一**：无论用什么 durable 实现，对编排核心暴露的只有 `register_long_task / poll / recover` 三个方法，切换成本极低（TDR-H04）。

---

## 6. 技术设计：自研 Harness 的架构与模块

### 6.1 目录结构

```text
orchestrator/
├── cli.py                    # 宿主 CLI 入口（Typer）：run / plan / approve / rollback
├── host.py                   # 薄宿主：接收指令，解析并调度对应 Skill
├── skill.py                  # Skill 注册与调度接口（skill 元数据 / 输入 schema / 执行）
├── dag.py                    # ★ 自研 DAG 状态机（Skill 内部的依赖传播 / stale / 回退）※核心 IP
├── scheduler.py              # ★ asyncio 调度器（拓扑排序 + 优先级队列 + 空间分区锁）
├── task_queue.py             # 优先级任务队列（asyncio）
├── durable/
│   ├── base.py               # DurableProvider 抽象接口
│   ├── local_sqlite.py       # P0 本地 checkpoint 持久化（单机默认）
│   ├── prefect_adapter.py    # （可选）轻量 durable，单进程更省
│   └── temporal_adapter.py   # （可选，P1+）生产级 durable execution
├── skills/                   # ★ 33 个领域 / 评估 Skill（= 领域角色的能力封装）
│   ├── scenes_pcg/           #   例：场景 / PCG
│   ├── gameplay/             #   例：玩法实现
│   ├── eval_gameplay/        #   例：E3 可玩性审计
│   └── ...                   #   每个 Skill 含：skill.yaml（元数据）+ prompt.md + tools 白名单 + steps 编排
├── rag.py                    # LanceDB 检索 + 注入
├── memory/                   # LanceDB 持久化
├── models.py                 # LiteLLM 封装 + 路由
└── mcp_client.py             # MCP Client（唯一写入者）
```

一个 Skill 的标准组成（以 `skills/scenes_pcg/` 为例）：

```text
skills/scenes_pcg/
├── skill.yaml                # 名称 / 输入输出 schema / 模型档位 / 工具白名单 / 风险分级
├── prompt.md                 # 面向宿主 Agent 的调用说明与领域策略
├── steps.yaml                # Skill 内部步骤（对应 DAG 节点）与依赖 / 回退阈值
└── tools/                    # 该 Skill 可调用的 Toolset 白名单声明
```

> **Skill 与领域"Agent"的关系**：`skills/<name>/` 即项目文档中对应领域角色（如 `Scene/PCG`、`E3_GameplayAudit`）的能力封装。概念上仍是"该领域由谁负责、怎么做"，但调用模型是"宿主 Agent 按任务加载对应 Skill"，而非 33 个常驻 sub-agent 互相调 tool。SharedState 路径仍按领域组织（`shared_state/<skill>/...`），与 PRD / TechDesign 的领域划分一致。

### 6.2 核心接口（`dag.py` / `scheduler.py`）

在 Skill / 插件范式下，自研 DAG 状态机是**宿主调度 Skill 后的执行载体**：一个 Skill 内部可包含多个有序 / 有依赖的步骤，DAG 节点对应 Skill 的"步骤 / 子任务"，而非 33 个平级 sub-agent。节点与调度如下：

```python
class DagNode:                      # 一个 Skill 内部的步骤 / 子任务
    skill: str                      # 所属 Skill，如 "scenes_pcg" / "eval_gameplay"
    step: str                       # Skill 内步骤标识，如 "generate" / "audit"
    shared_state_refs: list[str]    # 读/写的 SharedState 路径（推依赖边）
    severity: str                   # read_only | mutating | destructive（风险门禁）
    partition: SpacePartition | None  # 空间分区锁（可选）
    priority: int

class Dag:
    def propagate(self, changed: list[str]) -> list[str]:
        """上游 shared_state_delta 提交后，BFS 标记下游 stale（深度≤3）"""
        ...
    def resolve(self, node) -> list[str]:
        """本轮要跑的下游步骤（diff 后才决定是否重跑）"""
        ...

class Scheduler(asyncio-based):
    async def run(dag, steps) -> Report:
        # 拓扑排序 + 优先级队列调度
        # 每步通过 MCP Client 唯一写入者调用 Tool
        # 空间分区锁 + 单写入者串行化写
        # 评估 Skill（E1–E6）作为只读消费者，写 eval/*
        # 回退：工程分/体验分/商业分任一<70 → 定向重排队(≤3)
```

### 6.3 为什么这已足够"支撑未来长期发展"

| 长期需求 | 由谁满足 |
|---|---|
| 单机跑通（P0） | 内置 SQLite checkpoint + asyncio |
| 生产级长任务恢复 | 可选 Temporal（P1+），同一 `DurableProvider` 接口 |
| 分布式多机（远期） | asyncio 队列 → 可换分布式队列（Redis Stream/SQS），`DurableProvider` 换分布式实现 |
| UE6 迁移 / 换引擎 | 编排核心与引擎解耦（复用 TechDesign §2.4 / §12 原则），框架薄 → 迁移面小 |
| 新增 Skill / Toolset | 定义 Skill 元数据 + 注册 Toolset 即可（与 PRD 领域角色对应），底座不阻碍 |

---

## 7. 任务执行模型（同步 / 长任务两阶段）

Agent Harness 采用**两阶段长任务模式**：长任务的执行恢复统一交给 `DurableProvider`（§5）。

```
图节点（Skill 步骤发起长任务）
   │ 1. 校验/准备参数，同步返回 {job_id, status:"pending"}
   ▼
编排核心将该步骤 suspend（执行状态交给 DurableProvider 持久化）
   │
   ▼（异步收割协程轮询 UE 的 job_id，或经 Temporal 重放续跑）
   │  完成 → 结果写 shared_state + 触发步骤恢复
   ▼
编排核心恢复该步骤 → 读取结果 → 继续 Skill 后续步骤
```

**恢复的具体责任划分**：
- **同步短任务**（<10s）：编排核心 asyncio 直接调度，无持久化负担。
- **异步长任务**（>10s）：编排核心把 `job_id/trace_id/parent/副作用描述` 交给 `DurableProvider`。
  - `local_sqlite`：持久化到 `.logs/task_state.json` / SQLite，进程崩溃后按 `job_id` 重建、查询 UE 侧 job 状态（`pcg_get_job_status`）、继续或判定失败回退。
  - `temporal_adapter`：交给 Temporal workflow，天然带断点续跑 / retry / 不重复触发——避免外部副作用因重放而重复执行。
- **编辑器重启 / MCP 断线**：沿用 TechDesign §3.5 心跳与降级策略；只读类 Skill 仍可运行。

---

## 8. 与现有栈的对齐（SharedState / MCP / 记忆 / 模型）

- **SharedState（Git 事实源）**：遵循 TechDesign §5.3。`eval/*` 命名空间、评估 Skill 的只读写分离、`link_back_to` 定向回退全部维持。
- **MCP 单写入者**：编排核心（Skill 执行引擎）是唯一 Tool 调用发起方。
- **记忆分层（LanceDB）**：RAG、后验预测偏差写回等全部维持。
- **模型路由（LiteLLM）**：`fast/default/strong` 三档，模型可替换（对应 TDR-010）。Skill 元数据可声明自己的档位。
- **评估 Skill（E1–E6 + UX）**：作为只读、`strong` 模型的 Skill，写 `eval/*`，参与 DAG 回退（工程分/体验分/商业分）。由宿主在里程碑触发。

> **对齐结论**：Agent Harness 落地于编排执行层，遵循如下对齐——Skill / SharedState 契约 / Toolset / 安全治理 / 评估 Skill 均遵循 TechDesign 定义；编排核心（自研 DAG 语义，作为 Skill 执行引擎）为核心 IP，长任务持久化经 DurableProvider 外挂。上述各层保持一致的契约与边界。

---

## 9. SaaS 化与多租户对（对标 Manus 等业界 Agent 平台）

> **本节是本选型的长远视角**。项目未来以 **SaaS / 订阅 + 多租户协作** 形式商业化。在 §1.1 的 Skill / 插件范式下，SaaS 化沿**双路径**展开：
> - **路径 A（Skill 注入）**：底层 Skill 库可被用户自有的 Claude Code / Codex / DeepSeek Harness 通过 Skill 注入 / MCP 服务调用——无需自建宿主，天然契合用户已有工作流。
> - **路径 B（薄宿主托管）**：本项目提供轻量宿主 + 托管 UE 执行服务，以独立多租户 SaaS 的形式交付（对标 Manus 的多租户沙箱与配额计费）。
>
> 两条路径共用同一套 Skill 库与自研编排核心，仅宿主与执行环境的托管程度不同。因此底座选型必须**在一开始就不做会堵死任一方向的决策**。本节研究业界成熟 Agent 平台（以 Manus 为代表）的底座思路，确认本选型如何平滑演进到多租户托管形态。

### 9.1 本选型在多租户下的核心不变性

在 SaaS/多租户场景下，§5 的定稿（**自研最小编排核心 + 可选 Durable Execution 外挂**）仍然成立，理由是：

- **多租户暴露的问题不是"Agent 框架"层面，而是"资源隔离 / 配额 / 沙箱 / 规模化"层面**——这些恰恰是自研编排核心 + DurableProvider 外挂可以渐进式处理的部分，任何"图框架"（LangGraph/AgentKit/Claude SDK）都不解决这些，反而引入厂商锁定。
- **自研 DAG 语义（核心 IP）在多租户下可复用**：Tenant 只是 DAG 的一个命名空间 + 配额维度，图/状态机/回退逻辑完全不变（TDR-H06）。
- **DurableProvider 外挂天然适配多租户**：Temporal 原生支持按 namespace 隔离不同租户的工作流（multi-tenant namespace 模式），SQLite 单机只是 P0 降级（详见 §9.3）。

### 9.2 对标 Manus 的底座构成（业界参考）

Manus 是全球规模的通用 Agent 平台，其底座构成对本项目的 SaaS 化有直接参考价值（参考依据见文末）：

| Manus 底座要素 | 说明 | 本项目的对应/演进方向 |
|---|---|---|
| **Agent 沙箱（虚拟电脑）** | 用 **E2B / Firecracker 微虚拟机**给 agent 提供隔离的可执行环境 | UE MCP 本身是"沙箱外的执行端"；SaaS 化时每租户的 UE/工具执行需放隔离沙箱（§9.4） |
| **规模化基础设施** | 选择 AWS 等云基础设施承载全球多租户、弹性扩展 | 进程模型：从单机 → Kubernetes / 计算池弹性伸缩 |
| **按租户资源分配与配额** | 每个用户/组织的模型调用、计算资源需要配额与计费 | LiteLLM 后端加**租户维度 rate-limit / token 预算 / 计费**（§9.5） |
| **长任务执行** | 通用 agent 需要可靠的长运行 + 断点续跑 | **正是本选型的 DurableProvider（Temporal）**，无需额外发明 |
| **多模能力 / 统一网关** | 多模型、多供应商统一接入 | 维持 LiteLLM 三档路由，加多租户网关 |

> **一个关键洞察**：Manus 这类产品解决的核心挑战（**每个用户隔离的执行沙箱 + 配额计费 + 弹性规模化**）**和"Agent 编排图用什么框架"是正交的**。这进一步说明本项目"薄编排 + durable 外挂"的路子，不会成为 SaaS 化的障碍。

### 9.3 DurableProvider 在多租户下的职责

| 实现 | 单机/开发 | 多租户 SaaS（演进） |
|---|---|---|
| `local_sqlite` | P0 默认，单机调试 | 不可用于生产多租户（无隔离/无水平扩展） |
| `prefect_adapter` | 单进程轻量 | 单进程多租户（小规模可），水平扩展受限 |
| `temporal_adapter` | P1 生产 | **推荐**：Temporal **按租户 namespace 隔离** work-flows，天然支持多租户隔离、retry、断点续跑、水平扩展 |

**Temporal 多租户模式**（业界常见做法）：每个 Tenant 映射到一个 Temporal namespace，编排核心的 `DurableProvider` 按租户路由到对应 namespace——**编排核心零改动**，只改 `temporal_adapter.py` 的 namespace 解析。这正是 TDR-H04「统一 DurableProvider 接口」价值在多租户下体现。

### 9.4 多租户沙箱与执行隔离（对标 E2B/Firecracker）

SaaS 化时，UE 工具执行与 agent 代码不应跑在共享进程里，需每租户隔离：

```
Tenant A runner         Tenant B runner        ...
   │  UE MCP / 沙箱         │  UE MCP / 沙箱
   └──────┬─────────────────┴───┬──────────
          ▼                     ▼
   Orchestrator（共享控制面，只调度/不执行写）
    │ MCP Client（每租户各自唯一写入者连各自 UE 沙箱）
    ▼
   UE 5.8 实例（每租户独立编辑器/沙箱）
```

- **隔离模型**：每租户一个隔离执行环境（Firecracker 微 VM / Kubernetes Pod + 独立 UE 实例），相互不可见。
- **单写入者模式保持**：每租户内部仍是"该租户的唯一 Orchestrator 写入者"，多租户之间天然隔离，互不干扰。
- **SharedState 变为租户维度**：`shared_state/{tenant}/...` 或每租户独立 LanceDB 集合，评估 `eval/{tenant}/`，契约不变（仅增加租户维度键）。

### 9.5 多租户的配额 / 计费 / 模型网关

| 关注点 | 设计 |
|---|---|
| **模型配额** | LiteLLM 后端加租户维度 token 预算 / 并发限制 / 计费计量；`fast/default/strong` 路由可按租户缩放 |
| **计算配额** | 每租户 UE 沙箱的 CPU/GPU/时长配额（对标 Manus 按用户分配资源） |
| **调用计量** | Tool 调用、Agent 运行、长任务 duration 全部带 `tenant_id` 计量标签，供计费与成本核算 |
| **审计** | 现有 Trace（OTel）加租户维度，满足多租户可观测与合规 |

### 9.6 对底座选型的净结论（纳入约束 C7）

> 新增约束 **C7 支撑 SaaS / 多租户 / 订阅长期演进**。本选型（自研最小编排核心 + DurableProvider 外挂 + LiteLLM + 按租户隔离沙箱）**满足 C7**：
> - Skill / 插件范式天然支持两条商业化路径——(a) **Skill 注入**到用户自有的 Claude Code / Codex / DeepSeek Harness，(b) **薄宿主托管**为独立多租户 SaaS（§9 引言）；
> - 薄编排核心天然支持"多租户仅增加一个维度"，**无框架锁定阻碍**；
> - DurableProvider 外挂（Temporal）原生支持多租户 namespace 与水平扩展；
> - 未绑定任何厂商 Agent SDK，SaaS 化时不会被供应商绑架；
> - 与 Manus 类平台底座逻辑同构（沙箱隔离 + 配额计费 + durable 执行 + 弹性扩展），方向正确。

---

## 10. 演进路线与替换策略

| 阶段 | 形态 | 说明 |
|---|---|---|
| **P0（本阶段）** | 自研编排核心 + 薄宿主（CLI）+ `local_sqlite` durable | 本地闭环：薄宿主加载 Skill → 编排核心驱动 Skill 内部步骤 → 调 UE；无三方常驻服务 |
| **P1** | Skill 体系化 + 长任务升 Temporal | 领域能力完整封装为 Skill（目标：33 个）；接入 `temporal_adapter` 升生产级长任务恢复 |
| **P2** | Skill 注入第三方宿主 | 用户自有的 Claude Code / Codex / DeepSeek Harness 可直接加载本项目 Skill（Skill 注入 / MCP 服务），无需用薄宿主 |
| **P3（SaaS-PoC）** | 薄宿主托管 + 单实例多租户 | 编排核心按 tenant 维度隔离；`temporal_adapter` 按 namespace 路由；LiteLLM 加租户配额/计量 |
| **P4（SaaS 生产）** | 多租户托管 | Kubernetes 弹性计算池；每租户隔离沙箱（Firecracker/Pod）；按租户 UE 实例 + 唯一写入者；计费/审计打通 |
| **远期** | 若需 agent 层协作原语 | 可选接 Pydantic-AI 作为 Skill 内部实现细节，编排核心保持薄 |

**实施路径**：编排核心定位于自研 `orchestrator/`（`dag.py` / `scheduler.py` / `durable/` / `skill.py`），领域能力封装于 `skills/`。Skill / Toolset / SharedState / 治理遵循 TechDesign 定义。

---

## 11. 技术决策记录（TDR-Harness）

| ID | 决策 | 理由 | 备选 | 状态 |
|---|---|---|---|---|
| TDR-H01 | **编排核心采用自研最小编排状态机，不采用任何 Agent 图框架（含 LangGraph）** | 图/状态机/回退/分区为核心 IP，自研实现；Agent 图框架不满足长任务持久化 / API 稳定 / 供应商中立等约束（详见 §3） | LangGraph，或商业化/厂商 Agent SDK | 采纳 |
| TDR-H02 | **自研最小编排核心**（dag.py + scheduler.py + asyncio） | 图/状态机/回退/分区属于核心 IP；薄 → 低锁定、易 UE6 迁移、易新增 Agent | 商业化/厂商 Agent SDK | 采纳 |
| TDR-H03 | **Durable Execution 外挂（默认 Temporal，单机降级 SQLite/Prefect）** | 长任务断点续跑/不重复副作用是真正缺失的能力；外挂可替换、P0 不需常驻服务 | 全自建持久化 | 采纳 |
| TDR-H04 | **统一 `DurableProvider` 接口**（`register_long_task/poll/recover`） | 切换 Temporal/Prefect/SQLite 只改适配实现，编排核心零改动 | 直接绑 Temporal | 采纳 |
| TDR-H05 | 模型接口走 **LiteLLM**（三档路由，`fast/default/strong`） | 满足"模型不锁定"（对应 TechDesign TDR-010） | 厂商 SDK | 采纳 |
| TDR-H06 | **多租户 = 编排核心之上的额外维度（tenant_id）**，不改变 DAG/回退语义 | 自研核心天然支持"多租户仅增加一个维度"；SharedState/存储/评估加 tenant 键即可，核心逻辑复用 | 为多租户重写编排核心 | 采纳 |
| TDR-H07 | **SaaS 化演进方向**：DurableProvider 按租户 namespace（Temporal）+ 每租户隔离沙箱（对标 Manus/E2B）+ Kubernetes 弹性 + LiteLLM 租户配额计量 | 与 Manus 类平台底座逻辑同构（沙箱隔离 + 配额计费 + durable + 弹性），薄编排不阻碍 SaaS（详见 §9） | 绑定厂商 Agent 平台（AgentKit/Claude SDK） | 采纳 |
| TDR-H08 | **范式：Skill / 插件体系，非 sub-agent 网络**。领域能力封装为 Skill，由宿主 Agent（用户自有 Harness 或本项目薄宿主）调度；自研编排核心作为 Skill 的执行引擎 | 与 Claude Code / Codex / DeepSeek Harness 等业界主流同构；支持"Skill 注入第三方宿主"与"薄宿主托管 SaaS"双路径；33 个领域"Agent"对应 33 个领域 Skill（§1.1、§6.1） | 常驻 sub-agent DAG 协作 | 采纳 |

> 以上 TDR 为 Agent Harness 底座的正式决策记录，作为 TechDesign §13 编排相关决策的**一致补充**（对应并佐证其 TDR-012「编排核心自研 + Durable 外挂」决策）。

---

## 参考依据

- LangGraph 长任务短板与社反馈：LangGraph issue 关于 reasoning/慢、API 重构频繁（github.com/langchain-ai/langgraph）
- Durable Execution 是 agent 生产化关键与 Temporal LangGraph plugin：temporal.io/blog/temporal-langgraph-plugin-durable-execution；langchain.com/resources/langgraph-vs-temporal
- Pydantic-AI 接 Temporal/Prefect 做 durable execution：prefect.io/blog/prefect-pydantic-infra；github.com/pydantic/pydantic-ai-temporal-example
- OpenAI AgentKit / Agents SDK 定位 beta/快速原型与厂商生态：apidog.com/blog/openai-agentkit；composio.dev/content/openai-agents-sdk-vs-langgraph-vs-autogen-vs-crewai
- 框架锁定迁移成本，业界建议薄化：agentmarketcap.ai/blog/2026/04/12/agent-stack-migration-costs
- Agent 沙箱与虚拟电脑（Manus 用 E2B/Firecracker 微 VM 做执行隔离）：e2b.dev/blog/how-manus-uses-e2b-to-provide-agents-with-virtual-computers；spheron.network/blog/ai-agent-code-execution-sandbox-e2b-daytona-firecracker
- Manus 以 AWS 底座支撑全球多租户 Agent 的规模化：press.aboutamazon.com/aws/2025/12/manus-selects-aws；zenml.io/llmops-database/building-production-ai-agents-with-api-platform-and-multi-modal-capabilities
- Temporal 多租户 / durable 云控制系统（namespace 隔离、控制面）：temporal.io/blog/building-durable-cloud-control-systems-with-temporal
- 多租户 LLM 网关 / 配额计量模式：github.com/Ashara-kosi/llm-gateway；多租户 Agent 平台编排：github.com/dicosmode/agent-platform

---

*本文档为 Agent Harness（编排/运行时底座）选型的唯一事实源。与 TechDesign 不一致处，以本文档为准。*
