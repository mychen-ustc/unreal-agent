# Agent Harness（Agent 运行时底座）选型与技术设计

项目代号：AI Agent 驱动的高品质游戏开发
关联 PRD：[AI_Agent_Game_Dev_PRD.md](./AI_Agent_Game_Dev_PRD.md)（v0.2）
关联技术设计：[AI_Agent_Game_Dev_TechDesign.md](./AI_Agent_Game_Dev_TechDesign.md)（§2.3 / §6 / §13）
关联架构：[AI_Agent_Toolchain_Architecture-unreal.md](./AI_Agent_Toolchain_Architecture-unreal.md)（§1 四层 · §6 编排层）
关联路线图：[ROADMAP.md](./ROADMAP.md)（§1 双时间轴 · §3 商业轴 C0–C3 与本章 §10/§11 对齐）
状态：**定稿（v1.3）**

> **本文档的定位**：**Agent Harness（Agent 运行时底座）选型的权威依据与落地文档**。面向本项目「框架可替换 + 源码可控 + 单写入者 + 支撑 SaaS / 多租户长期演进」的约束，规定：
> - **核心立场**：项目的第一公民是**「能力包」**——即 **UE MCP Server + Toolset + Skill 资产**。它们是模型无关、宿主无关、可移植的真正核心 IP；完整能力包不出境，仅引流子集可注入主流 Harness（§11/§12）；
> - **范式**：核心能力封装为 **Skill / 插件**（与 Claude Code / Codex / DeepSeek Harness / OpenClaw / Hermes 等业界主流同构），由宿主 Agent 调度，而非常驻 sub-agent 网络（§1.1）；
> - **宿主可选（OSS）**：自研最小编排核心**从「第一公民」降级为「可选宿主的一实现」**——仅在你的薄宿主（路径 B）或需要长任务编排增强时用；可被第三方 Harness 完全取代，能力包不受影响；
> - **跨宿主（引流）**：通过「**Common Spec + 能力蒸馏 + 导入脚本**」把**引流体验子集**翻译注入主流 Harness（§11.3/§12）；完整能力包不出境；
> - **底座**：UE 工具平面为 **MCP**（唯一写入者）；可选自研编排核心 + 可选 Durable Execution 外挂 + LiteLLM；
> - **商业化（v1.3）**：优先**纯 SaaS**（§11 形态 A）；支持**私有化黑盒部署**（§11 形态 B，完整能力包跑客户机器，核心资产不可见，额外收费 + 协议约束）；Skill 注入仅作**引流/体验子集**（能力蒸馏工具 §11.3，形态 C）。资产保护与交付形态见 §11。
> 本文档是**该选型与能力包（Common Spec）规范的唯一事实源**（Single Source of Truth），TechDesign 相关章节以其为准并交叉引用。

> **v1.2 变更**：将根本立场从「编排核心是第一公民」调整为「**能力包（MCP Server + Toolset + Skill）是第一公民，编排核心是可选宿主之一实现**」；新增「跨 Agent Harness 集成的 Common Spec 与导入方案」（§12）；目标与核心能力在 §1 重述；§10 演进次序相应调整。既有选型结论（§4–§5）与全部 TDR 维持，仅作立场与定位层面重述与增补。
>
> **v1.3 变更**：新增「**商业交付形态与资产保护**」（§11），确立「纯 SaaS 为主推、私有化黑盒可支持、Skill 注入仅引流」三形态及**能力蒸馏工具 + Skill 五级划分（Tier 0–4）+ 最小可用版**；私有化黑盒 = **完整 UE Runtime 发行 + 引擎级 AI 定制**（规划内）；将「跨宿主导入」（§12）重新定位为**仅服务引流/体验子集（形态 C）**，不再作为完整能力包的对外交付通道；§10 演进路线相应重排；新增 TDR-H11/H12。原有编排选型（§4–§5）与全部 TDR 维持。

---

## 目录

- [1. 背景与目标、核心能力](#1-背景与目标核心能力)
- [2. 本项目对 Agent 底座的真实约束](#2-本项目对-agent-底座的真实约束)
- [3. 编排框架候选评估与排除依据](#3-编排框架候选评估与排除依据)
- [4. 候选底座调研与对比](#4-候选底座调研与对比)
- [5. 定稿选型：能力包为第一公民 + （可选）自研编排宿主](#5-定稿选型能力包为第一公民--可选自研编排宿主)
- [6. 技术设计：自研 Harness 的架构与模块](#6-技术设计自研-harness-的架构与模块)
- [7. 任务执行模型（同步 / 长任务两阶段）](#7-任务执行模型同步--长任务两阶段)
- [8. 与现有栈的对齐（SharedState / MCP / 记忆 / 模型）](#8-与现有栈的对齐sharedstatemcp--记忆--模型)
- [9. SaaS 化与多租户（对标 Manus 等业界 Agent 平台）](#9-saas-化与多租户对标-manus-等业界-agent-平台)
- [10. 演进路线与替换策略](#10-演进路线与替换策略)
- [11. 商业交付形态与资产保护](#11-商业交付形态与资产保护)
- [12. 跨 Agent Harness 集成的 Common Spec 与导入方案](#12-跨-agent-harness-集成的-common-spec-与导入方案)
- [13. 技术决策记录（TDR-Harness）](#13-技术决策记录tdr-harness)
- [参考依据](#参考依据)

---

## 1. 背景与目标、核心能力

### 1.0 本项目真正的目标

本项目「AI Agent 驱动的高品质游戏开发」的**终极目标**不是交付一个自研 Agent 运行时，而是**沉淀一套可复用的「游戏生产能力包」**，并让这套能力包能被当前与未来的任一主流 Agent Harness 调用来驱动 UE 生产。

**目标三层：**

| 层 | 目标 | 衡量 |
|---|---|---|
| **G1 能力可复用** | UE 的领域能力（PCG / Gameplay / Lighting / 评估…）封装为**宿主无关的 MCP Toolset + Skill 资产**，模型无关、框架无关 | 换模型、换宿主零改动；Skill 可独立更新/热加载 |
| **G2 宿主可选** | 不做「必须用 X」的绑定：能力包可注入 Claude Code / Codex / OpenClaw / Hermes / DeepSeek Harness，也可用自研薄宿主跑 | 同一 Skill 在 ≥2 个宿主上跑通同一任务 |
| **G3 编排可增强** | 长任务断点续跑、回退、依赖传播等增强能力以「可选宿主 / 可选 MCP 工具」形式存在，不阻塞 G1/G2 | durable / 回退可独立开关、可被第三方宿主经 MCP 调用 |

**目标倒推的根本立场（v1.2）**：

> **能力包（UE MCP Server + Toolset + Skill）是第一公民，是真正的核心 IP。自研编排核心从「第一公民」降级为「可选宿主之一实现」——只在自研薄宿主（路径 B）或需长任务编排增强时使用，不构成能力包的依赖。**

### 1.1 定稿底座（可选宿主视角）

本项目 Agent Harness 的运行时底座定义为：

> **底座 = 能力包（MCP 工具平面 + Skill 库）为第一公民；宿主可替换。默认/自有宿主 = 自研「最小编排核心」（Minimal Orchestration Core）+ 可选的 Durable Execution 引擎（Temporal / Prefect / SQLite）作为外挂长任务恢复层 + LiteLLM 统一模型接口 + asyncio 运行时。**

设计原则：**不把「能力包」绑定在某个第三方宿主或图框架上——能力包与宿主彻底解耦。** 「图/状态机/回退」这层（若用自研宿主）自研，为核心增强而非核心绑定；「长任务能否断点续跑」这层交给成熟引擎。

| 维度 | 定稿 |
|---|---|
| **第一公民（核心 IP）** | **UE MCP Server（12 个 Toolset 唯一写入者）+ 33 个领域 / 评估 Skill 资产（Common Spec，§12）** |
| **宿主（可替换）** | **自有薄宿主 = 自研 `orchestrator/host.py` 最小编排核心**；亦可注入 Claude Code / Codex / OpenClaw / Hermes / DeepSeek Harness（§12） |
| Agent 运行时（自有宿主） | **Python 3.11+，asyncio** |
| **编排/图（自有宿主时）** | **自研** `orchestrator/dag.py` 状态机 + 依赖传播 + stale + 回退 |
| **长任务恢复** | **可选外挂 Durable Execution 引擎**（默认 Temporal；轻量单机场景可退化为 Prefect 或内置 SQLite checkpoint） |
| **模型路由** | **LiteLLM**（统一三档模型，`fast/default/strong`；第三方宿主自带路由时直接复用其路由） |
| **MCP 客户端** | `mcp` Python SDK（官方）+ MCP Server 标准（后者是注入各宿主的通用接口） |

> **选型边界**：本项目不采用任何「Agent 图框架」（如 OpenAI AgentKit / Claude Agent SDK / LangGraph）作为**必须**的编排底座——原因见 §4 候选对比。但**这不再排斥第三方宿主**：Claude Code / Codex / OpenClaw / Hermes 本身就是合格宿主，可承载**引流体验的蒸馏子集**（§11 形态 C/§12）；完整能力包的运行则由自有宿主或私有化黑盒承载（§11 形态 A/B），不依赖必须的自研编排核心。

### 1.2 范式定位：Skill / 插件体系（与主流 Agent Harness 同构）

本项目的**能力**遵循业界主流 Agent Harness（Claude Code / Codex / DeepSeek Harness / OpenClaw / Hermes 等）的范式：**核心能力封装为 Skill / 插件，由宿主 Agent 按需调用，而不是做成常驻的 sub-agent 网络。**

| 范式维度 | 业界主流（Claude Code / Codex / DeepSeek Harness 等） | 本项目 |
|---|---|---|
| **交互单位** | 宿主 Agent（用户直接对话）+ Skill 库 | 宿主 Agent（用户自有的 Harness 或本项目薄宿主）+ Skill 库 |
| **领域能力** | 封装成 Skill / 插件（输入 schema + 提示词策略 + 工具集） | 封装成 Skill / 插件（领域 Agent 的能力沉淀为可复用 Skill） |
| **子 Agent** | 一般不暴露常驻 sub-agent；需要时做临时角色/工具 | 不暴露常驻 sub-agent 网络；领域职能以 Skill 形式提供 |
| **编排** | 宿主自主决策 + Skill 内部多步骤 | 宿主导调度 Skill；**Skill 内部步骤/回退在自有宿主时由自研最小编排核心驱动；第三方宿主（引流子集）时编译为其原生步骤/prompt（§12.4）** |

**关键澄清**：项目文档中的 **33 个领域 / 评估"Agent"在本范式中对应"33 个领域 Skill"**——它们在概念上仍是"某领域由谁负责"的角色，但**调用模型不是"33 个平级 sub-agent 互相调 tool"，而是"宿主 Agent 按任务调度对应 Skill"**。SharedState 路径仍按领域组织（`shared_state/<skill>/...`），语义不变。

这对底座定位有三个直接推论：
1. **能力包的可移植性是第一优先级**。Skill 必须写成宿主无关的「Common Spec」（§12），而非绑定某个宿主的私有 DSL，才能在同一份资产注入不同宿主。
2. **编排核心（若用）是可选宿主，不是能力包的必需层**。自研最小编排核心是自有薄宿主（路径 B）的实现细节；在第三方宿主（路径 A）下，它的「步骤/回退」被编译成该宿主能执行的形式（§12.4），DAG 语义以"能力注记"而非"执行引擎"形式保留。
3. **产品形态分两条、且商业上不等权**（v1.3）：(a) **能力蒸馏引流**——蒸馏子集被用户自有的 Claude Code / Codex / OpenClaw / Hermes 调用（§11/§12，仅 Demo/体验）；或 (b) **付费形态**——SaaS 托管（A）与私有化黑盒（B）承载完整能力包但**不出境**。完整能力包的「注入」只发生在自有薄宿主或客户黑盒内，绝不作为可产出的文件交付。

> 本节确立**「能力包（Skill / 插件 + MCP 工具平面）为第一公民」**为主范本；以下 §2–§12 的约束、选型、技术设计、跨宿主方案均在此立场下展开。

---

## 2. 本项目对 Agent 底座的真实约束

在选型前，先把约束说透——这些是本项目与"聊天式多 Agent demo"的本质差异：

| 约束 | 说明 | 对底座的影响 |
|---|---|---|
| **C1 单写入者 + 空间分区** | 唯一 MCP 写入者，多 Agent 按坐标分区 | 不需要框架内置的"协作协议/tool-use 自动分发"；**需要的只有串行调度 + 资源归属锁**，自研即可 |
| **C2 长任务很多且带外部副作用** | PCG 生成（<60s~几分钟）、全量编译（50–70min）、PIE 测试 | 底座必须解决**断点续跑 / 崩溃后恢复 / 不重复触发外部副作用**（durable execution）——这是 LangGraph 的短板 |
| **C3 图语义（依赖传播/stale/回退≤3）是核心增强（自有宿主时）** | 自研 DAG 引擎定义好了 | 作为「可选宿主」的增强；能力包本身不依赖它（§12），宿主可替换 |
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

### 3.4 与"自研 DAG 语义是核心增强（自有宿主）"冲突

本项目 90% 的编排价值在自研的依赖传播/stale/回退/空间分区（自有宿主时），LangGraph 只提供 StateGraph 原语——**它带来的加速度明显小于其 3.1–3.3 的成本**。用更薄的方案获取等价的图编排能力，代价更可控。**注意**：此结论针对「是否用 LangGraph 作自研编排的底座」，不影响把 Claude Code/OpenClaw 等当宿主注入能力包（§4.3 结论 4、§12）。

> **评估结论**：LangGraph 作为竞品框架在偏对话式、需快速 Demo 的场景具有竞争力，但**不满足本项目编排底座的约束**。本项目不采用，属针对本项目约束的正式裁决。

---

## 4. 候选底座调研与对比

对业界主流的 Agent 底座/编排方案进行调研与横向对比（2025–2026 现状）。评估维度贴合 §2 的约束 C1–C6；C7（SaaS / 多租户维度）的专项评估见 §9。

### 4.1 候选池与一句话定性

| 候选 | 类型 | 一句话定性 | 是否入选对比 |
|---|---|---|---|
| **LangGraph / LangChain** | Agent 图框架 | 图式多 Agent 编排，生态大，但长任务持久化弱、API 不稳定、厂商引力强（详见 §3 排除依据） | 否（已评估排除） |
| **自研最小编排核心** | 自研状态机 + asyncio | 薄、全掌控，是「自有薄宿主」的实现；**非能力包的必需依赖**（完整能力包可跑于自有宿主或私有化黑盒，见 §11） | **是（自有宿主可选项）** |
| **Temporal** | Durable Execution 引擎 | 生产级（MIT/YAML 开源），断点续跑/恢复/retry 成熟，非"agent 框架"但正是长任务底座 | **是（外挂）** |
| **Prefect**（多取 Pydantic-AI 配套） | Workflow 编排 + durable | 轻量、Python 原生、agent durable execution 支持正在变好 | **是（外挂备选/单机降级）** |
| **Pydantic-AI** | Python Agent 框架 | 类型安全的 agent 定义，已支持接 Temporal/Prefect 做 durable | **是（Agent 层备选，不自研 agent 协议时可用）** |
| **Claude Code / Codex (CLI)** | 宿主 Harness | 最强通用宿主；Skill（SKILL.md/AGENTS.md）+ MCP 原生支持；**作为引流体验的蒸馏子集注入目标（形态 C），而非编排底座** | **是（宿主·形态 C，§12）** |
| **OpenClaw / Hermes** | 宿主 Harness | 开源 Agent 运行时；Gateway+Skill/插件+MCP 兼容；**同为引流蒸馏子集注入目标** | **是（宿主·形态 C，§12）** |
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

1. **没有任何现成的"Agent 图框架"适合作本项目自研编排底座的必需依赖**——要么长任务弱（LangGraph/AgentKit/Claude SDK），要么强锁定（厂商 SDK），要么范式不匹配（CrewAI/通用 DAG）。这印证了"**不把能力包绑定在任一编排方案上**"的方向。
2. **真正缺的是一层 durable execution**（长任务断点续跑），这正是业界已用 Temporal 这类引擎补在 LangGraph 之上的能力。
3. **最优组合（自有宿主时）**：**自研最小编排核心（图/状态机/回退） + Temporal 外挂（长任务持久化）**。单机轻量场景（solo dev、无独立服务许可顾虑）可用 Prefect 或内置 SQLite checkpoint 降级，保持同一接口。
4. **新增结论（v1.2/v1.3）**：**Claude Code / Codex / OpenClaw / Hermes / DeepSeek Harness 等主流 Agent Harness 不作为「编排底座」候选评估的原因，不是它们不合格，而是它们应作为「引流体验的蒸馏子集注入目标」被复用，而非被排除**（§12）。完整能力包不出境；自研编排核心承载自有宿主（路径 B）与私有化黑盒（§11 形态 B）。

---

## 5. 定稿选型：能力包为第一公民 + （可选）自研编排宿主

### 5.1 能力包与可选宿主的分工

**第一公民 = 能力包**：UE MCP Server（唯一写入者）+ 33 个领域 / 评估 Skill（Common Spec，§12）。它不依赖任何特定宿主。

**可选宿主 = 自研最小编排核心**，仅在自有薄宿主（路径 B）或需长任务编排增强时使用：宿主调度某个 Skill 时，由它驱动该 Skill 内部的多步骤、依赖、回退与长任务。

```
┌──────────────────────────────────────────────────────────────┐
│  能力包（第一公民 · 核心 IP）                                   │
│  · UE MCP Server = 12 个 Toolset 唯一写入者（127.0.0.1:8000）  │
│  · 33 个领域 Skill 资产（Common Spec：skill.yaml + prompt.md   │
│    + steps.yaml + tools 白名单）                               │
│  · SharedState 契约（Git JSON 事实源）                         │
└───────────────────────┬──────────────────────────────────────┘
       可注入 / 可跑  ▼   （路径 A 第三方宿主 或 路径 B 自有宿主）
┌──────────────────────────────────────────────────────────────┐
│  可选宿主之一：自研最小编排核心（自有薄宿主，非必需）             │
│   · DAG 状态机 / 依赖传播 / stale 标记 / 回退(≤3)              │
│   · 任务队列(优先级) / 空间分区锁 / 单写入者调度               │
│   · 模型路由(LiteLLM) / 记忆分层(RAG) 注入                    │
│   ┌────────────────────────────────────────────────────┐      │
│  │  Durable Execution 适配层（薄，可选）                 │      │
│  │   · 长任务(job) 注册/句柄/恢复  <─可选─> Temporal      │      │
│  │   · 单机降级：Prefect / 内置 SQLite checkpoint         │      │
│  └────────────────────────────────────────────────────┘      │
└──────────────┬───────────────────────────────────────────────┘
               │ MCP Client（唯一写入者）
               ▼
   UE 5.8 MCP Server (127.0.0.1:8000)
```

- **能力包层**：`orchestrator/skills/<skill>/`（skill.yaml + prompt.md + steps.yaml + tools/whitelist.yaml）+ UE 侧 Toolset。它是**可移植、可售卖**的资产，是跨宿主注入的基础。
- **可选宿主层**：自研 `orchestrator/`（host.py / dag.py / scheduler.py / partition.py / task_queue.py），**不依赖任何 Agent 图框架**。可「关掉不用」，改用第三方宿主（§12）。
- **外挂层**：`orchestrator/durable/`（`temporal_adapter.py` / `prefect_adapter.py` / `local_sqlite.py`），统一 `DurableProvider` 接口，**可替换、可关闭**。
- **注入层**：`orchestrator/importers/`（§12）把`distiller` 蒸馏的引流子集翻译注入第三方宿主（形态 C）；完整能力包不走此层。

### 5.2 为什么编排核心是"可选"而不是"内置必需"

- **能力包可移植是第一优先**：Skill 写成宿主无关 Common Spec（§12.3），不绑定自研编排核心，才能注入任意宿主。
- **降级/复用友好**：单机 solo 场景可用自带薄宿主，不需要跑 Temporal；路径 A 场景直接注入 Claude Code / OpenClaw 等，完全不需要自研编排核心。
- **交『长任务』给第三方宿主或 Durable 外挂**：第三方宿主自带工具循环与模型路由；长任务断点续跑在自有宿主时经 `DurableProvider` 外挂，在第三方宿主时以 MCP 长任务工具形式暴露（§12.4）。
- **接口单一**：即便用自有宿主的 Durable 实现，对编排核心暴露的只有 `register_long_task / poll / recover` 三个方法，切换成本极低（TDR-H04）。

---

## 6. 技术设计：自研 Harness 的架构与模块

### 6.1 目录结构

```text
orchestrator/
├── cli.py                    # 宿主 CLI 入口（Typer）：run / plan / approve / rollback / import
├── host.py                   # 薄宿主（路径 B）：接收指令，解析并调度对应 Skill（可选宿主之一）
├── skill.py                  # Skill 注册与调度接口（skill 元数据 / 输入 schema / 执行）；遵循 Common Spec（§12.3）
├── dag.py                    # 自研 DAG 状态机（Skill 内部的依赖传播 / stale / 回退）※自有宿主实现，非能力包必需
├── scheduler.py              # asyncio 调度器（拓扑排序 + 优先级队列 + 空间分区锁）※自有宿主实现
├── task_queue.py             # 优先级任务队列（asyncio）
├── durable/
│   ├── base.py               # DurableProvider 抽象接口
│   ├── local_sqlite.py       # P0 本地 checkpoint 持久化（单机默认）
│   ├── prefect_adapter.py    # （可选）轻量 durable，单进程更省
│   └── temporal_adapter.py   # （可选，P1+）生产级 durable execution
├── skills/                   # ★ 33 个领域 / 评估 Skill（= 领域角色的能力封装；第一公民）
│   ├── scenes_pcg/           #   例：场景 / PCG
│   ├── gameplay/             #   例：玩法实现
│   ├── eval_gameplay/        #   例：E3 可玩性审计
│   └── ...                   #   每个 Skill 含：skill.yaml + prompt.md + steps.yaml + tools 白名单（§12.3）
├── distiller.py              # ★ 能力蒸馏（§11.3）：完整能力包 → 对外 Demo/体验子集（形态 C）
├── importers/                # ★ 引流子集注入层（§12）：只消费 distiller 蒸馏子集 → 目标宿主
│   ├── base.py               # Importer 抽象接口
│   ├── registry.py           # 宿主适配器注册表
│   ├── claude_code.py        #   适配：Claude Code（SKILL.md + .mcp.json）
│   ├── codex.py              #   适配：OpenAI Codex（AGENTS.md + 插件/MCP 配置）
│   ├── openclaw.py           #   适配：OpenClaw（Skill/插件 + 网关配置）
│   ├── hermes.py             #   适配：Hermes（Skill + worker 配置）
│   └── self_hosted.py        #   适配：自有薄宿主（直接读 skill.yaml，路径 B）
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
| 单机跑通（P0） | 内置 SQLite checkpoint + asyncio（自有宿主） |
| 生产级长任务恢复 | 可选 Temporal（P1+），同一 `DurableProvider` 接口；第三方宿主经 MCP 长任务工具暴露（§12.6） |
| 分布式多机（远期） | asyncio 队列 → 可换分布式队列（Redis Stream/SQS），`DurableProvider` 换分布式实现 |
| UE6 迁移 / 换引擎 | 能力包（MCP + Skill）与引擎解耦（复用 TechDesign §2.4 / §12 原则），宿主薄 → 迁移面小 |
| 新增 Skill / Toolset | 定义 Common Spec Skill + 注册 Toolset 即可（与 PRD 领域角色对应）；一个 Skill 注入所有宿主，底座不阻碍 |
| 跨宿主注入（P0/P1 起） | `orchestrator/importers/` 把 Common Spec Skill 翻译注入 Claude Code / Codex / OpenClaw / Hermes 等（§12） |

---

## 7. 任务执行模型（同步 / 长任务两阶段）

Agent Harness 采用**两阶段长任务模式**：长任务的执行恢复统一交给 `DurableProvider`（§5）。在自有薄宿主下，由编排核心驱动；在第三方宿主下，长任务能力以 MCP 工具形式暴露（`job_submit/job_poll/job_recover`，§12.6），任何宿主都能用。

```
图节点 / MCP 工具（Skill 步骤发起长任务）
   │ 1. 校验/准备参数，同步返回 {job_id, status:"pending"}
   ▼
编排核心（自有宿主）将该步骤 suspend，或第三方宿主调用 job_poll 收割
   │（执行状态交给 DurableProvider 持久化）
   ▼（异步收割协程轮询 UE 的 job_id，或经 Temporal 重放续跑）
   │  完成 → 结果写 shared_state + 触发步骤恢复
   ▼
编排核心/第三方宿主恢复该步骤 → 读取结果 → 继续 Skill 后续步骤
```

**恢复的具体责任划分**：
- **同步短任务**（<10s）：宿主 asyncio 直接调度，无持久化负担。
- **异步长任务**（>10s）：把 `job_id/trace_id/parent/副作用描述` 交给 `DurableProvider`（自有宿主内部）或封装为 MCP 长任务工具（第三方宿主，§12.6）。
  - `local_sqlite`：持久化到 `.logs/task_state.json` / SQLite，进程崩溃后按 `job_id` 重建、查询 UE 侧 job 状态（`pcg_get_job_status`）、继续或判定失败回退。
  - `temporal_adapter`：交给 Temporal workflow，天然带断点续跑 / retry / 不重复触发——避免外部副作用因重放而重复执行。
- **编辑器重启 / MCP 断线**：沿用 TechDesign §3.5 心跳与降级策略；只读类 Skill 仍可运行。

---

## 8. 与现有栈的对齐（SharedState / MCP / 记忆 / 模型）

- **SharedState（Git 事实源）**：遵循 TechDesign §5.3。`eval/*` 命名空间、评估 Skill 的只读写分离、`link_back_to` 定向回退全部维持。它是**宿主无关**的能力包一部分，跨宿主时路径语义不变。
- **MCP 单写入者 + 空间分区锁**：**下沉到 MCP/Toolset 层（SafeguardToolset + Toolset 拦截器）**，使无论哪个宿主调用都自动获得「唯一写入 + 不冲突」的一致性（§12.6）。编排核心不再是唯一持有这些保证的层。
- **记忆分层（LanceDB）**：RAG、后验预测偏差写回等全部维持；作为能力包的可选增强，第三方宿主可复用其自带记忆（如 Hermes 四层记忆）代替。
- **模型路由（LiteLLM）**：`fast/default/strong` 三档，模型可替换（对应 TDR-010）。自有宿主用 LiteLLM；第三方宿主复用其自带路由（§12.4 Hermes）。
- **评估 Skill（E1–E6 + UX）**：作为只读、`strong` 模型的 Skill，写 `eval/*`，参与回退（工程分/体验分/商业分）。由宿主在里程碑触发。

> **对齐结论**：能力包（Skill / SharedState 契约 / Toolset / 安全治理 / 评估 Skill）遵循 TechDesign 定义，且**宿主无关**；编排核心（自研 DAG 语义）仅作为自有宿主的实现，长任务持久化经 DurableProvider 外挂或作为 MCP 长任务工具体现。上述各层保持一致的契约与边界。

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

> **路线说明**：能力包 Common Spec 是一等资产。技术演进（自有宿主 / 跨宿主引流）与商业演进（SaaS / 私有化黑盒）并行，商业只沉淀在「能力包」之上，不改核心资产。
>
> **编号约定（避免与 ROADMAP 工程轴混淆）**：本章的 P0–P4 是「底座自身的技术/商业演进」，对应 [ROADMAP](./ROADMAP.md) 的**商业轴 C0–C3**；ROADMAP 的工程轴 P0–P6 里程碑（做什么、做到什么标准）不在此重复。两个「P 系列」分属两条平行时间轴（见 [ROADMAP §1](./ROADMAP.md#1-双时间轴总览)）。

| 阶段 | 方向 | 说明 |
|---|---|---|
| **P0（本阶段）** | 能力包成型 + 自有宿主闭环 | 能力包（Toolset + Common Spec Skill）+ 自有薄宿主（CLI）+ `local_sqlite` durable；本地闭环：自研宿主加载 Skill → 驱动步骤 → 调 UE；**同程跑通 1 个引流子集注入（如 Claude Code）作概念验证** |
| **P1** | 能力蒸馏 + 引流体系化 + 长任务升 Temporal | `distiller.py`（§11.3）+ `orchestrator/importers/` 补全（Claude Code / Codex / OpenClaw / Hermes）；领域能力完整封装为 Skill（目标：33 个）；接入 `temporal_adapter` |
| **P2（商业 A 主推）** | 纯 SaaS 上线 | 多租户托管（借 §9）：Kubernetes 计算池 + 每租户 UE 沙箱 + 唯一写入者 + 配额计量；客户只经 API/Web 使用，能力包不出境 |
| **P3（SaaS-PoC）** | 薄宿主托管 + 单实例多租户 | 自研宿主按 tenant 维度隔离；`temporal_adapter` 按 namespace 路由；LiteLLM 加租户配额/计量（§9） |
| **P4（商业 B 追加）** | 私有化黑盒交付 | 完整能力包封装为黑盒镜像/二进制交付客户机器/VPC（§11.2）；真私有化、不依赖你的服务；额外收费 + 协议约束 |
| **远期** | SaaS/私有化增强 & 协作原语 | 能力蒸馏策略丰富；可选接 Pydantic-AI 作 Skill 内部实现细节 |

> **次序说明**（v1.3）：把「跨宿主注入」从上一版的 P2 → 重排为 P1 的**引流子集**（只服务 Demo/体验，§11.4）；商业主路径改为「P2 纯 SaaS → P4 私有化黑盒」；能力包始终不出境。

---

## 11. 商业交付形态与资产保护

> 本章确立产品的**商业交付边界**：优先纯 SaaS，支持私有化黑盒，Skill 注入仅引流。核心原则：**付费形态下「能力包（UE MCP Server + Toolset + Skill + 数据）不出境」**；客户作为黑盒用户获得「运行系统」，而非「资产文件」。
>
> **启动/商业落地配套**：本章的 License/计量/资产保护钩子在 P0 的预埋清单，见 [ops/SECURITY-LICENSING](./ops/SECURITY-LICENSING.md)；阶段与联动见 [ROADMAP](./ROADMAP.md) §3。

### 11.1 三条交付形态（A / B / C）

| 形态 | 运行位置 | 交付给客户 | 客户能拿到 | 核心资产可见性 | 定位 |
|---|---|---|---|---|---|
| **A · 纯 SaaS（主推）** | 你的云 | API / Web | UE 结果、数据 | **客户永远看不见** | 商业化主形态 |
| **B · 私有化黑盒（客户要，可支持）** | 客户机器 / VPC | **一个隔离运行镜像/二进制**（内含**完整** UE Runtime 发行 + 能力包 + 网关 + 计量），只暴露 MCP/HTTP 契约 | 工具名 + JSON Schema + 结果 | **不可见（黑盒）**；靠逆向成本 + 协议约束 + 额外收费兜底 | 真私有化，收费更高，不依赖你的服务 |
| **C · Skill 注入（引流/试用）** | 客户本地 Harness | **能力蒸馏后的简版子集**（§11.3） | 有限 Skill + 简版 prompt | **只给低价值子集**，核心不出 | 对外 Demo / 体验 / 引流 |

**要点**：
- A 与 C 都"Asset 不出境"的严格程度不同：A 完全不出境；C 只蒸馏出子集。
- B 是有意维持的「真私有化」：完整能力包（含引擎内逻辑）在客户机器运行，**不调用你的服务**。此处**不追求 100% 不可逆向**（这是 LLM 能力包的物理上限），而是用「价值分层 + License/计量 + 协议约束 + 更高定价」让「破解成本 > 购买价、且破解后价值衰减」。

### 11.2 私有化黑盒（B）的架构与边界

```
客户环境 / VPC（黑盒容器/二进制）
┌──────────────────────────────────────────────────────┐
│  agent-service（你交付的唯一组件）                       │
│   · 内含完整 UE Runtime 发行 + 能力包 + 网关 + 计量/License  │
│   · 只暴露：                                             │
│      ① MCP 契约（HTTP）：工具名 + JSON Schema + 结果     │
│      ② 管理/计量 API：配额、心跳、License、脱敏日志        │
│   · 不暴露：内部逻辑 / 数据 / 秘钥 / skill 细节            │
│   · 真私有化：不调用你的服务；断网可用（受 License 约束）    │
└─────────────┬────────────────────────────────────────┘
              │ MCP（只用契约）
              ▼
    客户侧宿主（Claude Code / OpenClaw …）或你的薄宿主
```

**四根支柱**（让「黑盒」成立）：
1. **完整 UE Runtime + 引擎级定制是硬壁垒**：黑盒含**完整 UE Runtime 发行**——本项目规划对 UE 做引擎级 AI 定制（如推理嵌入渲染/校验管线、定制 Agent 沙箱、扩展 PCG 框架，架构文档 §0 原则三），这部分定制逻辑仅在 UE 源码内、不进 prompt/schema/不交付源码；客户端拿到的是「运行系统」，逆向需要同时对抗 UE 版权 + 源码级定制 + 编译混淆，成本极高。确定性逻辑（PCG 修正 / 数值平衡 / 风格校验 / 回退）做成容器内 C++ 服务 / 加密参数表，只以 MCP 工具结果浮现。
2. **计量 + License**：容器内强制上报 `license_key / metering / 心跳`（复用 Trace/OTel 计量标签）；断连/超量即降级或停机；私有化版**更高价 + 容量受限 + 版本滞后**，把客户往托管（A）推。
3. **数据飞轮留在你手里**：golden 样本、防幻觉 RAG 语料、评估基准、历史胜率数据只在你的服务端；私有化容器仅含「最小运行必需」运行数据，脱敏回传喂你的训练。→ 客户私有化越多，越依赖你的下个版本/数据，长期锁定越高。
4. **「不可见」 vs 「可审计」合规边界**：提供《交付物边界声明》——可承诺的不可见范围、可提供的审计/脱敏日志/合规证明、MCP 契约是唯一交互面；既满足企业合规又不泄内里。

### 11.3 能力蒸馏工具（distiller）与 Skill 分级——形态 C 的出口

为了让对外 Demo / 体验（C）**既能展示价值、又不泄露核心**，提供**能力蒸馏工具 `orchestrator/distiller.py`**，并按「Skill 价值」分层裁剪。核心思想：**每个 Skill 声明自己的能力等级（Tier），`distiller` 按目标场景（Demo / 试用 / 白标）自动拼出能力子集。**

#### 11.3.1 Skill 五级划分（Tier 0 – Tier 4）

每个 Skill 在 `skill.yaml` 声明 `tier`，贯穿「能跑什么 / 能做出什么 / 对外可见度」三维：

| Tier | 名称 | 能力范围 | 对外形态（C） | 实例 |
|---|---|---|---|---|
| **Tier 4** | 核心 IP | 依赖引擎定制 + 私有数据飞轮的独占能力 | **hidden（绝不出子集）** | 数值/经济平衡、E5/E6 商业与战术评估、引擎级 PCG 新能力 |
| **Tier 3** | 深度生产 | 独特工作流 + 强依赖内部 Toolset/RAG | hidden 或按合同极受限 | 全量 Build、Profiler 深度优化、风格质检闭环 |
| **Tier 2** | 标准生产 | 展示性高、独占性一般的生产能力 | lite（可进试用） | scenes_pcg 生成、Lighting 布光、Level 灰盒 |
| **Tier 1** | 基础辅助 | 通用辅助、低敏感 | lite（可进 Demo） | 命名规范校验、资产审计、目录查看 |
| **Tier 0** | 只读展示 | 纯查询、零副作用 | full（可进公开 Demo） | 列出 UE 工具、读项目元数据、版本信息 |

**判定维度**（在 skill.yaml 中由产品/技术共同定级）：
1. **独占性**：是否依赖私有 Toolset / 引擎定制 / 私有 RAG 语料（越高越 hidden）；
2. **展示性**：对外演示「看得懂、效果好」的程度；
3. **风险面**：mutating/destructive 越高越不宜进公开子集；
4. **商业化敏感度**：是否是可单独收费的拳头能力。

#### 11.3.2 最小可用版（MVP-subset / Tier ≤ 2 + Tier 0）

**定义**：对外 Demo 的「最小可用版」= **Tier 0 + Tier 1 + Tier 2** 三个等级的 Skill 子集，即：只读展示 + 基础辅助 + 标准生产。它能自洽地跑通一条完整的、可展示的 UE 生产闭环（如「按规格生成一个 PCG 场景 → 布光 → 截图回传」），但**不含任何 Tier 3/Tier 4**。

```
MVP-subset（最小可用版）＝ Σ { Tier 0：只读展示 } ∪ { Tier 1：基础辅助 } ∪ { Tier 2：标准生产 }
   ├─ Tool 白名单：只含上述 Skill 的工具；Tier 3/4 工具一律剪去
   ├─ Prompt：抽象化为范式化说明，去内部阈值/黑话/专有调法
   ├─ 数据：不含 golden 样本 / 私有 RAG 语料 / 未发布基准
   └─ 元数据：显式打标 demo / 试用 / 非商用，加静默水印
```

**判别标准**：是否进入「最小可用版」=「`distill_visibility` 是否至少为 `lite`」，而 `distill_visibility` 由 `tier` 推导：

| tier | 默认 distill_visibility | 说明 |
|---|---|---|
| Tier 4 | `hidden` | 绝不出子集（可另按合同白标） |
| Tier 3 | `hidden`（可手动提升为 lite） | 默认不出，按场景特批 |
| Tier 2 | `lite` | 进试用/体验 |
| Tier 1 | `lite` | 进 Demo |
| Tier 0 | `full` | 进公开 Demo |

**规则**：`distiller` 支持显式目标覆盖 `--tier<=2`（MVP）或 `--tier<=4`（内测）或按白名单精确裁剪；默认 `--tier=2`（MVP 最小可用版）。`skill.yaml` 声明的 `tier` 可被产品/技术覆盖，但**降低可见度**（如 Tier 2 → lite）由定义者决定、**提升可见度**（如 Tier 3 → lite）需人工确认（防止误把核心能力放出去）。

#### 11.3.3 distiller 流程与质量门

```
完整能力包（33 个 Skill，各含 tier + distill_visibility）
   │  distiller（蒸馏，--tier<=N / 白名单 / manifest）
   ▼
能力子集（对外发布）
   · Skill 裁剪：按 tier/distill_visibility 筛出子集（¶11.3.2）
   · Tool 白名单裁剪：子集内 Skill 的工具，且剔除 tier>=3 工具
   · Prompt 抽象化：去掉内部阈值/黑话/专有调法
   · 数据脱敏：无 golden / 私有 RAG / 未发布基准
   · 元数据打标：demo/试用/非商用 + 静默水印
   ▼ 质量门（gate，缺一不可）
   · 完整性：MVP 子集可从空项目跑通一条可展示 UE 生产闭环（smoke）
   · 纯净性：子集产物中无 tier>=3 的 Skill/工具/语料（hook 校验）
   · 自洽性：子集 Skill 的依赖与工具白名单闭环（可复用 dag 图校验）
```

- **出口**：把 `distiller` 产物（MVP/试用/白标）经 `importers/` 注入第三方宿主（§12），构成本项目「对外 Demo 与体验环境」的正式通道。
- **不做的事**：`distiller` 不用于产物「完整能力包」的对外交付；完整能力包只走 A（SaaS）或 B（私有化黑盒），均不出境。

### 11.4 对既有文档定位的收口

| 原概念 | 收口后的定位 |
|---|---|
| §9 双路径（路径 A 注入 / 路径 B 薄宿主） | **路径 A（注入）→ 只作形态 C 引流子集**；**路径 B（薄宿主托管）→ 形态 A/B 的载体** |
| §10 P2「第三方宿主为主」 | 降级为「引流体验」；付费主形态是 A（SaaS），其次 B（私有化黑盒） |
| §12 跨宿主 `importers/` | **不用于完整能力包交付**；仅用于形态 C 的蒸馏子集注入 |

---

## 12. 跨 Agent Harness 集成的 Common Spec 与导入方案

> **定位（v1.3）**：本章的「跨宿主导入」**只服务形态 C（引流/体验子集）**——即通过**能力蒸馏**生成的「简版能力子集」注入第三方宿主，作为对外 Demo 与体验环境。**它不是、也不被用作完整能力包的对外交付通道**；付费形态（SaaS / 私有化黑盒）的完整能力包不出境（见 §11）。Common Spec 是能力包的**源规范**：蒸馏子集从它派生，完整能力包也用同一规范，但这两者走不同出口。

### 12.1 目标与原则

**目标**：把「能力蒸馏子集」（§11.3，由 `distiller.py` 产出）翻译成宿主无关形式，经 `importers/` 注入主流宿主，作为对外 Demo/体验（形态 C）。为此：

1. **Skill 必须宿主无关**：子集 Skill 以「Common Spec」（声明式 YAML + Markdown 策略）编写，**不包含任何特定宿主私有字段**。宿主的专有需求由导入脚本在生成时补全，不回写源资产。
2. **工具平面唯一通道是 MCP**：UE 触达的统一接口是 MCP Server（HTTP+SSE，`127.0.0.1:8000`）。无论哪个宿主，都通过 `mcp_client` 调用「子集白名单内」的 Tool，保证「能力一致、写入者唯一」。
3. **编排注记 vs 执行引擎**：子集 Skill 的 `steps.yaml`（DAG 节点/依赖/回退）在自研宿主机是**执行语义**；在第三方宿主机则作为**能力注记**保留——导入时编译成该宿主可执行的形式（§12.4），而非丢给它一个它听不懂的 DAG 引擎。
4. **导入可逆、可回归**：导入是纯生成/翻译，不修改源能力包与蒸馏子集；支持某个宿主适配器独立演进、独立测试（§12.5）。
5. **边界**：`importers/` 只消费 `distiller` 的蒸馏子集，**绝不直接导入完整能力包**（完整能力包只走 §11 形态 A/B）。

### 12.2 Python 中 `importers/` 层的整体设计

`orchestrator/importers/` 提供一个 `import` CLI 子命令 + 每个宿主一个 Adapter（§6.1 目录结构）。

```
python -m orchestrator import --target claude_code|codex|openclaw|hermes|self_hosted [--skills <list>] [--mcp <url>] [--out <dir>]
```

每个 Adapter 实现统一接口：

```python
# importers/base.py
class HarnessImporter(ABC):
    target: str                       # 宿主标识，如 "claude_code" / "codex" / "openclaw"
    @abstractmethod
    def emit_skill(self, spec: SkillSpec, prompt: str, steps_cfg: StepsConfig) -> GeneratedSkillFile: ...
    @abstractmethod
    def emit_mcp_config(self, mcp_url: str) -> GeneratedConfigFile: ...
    @abstractmethod
    def emit_project_manifest(self, skills: list[SkillSpec]) -> GeneratedConfigFile: ...  # skills 索引/菜单
    def generate(self, skills: list[SkillSpec], mcp_url: str) -> ImportBundle:
        # 默认流程：逐 Skill 翻译 + MCP 配置 + 项目清单，汇总为可写入目标目录的 bundle
```

- **确定性**：同一输入在同一版本 Adapter 下输出一致（可 diff）。
- **无副作用**：只生成文件到 `--out` 目录 / 宿主的约定目录，不触发 UE 操作。
- **幂等**：重复导入覆盖同路径产物，源资产不变。

### 12.3 Common Spec（Skill 规范）

**源资产格式**（即本仓库 `orchestrator/skills/<skill>/`，已实现 §6.1）：

```text
skills/<skill>/
├── skill.yaml       # 元数据：名称/描述/输入输出 schema/模型档位/风险分级/tier(商业等级)/distill_visibility
├── prompt.md        # 面向宿主的调用说明与领域策略（Markdown，宿主注入系统提示）
├── steps.yaml       # 步骤（步骤标识/依赖/SharedState 引用/风险/档位/分区）——自研宿主下是 DAG 节点
└── tools/           # 该 Skill 可调用的 Toolset 白名单（静态校验）
```

**决定性商业字段**（§11.3，`skill.yaml` 顶层）：
- `tier: 0|1|2|3|4` —— Skill 能力等级（五级，见表 §11.3.1）；
- `distill_visibility: full|lite|hidden` —— 对外蒸馏可见度（由 `tier` 推导默认值，可覆盖但提升可见度须人工确认，§11.3.2）。

**「宿主无关字段黑名单」**：Common Spec 一律**不写** `claude_code:` / `codex:` / `openclaw:` 等私有前缀块。宿主要求的私有物（Claude Code 的 frontmatter 特定字段、Codex 的命令授权等）由 Adapter 在 `emit_*` 时补上，确保源资产纯净、可被任意新宿主复用。

### 12.4 各宿主 Adapter 的映射规则（初始版）

| 宿主 | Skill 映射 | MCP 配置 | 编排注记（steps）落法 | 说明 |
|---|---|---|---|---|
| **Claude Code** | 每个 Skill → `.claude/skills/<skill>/SKILL.md`（frontmatter: name/description; 正文=prompt.md + 工具说明） | `.mcp.json`（指向 `127.0.0.1:8000/mcp`） | steps.yaml 拍平为 SKILL.md 里的「执行步骤」自然语言片段；depends/severity/partition 转成「注意/约束」注记 | Anthropic Skills 规范为事实标准之一，社区 marketplace 同构 |
| **Codex (CLI)** | `AGENTS.md` 追加 Skill 入口 + 领域规则；可再配插件/命令 | MCP 配置/凭证（Codex 支持的 MCP 方式） | steps.yaml → AGENTS.md 的分步指令 + 工具使用守则 | 遵循 Codex AGENTS.md 约定 |
| **OpenClaw** | Skill → OpenClaw 插件/Skill 目录格式 | Gateway 注入 MCP 服务器（网关路由/会话/鉴权收口） | steps 转 OpenClaw 的 skill/工具编排；分区/回退作为能力注记与工具文档 | OpenClaw 是开源宿主，能力强但格式在演进，Adapter 需跟随版化 |
| **Hermes** | Skill → Hermes skill 定义 + worker 配置 | Gateway / worker 连接 | steps → Hermes skill 提示 + 多模型路由 profile | Hermes 以 Gateway + 四层记忆见长，Adapter 复用其模型路由，不需自带 LiteLLM 路由 |
| **DeepSeek Harness / 其它** | 按其插件/Skill 约定（如 Cordis 插件） | MCP 附着 | 同上原则 | 新增宿主 = 新增一个 Adapter，不改编核心 |

> **编排注记的核心原则**：`steps.yaml` 的依赖传播、回退阈值、空间分区等「自研 DAG 语义」**在第三方宿主不作为执行引擎运行**，而是**作为提示与约束注记**注入该宿主的 Skill 文档，让宿主 Agent 按注记自行分步调用 MCP 工具。真正需要确定性 DAG / 断点续跑 / 不重复副作用的场景，走「长任务 MCP 工具」（§12.6），或直接用自有宿主（路径 B）。

### 12.5 验证与回归

- **宿主无关自测**：Common Spec 字段合法性 + `steps.yaml` 依赖图有环检测（可复用 `dag.py` 的图校验）。
- **注入冒烟**：每个 Adapter 生成的 bundle 在**目标宿主上跑最小闭环**（如「展示 UE 工具列表」），验证 MCP 连通 + Skill 可被宿主发现。
- **同一任务多宿主对拍**：同一指令（如「生成生物群系 PCG 场景」）分别在 Claude Code / OpenClaw / 自有宿主跑一遍，对比产物与耗时，用于评估各宿主表现与取舍（§12.7）。
- **CI**：`importers/` 适配器纳入 repo CI，保证生成产物可 diff、可回归；宿主格式升级时以版本号驱动 Adapter 演进。

### 12.6 长任务与「单写入者 + 分区锁」的跨宿主下沉

跨宿主后，本来自研编排核心承担的长任务/回退/空间分区，需要下沉到能力包侧才能保证「第三方宿主也拿到这些差异化能力」：

1. **长任务**：UE 侧长任务（PCG / 编译 / PIE）保持「`async_long` 返回 job_id」的两阶段接口（§7）。第三方宿主通过 MCP 工具 `job_submit / job_poll / job_recover` 收割；若需断点续跑/不重复副作用，把这三工具接到 `DurableProvider`（Temporal/SQLite）。→ **长任务能力从「宿主内部」变为「MCP 工具」，任何宿主都能用。**
2. **单写入者 + 空间分区锁**：这两者是「UE Game Thread 串行 + 多 Agent 写冲突」的物理要求（TechDesign §2.2），本质属于 **MCP/Toolset 层**而非编排层。跨宿主时应把「写入前自动加分区锁 + 幂等 + 审批门」下沉进 SafeguardToolset / Toolset 拦截器，让**无论哪个宿主调用，都自动获得一致性**，不依赖宿主是否有全局调度。

> 这份下沉把「能力包的差异化」从「依赖某个编排核心」解放出来，是跨宿主成立的关键（TDR-H10）。

### 12.7 宿主取舍与演进

- **P0/P1**：优先验证 **Claude Code**（Anthropic Skills 规范最成熟、MCP 支持最顺、与本仓库 prompt.md 亲和度高）与**自有薄宿主**（路径 B 兜底）。
- **P1+**：补 **Codex / OpenClaw / Hermes**；用 §12.5 的对拍结果决定长期主宿主。
- **不追求「全宿主都精」**：Adapter 分层——「Skill 翻译」通用，「私有物补全」按宿主版化维护。核心投资永远在能力包（Toolset + Common Spec Skill），不在适配器。

---

## 13. 技术决策记录（TDR-Harness）

| ID | 决策 | 理由 | 备选 | 状态 |
|---|---|---|---|---|
| TDR-H01 | **编排核心采用自研最小编排状态机，不采用任何 Agent 图框架（含 LangGraph）** | 图/状态机/回退/分区为**自有宿主**实现；Agent 图框架不满足长任务持久化 / API 稳定 / 供应商中立等约束（详见 §3）。**该决策不排斥第三方宿主**——能力蒸馏子集可注入 Claude Code / Codex / OpenClaw / Hermes（§12）；完整能力包只走 A/B（§11） | LangGraph，或商业化/厂商 Agent SDK | 采纳 |
| TDR-H02 | **自研最小编排核心**（dag.py + scheduler.py + asyncio）作为**自有薄宿主的实现**，非能力包的必需依赖 | 图/状态机/回退可增强自有宿主；能力包（MCP + Skill）为第一公民，宿主可替换（§1/v1.2） | 商业化/厂商 Agent SDK | 采纳 |
| TDR-H03 | **Durable Execution 外挂（默认 Temporal，单机降级 SQLite/Prefect）** | 长任务断点续跑/不重复副作用是真正缺失的能力；外挂可替换、P0 不需常驻服务 | 全自建持久化 | 采纳 |
| TDR-H04 | **统一 `DurableProvider` 接口**（`register_long_task/poll/recover`） | 切换 Temporal/Prefect/SQLite 只改适配实现，宿主零改动；跨宿主时作为 MCP 长任务工具暴露出（§12.6） | 直接绑 Temporal | 采纳 |
| TDR-H05 | 模型接口走 **LiteLLM**（三档路由，`fast/default/strong`）；第三方宿主自带路由时复用宿主路由 | 满足"模型不锁定"（对应 TechDesign TDR-010）；跨宿主时不自带重复路由 | 厂商 SDK | 采纳 |
| TDR-H06 | **多租户 = 编排核心之上的额外维度（tenant_id）**，不改变 DAG/回退语义 | 自研核心天然支持"多租户仅增加一个维度"；SharedState/存储/评估加 tenant 键即可，核心逻辑复用 | 为多租户重写编排核心 | 采纳 |
| TDR-H07 | **SaaS 化演进方向**：DurableProvider 按租户 namespace（Temporal）+ 每租户隔离沙箱（对标 Manus/E2B）+ Kubernetes 弹性 + LiteLLM 租户配额计量 | 与 Manus 类平台底座逻辑同构（沙箱隔离 + 配额计费 + durable + 弹性），薄编排不阻碍 SaaS（详见 §9） | 绑定厂商 Agent 平台（AgentKit/Claude SDK） | 采纳 |
| TDR-H08 | **范式：Skill / 插件体系，非 sub-agent 网络**。领域能力封装为 Skill，由宿主 Agent（用户自有 Harness 或本项目薄宿主）调度 | 与 Claude Code / Codex / DeepSeek Harness 等业界主流同构；33 个领域"Agent"对应 33 个领域 Skill（§1.1、§6.1） | 常驻 sub-agent DAG 协作 | 采纳 |
| TDR-H09 | **能力包（UE MCP Server + Toolset + Skill）为第一公民；宿主（自研薄宿主 / 第三方 Harness）可替换** | 聚焦开发 Tool / Skill / Prompt，避免绑定任一运行时；完整能力包注入路径仅限 A/B（§11）与引流蒸馏子集（§12） | 绑定单宿主/必选自研宿主 | 采纳 |
| TDR-H10 | **Skill 以宿主无关 Common Spec 编写，经 `distiller.py` 蒸馏 + `orchestrator/importers/` 注入宿主；自研 DAG 语义在第三方宿主以「能力注记」落法，而非其执行引擎** | 能力包可移植性优先；跨宿主（引流子集）一致性与差异化（长任务/单写入者/分区锁）下沉到 MCP/Toolset 层（§12.3/12.4/12.6）；完整能力包不走注入 | 为每宿主各写一套私有 Skill | 采纳 |
| TDR-H11 | **商业交付三形态：纯 SaaS（A）为主推、私有化黑盒（B）可支持、Skill 注入（C）仅引流/体验**；完整能力包不出境，黑盒以「运行系统」交付而非「资产文件」 | 付费形态下能力包（MCP + Toolset + Skill + 数据）不出境；真价值放进客户端碰不到的层 + 计量/License + 数据飞轮 + 合规边界兜底（§11） | 向客户交付完整源码/资产 | 采纳 |
| TDR-H12 | **能力蒸馏工具 `distiller`**（`orchestrator/distiller.py`）+ **Skill 五级划分（Tier 0–4）+ 最小可用版（MVP-subset = Tier ≤2 + Tier 0）**：按 `tier`/`distill_visibility` 把完整能力包裁剪为对外 Demo/体验子集；Tier 3/4 默认 hidden | 让引流（C）既能展示价值又不泄露核心；每个 Skill 按价值定级，可稳定裁剪出最小可用版；`importers/` 只消费蒸馏子集（§11.3） | 直接把完整能力包作 Demo | 采纳 |

> 以上 TDR 为 Agent Harness 底座的正式决策记录，作为 TechDesign §13 编排相关决策的**一致补充**（对应其 TDR-012 编排自研 + Durable 外挂，新增 TDR-H09/H10 能力包第一公民与跨宿主，TDR-H11/H12 商业交付形态与能力蒸馏）。

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
- 跨宿主引流子集（跨 §12）：Claude Code Skills（Anthropic Skills 规范，repo-local `SKILL.md`）；Codex `AGENTS.md` 约定；OpenClaw 网关 / Skill 插件与 MCP 注入（docs.openclaw.ai）；Hermes 开源宿主（Gateway + Skill + worker，github.com/NousResearch/hermes-agent）；DeepSeek Harness 以 Cordis 插件框架加载 Skill 并可挂 Claude Code / Codex 为 subagent（github.com/dshbox/cordis）；Anthropic Skills 规范社区化 marketplace：github.com/bencium/bencium-marketplace、github.com/furiosa-ai/agent_skills；MCP 标准为实现跨宿主工具平面的统一通道：modelcontextprotocol.io
- 商业交付与资产保护（§11）：私有化黑盒镜像 / 能力蒸馏 / License 计量参考：SaaS + 私有化混合交付的资产不出境模式；LLM 能力包「可执行即可被运行时套录」的天花板（逆向窗口）；E2B / Firecracker 沙箱化执行隔离（前文 Manus 条目）作为黑盒容器隔离参考；数据/语料飞轮锁定（golden 样本、RAG 语料、评估基准不放行）。

---

*本文档为 Agent Harness（编排/运行时底座）选型的唯一事实源。与 TechDesign 不一致处，以本文档为准。*
