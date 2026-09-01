# UE 引擎工作流与协作约定（UE Engine Workflow）

项目代号：AI Agent 驱动的高品质游戏开发
关联：[environment-setup](./../environment-setup.md)（源码编译）｜ [TechDesign](./../ai-agent-game-dev-tech-design.md) §12（UE6 迁移）｜ [Architecture](./../ai-agent-toolchain-architecture-unreal.md) §0（源码可控/引擎级定制）

> 本文档约定 **UE 源码分支管理、引擎级 AI 定制放哪、如何构建/发布、如何与 orchestrator 对齐版本**。这是多人协作、且做引擎级定制前必须定的口径（架构 §0 原则三：拿完整 UE 源码做引擎级改造）。

---

## 1. 引擎来源与目录

| 项 | 约定 | 说明 |
|---|---|---|
| 引擎目录 | `/Users/Shared/UnrealEngine-5.8-source` | 独立于 Launcher 目录，源码版 |
| 引擎分支 | `5.8`（UE5 末代 LTS） | 锁定额分支，避免漂移 |
| 是否入库 | **不入库**（/Users/Shared 下，独立于仓库） | 仓库只放项目 `.uproject` 与描述 |
| 项目 | `unreal/UnrealAgent.uproject` | 仓库内 |
| 版本对齐 | 引擎 `EngineAssociation` + `engine_min/max_version` | Toolset 适配层据此判别（TechDesign §3.4） |

---

## 2. 引擎级 AI 定制（规划内，P0 起预留）

> 本项目规划对 UE 做**引擎级 AI 定制**：推理嵌渲染/校验管线、定制 Agent 沙箱、扩展 PCG 框架。这部分既是 P5+ 工程蓝图，也是私有化黑盒（C3）的核心壁垒（Harness §11 支柱 1、ROADMAP §5）。

**约定**：
- **定制不污染上游分支**：不做在 UE 官方 `5.8` 主干上；用「**仓库外 diff / 独立定制分支 / UE 源码子模块**」管理，保留升级/回退能力。
- **定制目录约定**（建议）：引擎 `Engine/Plugins/UnrealAgent/`（项目专用定制插件）对外独立管理。
- **通过 `EngineBridge` 抽象接入**：L1 适配层（TechDesign §12）持 `EngineBridge` 接口，UE 定制经此暴露，L2/L3/L4 不依赖 UE 具体类型，UE6 可平滑替换。
- **构建可复现**：引擎改动记录在仓库（描述 + patch/diff），不在 `/Users/Shared` 里裸改不记录。

### 2.1 三种定制形态

| 形态 | 例子 | 在哪 |
|---|---|---|
| 项目内插件 | 定制 PCG、Shaders | `unreal/Plugins/`（随项目仓库） |
| 引擎级修改 | 嵌推理、扩沙箱 | 引擎源码 diff/patch（独立管理，不入仓库） |
| UBT/工具链 | 编译/打包扩展 | 引擎 Build/BatchFiles 定制（同引擎 diff） |

---

## 3. 构建与发布约定

| 目标 | 命令/方式 | 时机 |
|---|---|---|
| Live Coding | 编辑器内增量编译 | 日常迭代（<30s 目标） |
| 全量编译 | `Build.sh UnrealEditor Mac Development` | nightly / 谨慎批次（50–70min，R-03） |
| 无头/CI | `UnrealEditor-Cmd`（commandlet） | CI 期验证 |
| 发布打包 | BuildToolset（UBT/UAT）→ `build_cook_run` | P5 |

- **冷编译纪律**：优先 Live Coding；全量放异步队列/nightly，不阻塞 Agent 循环（TechDesign §11）。
- **构建缓存**：DerivedDataCache / Intermediate 在 `.gitignore`，可被重建。

---

## 4. 分工与协作（多人）

| 角色 | 负责 |
|---|---|
| 引擎/AI 工程师 | Toolset 实现、引擎定制、UE 侧 SafeguardToolset |
| 后端/编排 | orchestrator、MCP client、LiteLLM、durable |
| 产品/商务 | Skill 定级（tier）、商业钩子 |

**协作红线**：
- 引擎源码目录（/Users/Shared）不随仓库分发；新人按 environment-setup 自行编译。
- 引擎定制 diff 有版本记录（便于 UE6 迁移判断：能携刻多少定制到 UE6）。
- Orchestrator ↔ UE 之间用 MCP 契约解耦，引擎版本变更只改 L1 `EngineBridge` 适配层。

---

## 5. UE6 迁移协作预留

- 迁移策略见 TechDesign §12.2：逻辑往 Verse 靠、MCP 架构复用 ≥ 80%、L1 适配重写。
- 引擎定制设计时就考虑「能否携带到 UE6」——凡是依赖 UE5 私有 API 的定制，在 Vision 评估时打标。

---

*本文档使 UE 源码分支与定制协作有据可依；建议在首次引擎级定制前、或多人加入前启用。*
