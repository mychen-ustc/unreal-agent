# 技术设计文档

项目代号：AI Agent 驱动的高品质游戏开发  
关联 PRD：[AI_Agent_Game_Dev_PRD.md](./AI_Agent_Game_Dev_PRD.md)（v0.2）  
关联前置文档：[项目背景与选型](./project-background-and-tech-selection.md)、[架构方案](./AI_Agent_Toolchain_Architecture-unreal.md)

> 本文档是 PRD 的技术落地层。PRD 定义「做什么」，本文档定义「怎么做」：模块划分、接口契约、数据结构、关键算法、并发模型、构建与部署、可观测性、可测试性。所有 PRD 编号（F-TOOL / Agent / AC 等）均在此给出实现映射。

---

## 目录

- [1. 设计目标与原则](#1-设计目标与原则)
- [2. 总体架构](#2-总体架构)
- [3. L1 宿主与协议适配层](#3-l1-宿主与协议适配层)
  - [3.5 UE 编辑器连接监督与任务恢复](#35-ue-编辑器连接监督与任务恢复)
- [4. L2 工具平面（Toolset）](#4-l2-工具平面toolset)
- [5. L3 领域智能体](#5-l3-领域智能体)
- [6. L4 编排与治理层](#6-l4-编排与治理层)
  - [6.2.1 长时任务的执行模型](#621-长时任务的执行模型langgraph-协调)
- [7. 安全治理体系](#7-安全治理体系)
- [8. 参考游戏技术实现](#8-参考游戏技术实现)
- [9. 工程化：构建、CI、部署](#9-工程化构建cideployment)
- [10. 可观测性与可测试性](#10-可观测性与可测试性)
  - [10.2.1 AI 产物质量评估层（evals）](#1021-ai-产物质量评估层evals)
- [11. 性能工程](#11-性能工程)
- [12. 可维护性、可扩展性与 UE6 迁移](#12-可维护性与-ue6-迁移)
- [13. 技术决策记录（TDR）](#13-技术决策记录tdr)
- [附录 A：目录结构约定](#附录-a目录结构约定)
- [附录 B：核心接口契约（IDL 摘要）](#附录-b核心接口契约idl-摘要)
- [附录 C：错误码与错误域分类](#附录-c错误码与错误域分类)

---

## 1. 设计目标与原则

### 1.1 设计目标

1. **确定性**：Agent 不直接产生 `.uasset`，只产出可复现的构建脚本（PCG Graph 描述、编辑器脚本、C++/Verse 源码、数据资产）。
   - **确定性承诺的范围是构建脚本层**：同一份输入 + 同一版工具链 = 同一份构建脚本文本（可 diff、可版本、可回滚）。
   - **生成的资产是"工程确定性"而非"数学确定性"**：PCG 并行分支与 GPU Override 的结果在 5.7+ 仍可能存在轻微差异（架构 §4）。因此所有 PCG 生成须 `pin seed`，且引擎/工具链升级后走"重新生成 + 与基线比对"流程，不直接信任旧基线。
2. **可控性**：每一个"写"动作都经过 Sandbox、Risk Gate、审批门禁，任何变更可回滚。
3. **可替换性**：模型、生成服务、外部资产库均通过接口隔离，更换 = 改一个配置。
4. **可迁移性**：L2/L3/L4 与引擎版本解耦，UE6 迁移复用率 ≥ 80%（PRD §5.5）。
5. **可观测性**：每次 Tool 调用、Agent 任务、编排决策均有结构化追踪，可重放。

### 1.2 设计原则

- **单一职责**：一个 Tool = 一个动作；一个 Agent = 一个领域职责。
- **静态无状态**：Tool 实现为静态/纯函数，不持有会话状态，状态外置到 SharedState。
- **结构化一切**：Tool 返回 JSON，Agent 间通信走 JSON Schema，禁止自由文本传语义。
- **失败即数据**：失败返回 `{ok: false, error_code, detail}` JSON，不抛异常（PRD §4.1.1）。
- **可复现优先于灵活**：Agent 生成脚本而非直接编辑，换来可 diff、可版本、可回滚。
- **单写入者 + 空间分区**：唯一拥有编辑器写入权的协调者，多 Agent 按坐标分区（PRD §4.1.3, §6）。

---

## 2. 总体架构

### 2.1 分层

```
┌────────────────────────────────────────────────────────────┐
│  L5  使用者界面（CLI · P0）→ Web Console / UE 面板（P1+）        │
├────────────────────────────────────────────────────────────┤
│  L4  编排与治理层（Orchestrator · DAG · RAG · 记忆 · 模型路由）│
├────────────────────────────────────────────────────────────┤
│  L3  领域智能体（33 个 Agent，按 SharedState Schema 通信）   │
├────────────────────────────────────────────────────────────┤
│  L2  工具平面 Toolset（10 个，结构化 JSON 工具接口）         │
├────────────────────────────────────────────────────────────┤
│  L1  宿主与协议适配（UE 5.8 MCP Server · ToolsetRegistry ·  │
│       Python/C++ 反射 · Safeguard 拦截器 · Git 钩子）        │
└────────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────┐
│  UE 5.8 编辑器 / 引擎（PCG · World Partition · Nanite ·    │
│  Lumen · Live Coding · UBT · UAT · Unreal Insights）        │
└────────────────────────────────────────────────────────────┘
```

> **分层编号说明**：本文档在架构文档的四层（L1 宿主 / L2 工具 / L3 智能体 / L4 编排）之上，额外补了一层 **L5 使用者界面**。语义一致——架构文档的 L4 编排即本文档的 L4；本文档只是把"UI 入口"显式剥离成独立的一层（P0 为 CLI，P1+ 为 Web/UE 面板），便于单独演进。L1–L4 的编号与架构文档完全对应，不冲突。

### 2.2 进程与数据流

- **UE 编辑器进程**：内嵌 MCP Server，绑定 `127.0.0.1:8000/mcp`（JSON-RPC over HTTP）。ToolsetRegistry 把 L2 Tool 暴露为工具。
- **编排进程（Orchestrator）**：独立进程（Python / 容器），作为 MCP Client 连 UE。负责 DAG、Agent 调度、模型调用、RAG、记忆。
- **Agent 进程/线程**：编排进程内以协程/任务形式运行，本身不直连 UE，全部通过 Orchestrator → MCP 调用 Tool。
- **唯一写入者**：Orchestrator 是唯一的 Tool 调用发起方；Agent 只产出"意图 + 参数"，由 Orchestrator 序列化写入。

> 这是与"让每个 Agent 直连 MCP"的关键架构差异：单写入者解决 Game Thread 串行 + 并发写冲突（R-04），并把审批/审计集中在一处。

> **单写入者 ≠ 空间分区锁，两者分层管理**：
> - **单写入者**是**物理写并发层**——Orchestrator 是唯一能发起 Tool 写调用的实体，保证 Game Thread 串行、审批/审计集中（聚焦 R-04）。
> - **空间分区锁**是**逻辑资源归属层**——解决"两个 Agent 的产物在坐标空间/资产路径上冲突"（如 Scene 与 Lighting 同时改北区），与写并发无关。
> - 实现上：所有写 Tool 调用天然串行（单写入者 + MCP 本就串行）；空间分区锁是 Orchestrator 调度时对**非同一坐标范围的并行授权**，不产生物理写竞争。两者职责不同，不可混用。

### 2.3 技术选型（实现层）

> 本节选型由 AI 技术专家结合团队定位（小团队 + UE 5.8 MCP + 源码可控）决策，**均为可替换接口，非框架锁定**。详细决策依据见 §13 TDR-006 ~ TDR-011。

| 关注点 | 选型 | 理由 |
|---|---|---|
| **编排框架** | **Python + LangGraph**（StateGraph 表达 DAG/回退）+ 自研 DAG 引擎（依赖传播、stale 标记） | LangGraph 提供状态图/条件边/Checkpoint 原语，加速 MVP；自研部分负责 PRD §4.1.3 的依赖 DAG 与回退语义 |
| Agent 运行时 | **Python 3.11+，asyncio** | 协程并发、AI 生态（LangChain/LlamaIndex）最成熟、与 UE Python Tool 同一语言 |
| **运行入口（P0）** | **CLI + 结构化 JSON 日志**（`python -m orchestrator run --task "..."`） | 最小成本、可被 CI 调用、日志可喂回 LLM；Web Console / UE 面板为 P1+（§6.5） |
| **模型接口（默认）** | **Anthropic Claude**（`claude-opus-4-5` 复杂 / `claude-sonnet-4-5` 主力 / `claude-haiku-4-5` 兜底）+ **LiteLLM 统一封装** | 代码/工具调用最强、长上下文、复杂推理领先；LiteLLM 满足"模型不锁定"（TDR-010） |
| MCP 客户端 | `mcp` Python SDK（官方） | 标准兼容 |
| SharedState 存储 | Git（事实源）+ Redis（运行时缓存）+ **LanceDB**（向量长期记忆） | LanceDB 嵌入式零运维、列式+磁盘索引性能优于 ChromaDB（TDR-009） |
| 任务队列 | asyncio + 优先队列（单机）；可选 Celery（分布式扩展） | P0 阶段单机即可 |
| 观测 | OpenTelemetry → 本地 OTLP collector → 文件/SQLite | 追踪 + 重放 |
| 测试 | pytest + UE 自动化测试框架（`py`-侧）+ GitHub Actions | CI |

**模型路由档位（默认映射，配置文件驱动，可随时扩 GPT / 开源）：**

| 档位 | 默认模型 | 典型任务 |
|---|---|---|
| `strong`（复杂推理） | `claude-opus-4-5` | 玩法设计、PCG 参数规划、缺陷根因分析、复杂代码生成 |
| `default`（主力） | `claude-sonnet-4-5` | 多数 Agent 任务、Tool 调用、GDD 撰写 |
| `fast`（简单/高频） | `claude-haiku-4-5` | 格式化、摘要、分类、命名规范校验、短 Tool 结果判断 |

**完整技术栈一览（P0）：**

```
CLI (Typer + Rich)              ← 运行入口：结构化 JSON 日志
   │
   ▼
LangGraph StateGraph            ← 编排：DAG + 回退循环 + Checkpoint
   │
   ├─ Agent Runtime (asyncio)   ← 33 个领域 / 评估 Agent
   │     │
   │     ├─ LiteLLM ──▶ Claude (Opus/Sonnet/Haiku)   ← 模型路由
   │     │
   │     └─ SharedState (Git JSON + Redis)
   │              │
   │              └─ LanceDB   ← RAG 长期记忆
   │
   └─ MCP Client (唯一写入者) ──▶ UE 5.8 MCP Server (127.0.0.1:8000)
```

### 2.4 选型原则：框架是加速器，核心 IP 自研

为避免"框架锁定"误解，明确边界：**LangGraph、LiteLLM、LanceDB 均是可替换的适配层**，真正的核心 IP 是：
- **自研 Toolset**（L2）—— 直接改 UE 引擎、模型无关
- **自研 SharedState 契约 + Agent 角色定义**（L3）—— JSON Schema，与框架解耦
- **自研编排语义**（L4）—— DAG 依赖传播、回退策略、空间分区，LangGraph 只是其 StateGraph 实现载体

若未来需替换 LangGraph 为自研状态机，仅需重写 `orchestrator/dag.py` 的 StateGraph 组装部分，Agent / Toolset / SharedState 均不动（TDR-006）。

---

## 3. L1 宿主与协议适配层

### 3.1 UE 侧组件

| 组件 | 实现 | 职责 |
|---|---|---|
| MCP Server | UE 5.8 内置 `ModelContextProtocol` 插件 | 监听 `127.0.0.1:8000/mcp`，JSON-RPC |
| ToolsetRegistry | `ToolsetRegistry` 插件 | 收集所有 `UToolsetDefinition`/`@toolset_registry` 注册的工具，生成 JSON Schema |
| Tool 实现 | **Python**（快速迭代）+ **C++**（`UToolsetDefinition` + `UFUNCTION(meta=(AICallable))`，性能/反射场景） | 执行引擎操作 |
| Safeguard 拦截器 | Python 中间件，注册在 Tool 调用链最前端 | 沙箱、风险分级、审批、超时 |

### 3.2 Tool 注册规范（契约）

**Python 写法**：

```python
from toolset_registry import toolset_registry, ToolInput, ToolOutput
from unreal import AssetToolsHelpers, EditorAssetLibrary
import json

class PCGToolset:
    @toolset_registry.tool_call(
        name="pcg_generate_graph",
        description="按 JSON 规格生成/修改 PCG Graph 资产",
        risk="mutating",
        schema={
            "biome": "string",
            "graph_path": "string",
            "nodes": "array",
            "bounds": "object"
        }
    )
    def generate_graph(params: dict) -> dict:
        # 1. Safeguard 已前置校验（沙箱 + 风险）
        # 2. 通过 unreal.PCG 蓝图/Python API 构造 Graph
        ...
        return {"ok": True, "asset_path": "...", "node_count": N}
```

**C++ 写法**：

```cpp
UCLASS()
class UPCGToolset : public UToolsetDefinition {
    GENERATED_BODY()
public:
    UFUNCTION(meta=(AICallable))
    static FToolResult GenerateGraph(const FString& Biome, const FString& GraphPath, const TArray<FSerializedPCGNode>& Nodes);
};
```

**统一返回结构**：

```json
{ "ok": true, "data": { ... }, "version": "1.2.0" }
{ "ok": false, "error_code": "SANDBOX_DENIED | INVALID_PARAM | PCG_COMPILE_FAIL | TIMEOUT", "detail": "..." }
```

### 3.3 调用生命周期（关键路径）

```
Agent 产出意图
   │  (intent JSON)
   ▼
Orchestrator 任务队列
   │  1. 查 Risk → 若 destructive 则阻塞等人工审批
   │  2. 分配空间分区锁（坐标范围）
   │  3. 注入 trace_id / parent_hash
   ▼
MCP Client ──JSON-RPC──▶ UE MCP Server
   │                        │
   │                        ▼
   │                  Safeguard 拦截器
   │                        │  (通过 / 拒绝 / 超时)
   │                        ▼
   │                  Toolset 执行（Game Thread）
   │                        │
   │                        ▼
   │                  Post-Tool Hook
   │                    ├─ Git auto-commit + diff
   │                    ├─ SharedState 版本化 (semver + SHA-256)
   │                    └─ OTel span 落盘
   │                        │
   ◀── tool_result JSON ─────┘
   │
   ▼
Orchestrator 更新 DAG / 触发下游 stale 传播
```

### 3.4 版本与兼容性

- 锁定 **UE 5.8 LTS** 提交哈希（R-01），`.uproject` 记录 `EngineAssociation`。
- Toolset 适配层：每个 Toolset 声明 `engine_min_version` / `engine_max_version`，版本不匹配时返回 `ENGINE_VERSION_MISMATCH` 而非崩溃。
- Python Tool 通过 `init_unreal.py` 注册；新增 `UFUNCTION` 需重启编辑器（文档化约束）。

### 3.5 UE 编辑器连接监督与任务恢复

整条流水线依赖"UE 编辑器在跑、MCP 连得上"，但编辑器可能崩溃、Python 插件重启、全量编译重启导致 MCP 连接中断。需要连接监督与恢复机制：

- **心跳**：Orchestrator 的 `mcp_client.py` 维护到 UE MCP 的 TCP/HTTP 心跳，超时判定断开。
- **任务状态持久化**：所有 `async_long` 任务的 `job_id`、`trace_id`、`parent` 写入 `.logs/task_state.json`（或 SQLite），与 LangGraph Checkpoint 配合。
- **断线恢复**：连接恢复后，Orchestrator 从持久化状态重建未完成任务——查询 UE 侧 job 是否仍在运行（`pcg_get_job_status`），在则继续收割，不在则判定失败并回退。
- **编辑器重启编排**：若检测到编辑器关闭，Orchestrator 标记所有依赖 UE 的任务为 `blocked`，等待人工 `--wait-editor` 重新就绪或自动拉起（脚本化启动 + `init_unreal.py` 自注册）。
- **降级策略**：只读类 Agent（S1/S2/S4 等不依赖 UE 的）在编辑器离线时仍可运行；写/引擎类 Agent 阻塞。

---

## 4. L2 工具平面（Toolset）

### 4.1 全景与 PRD 映射

| Toolset | PRD 编号 | 优先级 | 实现语言 | 关键工具（示例） |
|---|---|---|---|---|
| ProjectToolset | F-TOOL-01.1 | P0 | Python | `project_check_naming`、`project_audit_assets`、`project_list_directory` |
| SafeguardToolset | F-TOOL-01.5 / §7 | P0 | Python（拦截器） | `safeguard_check_path`、`safeguard_request_approval`、`safeguard_rollback` |
| PCGToolset | F-TOOL-01.2 | P1 | C++ + Python | `pcg_generate_graph`、`pcg_run_async`、`pcg_get_output`、`pcg_validate` |
| ArtPipelineToolset | F-TOOL-01.3 | P1 | Python | `art_import_mesh`、`art_configure_nanite`、`art_create_material_instance` |
| BuildToolset | F-TOOL-01.4 | P1 | Python | `build_live_coding`、`build_full`、`build_cook_run`、`build_run_pie_tests` |
| LightingToolset | F-TOOL-01.6 | P1 | Python | `lighting_place_directional`、`lighting_set_postprocess`、`lighting_bake_lightmass` |
| AudioToolset | F-TOOL-01.7 | P2 | Python | `audio_place_ambient`、`audio_create_sound_cue` |
| UIToolset | F-TOOL-01.8 | P2 | Python | `ui_create_umg_widget`、`ui_bind_datatable` |
| DataToolset | F-TOOL-01.9 | P2 | Python | `data_csv_to_datatable`、`data_validate_rows` |
| ProfilerToolset | F-TOOL-01.10 | P2 | C++ + Python | `profiler_capture_gpu`、`profiler_parse_insights`、`profiler_report` |
| PlaytestToolset | F-TOOL-01.11 | P2 | Python | `playtest_record_session`、`playtest_replay`、`playtest_metrics`、`playtest_smoke` |
| BenchmarkToolset | F-TOOL-01.12 | P2 | Python | `benchmark_refresh_competitors`、`benchmark_align`、`benchmark_report` |

### 4.2 公共规范

- **命名**：`{toolset}_{verb}_{noun}`，全小写蛇形。
- **参数**：所有参数在 JSON Schema 中声明类型、范围、必填；`bounds`/`coordinates` 统一为 `{min: {x,y,z}, max: {x,y,z}}`。
- **返回**：统一 `ToolResult`（见 §3.2）；大对象只返回引用（资产路径 / 句柄），不内联二进制。
- **幂等**：所有 `create/update` 接受 `idempotency_key`，重复调用不产生副作用。
- **超时**：默认 30s，长任务走 `async + poll`（见 PCGToolset）。

### 4.3 关键 Toolset 设计

#### 4.3.1 PCGToolset（核心）

```
pcg_generate_graph(spec: PCGGraphSpec) → {asset_path, node_count}
pcg_run_async(asset_path, bounds)      → {job_id}
pcg_get_job_status(job_id)             → {status, progress, result_path}
pcg_get_output(asset_path, bounds)     → {instances: [...], stats}
pcg_validate(asset_path)               → {ok, errors: [...]}
```

- `PCGGraphSpec`：JSON 描述节点（Surface Sampler / Mesh Spawner / Transform / Filter）+ 边（属性连接），由 Scene/PCG Agent 产出。
- 异步机制：调用 `UPCGGenerateGraphAsync`（PRD §4.2 引用），立即返回 `job_id`；Orchestrator 轮询/回调。
- 验证：节点参数类型、资产引用存在性、循环检测。

#### 4.3.2 BuildToolset

```
build_live_coding(sources: [path]) → {ok, errors}
build_full(target: "Editor|Game")  → {ok, duration_s, errors}
build_cook_run(platform, config)   → {ok, artifacts: [path]}
build_run_pie_tests(test_names)    → {passed, failed, screenshots: [path]}
```

- 编译：封装 `UnrealBuildTool`；Live Coding 走编辑器命令，全量走 CLI（可异步排队，缓解 R-03）。
- 测试：启动 PIE → 执行 `Functional Testing` 蓝图/Python 脚本 → 截图 → 返回结果。

#### 4.3.3 SafeguardToolset（详见 §7）

- 提供 `safeguard_check_path(path) → {allowed, zone}`、`safeguard_request_approval(tool, params, risk) → {approved}`。
- 是所有写类 Tool 的前置依赖（AOP 式注入，避免每个 Tool 重复实现）。

#### 4.3.4 PlaytestToolset（评估底座）

```
playtest_record_session(player_handle, bounds, duration_s, seed) → {clip_id}
# 自动角色按某策略玩一段，录制状态/事件/截图帧（生成→游玩→收集轨迹的可重复实验）
playtest_replay(clip_id, override_params={...})               → {trajectory, events, frames}
# 用不同参数回放同一段轨迹（更快/更贪/更探索），供评估多视角批判
playtest_metrics(clip_id, metrics=["deaths","pacing","pickups","time_gates"]) → {report}
playtest_smoke(level_path, waypoints)                         → {reachable, blockers}
# 自动走通 spawn→collect→open 最小路径（AutoUE Generation→Cruise→Replay 闭环），作为可玩性冒烟自证
```

- 驱动 PIE，输出可被 E1/E3/UX 消费的量化游玩数据；异步长任务走 §6.2.1 的外部任务句柄模式。

#### 4.3.5 BenchmarkToolset（横向对标底座）

```
benchmark_refresh_competitors(genre, limit) → {matrix_version}
benchmark_align(artifact_ref, competitor_key, axis) → {score, delta}
benchmark_report(matrix, weights)          → {weighted_score, verdict, rationale}
```

- 负责竞品/市场数据的**定期刷新**（Steam 好评率趋势、评论极性、续作/品类热度），进 LanceDB 长期记忆，避免横向对标停留在立项当天。供 E6 与后验 Agent 消费。

---


## 5. L3 领域智能体

### 5.1 Agent 抽象

```python
@dataclass
class AgentInput:
    task: str                     # 自然语言/结构化指令
    shared_state_ref: str         # 读写的 SharedState 路径
    context: dict                 # RAG 片段、上游产物、风格指南等
    trace_id: str

@dataclass
class AgentOutput:
    result: dict                  # 结构化产出（构建脚本/提案/报告）
    shared_state_delta: dict      # 对 SharedState 的变更
    next_agents: list[str]        # 触发的下游
    artifacts: list[str]          # 产出文件路径

class DomainAgent(ABC):
    name: str
    role: str
    model_profile: str            # "fast" | "strong"
    system_prompt: str
    tools: list[str]              # 可调用 Tool 白名单

    @abstractmethod
    async def run(self, inp: AgentInput) -> AgentOutput: ...
```

- **模型路由**：`fast` → Haiku/Flash（简单生成、格式化）；`strong` → Opus/Pro（设计、代码、评审）。配置驱动，可替换（PRD §4.1.3）。
- **工具白名单**：每个 Agent 仅暴露所需 Tool，最小化权限（例：Market Analyst 只用 `project_list_directory` + RAG，无写权限）。

### 5.2 Agent 实现映射

**策略与研究组（S1–S6，PRD §4.1.3）**

| Agent | 输入 | 产出（SharedState 路径） | 关键 Tool / 数据源 |
|---|---|---|---|
| S1 Market & Audience Analyst | 品类关键词 | `/strategy/market_report.json` | RAG（Steam 数据/行业报告 API）、`data_csv_to_datatable` |
| S2 Competitive Intelligence | 品类 | `/strategy/competitor_matrix.json` | Web 检索、RAG、结构化抽取 |
| S3 Game Design Strategist | 市场缺口 | `/strategy/game_design/*.json` | RAG（GDD 模板）、`director_create_gdd` |
| S4 Business & Platform Strategist | 玩法方案 | `/strategy/business_model.json` | 定价模型计算、EGS/Steam 分成对比 |
| S5 Technical Feasibility Analyst | 方案 | `/strategy/tech_feasibility.json` | RAG（UE 文档/源码）、`profiler_report` |
| S6 Creative Direction Strategist | 世界观方向 | `/strategy/creative_direction.json` | 图像生成 API、情绪板、风格指南 |

**预生产组（①–④）**

| Agent | 产出 | 关键 Tool |
|---|---|---|
| ① Director | `/gdd/main.json`（结构化 GDD） | RAG、任务拆解 |
| ② Concept Artist | `/art/style_guide.json` + 参考图 | 图像生成 API |
| ③ Level Designer | `/level/blockout.json`（waypoints/zones/pacing） | `pcg_*`、`project_audit_assets` |
| ④ Data Agent | `/data/*.csv` → DataTable | `data_csv_to_datatable` |
| W1 Writer | `/narrative/*.json`（剧情/对白/情境/文案） | LLM + 叙事模板 RAG |
| ND System / Numerical Designer | `/system_balance/*.json`（成长/产出/战斗数值/经济） | LLM + 数值设计理论 RAG + 平衡仿真 |

**生产组（⑤–⑪）**

| Agent | 产出 | 关键 Tool |
|---|---|---|
| ⑤ Asset Retriever | 资产引用列表 | Fab/Quixel API、本地库检索 |
| ⑥ Scene/PCG | PCG Graph + 截图验证 | `pcg_generate_graph`、`pcg_run_async`、截图 |
| ⑦ 3D Asset Generator | 外部生成资产 | 图像/3D API、`art_import_mesh` |
| ⑧ Lighting | 灯光 + PostProcess | `lighting_*`、截图比对 |
| ⑨ Gameplay | Verse/C++ 模块 | `build_live_coding`、代码生成 |
| ⑩ Audio | 音效配置 | `audio_*` |
| ⑪ UI | UMG Widget | `ui_create_umg_widget` |
| TA Technical Artist | `/art/tech_spec.json` + 资产技术校验 | ArtPipeline、Material、`profiler_report` |
| PC Player Character Designer | `/character/player.json`（体感/动作风格/手感 KPI） | LLM + 动作设计理论 RAG |
| EB Enemy & Boss Designer | `/character/enemies/*.json`（行为/攻击/数值/难度） | LLM + 竞品行为库 RAG |
| AN Animation Agent | `/character/animation/*.json`（状态机/校验结论） | 外部动画 API + ArtPipeline |

**验证与交付组（⑫–⑭）**

| Agent | 产出 | 关键 Tool |
|---|---|---|
| ⑫ Profiler | 超标报告 | `profiler_*` |
| ⑬ Reviewer/QA | 评审 + 缺陷报告（工程分） | 代码审查 LLM、`build_run_pie_tests` |
| ⑭ Build Agent | 可执行包 | `build_cook_run` |

**评估组（E1–E6 + UX，全部只读 `strong`，写 `eval/*`）**

| Agent | 产出（SharedState 路径） | 关键 Tool / 数据源 |
|---|---|---|
| E1 Experience Auditor | `/eval/experience.json`（节奏/动线痛点） | `playtest_replay`、pacing_curve |
| E2 Content Critic | `/eval/content.json`（风格/氛围/音频一致性） | 截图、场景渲染、风格指南比对 |
| E3 Gameplay / Fun Auditor | `/eval/gameplay.json`（机制/手感/数值失衡） | `playtest_metrics`、DataTable |
| E4 Design & Economy Judge | `/eval/design.json`（关卡/经济/收集鸡肋） | blockout、数值、通关数据 |
| E5 Monetization & Market Fit | `/eval/monetization.json` | S4 输出、business_model |
| E6 Benchmark & Horizontal | `/eval/benchmark.json`（横向对照 + 受欢迎度 + GO/NO-GO/PIVOT） | `benchmark_*`、S1/S2 数据 |
| UX Playtest Researcher | `/eval/playtest_insights.json`（玩家卡点量化） | `playtest_record_session`、`playtest_replay` |

### 5.3 SharedState 契约

- **存储**：Git 仓库内 `shared_state/` 目录，JSON 文件按路径组织（见上表）。事实源即 Git，天然可回滚。
- **消息信封**：

```json
{
  "schema_version": "1.2.0",
  "parent_hash": "sha256:...",
  "producer": "LevelDesigner",
  "created_at": "ISO8601",
  "payload": { ... }
}
```

- **传播规则**：上游变更 → Orchestrator 标记下游 `stale`（深度 ≤ 3）→ 下游 Agent 拉取 diff → 决定是否重跑。禁止自由文本传递（PRD §4.1.3）。

**评估命名空间 `eval/*`（与生产读写分离）**：

评估组只读 `game/*`、`strategy/*` 等生产/策略区，**只写 `shared_state/eval/`**，永不回写生产产物区。评估结果不触发下游生产 `stale`（因为评估不产生被下游消费的生产变更）；它通过 Orchestrator 的**定向回退**把结论送回目标生产 Agent。`eval/*` 也在 Git 事实源内，可 diff、可回滚、可作为前后评估回归对比。

评估报告统一信封（复用 §5.3 信封 + 增加评估专有字段）：

```json
{
  "schema_version": "1.2.0",
  "parent_hash": "sha256:gameplay-v3",
  "producer": "E3_GameplayAudit",
  "created_at": "ISO8601",
  "audience": "hardcore",
  "evaluated_artifacts": ["/game/gameplay/spec.json", "/game/data/balance.json"],
  "axis_scores": { "fun_loop": 54, "combat_feel": 41, "growth": 38, "balance": 29 },
  "critical_flaws": [
    { "id": "F-017", "severity": "critical", "axis": "numerical", "desc": "后期成长曲线坡度不足", "link_back_to": "ND" }
  ],
  "recommendation": { "verdict": "FIX", "target": "ND", "reason": "数值失控将劝退玩家" }
}
```

- `audience`：本份报告站位的用户画像（hardcore / casual / progress / visual / horror-vet）——实现"不同用户角度批判"。
- `axis_scores` + 画像权重折算出综合"体验分 / 商业分"（0–100），供 §6.2 回退触发。
- `critical_flaws[].link_back_to`：定位回退目标生产 Agent（Gameplay / PC / EB / ND / Scene / ③ Level Designer 等）。
- `recommendation.verdict`：`FIX / GO / NO-GO / PIVOT`，`GO/NO-GO/PIVOT` 进人工审批卡点。

---

## 6. L4 编排与治理层

### 6.1 Orchestrator 核心组件

```
┌──────────────────────────────────────────────┐
│              Orchestrator                    │
│  ┌──────────┐  ┌────────┐  ┌────────────┐  │
│  │ TaskQueue │  │ DAG    │  │ Retry/     │  │
│  │ (优先级)  │  │ Engine │  │ Loop(≤3)  │  │
│  └────┬─────┘  └───┬────┘  └─────┬──────┘  │
│       │            │             │         │
│  ┌────▼────┐  ┌────▼────┐  ┌─────▼──────┐  │
│  │ Model   │  │ RAG     │  │ Memory     │  │
│  │ Router  │  │ Grounder│  │ Manager    │  │
│  └────┬────┘  └────┬────┘  └─────┬──────┘  │
│       │            │             │         │
│  ┌────▼────────────▼─────────────▼──────┐   │
│  │        MCP Client (唯一写入者)        │   │
│  └─────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
```

### 6.2 DAG 引擎

- **节点**：Agent 任务；**边**：`SharedState` 读写依赖（自动从 `shared_state_ref` 推导）。
- **调度**：拓扑排序 + 优先队列；同一层可并发（受空间分区锁约束）。
- **失效传播**：上游 `shared_state_delta` 提交后，BFS 标记下游 `stale`（深度 ≤ 3，PRD §4.1.3）；下游 Agent 被调度时先 `diff` 决定是否重跑，避免无效计算。
- **回退循环**：**工程分（⑬ Reviewer）、体验分与商业分（E1–E6）任一 < 70 或含 critical bug → 按报告的 `link_back_to` 定位责任 Agent → 重新入队（最多 3 次）→ 仍失败则升级人工**。评估组自身只读，不回写生产，避免评估引发无效重跑。

#### 6.2.1 长时任务的执行模型（LangGraph 协调）

LangGraph 的 StateGraph 是同步图推演模型，天然不适合让一个节点阻塞等待几十秒到几十分钟的长任务（PCG 生成、全量编译、PIE 测试）。为此引入**两阶段节点 + 外部任务句柄**模式：

```
图节点（Agent 发起长任务）
   │ 1. 校验/准备参数，同步返回 {job_id, status:"pending"}
   ▼
StateGraph 将该边标记为 `suspended`（节点返回特殊值，不继续图推演）
   │
   ▼（后台 asyncio 任务继续轮询 UE 的 job_id）
   │  异步收割 → 结果写入 shared_state + 触发图节点恢复
   ▼
StateGraph 恢复该节点 → 读取结果 → 继续下游
```

具体规则：
- Agent 的 Tool 调用分两类：`sync`（< 10s，正常走图步）与 `async_long`（> 10s，返回 `{job_id}` 即挂起）。
- 挂起节点让出协程控制权，`TaskQueue` 调度其它就绪分支，**不阻塞无关任务并行**。
- `job_id` 统一注册到 Orchestrator 的 `AsyncJobRegistry`，由独立收割协程轮询/回调 UE 的 `pcg_get_job_status` / `build_status`，完成后恢复挂起节点。
- LangGraph 的 Checkpoint（TDR-006）持久化挂起状态，进程重启后可恢复未完成的异步任务，避免长任务因崩溃丢失。

> 这一模式把"图推演"（快）与"长动作等待"（慢）解耦，是 P0 能否跑通 `run_pie_tests`、`pcg_run_async`、全量编译的关键。

### 6.3 RAG Grounding

- **语料（按优先级）**：
  1. **UE 5.8 MCP / ToolsetRegistry 实验文档**（最高优先——它是 Experimental、API 面窄且最易变，是工具幻觉重灾区；随 `engine_min_version` 锁定并跟随版本更新）
  2. UE 官方 API/引擎文档
  3. 项目编码规范、`shared_state` 已验证产物
  4. 引擎源码（`Engine/Source`，符号级）
  5. 历史已验证 Tool / 脚本（录制的 golden 样本）
- **索引**：按符号（类名/函数名/蓝图节点）+ 语义双索引；检索结果带 `source + 版本` 元数据；MCP 语料单独标注 `experimental_mcp` 标记，提示 Agent 谨慎处理不确定项。
- **注入**：作为 Agent `context` 片段，显著降低幻觉（R-05）。

### 6.4 记忆分层

| 层级 | 存储 | 内容 | TTL |
|---|---|---|---|
| 短期 | 进程内 dict | 当前对话/任务上下文 | 任务生命周期 |
| 工作记忆 | SharedState（Git） | Agent 间传递的结构化状态 | 项目生命周期 |
| 长期（RAG） | **LanceDB**（嵌入式，`./memory/lancedb/`） | 已验证代码片段、风格指南、UE 官方文档片段、历史决策、**后验预测偏差、竞品/市场基线** | 永久 |

- **LanceDB 选型理由**：嵌入式、零独立服务、数据与项目同目录（可 gitignore/备份）、列式存储 + 磁盘索引，大数据量下性能优于 ChromaDB；支持向量 + 全文 + 元数据混合检索，契合 UE API 符号+语义双索引需求（TDR-009）。
- **后验与竞品基线**：立项时 E6 的横向预测（受欢迎分 + GO/NO-GO + 关键假设）存档；上线/内测后由**后验环节**逐条核对"预测 vs 实际"，把**预测偏差标注**写回长期记忆，修正下一次立项的市场基线与 E6 权重。BenchmarkToolset 定期刷新的竞品数据同样落此长期记忆（标注 `source + version + 采集时间`），避免横向对标停留在立项当天。
- **索引结构**：每个文档带 `source + 版本 + chunk_type` 元数据；检索返回带 `score` 的结果片段，注入 Agent `context`。
- **迁移**：通过 LangChain `VectorStore` 抽象接入；未来若需分布式可平滑换 Qdrant，仅改适配层。

### 6.5 运行入口与人工卡点

**运行入口（P0）：CLI + 结构化日志**（TDR-011）

- 入口命令：`python -m orchestrator run --task "<自然语言需求>" [--plan <plan_id>] [--dry-run]`。
- 框架：**Typer**（CLI 解析）+ **Rich**（终端美化 + 实时 DAG/审批展示）。
- 输出：每条 Tool/Agent 事件以 **JSON Lines** 写入 `.logs/trace.jsonl`，既给人看，也作为下次任务的上下文片段（可被 LanceDB 索引）。
- 审批交互（P0）：CLI 内联 `y/N` 确认（替代 Web Console），支持 `--auto-approve-read-only` / `--require-approval destructive` 开关，便于 CI 自动化。

**运行入口演进路线：**

| 阶段 | 形态 | 说明 |
|---|---|---|
| P0（本阶段） | **CLI + 结构化日志** | 成本最低，Agent 可编程驱动，跑通闭环 |
| P1+ | Web 控制台（可选） | 可视化编排/DAG/审批/监控；作为 CLI 的前端换皮，不改编排核心 |
| P2+ | UE 编辑器内面板（可选） | 在 UE 内查看 Agent 进度；受 MCP/反射限制，不承载核心交互 |

**人工卡点：**

- 阻塞清单（配置化）：`destructive` 操作、`build_cook_run`、`git push`、资产入库。
- 审批展示（P0）：CLI 内联 diff + 风险等级 + 一键批准/拒绝/回滚；P1+ 可选 Web Console 增强可视化（TDR-011）。

**审批挂起时 DAG 的语义**：

当一个任务需要人工审批时，它进入 `WAITING_APPROVAL` 状态，挂起于 TaskQueue：
- **该节点及其唯一的写后继被挂起**——依赖它输出的下游分支不会调度，避免读到未审批的中间态。
- **无关分支继续运行**：没有依赖关系、且位于不同空间分区/不同只读路径的任务正常推进，不让一个等待卡死整条流水线。
- **审批通过** → 任务出队，写行为执行 → `post-tool` hook 落库 → 挂起的下游自动解除 stale 并调度。
- **审批拒绝** → 任务标记失败，回退语义同 §6.2 回退循环，产出不落库、不触发下游。
- 审批中支持"diff 预览"：批准前展示将被写入的完整 diff + 风险等级 + 目标资产路径，避免盲批。

---

## 7. 安全治理体系

### 7.1 四道闸门（PRD §4.1.2）

| 闸门 | 实现 | 规则 |
|---|---|---|
| ① File Sandbox | `SafeguardToolset`（运行时）+ Git `pre-commit`（提交时） | `no_touch_zones = [/Engine/, /Plugins/CoreFramework/]`；Agent 仅写 `/Game/Generated/`、`shared_state/` |

> **① 的两层职责边界（不重复、不冲突）**：
> - **运行时（SafeguardToolset / AOP 拦截）**：在 Tool 执行前**拦行为**——阻止越界写入，是第一道也是实时裁决。属"行为拦截层"。
> - **提交时（Git `pre-commit`）**：在 commit 前**兜底审计**——校验即将入库的 diff 不违反命名/沙箱白名单，属"审计兜底层"。这条主要防"绕过运行时、恶意/误提交"。
> - 职责不同：运行时负责"不让 Agent 做到"，提交时负责"确保进库的东西干净"。两者独立触发，任何一道拒绝即失败。
| ② Risk Gating | Orchestrator 前置检查 | `read_only` 放行 / `mutating` 轻量审批 / `destructive` 人工确认 |
| ③ Version Hook | Git `post-tool` hook | 每次 `mutating` 自动 commit（`feat(agent): <agent> <intent>`）+ diff 报告；`destructive` 打 tag 便于回滚 |
| ④ Timeout & Isolation | Tool 调用包装 | 30s 超时；首次验证用 disposable sandbox map（`/Game/Sandbox/`），通过后再合并 |

### 7.2 回滚

- `safeguard_rollback(commit_sha)` → `git reset --hard <sha>` + 重新加载关卡。目标：≤ 1 分钟（PRD §5.3）。
- 空间分区锁在回滚期间释放并重建。

### 7.3 网络与认证

- MCP 仅绑 `127.0.0.1`（R-07）；多机协作场景通过 SSH 隧道，不开放端口。
- 当前版本假设本机单人操作；多用户场景后续引入 Token + TLS（记录为 follow-up，非本期范围）。

---

## 8. 参考游戏技术实现

> 本节把 PRD §4.2 的功能需求落到具体技术方案。参考游戏是工具链的验证载体，其实现必须**全程走 Agent 流水线**以证明工具链有效性。

### 8.1 场景与 PCG

- **生物群系**：森林 / 废墟 / 山地，各对应一份 `PCGGraphSpec`（PRD §4.2 PCG 场景生成）。
- **地形**：`Landscape` + 分层权重（spline 驱动群系边界），由 Level Designer 输出坐标分区。
- **植被/遗迹**：Surface Sampler + Mesh Spawner，密度/坡度/高度约束从风格指南读取。
- **交互物**：可收集品（符文石）、机关、敌人生成点 → `PCGPoint` + 自定义 Actor 标签，由 Gameplay Agent 绑定逻辑。
- **迭代闭环**：生成 → 截图 → Vision 模型/人工评分 → 调整参数 → 重生成。

### 8.2 玩法（Gameplay）

- **角色**：第三人称 Character（移动/跳跃/攀爬/交互），C++ 基类 + 蓝图子类（蓝图仅作数据容器，逻辑走 C++/Verse，规避 R-02）。
- **收集系统**：`ACollectible` 组件 + `UGameplayStatics` 计数，状态入 DataTable。
- **解谜**：触发器（Trigger Box）+ 状态机（`UStateTree` 或 Verse），机关门/移动平台/压力板。
- **战斗（轻量）**：近战/闪避 + 敌人 AI（`Behavior Tree` + `Environment Query System`），巡逻/追击/攻击。
- **关卡状态机**：`ULevelStateMachine`（未激活→进行中→完成），驱动全局事件。

### 8.3 资产管线

```
外部生成 API ──▶ 临时目录 ──▶ 质检 Agent（风格/三角面/内容安全）
                                        │ 通过
                                        ▼
                              ArtPipelineToolset
                                ├─ art_import_mesh
                                ├─ art_configure_nanite
                                └─ art_create_material_instance
                                        │
                                        ▼
                              /Game/Generated/Assets/
                                + SourceAssetMetadata（prompt/模型/license）
```

- 元数据写入每条资产的 `AssetUserData`，支持溯源与 license 审计。

### 8.4 关卡设计 / Blockout

1. Director 拆解 GDD → Level Designer Agent 产出 `blockout.json`：
   - `waypoints: [{id, pos, type: spawn|poi|climax|exit}]`
   - `zones: [{id, bounds, purpose: explore|puzzle|combat}]`
   - `pacing_curve: [{time, tension}]`
2. Scene/PCG Agent 读取 `blockout.json` 作为 PCG 约束（POI 处留空、路径两侧密度衰减等）。
3. Blockout 用简单几何体（`Static Mesh Cube/Ramp`）占位，验证动线后再替换为最终资产。

### 8.5 灯光、音频、UI

- **灯光**：风格指南（色调偏冷、材质风化石材/金属/苔藓）→ Directional + Sky Light + Sky Atmosphere + 逐 POI 局部光源 → PostProcess（Tone Mapping/Bloom/AO/曝光）→ 截图比对。
- **音频**：按 biome 放置 `Ambient Sound`（风/水/鸟鸣）；交互 SFX 绑定事件；`Sound Cue` + `Attenuation`（距离衰减/空间化）。
- **UI**：UMG Widget（HUD 收集计数、进度、交互提示"按 E 收集"），数据源绑定 DataTable，支持热更新数值。

### 8.6 性能剖析

- Profiler Agent 调用 `profiler_capture_gpu/cpu` → 解析 Unreal Insights `.utrace` → 生成超标报告（帧率/资产密度/draw call 阈值）。
- 超标 → 回传 Scene/Lighting Agent 优化（减密度、合并实例、调 LOD），形成闭环。

---

## 9. 工程化：构建、CI、部署

### 9.1 仓库结构

```
repo/
├── unreal/                    # UE 5.8 项目（.uproject）
│   ├── Source/                # C++ Toolset / Gameplay
│   ├── Content/Python/        # Python Toolset + init_unreal.py
│   ├── Plugins/ToolsetRegistry/
│   └── ...
├── orchestrator/              # L4 编排（Python）
│   ├── cli.py                # CLI 入口（Typer）：run / plan / approve / rollback
│   ├── dag.py                # 自研 DAG 引擎（依赖传播、stale、回退）
│   ├── state_graph.py        # LangGraph StateGraph 组装（可替换适配层）
│   ├── agents/                # 33 个领域 / 评估 Agent（生产 + 评估组分目录）
│   ├── rag.py                # LanceDB 检索 + 注入
│   ├── memory/                # LanceDB 持久化目录（gitignored）
│   ├── models.py             # LiteLLM 封装 + 模型路由（fast/default/strong）
│   ├── config/models.yaml    # 模型映射配置（TDR-010）
│   └── mcp_client.py         # MCP Client（唯一写入者）
├── shared_state/              # SharedState（Git 事实源）game/ · strategy/ · eval/ · narrative/ · character/
├── .logs/trace.jsonl          # 结构化追踪日志（CLI 输出）
├── tests/                     # pytest + UE 自动化测试
├── docs/                      # PRD / 本设计文档 / ADR / TDR
└── .github/workflows/ci.yml
```

### 9.2 CI 流水线（GitHub Actions）

```
push / PR
  ├─ lint（Python ruff, C++ clang-format, JSON Schema 校验）
  ├─ unit-test（pytest + Tool 单元测试，mock UE）
  ├─ schema-check（SharedState 契约 / Tool JSON Schema）
  ├─ build-editor（UBT 编译 Editor, 增量）
  ├─ smoke-test（启动编辑器 → list_tools → 最小闭环 AC-P0-06）
  └─ artifact（构建产物 + 覆盖率报告）
```

- 全量编译（R-03，50–70min）放在 nightly，不阻塞 PR。
- Git hook：`pre-commit` 校验命名/沙箱白名单；`post-tool`（运行时）自动 commit Agent 改动。

### 9.3 部署形态

- **开发期**：编排进程 + UE 编辑器同机（本机单人，符合 R-07）。
- **CI 期**：UE 运行于容器/GitHub Runner（GPU 可选，用于渲染截图验证）。
- **对外/团队协作（未来）**：编排服务化 + UE 远程 MCP（SSH 隧道 + Token），本期不做。

---

## 10. 可观测性与可测试性

### 10.1 追踪

- OpenTelemetry：`trace_id` 贯穿 UI → Orchestrator → Agent → Tool → UE。
- Span 属性：agent、tool、risk、duration、ok、error_code、shared_state_version。
- 落盘 OTLP → 本地 SQLite/文件，支持按 trace_id 重放单次调用链。

### 10.2 测试金字塔

| 层 | 范围 | 工具 | 示例（对应 PRD AC） |
|---|---|---|---|
| 单元 | Tool / Agent 纯逻辑 | pytest | Tool JSON Schema 校验 |
| 集成 | Tool ↔ UE（mock MCP） | UE Python API + pytest | AC-P0-03 沙箱、AC-P0-04 审批 |
| 端到端 | 完整流水线（含策略/生产） | UE 自动化测试 + Agent 编排 | AC-P2-07 提案、AC-P3-01 流水线、AC-P4-03 介入率 |
| 验收 | PRD 每条 AC | 手工 + 自动化混合 | §11 全量；AC-P0/1/2/3/4 全覆盖 |

> **AC 全覆盖**：验收层覆盖 PRD §9 的 36 条 AC（P0: 01–06，P1: 01–08，P2: 01–07，P3: 01–11，P4: 01–04）。每阶段在对应里程碑交付时逐条过验，见 §7。

- 每个 Tool 配套**录制回放**：录制一次真实 UE 响应，后续测试 replay，避免依赖运行中的编辑器。

### 10.2.1 AI 产物质量评估层（evals）

测试金字塔测的是"程序逻辑"，但 AI 系统的关键风险在**模型产物的质量**——Director 出的 GDD 是否完整、PCG 规格是否合理、生成的 Verse 代码是否正确。这需要独立的 evals 层：

| eval 维度 | 评估方法 | 通过标准 |
|---|---|---|
| GDD 完整性 | golden 模板 + 必需字段校验 | 必填字段齐全、无逻辑冲突 |
| PCG 规格合理性 | 结构校验 + 参数区间 + 资产引用存在性 | 全部通过 `pcg_validate` |
| 代码正确性 | 编译（`build_live_coding`）成功后跑单元/功能测试 | 0 编译错 + 目标功能通过 |
| 风格一致性 | Vision 模型 + 人工采样比对风格指南 | 达标率 ≥ 90%（AC-P4-02） |
| 内容安全 | 评测 Agent 审核 | 无违规资产 |
| 回归基准 | 历史 golden 用例重新跑，对比产物差异 | 无意外退化 |

**工程化**：
- `tests/eval_cases/*.yaml` 存放 golden 用例（输入 + 期望产物特征），`evals/` 脚本批量跑。
- evals 结果写入 `.logs/evals.jsonl`，纳入 CI。
- **模型/工具链升级后强制跑 evals 回归**，防止"换模型后 GDD 质量下降"这类静默退化。

> **评估组与 evals 的关系**：本节 evals 层评估的是"工具链/Agent 的产物质量"（程序正确性层）；§5.2 的评估组（E1–E6 + UX）评估的是"游戏本身值不值得做、用户爱不爱、能否赚钱"（产品层，产出 `eval/*` 报告，含体验分/商业分）。两者都进回退循环（§6.2，任一 < 70 触发）。**后验评估**在参考游戏内测/上线早期数据回落后触发：核对"E6 立项预测 vs 实际"，预测偏差写回 LanceDB（§6.4），作为后续立项与评估权重的训练基线。

### 10.3 指标（对接 PRD §5.1）

`tool_call_duration_seconds`、`pcg_generation_seconds`、`build_duration_seconds`、`human_intervention_rate`、`agent_retry_count`、`rollback_count` —— 全部以 Prometheus 格式暴露，CI 中对比基线判定达标。

---

## 11. 性能工程

| 目标（PRD §5.1） | 实现手段 |
|---|---|
| Live Coding < 30s | 增量编译 + 优先 Live Coding；全量走异步队列 |
| PCG 单关卡 < 60s | 异步 `pcg_run_async` + 空间分区并行生成 + 实例合并 |
| Tool 调用 < 10s（超时 30s） | 同步短任务；长任务转 `async + poll` |
| 端到端：提案 < 4h / 可玩关卡 < 8h | DAG 并发调度 + 模型路由（fast/strong）+ 缓存 RAG 与生成资产 |
| 人工介入率 < 20% | 闭环回退（≤3）+ RAG grounding + 风格约束质检 |
| 参考游戏 60 FPS @ 1440p (RTX 4070) | Nanite + Lumen Lite、实例合并、Profiler 闭环优化 |
| 主机 30 FPS 稳定 | 动态分辨率 + 主机 DevKit P3 评估 |

- **冷编译缓解（R-03）**：Live Coding 为主、全量夜间构建、编译结果缓存。
- **Game Thread 串行（R-04）**：单写入者 + 空间分区锁，Orchestrator 序列化所有写。

---

## 12. 可维护性与 UE6 迁移

### 12.1 可维护性设计

- **模型可替换**：默认 Claude（Opus/Sonnet/Haiku 三档），通过 **LiteLLM 封装**，换模型 = 改一个配置文件（`orchestrator/config/models.yaml`），满足"模型不锁定"（TDR-010、PRD §5.4）。
- **向量库可替换**：LanceDB 通过 LangChain `VectorStore` 抽象接入，换 Qdrant/Milvus = 改适配层（TDR-009）。
- **编排可替换**：LangGraph 仅实现自研 DAG/状态图语义，重写 `orchestrator/dag.py` 即可切换自研状态机，Agent / Toolset / SharedState 不动（TDR-006）。
- **Toolset 版本适配**：适配层集中在 `orchestrator/adapters/ue_bridge.py`，MCP API 变更 = 改一个文件。
- **文档覆盖**：每个 Tool 公开方法 100% docstring + JSON Schema 自动生成（CI 校验）。
- **新增 Agent / Toolset**：定义 Schema + 注册即可，无需改编排层（PRD §5.5）。

### 12.2 UE6 迁移策略（TDR-004）

- **现状**：UE 5.8 为计划末代 UE5；UE6 Early Access 2027 末，稳定版 2028–2029；UE6 逐步弃用蓝图/Actor，转向 **Verse + Scene Graph**（提供转换工具）。
- **本设计的前瞻适配**：
  1. **逻辑往 Verse 靠**：Gameplay 逻辑（状态机、收集、解谜、敌人 AI）优先用 Verse，C++ 仅作性能/引擎扩展。
  2. **MCP 架构与引擎解耦**：L1 适配层抽象为 `EngineBridge` 接口，UE6 实现替换；L2/L3/L4 不依赖 UE 具体类型。
  3. **共享状态标准化**：SharedState 用引擎无关 JSON，迁移时不丢失。
  4. **复用率 ≥ 80%**：目标为 Toolset 业务逻辑 + Agent + Orchestrator 复用，仅适配层重写。
- **节奏**：P5（第 43–52 周）后启动 UE6 迁移；P4 前做兼容性 PoC（R-09）。

---

## 13. 技术决策记录（TDR）

| ID | 决策 | 理由 | 备选 | 状态 |
|---|---|---|---|---|
| TDR-001 | Agent 只产构建脚本，不直接改 .uasset | 确定性/可复现/可回滚；规避蓝图二进制（R-02） | 直接编辑 API | 采纳 |
| TDR-002 | Orchestrator 作为唯一 MCP 写入者 | 解决 Game Thread 串行 + 并发写（R-04）；集中审计/审批 | 每 Agent 直连 | 采纳 |
| TDR-003 | Python Tool 为主 + C++ Tool 为辅 | Python 迭代快覆盖 90%；C++ 用于 PCG/Profiler 性能路径 | 全 C++ | 采纳 |
| TDR-004 | 逻辑优先 Verse，C++ 仅扩展 | UE6 Verse + Scene Graph 路线，降低迁移成本 | 全 C++/蓝图 | 采纳 |
| TDR-005 | SharedState 以 Git JSON 为事实源 | 天然版本化 + 回滚，满足 §7 回滚目标 | 数据库 | 采纳 |
| TDR-006 | 编排用 **Python + LangGraph** + 自研 DAG | LangGraph 提供 StateGraph/条件边/Checkpoint 原语加速 MVP；依赖传播、stale 标记、回退语义自研。LangGraph 为可替换适配层，非框架锁定 | 纯自研状态机 | 采纳 |
| TDR-007 | MCP 绑 127.0.0.1 + 本机单人 | 满足 R-07，简化认证；多用户为 follow-up | Token 认证 | 本期采纳 |
| TDR-008 | 全量编译放 nightly，不阻塞 PR | 缓解 R-03 长编译 | 分布式编译 | 采纳 |
| TDR-009 | **RAG / 长期记忆用 LanceDB** | 嵌入式零运维、列式+磁盘索引性能优于 ChromaDB；支持向量+全文+元数据混合检索；数据随项目走 | ChromaDB / Qdrant | 采纳 |
| TDR-010 | **默认 LLM 用 Anthropic Claude**（Opus 复杂 / Sonnet 主力 / Haiku 兜底），LiteLLM 封装 | 代码/工具调用最强、长上下文、复杂推理领先；三档路由平衡成本与质量；LiteLLM 保证模型可替换 | GPT / 开源本地 | 采纳 |
| TDR-011 | **运行入口 P0 用 CLI + 结构化 JSON 日志**（Typer + Rich） | 最小成本、可被 CI 调用、日志可喂回 LLM/索引；Web Console / UE 面板为 P1+ 前端换皮 | Web Console | 采纳 |

---

## 附录 A：目录结构约定

```
/Game/Generated/        # Agent 唯一可写业务目录
  /Assets/              # 外部生成并导入的资产
  /PCG/                 # PCG Graph 资产
  /Blueprints/          # 蓝图（数据容器）
/Sandbox/               # 隔离验证 map
/Engine/                # 只读（沙箱禁止）
shared_state/           # SharedState JSON（Git 事实源）
  /strategy/             # 策略与研究（S1–S6）
  /gdd/                  # Director GDD
  /narrative/            # W1 叙事文案
  /art/style_guide.json  # Concept Artist
  /level/blockout.json   # Level Designer
  /data/                 # Data Agent → DataTable
  /system_balance/       # ND System/Numerical Designer
  /character/            # 玩家角色 / 敌人 / Boss / 动画
  /game/                 # Scene/Gameplay/Audio/UI 产物
  /eval/                 # 评估组报告（E1–E6 + UX，只写此区）
docs/                   # 设计文档
```

**`/Game/` 命名空间 ⟷ 磁盘路径映射规则**：

UE 内部用 `/Game/` 前缀的虚拟路径，磁盘上是 `{project}/Content/`。映射规则：
- `/Game/Generated/Assets/xxx` ⟷ `{repo}/unreal/Content/Generated/Assets/xxx.uasset`
- `shared_state/` 在仓库根，**不映射到 UE 资产**，是纯编排层的结构化状态（Git 事实源）
- Orchestrator 的 `adapters/ue_bridge.py` 持有统一映射函数（`game_path↔disk_path`），所有 Toolset 走它，避免每个 Tool 重复实现
- 沙箱白名单按 **UE 命名空间**（`/Game/Generated/`）判定，磁盘路径只是底层的物理解释

**SharedState → UE 资产的落地链路**：

```
shared_state/<agent>/<artifact>.json      # 结构化规格（如 blockout.json）
   │  Orchestrator 校验 schema + 审批
   ▼
Toolset 调用（唯一写入者）                  # 如 pcg_generate_graph(graph_path, spec)
   │  ue_bridge 做 /Game/↔磁盘映射
   ▼
UE 资产写入（/Game/Generated/...）          # 引擎编译生成 .uasset
   │  post-tool hook：Git auto-commit + shared_state 版本化
   ▼
git log 可回溯：shared_state JSON 变更 ↔ UE 资产变更 一一对应
```

这条链路保证：Agent 只产 JSON 规格，落到哪块 UE 资产、是否进 Git，都聚焦在 Orchestrator 一处，可审计、可回滚。

## 附录 B：核心接口契约（IDL 摘要）

```typescript
// Tool 统一返回
type ToolResult = { ok: true; data: any; version: string }
                | { ok: false; error_code: string; detail: string };

// PCG Graph 规格
type PCGGraphSpec = {
  biome: string;
  graph_path: string;
  nodes: PCGNode[];
  bounds: { min: Vec3; max: Vec3 };
};
type PCGNode = { id: string; type: string; params: Record<string, any>; inputs: Edge[] };

// SharedState 信封
type SharedStateEnvelope = {
  schema_version: string;
  parent_hash: string;       // SHA-256
  producer: string;
  created_at: string;
  payload: any;
};

// Agent 产出
type AgentOutput = {
  result: Record<string, any>;
  shared_state_delta: Record<string, any>;
  next_agents: string[];
  artifacts: string[];
};
```

## 附录 C：错误码与错误域分类

统一 `error_code` 分类，集中在此定义（Tool / Agent / Orchestrator 共用）。错误码分域 + 序号：

| 域 | 错误码 | 含义 | 触发时机 | 处理 |
|---|---|---|---|---|
| **安全域** | `SANDBOX_DENIED` | 写入被沙箱拒绝 | 触达 `no_touch_zones` | Agent 改目标路径重试 |
| | `RISK_NOT_APPROVED` | 审批未通过 | `destructive`/`mutating` 待批 | 挂起/拒绝 |
| | `AUTH_MISSING` | 无认证凭据 | 多机/未来 Token 场景 | 阻塞 |
| **参数域** | `INVALID_PARAM` | 参数不符合 Schema | Tool 校验失败 | Agent 修正重试 |
| | `SCHEMA_VERSION_MISMATCH` | 契约版本不兼容 | `schema_version` 不一致 | 升级适配层 |
| **引擎域** | `ENGINE_OFFLINE` | UE 编辑器/MCP 断开 | 心跳超时 | 连接恢复/重试 |
| | `ENGINE_VERSION_MISMATCH` | 引擎版本不在 Toolset 支持范围 | 版本检查 | 锁定正确引擎 |
| | `PCG_COMPILE_FAIL` | PCG 图编译失败 | `pcg_validate` | 返回节点级错误详单 |
| | `PCG_GENERATION_FAIL` | 生成失败 | `pcg_run_async` 失败 | 查 job 状态重试 |
| | `BUILD_FAIL` | 编译失败 | `build_live_coding/full` | 返回编译错误列表 |
| | `PIE_TEST_FAIL` | 自动化测试未通过 | `build_run_pie_tests` | 返回失败用例 |
| **时间域** | `TIMEOUT` | 超时（默认 30s） | Tool 无响应 | 转异步或失败重试 |
| | `ASYNC_JOB_LOST` | 长任务 job 句柄丢失 | 编辑器重启/崩溃 | 从 Checkpoint 恢复 |
| **通用域** | `NOT_FOUND` | 资产/路径/引用不存在 | 引用校验 | Agent 更正 |
| | `CONFLICT` | 空间分区/资产冲突 | 多 Agent 写同区 | Orchestrator 串行化 |
| | `UNKNOWN` | 未分类异常 | 兜底 | 记录 + 升级人工 |

> 约定：错误码大写蛇形；每个 Tool 的 `detail` 必须返回机器可读的错误位置（资产路径 / 节点 ID / 用例名）。CI 对未登记的错误码报警，强制收录。

---

**文档结束** — 本技术设计文档与 PRD v0.2 功能需求、技术约束、验收标准逐项对应；任何与 PRD 不一致之处，以 PRD 为准并触发版本更新（schema_version 递增）。
