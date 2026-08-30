# 项目背景与技术选型

这份文档记录引擎选型的决策过程，作为 PRD 和架构方案的前置上下文。结论先行：选 Unreal Engine 5.8 LTS。

---

## 一、我们要解决什么问题

一个 AI 技术背景的小团队，想做高品质游戏，而且必须对技术资产有完全掌控权。这件事的核心矛盾是：人少，但品质要求不低。

解法不是多招人，而是把 AI Agent 当作工程团队的一部分——让 Agent 承担场景搭建、玩法实现、测试验证这些重复性高的工作，人把精力留给真正需要判断力的地方。

这个定位决定了引擎选型的四条硬杠杠：

- 源码必须能拿到、能改、能重编译，不然引擎级的 AI 改造无从谈起
- 资产管线必须可控、可复现、可进版本管理
- 要有成熟的程序化生成框架，不能自己从零搭
- AI 工具链必须开放，不能绑定在任何一家模型供应商上

Unity 的强项——Asset Store 现成资源、C# 上手快、移动端生态——恰好跟我们的诉求错位。UE 的源码开放、PCG 闭环、MCP 架构级入口，反而精准命中。

---

## 二、引擎对比

| 对比维度 | Unreal Engine | Unity | 对我们的意义 |
|---|---|---|---|
| 源码访问 | 完整 C++ 源码，GitHub 免费 | C# 仅为只读 Reference Source | 决定性——必须能改引擎 |
| 修改/重编译 | 可定制、调试、改引擎 | 需购买商业源码许可 | UE 通，Unity 断 |
| 图形渲染 | Nanite + Lumen + MegaLights | URP/HDRP，跨平台灵活 | 品质要求 → UE |
| 程序化生成 | PCG 框架 5.7 已 Production-Ready | 需自行搭建 | 小团队出量 → UE |
| AI 整合 | MCP + ToolsetRegistry，开放标准 | 原生套件，封闭 | 自研工具链 → UE |
| 2D / 移动端 | Paper2D 已停滞 | 王者 | 非目标场景 |
| 成本 | 百万美元内免费，超出 5% 版税 | Personal ≤20万，Pro 2,310/席/年 | 初创阶段 UE 更友好 |

UE 不是没有代价。蓝图是二进制的，MCP 还标着 Experimental，C++ 冷编译一次 50 到 70 分钟，Tool 调用只能串行在 Game Thread 上跑。但这些都是工程问题，不是架构问题，对 AI 技术专家来说属于可解决范畴。

---

## 三、商业生态

Unity 的生态是"让 100 万开发者跑通商业模式"——Asset Store 8 万多资产，移动变现链路成熟，广告 SDK 是一等公民。团结引擎覆盖了微信、抖音小游戏和鸿蒙，但国内和国际是两套生态。

Unreal 的生态是另一条路：Fab 加 Quixel Megascans 免费，高品质 3D 扫描资产，一个人就能出 3A 级视觉。Epic Online Services 多人服务免费，EGS 分成 12% 且 UE 游戏免版税。源码开放本身就是终极学习资源，社区浓度高——AAA、影视、建筑可视化都在这边。Clair Obscur、Manor Lords、黑神话、Split Fiction，都是小团队甚至个人用 UE 做出来的高品质作品。

我们的定位属于后者。

---

## 四、AI 整合对比

| 维度 | Unity 6.2 AI | Unreal 5.8 AI |
|---|---|---|
| 架构哲学 | 一体化原生套件，编辑器内闭环 | 开放协议（MCP），由外向内驱动 |
| 模型锁定 | 内建模型 + 第三方网关 | 完全开放，任选 Claude/Gemini/自建 |
| 资产生成 | 内建 Generators（精灵/纹理/动画/声音） | 扩散模型进引擎（预计 2027 初） |
| 运行时推理 | Inference Engine（原 Sentis），本地免费 | 未重点强调 |
| 成熟度 | Beta，功能完整 | MCP Experimental，核心演示已跑通 |
| 可扩展性 | Opt-in，默认不训练；底层不可改 | 协议层可自行扩展 |

UE 的 MCP 架构分三层：MCP Server（HTTP + JSON-RPC）是外部大门，ToolsetRegistry 负责注册工具并自动生成 Schema，反向 MCPClient 让 UE 也能作为 Agent 网络节点。对 AI 专家来说，给 UFUNCTION 打一个 `meta=(AICallable)` 标签，LLM 就能自动发现并调用。

---

## 五、选型结论

Unreal Engine 5.8，理由按优先级排：

1. 源码可控——这个 Unity 满足不了，而引擎级 AI 改造必须要有
2. AI Agent 有架构级入口——MCP + ToolsetRegistry + AICallable，是专业主场
3. PCG 加高品质渲染闭环——支撑小团队出品质
4. 模型不锁定——技术护城河
5. 百万美元内免费，EOS 免费，EGS 免版税——商业友好

UE6 方面：5.8 是 UE5 时代最后一个大版本，作为 LTS 开项目正合适。UE6 Early Access 预计 2027 年末，三大支柱是 Verse 语言、开放内容可移植性、内置 AI/MCP。届时蓝图和传统 Actor 会逐步被 Verse + Scene Graph 替代。应对策略是核心逻辑往 Verse 侧靠，MCP 架构层本身可以复用。

---

## 六、AI Agent 工具链架构

完整的架构方案、14 个领域 Agent 设计、10 个 Toolset、PCG 策略、编排层和落地路线图，见架构文档：

[AI_Agent_Toolchain_Architecture-unreal.md](./AI_Agent_Toolchain_Architecture-unreal.md)

功能需求、验收标准、里程碑和风险登记册，见 PRD：

[AI_Agent_Game_Dev_PRD.md](./AI_Agent_Game_Dev_PRD.md)

架构上的几个关键判断：

- Agent 只生成构建脚本（PCG 图、Python 脚本、C++/Verse 代码、DataAsset），不直接捏造 .uasset。引擎确定性编译 → 可复现、可 diff、可版本管理
- 自研 Toolset 是投入重点。Python 侧 `@toolset_registry.tool_call`，C++ 侧 `UFUNCTION(meta=(AICallable))`，共 10 个 Toolset 覆盖全管线
- 治理层必须自研：File Sandbox、Risk 分级审批、Git 钩子、disposable sandbox map 验证
- 14 个 Agent 覆盖工业全管线：预生产（Director / Concept Artist / Level Designer / Data）→ 生产（Asset / Scene / Lighting / Gameplay / Audio / UI / 3D Asset）→ 验证交付（Profiler / Reviewer / Build）

---

## 七、供 PRD 继承的上下文

| PRD 章节 | 应继承的约束 |
|---|---|
| 产品定位 | 产品本体是 AI 多 Agent 游戏开发系统；参考游戏是其验证载体 |
| 技术选型 | UE 5.8 LTS，源码分支管理，UE6/Verse 迁移预留 |
| AI 架构 | MCP + 自研 Toolset + 多 Agent 编排；模型不锁定；Agent 产出构建脚本 |
| 资源管线 | PCG 框架为主，Quixel/Fab 高品质资产，可复现、可版本管理 |
| 质量与治理 | File Sandbox、Risk 分级审批、Git 钩子、sandbox map 验证、单写入者 |
| 引擎授权 | 百万美元内免费，EOS 免费，EGS 对 UE 游戏有发行优惠 |
| 参考游戏选型 | 参考游戏品类需有市场数据支撑，作为工具链的行业说服力验证 |
| 风险与依赖 | MCP Experimental、蓝图二进制、冷编译慢、Game Thread 串行 |

PRD 中参考游戏的品类、平台、美术风格等具体选型，已在 PRD §1.3 和附录 A 中基于市场数据确认。

---

*2026 · 基于引擎对比、商业生态分析、AI 整合对比与架构方案整理*