# 治理运行规程（Governance-Ops）

项目代号：AI Agent 驱动的高品质游戏开发
关联：[TechDesign](./../ai-agent-game-dev-tech-design.md) §7 安全治理 / §6.5 人工卡点 ｜ [PRD](./../ai-agent-game-dev-prd.md) §4.1.2 ｜ [STARTUP-GATE](./STARTUP-GATE.md)

> 本文档是**人工审批、回滚、数据状态、审计**的 SOP（运行规程）。启动后第一个 `destructive` 操作、第一次回滚、第一份数据备份，都按这里的流程走。

---

## 1. 审批流程（人工卡点 SOP）

### 1.1 审批分级（与设计一致）

| 风险 | 动作 | 审批人 | 响应时限（建议） |
|---|---|---|---|
| `read_only` | 自动放行 | — | 即时 |
| `mutating` | 轻量审批（CLI 内联 y/N） | P0：AI 技术专家本人 | ≤ 数分钟 |
| `destructive` | 强制人工确认（diff 预览） | P0：AI 技术专家本人 | ≤ 数分钟 |

### 1.2 SOP（destructive 最严）

```
1. Agent 产出意图 → Orchestrator 判定 destructive →
2. 挂起于 TaskQueue(WAITING_APPROVAL)，锁写后继，无关分支继续 →
3. 审批人收到 diff 预览（CLI 内联：将写入的完整 diff + 风险等级 + 目标资产路径）→
4. 批准 → 出队执行 → post-tool hook 落库 → 下游 stale 解除；
   拒绝 → 标记失败 → 不落库、不触发下游。
5. 超时（无响应）→ 按「默认拒绝」或「升级」处理（见下）。
```

### 1.3 升级与默认策略

- **审批超时**：P0 默认**拒绝并提示**（安全优先）；若为阻塞性审批可配置 `--approve-timeout-s` 后自动升级到更高权限人。
- **审批失败**（拒绝/超时）→ 走 §2 回滚语义，产出不落库。
- **单人流程**：当前 P0 是单 AI 技术专家，审批人即本人；多人加入后按「负责人矩阵」分派（§4）。

### 1.4 CLI 相关命令

- `orchestrator approve --task-id <id> --allow/--deny`
- `orchestrator run --task "..." --require-approval`（关闭只读自动放行，CI/演示用）

> ⚠️ **当前代码状态**：`approve` 命令是**占位**（见 STARTUP-GATE §2 AC-P0-04）。本 SOP 先定规，启用的审批链需在 P0 首周落码接通。

---

## 2. 回滚 SOP

| 触发 | 动作 | 目标 |
|---|---|---|
| 审批拒绝 / 失败回退 | `safeguard_rollback(commit_sha)` → `git reset --hard <sha>` + 重载关卡 | 回到改写前 |
| 误提交 | Git 自动 commit 支持一键 revert（`git revert` 或 `reset --hard`） | 恢复到安全提交 |
| 空间分区锁 | 回滚期间锁释放并重建 | 避免死锁/冲突 |

**原则**：
- 每次 `mutating` 后自动 commit + diff 报告（Git 事实源）。
- 回滚目标 ≤ 1 分钟（PRD §5.3）。
- 回滚是**破坏性操作**，建议也经一次人工确认（除非是自动化的回退循环）。

---

## 3. 数据 / 状态运维口径

| 状态层 | 存储 | git 管理 | 备份/恢复 |
|---|---|---|---|
| 工作记忆 | SharedState（Git JSON） | 事实源，随 commit 落库 | 靠 Git 历史即可回滚到任意提交 |
| 长期记忆 | LanceDB `orchestrator/memory/` | gitignore（可重建） | **定期导出向量备份**（如 `lancedb` 快照）；丢失可重灌 |
| 运行日志 | `.logs/`（trace.jsonl / evals.jsonl） | gitignore | **随需留存**；可作为 RAG 语料/审计 |
| UE 资产 | `/Game/Generated/` + Git 钩子 commit | 改动自动 commit | 靠 Git；.uasset 需引擎编译复现 |
| 模型配置 | `.env` / `config/models.yaml` | `.env` 不入库；models.yaml 入库 | 密钥存 .env，不入库 |

**规则**：
- `memory/`、`.logs/` 是**可再生/非事实源**，不 commit（.gitignore 已覆盖）。
- SharedState 与 UE 资产之间的对应关系靠 commit（`shared_state JSON 变更 ↔ UE 资产变更 一一对应`，TechDesign 附录 A）。
- **多人/多机前**：补 LanceDB 备份脚本 + 明确「谁负责拉/推」。P0 单人可不设。

---

## 4. 负责人矩阵（Roles & RACI）

| 事项 | P0（单人） | 多人后 |
|---|---|---|
| 编排 / Toolset / RAG | AI 技术专家 | 引擎/后端工程师分域 |
| 审批（destructive） | AI 技术专家 | 对应生产域负责人 |
| 数据备份 / 运维 | AI 技术专家 | 专人 |
| 商业 / License 钩子 | AI 技术专家 | 产品/商务 + 架构 |

---

## 5. 审计口径

- 审计日志 = **不可变更的事实**；RAG 语料 = **可清洗的知识**。两者**严格分离**（见 SECURITY-LICENSING §2）。
- 每次模型调用 / Tool 调用 / 审批决策 全量落 trace（OTel spans + trace.jsonl）。

---

*本文档是治理 SOP，配合 STARTUP-GATE 中 AC-P0-04/05 一起启用。*
