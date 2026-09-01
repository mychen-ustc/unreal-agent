# 文档查漏补缺盘点报告（正式启动代码研发前）

> 生成时间：P0 地基启动前
> 范围：`README.md`、`docs/` 主文档（PRD / TechDesign / 架构 / Agent Harness / ROADMAP / reference-game / environment-setup）+ `docs/ops/`
> 方法：人工交叉检查 + 多 agent 系统性盘点（交叉引用 / AC 编号 / 术语一致性）
> 处置状态：**缺口 1、缺口 2、风险 A、风险 E、风险 B、风险 C 已在本轮修复**（详见正文各节的"✅ 已处置"标记）

---

## 0. 结论先行

**文档体系整体非常成熟**：交叉引用基本闭环、ops/ 运维套件质量高、AC 编号连续无断裂、代码脚手架与文档选型对齐。文档已经"能支撑正式启动"。

> **本轮已完成的修复**（对应盘点发现的缺口与风险）：
> - **缺口 1**：TechDesign §2.1 分层图 Toolset「10 个」→「12 个」✅
> - **缺口 2**：environment-setup 全库移除 `langgraph` 核心依赖（安装命令 / import 验证 / 依赖清单）✅
> - **风险 A**：架构文档 Ⅎ式对齐——概述/§1 分层图与 mermaid/§2（含 §2.6/§2.7）/§3.3 单写入者/§6/§7/§10 术语表；修正目录错位（补 2.5 评估组）✅
> - **风险 E**：tech-design 内部一致性——§2.1 L3/L4、§2.2 进程流、§2.5/§6 标题、§5 Skill 抽象、§9.1 `agents/`→`skills/` 收口、法式引号、目录锚点 ✅
> - **风险 B / C**：reference-game AC-REF-02/03/04 改为**引用 PRD AC-P4-***（消除重复双写），交付表补 AC-REF 编号，形成「交付物↔验收」自洽 ✅
> - **附带**：全库「评测 Agent」统一为「评估 Skill（资产质检）」✅

---

## 1. 明确需修复的缺口（建议改）

### 🔴 缺口 1：TechDesign §2.1 分层图 Toolset 数量滞后（10 → 12） ✅ 已处置
- **位置**：`docs/ai-agent-game-dev-tech-design.md` §2.1 line 70
- **现状**：「L2 工具平面 Toolset（**10 个**，结构化 JSON 工具接口）」
- **问题**：本项目已为 12 个 Toolset（此前新增 PlaytestToolset + BenchmarkToolset），其它文档均已对齐为 12。此分层图遗漏。
- **处置**：已改为「Toolset（12 个）」，与 §4.1 表格一致。

### 🟠 缺口 2：environment-setup 仍把 langgraph 列为核心依赖 ✅ 已处置
- **位置**：`docs/environment-setup.md` line 17 / 42 / 155 / 171 / 324
- **现状**：5 处把 `langgraph` 列为「核心依赖」，装进 conda 环境、放进 `pip install` 命令、放进 import 验证。
- **问题**：Agent Harness 选型已**剔除 LangGraph**；`pyproject.toml` 与 `orchestrator/requirements.txt` 均不含 langgraph。环境文档仍让新手装它，与选型/代码矛盾（误导 + 版本漂移风险）。
- **处置**：已从 5 处移除 `langgraph`（依赖清单/安装命令/import 验证/版本记录），与选型一致。

---

## 2. 结构性风险（需人工决策）

### 🟠 风险 A：架构文档范式脱节（最需决策） ✅ 已处置
- **位置**：`docs/ai-agent-toolchain-architecture-unreal.md` —— §1 分层图 / §2 领域智能体 / §3–§7 数据流 / §8 / §10 / §0
- **现状**：这份文档处于"半更新"状态——§6 编排层和 §8 已局部对齐（自研最小编排 + DurableProvider + 指向 ROADMAP），但**核心骨架仍是旧范式**：
  - §1 分层图把「L4 自研 Orchestrator」当作**固定必需**顶层；
  - §2 以「33 个平级 sub-agent + Agent 间通信」为主线；
  - §3–§7 数据流 / mermaid 图 / 端到端工作流**假设必须经自研 Orchestrator 驱动**；
  - **新范式关键词全 0**：能力包 / Common Spec / 跨宿主 / distiller / Tier / importers / 第一公民 / 宿主可选 — 均未出现。
- **对比**：TechDesign 已同步（TDR-012~014：能力包第一公民、宿主可选、商业三形态 + `importers/`/`distiller.py`/`skills/`）；Agent Harness 有 §11 商业三形态 + §12 跨宿主 Common Spec；ROADMAP 以「能力包」为双时间轴核心。
- **后果**：两层核心文档对"系统怎么搭"给出不一致的图。技术/新人按架构文档读，会得到与实现（能力包第一公民、宿主可替换）相反的认知。
- **建议**（按滞后严重度）：
  1. **§1 总体架构**（最高优先）：四层图 + 概述 + mermaid 改为「能力包为第一公民、编排宿主可选/可替换、第三方宿主经 MCP 直驱能力包」；
  2. **§2 领域智能体**：把「33 平级 sub-agent」定性为「33 领域 Skill（Common Spec），宿主调度」；
  3. **§3–§7 数据流 / 工作流**：修正"必须经自研 Orchestrator 驱动"，补充跨宿主视角；单写入者来源修正为 MCP/Toolset 层；
  4. **§8 / §10**：补 C0–C3 商业轴与能力包核心轴；术语表补新范式术语。
  - **保留原则**：§3（MCP 工具平面）、§4（PCG）、§5（外部生成）是稀缺技术背景，**保留**；只改写范式表述。
- **✅ 处置**：已按上述顺序完成——概述改为能力包第一公民；§1 分层图 + mermaid 改为「可选编排宿主 + 33 个 Common Spec Skill」；§2 改 Skill 范式（含 §2.6/§2.7）；§3.3 单写入者下沉到 UE MCP 层；§6 标「可选宿主」；§7 加第三方宿主说明；§10 术语表补能力包/Skill/宿主/distill；修正目录错位（补 2.5 评估组）。

### 🟠 风险 B：AC-REF 与 PRD AC-P4 重复定义 ✅ 已处置
- **位置**：`reference-game.md` §7（AC-REF-02/03/04）↔ `PRD` §9.5（AC-P4-01/02/04）
- **现状**：AC-REF-02/03/04（外部生成接入 / 质量控制 / 资产元数据）与 PRD AC-P4-01/02/04 **重复定义**（其中 2 条完全相同）。
- **后果**：同一批验收标准双份维护，后续改动易不一致。
- **✅ 处置**：AC-REF-02/03/04 改为**引用 PRD AC-P4-01/02/04**（reference-game §7 保留参考游戏专属的 AC-REF-01 + 对重合项的引用），消除双写；并补「全项目验收全集口径」说明。

### 🟡 风险 C：AC-REF ↔ 里程碑映射只存在于 ROADMAP ✅ 已处置
- **位置**：`reference-game.md` §7「关键交付」表（P3/P4/P5）未标 AC-REF 编号；映射仅 ROADMAP §2。
- **后果**：reference-game 若调整 AC 号，ROADMAP 映射静默失配。
- **✅ 处置**：reference-game §7 交付表已增加「AC-REF」列（AC-REF-01 / 02~04），形成「交付物↔验收 AC」自洽闭环。

### 🟡 风险 D：TechDesign「36 条 AC」口径未说明 AC-REF ✅ 已处置
- **位置**：`TechDesign.md` §10.2
- **现状**：「36 条 AC」算术正确（=PRD 的 P0~P4），但 **未计入参考游戏 AC-REF-01~04**（全项目 AC 全集实为 36+4=40）。
- **✅ 处置**：已在 TechDesign §10.2 补口径说明（"36 条为 PRD 工具链本体；参考游戏验收见 reference-game §7"，明确 AC-REF 不与 36 条重复计数）；reference-game §7 亦补「全集口径」注。

---

## 2.5 术语一致性补充发现（第三组盘点的交叉核对）

### 🟠 风险 E：tech-design 内部「新旧范式」并存 ✅ 已处置
- **位置**：`docs/ai-agent-game-dev-tech-design.md` —— §2.1 分层图 / §2.2 进程流 / §5.1「Agent 抽象」/ §5.2「Agent 实现映射」/ §9.1 目录 `agents/` 与 `skills/` 并存
- **问题**：tech-design 的主体已对齐新范式（§2.3/§2.4 能力包第一公民、§6 可选宿主、TDR-012~014、`importers/`/`distiller.py`/`skills/`），但若干章节残留旧范式：
  - §2.1 分层图 L4 仍把「Orchestrator」画成必需层（与 §2.4「可选宿主」冲突）；L2 仍写「10 个」Toolset（实际 12）；
  - §2.2 进程流强调「编排进程（Orchestrator）是唯一 Tool 调用发起方」，未按「能力包 / 单写入者在 UE MCP 层」下沉；
  - §5 章节仍以「Agent 抽象 / Agent 实现映射」命名，与 §2.4/§9.1 的「Skill」叙事冲突（同物两视角未交代）；
  - §9.1 目录 `agents/` 与 `skills/` 并存（注释已写"agents 迁移到 Common Spec Skill"，属过渡态）。
- **后果**：tech-design 是**唯一"既对又错"的文档**——对新读者最易误导（同名章节一半新一半旧）。
- **建议**：优先修 tech-design 内部一致性——分层图 L2（10→12）+ L4（可选宿主）、§2.2 进程流（唯一写入者下沉到 UE MCP）、§5 标题统一为「Skill 定义 / 映射」，`agents/` 与 `skills/` 收口为 `skills/` 唯一事实源。
- **✅ 处置**：已修——§2.1 L2（10→12）+ L3（33 Skill）+ L4（可选宿主）、§2.2 进程流（单写入者下沉到 UE MCP）、§5 改「L3 领域能力（Common Spec Skill）· Skill 抽象/映射」、§6 改「自有编排宿主（可选宿主之一）」、§9.1 `agents/`→`skills/` 收口（注明 agents 过渡保留）、§1.1 观测"Skill 步骤"、目录锚点 §6.2.1 修正。

### 🟡 次要硬伤（顺手可修，非概念冲突） ✅ 已处置
| 文档 | 位置 | 问题 |
|---|---|---|
| tech-design | §6.2.1 line 488 | 用了法式引号 `«可选宿主之一»`，应为中文直角引号「」（已改） |
| harness / ROADMAP / tech-design | 全文 | `Tier`（大写能力等级）与 `skill.yaml#tier`（小写字段名）写法未统一——建议"能力等级用大写 Tier 0–4、字段名用小写 tier"，可后续统一（**低优先，保留待统一**） |

> 说明：第三组关于"架构文档目录与正文小节号错位"的结论经复核为**误报**（架构文档顶层目录未列 2.x 子节，正文 2.1~2.7 自洽），已剔除，不构成缺口。

---

## 3. 已确认健康、无需改动的部分 ✅

- **交叉引用**：kebab-case 重命名后所有内部链接（`./docs/*.md`、`./ops/*.md`、`./ideas/*.md`、`../` 相对路径）均有效，无指向旧 Pascal_Snake 文件名的断裂。
- **数量一致性（主体）**：33 Agent / 12 Toolset 在 PRD / 架构 / Agent Harness / ROADMAP 中一致（唯一例外是 tech-design §2.1 分层图 L2 仍写"10 个"，见缺口 1）。
- **AC 编号**：PRD AC-P0~P4（共 36 条）连续无跳号；ROADMAP 引用的每一段 AC 均被 PRD 覆盖；38 个 AC 引用集合 == 定义集合，无悬空/未定义/重复编号。
- **里程碑**：PRD §7 与 ROADMAP §2 阶段/周期/目标逐项一致。
- **ops/ 套件**：STARTUP-GATE / GOVERNANCE-OPS / SECURITY-LICENSING / UE-ENGINE-WORKFLOW / CONTRACTS 质量高，与主文档交叉闭环，且已对齐代码脚手架实际状态（"编排语言脚手架"，接真 UE 的硬 Gate 未就绪）——诚实、可执行。
- **代码-选型对齐**：`pyproject.toml` / `orchestrator/requirements.txt` 依赖与选型一致（无 langgraph，LiteLLM/MCP/LanceDB/OTel）。
- **README 代码进展**与 STARTUP-GATE §2 代码现状描述自洽。

---

## 4. 建议的落地次序（启动前）

| 次序 | 项 | 类型 | 依赖 |
|---|---|---|---|
| 1 | **风险 A：架构文档范式对齐** | 需决策后改 | 先确认「保留角色清单 + 加 Skill 定性」还是「整体改写」 |
| 2 | **风险 E：tech-design 内部新旧范式并存**（含缺口 1 的 L2 10→12、L4 可选宿主、§2.2 进程流、§5 标题、agents//skills/ 收口） | 需决策后改 | 无 |
| 3 | **风险 B：AC-REF 重复** | 需产品方确认意图 | 确认保留哪一套 |
| 4 | **缺口 2：environment-setup 移除 langgraph** | 直接改 | 无 |
| 5 | 风险 C / 风险 D / 次要硬伤（法式引号、Tier 大小写） | 低风险小改 | 无 |

> 说明：风险 A（架构）与风险 E（tech-design）是**同一范式问题在两个文档的不同表现**，建议一起决策、一起改，保证两份文档对"能力包第一公民 / 宿主可选 / 33 Skill"表述一致。

---

*本文档为 P0 启动前的查漏补缺盘点；第 2 节的风险 A/B 需人工决策后执行修复。*
