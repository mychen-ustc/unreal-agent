# 契约与版本管理（Contracts & Versioning）

项目代号：AI Agent 驱动的高品质游戏开发
关联：[TechDesign](./../ai-agent-game-dev-tech-design.md) 附录 A/B/C（目录/IDL/错误码）｜ [PRD](./../ai-agent-game-dev-prd.md) §4.1.3 SharedState 通信

> 本文档把「契约怎么定义、怎么校验、怎么版本化、破坏性变更怎么处理」变成**可执行的实操口径**。启动后 Agent/SharedState/Tool 一起动，schema 漂移与错误码失配会最先爆发。

---

## 1. 契约清单（哪些算契约）

| 契约 | 位置 | 谁消费 |
|---|---|---|
| Tool 输入/输出 JSON Schema | UE Toolset（反射） | Agent + Orchestrator |
| SharedState 信封 + Schema | `shared_state/*`（Git 事实源） | Agent 间通信 |
| 错误码（错误域分类） | TechDesign 附录 C | 全局统一 |
| Skill 元数据（tier/distill_visibility） | `skill.yaml` | distiller / imports |

---

## 2. 版本化规则

- **语义化版本**：`schema_version` 用 semver（如 `1.2.0`）。
- **不变量**：同一 `schema_version` 下，json schema 不可变。**版本升了，schema 才可改**。
- **信封必备**：每条 SharedState 带 `schema_version` + `parent_hash`（SHA-256）+ `producer`（TechDesign §5.3）。

### 破坏性变更（Breaking）流程

```
1. 要改 schema → 先升 schema_version（如 1.2.0 → 1.3.0）→
2. 登记 changelog（改了什么、兼容策略）→
3. 兼容策略：
   - 向后兼容（新增可选字段）：只升 minor；
   - 破坏（删字段/改类型）：升 major，旧版本可在过渡期双写/迁移。
4. 更新所有生产者/消费者的 `engine_min/max_version` / `schema_version` 判定。
```

说明：TechDesign 附录 A 已约定「schema_version 递增并触发版本更新」；这里补充"何时算破坏"与迁移策略。

---

## 3. 契约校验（可执行，非手写文档）

**目标**：让 `schema-check` 成为一个能跑的脚本（CI 纳入，TechDesign §9.2 提到 `schema-check`）。

- `orchestrator/scripts/schema_check.py`（建议命名）：遍历 `shared_state/*` + Tool schema，做：
  1. **JSON Schema 合法性校验**：每个 json 符合声明的 schema；
  2. **信封必填字段校验**：`schema_version / parent_hash / producer` 齐全；
  3. **错误码登记校验**：代码里的 `error_code` 必须在 TechDesign 附录 C 登记（未登记 → CI 告警）；
  4. **distill 字段校验**：`skill.yaml` 的 `tier ∈ {0..4}`、`distill_visibility ∈ {full,lite,hidden}`。
- 纳入 CI/`pytest`：schema 漂移、错误码失配、tier 非法 → 直接失败。

---

## 4. 错误码管理

- **分类不变**：安全/参数/引擎/时间/通用 五域（TechDesign 附录 C）。
- **每个 Tool 的 `detail` 必须返回机器可读错误位置**（资产路径/节点 ID/用例名）。
- **新增错误码流程**：先在附录 C 登记，再在代码使用；`schema_check` 强制「代码用过的错误码必须被登记」。
- **`UNKNOWN`** 是兜底：出现即记录 + 升级人工，不入常规 flow。

---

## 5. P0 落地动作

| # | 动作 | 交付 |
|---|---|---|
| C-01 | 建 `schema_check.py` 骨架 + 跑通 SharedState 信封校验 | 脚本存在、能测 |
| C-02 | 把 `tier`/`distill_visibility` 加进 `skill.yaml` 解析与校验 | skill.py 支持 |
| C-03 | 建立错误码登记清单（基于 TechDesign 附录 C） | `errors.yaml` / 表格 |
| C-04 | 纳入 CI（或至少 pytest 挂上 schema 校验） | 测试覆盖 |

> 这些对应 STARTUP-GATE 的 G-10（契约校验脚本）。

---

*本文档让契约「可执行校验」而非只存在文档里；P0 建骨架，P1 起随 Agent/Tool 数增长完善。*
