# 启动前置条件 Gate（Launch Gate）

项目代号：AI Agent 驱动的高品质游戏开发
关联：[ROADMAP](./../ROADMAP.md) P0 地基 ｜ [PRD](./../AI_Agent_Game_Dev_PRD.md) §9 验收 ｜ [TechDesign](./../AI_Agent_Game_Dev_TechDesign.md) §3/§6/§7 ｜ [environment-setup](./../environment-setup.md)

> 本文档回答：「**满足什么 = 可以正式启动 P0 地基**」。正式启动不是"读完文档就开跑"，而是逐条过 Gate。每项标记 `✅ 已就绪 / 🟡 有条件 / ❌ 未就绪`。
>
> 这里同时维护**「代码实现 ↔ PRD AC 现状对照」**，避免"文档说能跑、代码没测过"的脱节。启动后定期刷新本表。

---

## 目录

- [1. 启动前置条件（Gate）](#1-启动前置条件gate)
- [2. 代码实现 ↔ AC 现状对照](#2-代码实现--ac-现状对照)
- [3. 首次提交约定](#3-首次提交约定)
- [4. 启动后的前两周节奏](#4-启动后的前两周节奏)

---

## 1. 启动前置条件（Gate）

> 逐条核对；全部 `✅` 才进入 P0 地基正式研发，`🟡` 需记录明确的前置/时限，`❌` 处理完才能启动。

| # | Gate | 关键验收 | 状态 | 说明 |
|---|---|---|---|---|
| G-01 | 环境就绪 | Xcode、UE 5.8 源码版、conda、Redis、模型凭据、Git | 🟡 | 见 environment-setup §0；**唯一待办 MetalToolchain 组件**（带渲染编辑器会话） |
| G-02 | 首次提交 | `orchestrator/`、`pyproject.toml`、`unreal/` 首次纳入 git | ❌ | 当前均为未跟踪（见 §3） |
| G-03 | 测试骨架 | `tests/` 存在，P0 单元测试可跑（pytest 空跑通过） | ❌ | 当前无 `tests/` |
| G-04 | AC-P0-01 MCP 插件启用 | UE 插件启用 + `127.0.0.1:8000/mcp` 响应 | 🟡 | 依赖 G-01 补 MetalToolchain 后验证 |
| G-05 | 审批/回滚 SOP 就绪 | 审批人已定、CLI 审批命令可用（非占位） | ❌ | 当前 `approve`/`rollback` 为**占位**（见 §2） |
| G-06 | 凭据安全 | `.env` 不入库（已 gitignore）、密钥不写进文档/日志 | ✅ | .gitignore 已含 `.env` |
| G-07 | 分支策略 | main 受保护 / 开发分支约定已定 | 🟡 | 建议 P1 多人前启用受保护分支 |
| G-08 | 数据/备份口径 | SharedState(Git)、memory(gitignore)、.logs 的保留/备份规则明确 | 🟡 | 见 ops/GOVERNANCE-OPS §数据 |
| G-09 | 商业钩子预埋 | distiller 骨架、计量标签、审计不可篡改预留（P0 埋点） | ❌ | 见 ops/SECURITY-LICENSING §P0 预埋 |
| G-10 | 契约校验脚本 | `schema-check`（SharedState/Tool JSON Schema + 错误码登记）能跑 | ❌ | 见 ops/CONTRACTS |

> **决策**：并非所有 Gate 都要在"第一天"全绿。**硬 Gate（必须全绿才能启动）**：G-01、G-02、G-03、G-05、G-06。**软 Gate（P0 期间补但方向先定）**：G-04、G-07、G-08、G-09、G-10。

---

## 2. 代码实现 ↔ AC 现状对照

> 诚实标注：`✅` 已实现可验证 ｜ `🟡` 部分实现/占位 ｜ `❌` 未实现。这是"文档 vs 代码"的对账，**启动首周就要补差距**。

| PRD AC | 需求 | 代码现状 | 差距 / 行动 |
|---|---|---|---|
| **P0-01** MCP 三件套插件启用 | 插件启用 + `/mcp` 响应 | 🟡 `mcp_client.py` 有 HttpTransport 但 `--no-stub` 需真 UE | 补 MetalToolchain → 真 UE 验证 |
| **P0-02** ProjectToolset 注册 | `list_tools` 返回全部工具 + Schema | 🟡 MCP 桩有工具列表；真 Toolset 未连 | 接 UE 后验证 schema 反射 |
| **P0-03** 沙箱生效 | 写入 `/Engine/` → `sandbox_denied` | ❌ 沙箱在 UE 侧 SafeguardToolset，编排侧未测 | 需 UE + SafeguardToolset |
| **P0-04** 审批分级 | read_only 放行 / mutating 审批 / destructive 阻塞 | 🟡 `--auto-approve-read-only` 有开关；`approve` 命令是占位 | 打通 `approve` 真实审批链 |
| **P0-05** Git 钩子自动 commit | mutating 后自动 commit + diff | ❌ `rollback` 是占位；post-tool Git hook 未实现 | 落地 post-tool hook |
| **P0-06** 最小闭环 | 放置 Cube → 出现 → 回滚 → 消失 | 🟡 CLI `run` 走 Skill/DAG；"放置 Cube"需真 UE + 回滚 | 连 UE 跑通最小闭环 |

**结论**：当前 `orchestrator/` 是**「编排语言脚手架」**（DAG / Skill 装载 / MCP 桩 / trace / LiteLLM 都可见），但把 SDK 能力**接真 UE 的 AC-P0 六项几乎都差「连真 UE + 审批/回滚落地」这一层**。这是 P0 地基第一周的真实工作重心。

---

## 3. 首次提交约定

> 启动前完成首次提交，理由：文档与代码握手、可回滚、可协作。

- **应纳入 git**：`docs/`、`README.md`、`orchestrator/`、`pyproject.toml`、`unreal/`（UE 项目描述，非引擎二进制，引擎源码在 `/Users/Shared/UnrealEngine-5.8-source` 不入库）、`.env.example`、`.gitignore`。
- **不应纳入**：`.env`（凭据）、`orchestrator/memory/`（可重建）、`.logs/`（运行日志）、`ideas/`（灵感归档，已 gitignore）、引擎 DerivedDataCache/Intermediate 等（.gitignore 已覆盖）。
- **首次提交内容**：以「docs + orchestrator 脚手架 + pyproject + 首个通过的测试」为一组，commit message 形如 `chore: 首次提交（P0 脚手架 + 文档底座）`。
- **分支策略（建议）**：长期只给 `main` 加受保护规则（限 merge via PR）；个人开发用短生命周期特性分支。多人加入前落实。

---

## 4. 启动后的前两周节奏

| 周 | 目标 | 关键动作 |
|---|---|---|
| 第 1 周 | 环境闭环 + 首次提交 + 测试骨架 | 补 MetalToolchain → 真 UE `/mcp` 响应；建 `tests/` 首条 pytest；首次 git commit |
| 第 1–2 周 | AC-P0-01~06 逐个转绿 | 从「连真 UE + 审批/回滚落地」切入，把 §2 的 🟡/❌ 逐项清为 ✅ |
| 第 2 周 | 商业钩子预埋 | distiller 骨架、计量标签、审计不可篡改的最小埋点（见 ops/SECURITY-LICENSING） |

---

*本文档随 P0 推进定期刷新；当前"未就绪"项为 P0 地基的启动工作重点。*
