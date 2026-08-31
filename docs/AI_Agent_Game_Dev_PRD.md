# 产品需求文档

项目代号：AI Agent 驱动的高品质游戏开发  
版本：v0.2 定稿  
前置文档：[项目背景与技术选型](./project-background-and-tech-selection.md)、[架构方案](./AI_Agent_Toolchain_Architecture-unreal.md)

> 本文 PRD 聚焦**多 Agent 游戏开发系统（产品本体）**的功能、非功能、里程碑与验收需求。用于端到端验证系统能力的"参考游戏"仅在测试/验证环节作为产出物引用，其选型、规格、内容与验收标准统一维护在 [参考游戏（验证载体）](./reference-game.md)。

---

## 目录

- [1. 产品愿景与定位](#1-产品愿景与定位)
- [2. 目标用户](#2-目标用户)
- [3. 产品范围](#3-产品范围)
- [4. 功能需求](#4-功能需求)
- [5. 非功能性需求](#5-非功能性需求)
- [6. 技术约束](#6-技术约束)
- [7. 里程碑与交付](#7-里程碑与交付)
- [8. 风险登记册](#8-风险登记册)
- [9. 验收标准](#9-验收标准)
- [附录 A：产品决策记录](#附录-a产品决策记录)
- [参考游戏（验证载体）→ 单独文档](./reference-game.md)

---

## 1. 产品愿景与定位

### 1.1 愿景

构建一套开放、可治理、不绑定模型的 AI 多 Agent 游戏开发系统。它本身不是一个游戏，而是一条由 AI Agent 驱动的游戏研发流水线——让一个小团队以接近 3A 的品质标准，从市场调研、概念设计一路到场景搭建、玩法实现、测试发布的完整闭环，开发出高品质游戏。

### 1.2 产品定位

**产品本体**：一套运行在 UE 5.8 之上的 AI 多 Agent 开发系统。包含 33 个领域与评估 Agent（覆盖市场调研、概念设计、关卡与角色设计、数值经济、场景生成、玩法编程、动画、灯光、音频、UI、性能剖析、质检与用户立场评估、打包全流程）、12 个自研 Toolset、一个编排层（Orchestrator）和一套安全治理体系。使用者通过自然语言或结构化指令驱动它，Agent 产出可复现、可版本管理、可回滚的构建脚本，最终由 UE 编译生成游戏资产。

**落地验证方式**：为避免空转，系统绑定一个"参考游戏"（见 §1.3）作为端到端的验证载体——用它来证明这套工具链真的能做出一个可玩的、高品质的游戏。参考游戏是手段，不是产品本身的收入来源。

**核心竞争力**：
- 自研 Toolset + 自研编排层（L2/L4），源码可控，模型不绑架
- 33 个 Agent 覆盖从市场调研到打包发布及上线后复盘再开发的完整工业管线
- 开放标准（MCP）驱动 UE，可平滑迁移 UE6
- 安全治理：文件沙箱、风险分级审批、Git 钩子、自动驾驶式回滚

### 1.3 参考游戏（验证载体）

一个用于验证工具链能力的参考游戏。它本身不是产品，只是展示"这套 Agent 系统能做出什么"的落地 Demo 与压力测试。其具体选型、规格、内容需求、性能与验收标准均不在本 PRD 内展开，统一维护在 [参考游戏（验证载体）](./reference-game.md)；PRD 仅在测试/验证与里程碑环节将其作为端到端验收产出物引用。

---

## 2. 目标用户

产品是 AI 多 Agent 开发系统，目标用户是**系统的使用者**（直接客户）。系统产出的验证载体（参考游戏）的受众画像仅用于端到端品质验收，属 [参考游戏（验证载体）](./reference-game.md) 的内容，不在目标用户范畴内展开。

### 2.1 系统使用者（直接用户）

| 画像 | 描述 | 核心需求 |
|---|---|---|
| AI 技术专家（本项目决策者与首批使用者） | 编排 Agent、定制 Toolset、监控生成质量 | 高效可控的生产力、可治理的流程、可量化的产出 |
| 独立/小团队开发者 | 没有完整的美术、策划、程序团队，靠少数人做高品质游戏 | 用自然语言驱动完成场景、玩法、测试的自动化生成 |
| 未来扩展的开发者 | 基于本工具链开发其他 UE 项目的团队 | 可复用的通用管线、模型可替换、UE6 迁移平滑 |

---

## 3. 产品范围

### 3.1 范围内

- **AI 多 Agent 开发系统（产品本体）**：L2 自研 Toolset（12 个）+ L3 领域与评估 Agent（33 个）+ L4 编排层 + 安全治理，完整闭环
- **策略与研究组**：S1–S6，市场调研、竞品分析、玩法设计、商业推演、技术评估、创意方向，产出《游戏概念提案》
- **场景生成管线**：PCG 驱动的生物群系地形/植被/遗迹/交互物程序化生成
- **玩法代码生成**：Verse/C++ 交互逻辑、状态机、AI 行为
- **外部资产管线**：纹理/3D/音频生成 → 质检 → 导入 UE → Nanite 适配
- **自动化测试与评审**：PIE 自动化测试、截图比对、代码审查、评分回退循环
- **端到端验证产出物**：绑定一个参考游戏（规格见 [参考游戏文档](./reference-game.md)）作为端到端验证产出物，其具体内容范围不在此展开

### 3.2 范围外（当前版本）

- 参考游戏自身的内容范围（商业化发行 / 多人联网 / 完整叙事 / 本地化等）：见 [参考游戏（验证载体）](./reference-game.md)
- 工具链对外销售/授权：当前对内自用，商业化授权模式后续再定
- 移动端适配：不针对 iOS/Android

---

## 4. 功能需求

### 4.1 AI Agent 工具链系统

#### 4.1.1 MCP 工具平面（L2）

基于 UE 5.8 MCP + Toolset Registry，构建 12 个自研 Toolset，提供 Agent 可发现、可调用的结构化工具接口。所有 Tool 返回结构化 JSON，函数静态无状态，一个 Tool 一个职责，失败不抛异常。

| 子功能 | 职责 | 优先级 |
|---|---|---|
| F-TOOL-01.1 ProjectToolset | 命名规范校验、目录结构检查、资产审计 | P0 |
| F-TOOL-01.2 PCGToolset | 按 JSON 规格生成/修改 PCG 图、异步触发生成、读取结果 | P1 |
| F-TOOL-01.3 ArtPipelineToolset | 导入外部生成资产（纹理/网格/材质）、配置 Nanite、创建材质实例 | P1 |
| F-TOOL-01.4 BuildToolset | Live Coding 编译、全量编译、启动 PIE、自动化测试 | P1 |
| F-TOOL-01.5 SafeguardToolset | 文件沙箱边界检查、操作风险分级、审批门禁、Git 钩子 | P0 |
| F-TOOL-01.6 LightingToolset | 放置/调整光源、配置 PostProcess Volume、Lightmass 烘焙 | P1 |
| F-TOOL-01.7 AudioToolset | 放置环境音/音效、配置 Sound Cue/Attenuation | P2 |
| F-TOOL-01.8 UIToolset | 生成/修改 UMG Widget、绑定 DataTable、字体/颜色规范校验 | P2 |
| F-TOOL-01.9 DataToolset | CSV 导入、DataTable 资产创建、行数据校验 | P2 |
| F-TOOL-01.10 ProfilerToolset | 触发 GPU/CPU Profiler、解析 Unreal Insights 输出、生成超标报告 | P2 |
| F-TOOL-01.11 PlaytestToolset | 录制游玩轨迹 / 多参数回放 / 游玩指标（死亡/节奏/收集/卡点）/ 冒烟自证 | P2 |
| F-TOOL-01.12 BenchmarkToolset | 竞品/市场数据刷新与对齐（供横向对比与后验，喂 E6/UX） | P2 |

#### 4.1.2 安全与治理

UE MCP 没有认证、串行执行、Agent 可能改错关卡或重复创建对象。需要自建安全层：

| 子功能 | 说明 | 优先级 |
|---|---|---|
| F-TOOL-02.1 File Sandbox | `no_touch_zones`：`/Engine/` 和核心框架目录只读；Agent 仅写 `/Game/Generated/` | P0 |
| F-TOOL-02.2 Risk Gating | 三级审批：`read_only` 自动放行 / `mutating` 轻量审批 / `destructive` 强制人工确认 | P0 |
| F-TOOL-02.3 版本控制钩子 | Agent 每次改动后自动 commit + diff 报告，支持一键回滚 | P0 |
| F-TOOL-02.4 超时与隔离 | Tool 调用 30s 超时；disposable sandbox map 做初次验证 | P0 |

#### 4.1.3 领域智能体（L3）

**33 个角色专精 Agent**，覆盖从市场调研到打包发布、再到上线后复盘与二次开发的完整工业管线，通过 SharedState（结构化 JSON）通信。按阶段分为**策略与研究 / 预生产 / 生产 / 验证与交付 + 评估组**五组：生产型 Agent 负责把游戏做出来，评估型 Agent（E1–E6 + UX + W1/TA 评价）负责站在用户与市场立场批判性地找问题、保证品质与商业可行。

##### 策略与研究组（绿光阶段）

在确定游戏方向之前，先做足功课——市场分析、竞品研究、玩法概念验证、商业推演、技术可行性评估。这组 Agent 的输入是模糊的方向，输出是结构化的《游戏概念提案》，供人工审阅和选择。

| Agent | 核心能力 | 优先级 |
|---|---|---|
| S1 Market & Audience Analyst | 拉取市场数据（品类趋势/收入/用户画像）+ 市场规模估算 + 受众分析 | P1 |
| S2 Competitive Intelligence | 扫描竞品 → 生成竞品矩阵 + 特征对比 + 差异化机会分析 | P1 |
| S3 Game Design Strategist | 基于市场缺口提出 2–3 套核心玩法方案 + 机制设计 + 玩家体验模型 | P1 |
| S4 Business & Platform Strategist | 收入模型推演 + 平台策略 + 定价方案 + 18 个月盈亏预测 | P1 |
| S5 Technical Feasibility Analyst | 技术可行性评估 + 范围估算 + 关键风险识别 + 引擎能力匹配 | P1 |
| S6 Creative Direction Strategist | 世界观框架 + 叙事方向 + 视觉/音频策略 + 情绪板生成 | P1 |

提案由人工审阅后，选中的方向进入预生产——结构化数据直接注入 Director 的 GDD 流程。

##### 预生产组——在动任何资产之前，先确定做什么和长什么样：

| Agent | 核心能力 | 优先级 |
|---|---|---|
| ① Director | 解析用户意图 → 生成 GDD 结构化 JSON + 任务拆解 | P2 |
| ② Concept Artist | 生成风格指南 + 参考图 + 视觉规范（色调/材质语言/光照 mood） | P2 |
| ③ Level Designer | 生成 Blockout 规格（玩家动线/POI 坐标/空间分区/节奏曲线） | P1 |
| ④ Data Agent | 玩法数值规格 → CSV → DataTable 资产创建与校验 | P2 |
| W1 Writer | 剧情/对白/情境文本 + 文案资产（任务目标/物品说明/关卡提示） | P2 |
| ND System / Numerical Designer | 成长曲线 / 资源经验产出 / 战斗数值平衡 / 经济回收规格 | P1 |

> **ND 与 ④ 的分工**：④ Data Agent 是"数值录入与资产化"（把已定规格写成 CSV、建 DataTable）；ND 才是"数值/经济设计决策者"。ND 产出数值设计规格（喂给 ⑨ Gameplay 与敌人/Boss 设计），④ 负责落地成引擎可读 DataTable，两者不可混用。

> **垂直切片（Vertical Slice）**：正式全量生产前，必须经历一轮核心玩法垂直切片——Director 从 GDD 裁出一段最小的可玩循环（探索→收集→解谜→战斗），由 Scene/PCG、Gameplay、角色类 Agent、ND 先做到"手感成立"。这是玩法风险对冲，避免全量内容做完才发现核心玩法无趣（对标大厂 prototype / vertical-slice gate）。通过后才进入全量生产。

生产组——实际产出场景、玩法、资产：

| Agent | 核心能力 | 优先级 |
|---|---|---|
| ⑤ Asset Retriever | 检索 Fab/Quixel/本地库资产，返回结构化引用列表 | P1 |
| ⑥ Scene/PCG | 基于 Blockout + 风格指南生成 PCG 图 + 异步触发生成 + 截图验证 + 迭代优化 | P1 |
| ⑦ 3D Asset Generator | 在风格指南约束下调用外部 API 生成纹理/网格/材质 → 质检 → 导入 UE | P3 |
| ⑧ Lighting | 根据风格指南放置/调整光源 + PostProcess Volume + 截图验证氛围 | P1 |
| ⑨ Gameplay | 生成 Verse/C++ 玩法模块 + 编译 + 错误修复 | P2 |
| ⑩ Audio | 放置环境音 + SFX + 配置 Sound Cue/Attenuation | P2 |
| ⑪ UI | 生成 UMG Widget（HUD/交互提示/状态面板）+ 绑定 DataTable | P2 |
| TA Technical Artist | 主材质/shader/渲染规范 + 生成资产技术校验 + 性能优化建议 | P1 |
| PC Player Character Designer | 玩家角色设定（体感/动作风格/成长/手感 KPI），供 Gameplay/动画实现 | P1 |
| EB Enemy & Boss Designer | 敌人/Boss 白皮书（行为/攻击模式/数值/难度曲线，对齐 ND 数值基线） | P1 |
| AN Animation Agent | 动作状态机 + 动画实现 + 外购动画技术质检（IK/locomotion/根运动） | P1 |

验证与交付组——全部产出进验证闭环：

| Agent | 核心能力 | 优先级 |
|---|---|---|
| ⑫ Profiler | 运行 GPU/CPU Profiler + 解析 Unreal Insights 输出 + 生成超标报告 | P2 |
| ⑬ Reviewer/QA | 代码审查 + 自动化测试 + PIE 截图比对 + 评分 + 缺陷报告 | P2 |
| ⑭ Build Agent | 通过评审后触发平台打包（UBT）+ 生成可执行包 | P3 |

评估组——**用户立场的批判审验，与生产/工程评审解耦**：

| Agent | 核心能力 | 优先级 |
|---|---|---|
| E1 Experience Auditor | 批判关卡节奏/动线/挫败与成就感曲线，输出体验痛点清单 | P2 |
| E2 Content Critic | 批判美术风格/场景氛围/音频一致性/UI 可用性，找素材出戏点 | P2 |
| E3 Gameplay / Fun Auditor | 批判核心玩法循环/战斗手感/成长曲线/数值平衡，找机制无聊点/手感问题 | P2 |
| E4 Design & Economy Judge | 批判关卡结构/解谜/收集奖惩/时间经济，找关卡与收集鸡肋点 | P2 |
| E5 Monetization & Market Fit | 批判定价/内容量/平台/回收模型是否成立 | P2 |
| E6 Benchmark & Horizontal | 与现有游戏横向全维度对比 → 对照评分 + 受欢迎度预测 + GO/NO-GO/PIVOT | P2 |
| UX Playtest Researcher | 收录游玩轨迹 → 量化"玩家在哪卡住/放弃"，供 E 组与生产定位 | P2 |

> 评估组全部**只读、`strong` 模型**，只写 `shared_state/eval/`，永不写生产产物区——防止"被评估方污染评估方"。评估可在任意里程碑触发（可玩切片/区域完成/数值改版），不是交付末尾的一次性检查。W1（叙事内容评价）与 TA（技术美术评价）兼具生产与评价职能，评估定位见上表。

Agent 间通信全部走 SharedState JSON Schema，不传自由文本。每条消息携带 `version`（semver）和 `parent_hash`（SHA-256）。Orchestrator 维护依赖 DAG，上游变更自动标记下游 stale，下游 diff 后决定是否重跑。传播深度限制在 3 层。多 Agent 并发写同一关卡时按坐标范围分区，共享区单独协调。**评估组作为 DAG 的只读消费者**：评估结果写入 `eval/*`，不回写生产区，因此不会自行触发下游生产 stale；它通过定向回退（见 §4.1.4 回退规则）把结论送回具体的生产 Agent。

#### 4.1.4 编排层（L4）

编排核心采用**自研最小编排状态机**（asyncio，DAG 依赖传播 + 回退 + 空间分区），长任务持久化经统一 `DurableProvider` 接口外挂成熟引擎（Temporal / Prefect / SQLite），不绑定任何 Agent 图框架（详见 [Agent Harness 选型与技术设计](./agent-harness-selection-and-design.md)），搭配 MCP Client。负责：

| 子功能 | 说明 | 优先级 |
|---|---|---|
| 任务编排 | 顺序 / 条件分支 / 循环回退（**工程分 / 体验分 / 商业分任一 < 70 或含 critical bug → 回退，最多 3 次**） | P2 |
| 依赖 DAG 引擎 | 维护 Agent 间有向无环依赖图；上游变更自动标记下游 stale；传播深度 ≤ 3 层 | P2 |
| RAG Grounding | 检索 UE 官方文档 + 项目规范 + 引擎源码，注入 Agent 上下文 | P1 |
| 记忆分层 | 短期（对话）→ 工作记忆（SharedState）→ 长期（向量库，已验证代码索引 + 后验预测偏差） | P2 |
| 模型路由 | 简单任务用小模型（Haiku/Flash）、复杂任务用大模型（Opus/Pro）；模型可替换 | P2 |
| 人工卡点 | 不可逆操作（构建/发布）强制人工审批；生成资产入库前人工过审；**GO/NO-GO/PIVOT 立项裁决进人工审批** | P0 |

> **回退触发规则**：工程评审（⑬ Reviewer）给"工程分"，评估组（E1–E6 + UX）给"体验分"与"商业分"。三者**任一 < 70 或含 critical 缺陷**即定向回退到对应的生产 Agent（E3 可玩性低 → Gameplay/PC/EB；E1 体验差 → ③ Level Designer；E5/E6 商业不成立 → S4/ND），最多 3 次，仍失败升级人工。评估结论带 `link_back_to` 字段定位目标 Agent。

---

### 4.2 参考游戏项目内容需求

**参考游戏（验证载体）本身的具体内容需求（PCG 场景 / 核心玩法 / 资产管线 / 关卡 Blockout / 灯光后处理 / 音频 / UI / 性能剖析）不属于产品本体的功能需求，不在本 PRD 内展开。** 这些内容由生产 Agent 落地，其需求规格统一维护在 [参考游戏（验证载体）§5](./reference-game.md#5-参考游戏项目需求) 中。

工具链为参考游戏提供的通用能力——MCP 工具平面（PCGToolset、ArtPipelineToolset、BuildToolset 等）、编排层、评估与回退闭环——均在 §4.1 中定义；参考游戏内容只是这些通用能力的**应用实例**，不新增独立功能需求。

---

## 5. 非功能性需求

### 5.1 系统性能（工具链自身）

| 指标 | 目标值 | 度量方式 |
|---|---|---|
| 冷编译时间 | 增量 Live Coding < 30s；全量编译异步，不阻塞 Agent 循环 | 计时 |
| PCG 生成时间 | 单关卡（500 资产）< 60s | 计时 |
| Agent Tool 调用 | 单次 < 10s；超时 30s | 计时 |
| 端到端流水线 | 模糊需求→概念提案 < 4h；提案→可玩关卡 < 8h | 计时 |
| 人工介入率 | 完整流程人工干预 < 20% 操作步骤（P4 目标） | 统计 |

### 5.2 参考游戏性能（系统产出物的品质验证）

参考游戏用于验证工具链产出质量，其性能指标（帧率等）详见 [参考游戏（验证载体）§6](./reference-game.md#6-参考游戏性能需求)，不在此重复。

### 5.3 安全

| 指标 | 要求 |
|---|---|
| 沙箱边界 | Agent 无法写入 `/Engine/`、核心框架目录 |
| 网络隔离 | MCP 仅绑定 `127.0.0.1`，不暴露到局域网 |
| 审批覆盖 | 所有 `destructive` 操作 100% 经人工确认 |
| 回滚能力 | 每次 Agent 改动后 ≤ 1 分钟内可一键回滚 |

### 5.4 可维护性

| 指标 | 要求 |
|---|---|
| 模型可替换 | 更换 LLM 提供商 ≤ 1 个配置文件变更 |
| Toolset 版本适配 | MCP API 变更时，适配层修改 ≤ 1 个文件 |
| 文档覆盖率 | 每个 Toolset 公开方法 100% 有 docstring + JSON Schema 自动生成 |

### 5.5 可扩展性

| 指标 | 要求 |
|---|---|
| 新增 Agent | 新增一个领域 Agent ≤ 定义 Schema + 注册 Toolset，无需改编排层 |
| 新增 Toolset | 新增一个 Toolset ≤ 实现 ToolsetDefinition 子类 + 注册 |
| UE6 迁移 | L2/L3/L4 代码复用率 ≥ 80% |

---

## 6. 技术约束

以下约束从项目背景和架构文档继承，PRD 不做二次决策：

| 约束 | 来源 |
|---|---|
| 引擎：Unreal Engine 5.8 LTS，完整源码分支管理 | 背景文档 |
| AI 协议：MCP + Toolset Registry，开放标准 | 背景文档 |
| 模型：不锁定，任选 Claude/GPT/开源/自建微调 | 背景文档 |
| Agent 产出物：构建脚本，不直接捏造 .uasset | 架构文档 §0 |
| 并发控制：单写入者 + 空间分区 | 架构文档 §3.3 |
| 版本控制：Git，Agent 改动自动 commit | 架构文档 §3.3 |
| 引擎授权：百万美元内免费；参考游戏的 UE 发行享有 EGS 优惠（非产品本体收入） | 背景文档 |

---

## 7. 里程碑与交付

| 阶段 | 周期 | 目标 | 关键交付 |
|---|---|---|---|
| P0 地基 | 第 1–4 周 | MCP 打通、首个 Toolset、安全体系 | ProjectToolset + SafeguardToolset 可用；Agent 能安全改关卡并回滚 |
| P1 核心工具链 | 第 5–12 周 | PCG + Level Designer + Lighting + Asset Retrieval + Build/Test + RAG | Level Designer 产出 Blockout；PCG 图可由 Agent 生成并执行；灯光自动化；编译测试自动化 |
| P2 策略与研究组 | 第 13–18 周 | S1–S6 Strategy & Research Agent 上线；首份《游戏概念提案》产出 | 市场报告 + 竞品矩阵 + 玩法方案 + 商业模型 + 技术评估 + 创意方向全部自动化生成 |
| P3 多智能体 | 第 19–30 周 | 33 个 Agent + Orchestrator + 依赖 DAG 联调；**垂直切片**；评估组 + 回退闭环 | 端到端流水线跑通（提案→垂直切片→可玩关卡）；变更传播与评估触发自动生效；产出参考游戏可玩切片（规格见 [参考游戏文档](./reference-game.md)） |
| P4 实战打磨 | 第 31–42 周 | 外部生成模型接入、质量控制、评估组上线；以参考游戏完整关卡为验证产出物 | 完整关卡由 AI 驱动生成；评估组多画像批判 + 横向对标通过；人工介入率 < 20% |
| P5 发布准备 | 第 43–52 周 | 优化、打磨、平台适配 | 参考游戏产出可提交包体（验证工具链发布能力，见 [参考游戏文档](./reference-game.md)） |
| P5+ 运营与后验 | 上线后 | 后验评估（立项预测 vs 实际）、运营期平衡调整、二次开发 | 预测偏差写回长期记忆改进立项；热更新/平衡调整自动触发 |
| P6 UE6 迁移 | 2027+ | Verse + Scene Graph 适配 | 核心逻辑迁 Verse；MCP 架构复用 ≥ 80% |

验收标准见 §9。

---

## 8. 风险登记册

| ID | 风险 | 影响 | 概率 | 缓解措施 | 负责人 |
|---|---|---|---|---|---|
| R-01 | MCP 仍 Experimental，API 变更 | 高 | 中 | Toolset 加版本适配层；锁定 5.8 LTS | AI 技术专家 |
| R-02 | 蓝图二进制，Agent 无法直接读写 | 中 | 高 | 坚持构建脚本路径；Python/C++ 反射层 | AI 技术专家 |
| R-03 | 冷编译慢（50–70min）打断反馈环 | 中 | 高 | 优先 Live Coding；异步编译队列；增量编译 | AI 技术专家 |
| R-04 | Game Thread 串行，不能并发写 | 中 | 高 | 编排层单写入者 + 空间分区 | AI 技术专家 |
| R-05 | 工具幻觉，复杂 API 调用出错 | 高 | 中 | RAG grounding + 设计模式约束 | AI 技术专家 |
| R-06 | 外部生成模型 API 不稳定/下架 | 中 | 中 | 多模型供应商备选；本地缓存已生成资产 | AI 技术专家 |
| R-07 | 无认证 / 本地仅，安全风险 | 高 | 低 | 本机使用 + 沙箱 + 网络隔离 | AI 技术专家 |
| R-08 | AI 生成资产风格不一致 | 中 | 中 | Concept Artist Agent 产出风格指南作为约束；评测 Agent 质检拒绝率 > 90% | AI 技术专家 |
| R-09 | UE6 迁移成本超预期 | 中 | 低 | 核心逻辑提前往 Verse 靠；MCP 架构层与引擎解耦；P4 前做兼容性 PoC | AI 技术专家 |

---

## 9. 验收标准

### 9.1 P0 地基验收

| # | 验收项 | 方式 | 通过标准 |
|---|---|---|---|
| AC-P0-01 | MCP 三件套插件启用 | 手动检查 | `ModelContextProtocol` + `ToolsetRegistry` + `AllToolsets` 均启用，`http://127.0.0.1:8000/mcp` 响应 |
| AC-P0-02 | ProjectToolset 注册成功 | 自动化测试 | MCP Client 调用 `list_tools`，返回全部工具及 JSON Schema |
| AC-P0-03 | 沙箱生效 | 自动化测试 | Agent 尝试写入 `/Engine/` → 返回 `sandbox_denied` |
| AC-P0-04 | 审批门禁分级生效 | 自动化测试 | `read_only` 自动放行；`mutating` 触发审批；`destructive` 阻塞等人工确认 |
| AC-P0-05 | Git 钩子自动 commit | 自动化测试 | Agent 执行 `mutating` 操作后自动生成 commit（含 diff）+ 可一键 revert |
| AC-P0-06 | 最小闭环 | 端到端测试 | Agent 执行"在关卡中放置一个 Cube"→ 关卡中出现 Cube → 回滚 → Cube 消失 |

### 9.2 P1 核心工具链验收

| # | 验收项 | 方式 | 通过标准 |
|---|---|---|---|
| AC-P1-01 | PCGToolset 生成 PCG 图 | 自动化测试 | 给定 JSON 规格（含 Surface Sampler + Mesh Spawner 参数），Agent 生成合法 PCG Graph 资产 |
| AC-P1-02 | PCG 异步生成 | 自动化测试 | 调用 `UPCGGenerateGraphAsync` → 关卡中出现生成结果 → `GetGeneratedGraphOutput` 返回正确数据 |
| AC-P1-03 | BuildToolset 编译 | 自动化测试 | Agent 提交 Verse/C++ 代码 → Live Coding 编译成功 → 无编译错误 |
| AC-P1-04 | PIE 自动化测试 | 自动化测试 | 启动 PIE → 运行自动化测试脚本 → 返回通过/失败结果 + 截图 |
| AC-P1-05 | ArtPipeline 导入 | 自动化测试 | 外部生成的纹理/网格 → 导入 UE → 自动配置 Nanite → 材质实例创建 |
| AC-P1-06 | RAG 知识库可用 | 手动验证 | Agent 调用 UE API 时，检索到对应官方文档片段并正确使用 |
| AC-P1-07 | Level Designer 产出 Blockout | 自动化测试 | 给定 GDD 任务 JSON → 产出 Blockout 规格（含 waypoints/zones/pacing_curve），坐标在关卡范围内 |
| AC-P1-08 | Lighting 自动布光 | 自动化测试 | 给定 PCG 场景 + 风格指南 → 自动放置主光源 + PostProcess Volume → 截图亮度/色温在风格指南范围内 |

### 9.3 P2 策略与研究组验收

| # | 验收项 | 方式 | 通过标准 |
|---|---|---|---|
| AC-P2-01 | Market Analyst 产出市场报告 | 自动化测试 | 给定品类关键词 → 产出报告（含 3 年收入趋势/用户画像/TAM 估算），引用 ≥ 5 个数据源 |
| AC-P2-02 | Competitive Intelligence 产出竞品矩阵 | 自动化测试 | 给定目标品类 → 扫描 ≥ 15 款竞品 → 生成特征对比矩阵 + 差异化缺口分析 |
| AC-P2-03 | Game Design Strategist 产出玩法方案 | 手动验证 | 基于市场缺口提出 ≥ 2 套核心玩法方案，每套含玩法循环图和机制概要 |
| AC-P2-04 | Business Strategist 产出商业模型 | 自动化测试 | 对每套玩法方案输出定价策略 + 18 个月盈亏推演 + 平台分成对比 |
| AC-P2-05 | Technical Feasibility 产出评估报告 | 手动验证 | 对每套方案输出技术可行性结论 + 关键风险清单 + 范围估算 |
| AC-P2-06 | Creative Direction 产出世界观框架 | 手动验证 | 产出含世界观概述 + 叙事基调 + 视觉情绪板 + 音频策略的创意方向文档 |
| AC-P2-07 | 概念提案完整生成 | 端到端测试 | 模糊方向输入 → 6 个 Agent 协同 → 产出 15–20 页《游戏概念提案》，人工评审通过 |

### 9.4 P3 多智能体验收

| # | 验收项 | 方式 | 通过标准 |
|---|---|---|---|
| AC-P3-01 | 端到端流水线 | 端到端测试 | 输入自然语言需求 → Director 拆解 → 各 Agent 执行 → 关卡可玩，全程无需人工干预 |
| AC-P3-02 | 闭环回退 | 端到端测试 | Reviewer 评分 < 70 → 自动回退对应 Agent 修复 → 重编译 → 重新评分，最多 3 次 |
| AC-P3-03 | SharedState 通信 | 代码审查 | 所有 Agent 间通信使用 JSON Schema，无自由文本传递 |
| AC-P3-04 | 空间分区 | 端到端测试 | 2 个 Agent 并发写不同坐标范围 → 无冲突 → 关卡完整 |
| AC-P3-05 | 端到端产出参考游戏可玩切片 | 手动游玩 | 通过参考游戏可玩切片验证工具链端到端产出能力，通关标准见 [参考游戏文档 §7](./reference-game.md#7-验收与交付标准) |
| AC-P3-06 | 依赖 DAG 变更传播 | 自动化测试 | 上游 Agent 修改 SharedState → Orchestrator 标记下游 stale → 下游 Agent 收到通知并 diff 响应 |
| AC-P3-07 | UI Agent 生成 HUD | 自动化测试 | 给定玩法规格 + DataTable → 生成 UMG Widget（含收集计数 + 交互提示）→ PIE 中正确显示 |
| AC-P3-08 | Audio Agent 放置音效 | 自动化测试 | 给定场景描述 → 放置环境音 + 交互 SFX → PIE 中可听到，Attenuation 正确 |
| AC-P3-09 | Profiler Agent 报告 | 自动化测试 | 运行 Profiler → 输出超标报告（含帧率/draw call/资产密度）→ 标记超标区域坐标 |
| AC-P3-10 | Concept Artist 风格指南 | 手动验证 | 给定 GDD 美术描述 → 产出风格指南（含参考图/色调/材质语言），人工评审通过 |
| AC-P3-11 | Data Agent 管线 | 自动化测试 | CSV 文件 → 导入 DataTable → Gameplay Agent 正确读取数值 |

### 9.5 P4 实战打磨验收

| # | 验收项 | 方式 | 通过标准 |
|---|---|---|---|
| AC-P4-01 | 外部生成资产接入 | 端到端测试 | 文本 prompt → 外部生成纹理/3D 网格 → 质检 → 自动导入 UE（验证 ArtPipeline 能力；产出标准见 [参考游戏文档 §7](./reference-game.md#7-验收与交付标准)） |
| AC-P4-02 | 质量控制（评测 Agent） | 自动化测试 | 评测 Agent 拒绝不符合风格/规范的资产（准确率 > 90%） |
| AC-P4-03 | 人工介入率 | 统计 | 完整关卡生成过程中，人工干预次数 < 总操作步骤的 20% |
| AC-P4-04 | 资产元数据完整 | 审计 | 100% 生成资产可追溯到来源 prompt、模型版本、license |

---

## 附录 A：产品决策记录

以下仅保留**多 Agent 开发系统（产品本体）**的形态决策。参考游戏（验证载体）的选型决策（品类、平台、美术风格、时长、多人/本地化、对标作品等）已迁至 [参考游戏（验证载体）§8](./reference-game.md#8-产品决策记录参考游戏部分)。

| # | 事项 | 决策 | 依据 |
|---|---|---|---|
| 1 | 产品形态 | **AI 多 Agent 开发系统**（本体），参考游戏为其验证载体 | 多 Agent 系统是核心 IP（L2 Toolset + L4 编排层），参考游戏证明其产出能力 |

---

*PRD v0.2 · 定稿 · 所有产品决策已确认*