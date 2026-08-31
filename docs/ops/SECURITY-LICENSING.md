# 安全、审计与授权计量（Security & Licensing）

项目代号：AI Agent 驱动的高品质游戏开发
关联：[Agent Harness §11](./../agent-harness-selection-and-design.md#11-商业交付形态与资产保护)（商业交付/资产保护/Skill 分级）｜ [TechDesign](./../AI_Agent_Game_Dev_TechDesign.md) §7/§10 ｜ [ROADMAP](./../ROADMAP.md) §3 商业轴 / 资产保护

> 本文档把「安全 🛡、审计 📜、授权计量 🔢」统一成一份可执行的基建口径。重点：**把商业化的 License/计量/资产保护钩子在 P0 就预先埋进代码**，否则 C1/C2（蒸馏/计费）会返工。

---

## 1. 三层：安全 / 审计 / 计量

| 层 | 目的 | 承载 | 生命周期 |
|---|---|---|---|
| **安全（Safety）** | 阻断越界/误操作 | File Sandbox + Risk Gate + Git 钩子 | 运行时即时 |
| **审计（Audit）** | 事实记录、可追溯、可重放 | Trace（OTel + trace.jsonl），**不可篡改** | 长期留存 |
| **计量（Metering）** | 授权、配额、计费、License | `metering` 标签（tenant/agent/duration/token） | 跨交付形态 |

---

## 2. 审计与 RAG 语料严格分离（关键红线）

> 审计日志是**事实**，RAG 语料是**知识**。两者不得混用、不得互相污染。

| | 审计（Audit） | RAG 语料（Knowledge） |
|---|---|---|
| 内容 | 每次模型调用（prompt/response）、每 Tool 调用、每审批决策、Time+tenant | 已验证代码片段、风格指南、UE 文档、后验偏差 |
| 是否可变 | **不可变**（只追加，防篡改） | 可清洗/可重建 |
| 存储 | `.logs/trace.jsonl` + OTel（追加写） | LanceDB `memory/` |
| 用途 | 合规、重放、计量 | 检索增强、记忆 |
| git | gitignore（运行时数据） | gitignore（可重建） |

**P0 落地**：trace writer 已追加写 JSON Lines；**补充**任何「修改既有 trace 行」的操作都应视为异常。

---

## 3. License / 计量钩子（P0 预埋）

> 商业交付形态 A（SaaS）/ B（私有化黑盒）/ C（引流蒸馏）都要计量（见 Harness §11、ROADMAP §3）。**计量的"记录数据"必须在 P0 就设计好**，否则 C2/C3 只能补历史债。

### 3.1 P0 预埋的计量标签（最小骨架）

每条 Tool 调用 / Agent 运行 / 长任务，`trace` / `metering` 事件带以下字段（P0 先记录、C 段再转计费）：

```
event: tool_call | agent_run | long_task | model_call
timestamp_utc: ISO8601
tenant_id:     ""            # P0 单租户置空；C2 起填
license_key:   ""            # B/C3 填；P0 全程空
agent:         scenes_pcg
tool:          pcg_generate_graph
risk:          mutating
duration_s:    12.3
model_tier:    default
token_usage:   {input, output}
trace_id:      ...
```

> 目标：**字段现在就进结构，值现在可为空**。运行链路（mcp_client / models / trace）带上这些字段，不改变现状行为，只预留位。

### 3.2 各形态的计量策略

| 形态 | 计量点 | 承载 |
|---|---|---|
| C1 引流 | 子集水印 + 用量上报（限 demo） | distiller 产物 + 计量标签 |
| C2 SaaS | 租户 token/时长/并发预算 | LiteLLM 后端 + Metering API |
| C3 私有化黑盒 | 容器内 License / 心跳 / 脱敏回传 | 黑盒容器内的 metering |

### 3.3 计量安全

- 计量上报走独立通道（不混入业务 trace，避免被恶意清改）。
- 私有化黑盒内：License 心跳断连/超量 → 降级或停机（见 Harness §11.2 支柱 2）。

---

## 4. 资产保护钩子（P0 预埋）

> 商业核心：能力包不出境（A/B），仅蒸馏子集出境（C）。P0 埋两处「钩子」，让 C1/C3 顺畅：

1. **Skill `tier` / `distill_visibility` 字段**：`skill.yaml` 现在就声明 `tier` 与 `distill_visibility`（§11.3 / §12.3）。即便是 P0 的 `scenes_pcg`，也先定级（如 Tier 2 / lite）。
2. **`distiller.py` 骨骼**：P0 只放函数签名 + `tier<=2` 裁剪逻辑骨架；C1 填完整。**现在建 **空文件 + 接口**，让"它应该在"被明文记录。

### 数据最小化原则（贯穿 C2/C3）

- 私有化容器只含「最小运行必需」的 RAG/数据（golden 样本、私有语料、未发布基准**不随容器交付**，见 Harness §11.2 支柱 3）。
- 回传数据**脱敏**（去业务敏感字段后再上报计量/审计）。

---

## 5. 安全基线清单（P0）

| 项 | 要求 |
|---|---|
| MCP 绑定 | 仅 `127.0.0.1`，不暴露局域网（TechDesign §7.3） |
| 沙箱 | `/Engine/` 等只读；Agent 仅写 `/Game/Generated/` + `shared_state/` |
| 审批覆盖 | 所有 `destructive` 100% 人工确认 |
| 凭据 | `.env` 不入库；密钥不写文档/日志；Log 脱敏（不外泄 api_key） |
| 审计 | 模型/Tool/审批全量落 trace，追加写、防篡改 |
| 回滚 | mutating 后自动 commit，≤1min 可回滚 |

---

*本文档随商业里程碑（C1–C3）持续演进；P0 只需落实「预埋钩子」与安全基线，不提前实现商业化完整逻辑。*
