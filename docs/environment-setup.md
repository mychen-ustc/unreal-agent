# 环境准备指南 · 研发 / 运行环境

> **适用**：研发启动前的环境搭建（本机单人开发，即 TechDesign §9.3「开发期」形态）。
> **关联文档**：[PRD](./AI_Agent_Game_Dev_PRD.md) §6 技术约束 / §7 里程碑 ｜ [TechDesign](./AI_Agent_Game_Dev_TechDesign.md) §2.3 技术选型 / §9 工程化。
> **最后核验**：对应当前机器环境现状的差异已在下文逐条标出。

---

## 0. 一句话结论

当前机器（Apple M5 · 24 GB RAM · 685 GB 空闲磁盘 · macOS 26.5）**满足本阶段研发运行基线**。

**已完成的环境准备**（见 §12 进度记录）：
- ✅ **UE 5.8 源码版编译完成**：`/Users/Shared/UnrealEngine-5.8-source`（5.8 分支）。`Build.sh UnrealEditor Mac Development` **5726/5726 全部通过**，2072 个引擎+插件模块 dylib 已 marshal 到 `Engine/Binaries/Mac/`，`UnrealEditor.modules` 完整清单已生成；编辑器实测**可完成插件/模块/Slate UI/Metal RHI 初始化**。
- ⚠️ **仅剩 Metal toolchain 组件待补**：CoreSimulator 复检已修复；但 `metal` 仍是 stub（`/Library/Developer/Components/` 空），引擎初始化到最后一步 Metal 着色器编译时停住（`cannot execute tool 'metal'`）。此非编译/引擎问题，补装 `sudo xcodebuild -downloadComponent MetalToolchain`（需网络可达 Apple、建议绕代理）即可跑通带渲染的完整编辑器会话；**MCP/命令行工具链基础不受影响**。
- ✅ **Xcode 26.6 完整版 + 许可已接受**，`xcode-select` 指向正确（完整版）。
- ✅ **Python 环境就绪**：conda `unreal-agent` 环境（Python 3.13.14）+ 全部核心依赖（langgraph / litellm / mcp / lancedb / opentelemetry / pytest / pydantic 等，已 import 验证）。
- ✅ **模型凭据已配置并连通验证**：`.env` 已填 `LLM_BASE_URL` / `LLM_API_KEY`，LiteLLM 实测成功调用 DeepSeek `deepseek-chat` 并返回响应。
- ✅ **Redis 就绪**：brew 安装 v8.10.1 并已启动，`redis-cli ping` → `PONG`（无认证要求）。
- ✅ **Git 身份已配置**：`user.name=mychen-ustc`、`user.email=136499614@qq.com`。

**关键遗留问题（阻塞完整引擎会话）**：
- **仅剩 1 项待办**：Xcode **`MetalToolchain` 组件**（CoreSimulator 已复检修复；`.app` finalize 问题已随 CoreSimulator 修复，`.app` 仍手动组装）。启用带渲染的完整编辑器会话（P0 的可视化验证）需补装：`sudo xcodebuild -downloadComponent MetalToolchain`（需网络可达 Apple 域名，建议绕代理后执行）。

**研发启动就绪状态**：Xcode、UE 5.8 引擎（**编译 + 引擎初始化完成**）、Python 依赖、Redis、模型凭据、Git 均已就绪；**唯一待办**是补装 Xcode 的 `MetalToolchain` 组件以启用**带渲染**的完整编辑器会话（MCP/命令行工具链基础不受影响），补齐后即可进入 **P0 地基**（AC-P0-01~06）。

---

## 1. 环境全景核对表

依据 TechDesign §2.3 技术选型和 §9.3 部署形态，研发运行需要以下组成部分：

| 编号 | 组件 | 技术选型（TechDesign） | 本机现状 | 状态 |
|---|---|---|---|---|
| E-01 | 硬件 | UE 5.8 编辑器能跑、可增量编译 | Apple M5 / 24 GB RAM / 685 GB 空闲 / Docker 可用 | 🟡 满足基线，见 §2 |
| E-02 | 操作系统 | macOS（UE 5.8 官方支持） | macOS 26.5.1 (arm64) | ✅ |
| E-03 | 完整 Xcode + CLT | UE C++ 编译/Live Coding 必需 | Xcode 26.6（完整版）+ 许可已接受，`xcode-select`= `/Applications/Xcode.app/...`；SDK 26.5 | ✅ 已完成（*simulator 组件未装，非阻塞*） |
| E-04 | UE 5.8 LTS 引擎 | 源码编译安装（§4.1） | 编译通过（5726/5726，2072 引擎+插件模块齐全）；CoreSimulator 已修复，编辑器初始化到 RHI/渲染，**仅 Metal toolchain 组件待补** | 🟡 编译+引擎初始化通过；渲染会话仅待补 MetalToolchain 组件 |
| E-05 | Python 运行时 | 3.11+（用 3.11/3.12/3.13 均可） | conda `unreal-agent` env = Python 3.13.14 | ✅ 已完成 |
| E-06 | Python 依赖 | langgraph / litellm / mcp / pytest / lancedb / opentelemetry / typer / rich | 已全部装进 `unreal-agent` env（import 验证通过） | ✅ 已完成 |
| E-07 | Redis | SharedState 运行时缓存 | v8.10.1 已装并启动，`ping` → PONG | ✅ 已完成 |
| E-08 | LanceDB | 向量长期记忆（嵌入式） | v0.37.1 已随 E-06 安装 | ✅ 已完成 |
| E-09 | Git | 版本控制 + 自动 commit | git 2.50.1；`user.name=mychen-ustc` / `email=136499614@qq.com` | ✅ 已完成 |
| E-10 | 模型凭据 | 自定义供应商 base_url + model_name（LiteLLM 封装） | `.env` 已填 base_url/key；LiteLLM 实测 `deepseek-chat` 返回成功 | ✅ 已完成 |
| E-11 | Docker | 仅 CI 期 UE 容器用；开发期不需要 | Docker 29.6 可用 | ✅ 可选 |
| E-12 | 观测后端 | OpenTelemetry → OTLP → 本地文件/SQLite | opentelemetry 已随 E-06 安装 | ✅ 已就绪 |

> **状态图例**：✅ 已完成 / 就绪 ｜ 🟡 可用但有前提/非阻塞 ｜ ❌ 缺失需处理。
> **§0 之后新增的自动准备工作** 已全部反映到本表（原 E-05~E-12 缺失项均已闭环）。

> 标记说明：✅ 已就绪 ｜ 🟡 可用但有前提/非阻塞 ｜ ❌ 缺失，启动前必须处理。

---

## 2. 硬件与 OS 核验（E-01/E-02）

```bash
# 对照本机测试（当前已实测通过）
sw_vers                      # macOS 26.5.1
uname -m                     # arm64
sysctl -n machdep.cpu.brand_string   # Apple M5
sysctl -n hw.memsize                  # 应为 ≥ 16GB；本机 24GB
df -h /                      # 需预留 ≥ 100GB；本机 685GB 空闲
```

**RAM 提示**：TechDesign §9.2 提到全量编译需 50–70 min（R-03）。24 GB RAM 对「UE 5.8 编辑器运行 + Orchestrator + 参考游戏」同机可支撑，但**不建议同时开启浏览器多标签 / 视频渲染等高耗内存进程**。若后续 P4（3-4 生物群系完整关卡）阶段吃紧，考虑加内存或拆到更强工作站。

---

## 3. 安装完整 Xcode（E-03）

> UE 的 C++ 编译（`UToolsetDefinition`、C++ Gameplay）与 Unreal Insights 依赖完整 Xcode
> 工具链，仅有 Command Line Tools 是不够的。

```bash
# 1) 用 App Store 安装「Xcode」（或从 Apple Developer 下载 .xip）。
#    安装完务必执行：
sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer
xcodebuild -version          # 应输出版本号而非 CLT 错误
sudo xcodebuild -license accept

# 2) 确认 SDK：
ls /Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/
```

> 最低要求：Xcode 版本需满足 UE 5.8 的要求（随引擎的 `Setup.command` 校验）。本机 SDK 已含 26.5，通常满足新 UE。

---

## 4. 安装 UE 5.8（E-04）

> **决策变更**：Launcher 二进制发行版下载多次失败，**改用源码编译安装**（TechDesign `§9.1` 本就倾向「完整 UE 源码分支管理」，亦满足「完整源码分支」约束）。源码版还支持后续引擎级改造（定制沙箱、扩展 PCG 等）。
> 前置条件（均已确认就绪）：
> - 完整 Xcode 26.6 + 已接受许可（`sudo xcodebuild -license accept`）。
> - Epic 账号已绑定 GitHub 并授权 `EpicGames/UnrealEngine`；本机 SSH key 已加入 GitHub（`git@github.com:EpicGames/UnrealEngine.git` 可 `git ls-remote`）。

### 4.1 源码版（主路径，本机当前采用）

> 分支：`5.8`。安装目录：`/Users/Shared/UnrealEngine-5.8-source`（独立于 Launcher 目录，避免覆盖）。

```bash
# 1) 浅克隆（仅 5.8 分支，减小体积；如需完整历史/切换分支再取全量）
cd /Users/Shared
git clone --depth 1 --single-branch --branch 5.8 \
  git@github.com:EpicGames/UnrealEngine.git UnrealEngine-5.8-source

cd UnrealEngine-5.8-source
# 2) 下载引擎依赖（对源码版必需的第三方库/DCC 工具；约需一定网络与磁盘）
./Setup.command            # 需 `--force`?否，首次直接跑

# 3) 生成构建文件（Xcode / Deploy 用）
./GenerateProjectFiles.command

# 4) 编译引擎（冷编译耗时较长，建议后台跑、可增量）
#    UE 5.8 编辑器 target 名为 UnrealEditor（非 UE5Editor）
./Engine/Build/BatchFiles/Mac/Build.sh UnrealEditor Mac Development
```

> 编译产物：`Engine/Binaries/Mac/UnrealEditor`（+ 引擎/插件模块 dylib）。编译后用 `GenerateProjectFiles` 产出的 `UE5 (Mac).xcworkspace` 的 `UnrealEditor` scheme 亦可，但本机 xcodebuild 因 Xcode 组件缺失无法完整 finalize `.app`（见 §12.1）。
> 本机为 macOS（arm64）。UE 首次运行生成 `DerivedDataCache`（可达数十 GB），已在 `.gitignore` 排除。

### 4.2 Launcher 二进制版（备用）

> Launcher 二进制发行版下载多次失败，暂不采用；若后续需要「开箱即用」的二进制（源码版之外的快速验证），且 Epic Launcher 网络恢复，可按§4.1 之前的步骤：
>
> 1. Epic Games Launcher → Unreal Engine → **5.8** → 安装到 `/Users/Shared/UnrealEngine/5.8`。
> 2. 核验 `ls /Users/Shared/UnrealEngine/5.8`。
>
> 本仓库当前以 **源码版** 为引擎来源，依赖 `~/UnrealEngine-5.8-source/Engine/...` 路径（见 §11 每日运行）。

---

## 5. Python 环境（E-05 / E-06）

按已确认决策，使用 **Conda 独立环境**，避免污染 base 环境、便于管理非 pip 依赖。

### 5.1 创建 conda 环境

```bash
# 使用 conda 建独立环境（Python 不低于 3.11）
conda create -n unreal-agent python=3.13 -y
conda activate unreal-agent
python --version            # 3.13.13
```

### 5.2 安装 Python 依赖

核心依赖来自 TechDesign §2.3；当前仓库尚无锁文件，先按最小集安装：

```bash
pip install --upgrade pip
pip install \
  langgraph litellm "mcp>=1.0" \
  typer rich \
  pytest \
  lancedb \
  opentelemetry-api opentelemetry-sdk \
  pytest-asyncio pydantic

# 其余（按需，P1+ 再用）：celery（分布式队列）、prometheus-client（指标、§10.3）
```

> 建议后续在 `orchestrator/requirements.txt`（或 `pyproject.toml`）固化为锁文件，保证 CI（GitHub Actions）与本地一致。

### 5.3 核验

```bash
conda activate unreal-agent
python -c "import litellm, langgraph, mcp, lancedb, typer, rich, opentelemetry; print('deps ok')"
```

---

## 6. Redis（E-07）

> TechDesign §2.3：`SharedState 存储 = Git（事实源）+ Redis（运行时缓存）+ LanceDB（向量记忆）`。
> P0 阶段任务量小，可用「嵌入式/LanceDB 直存」顶替运行时缓存；**建议在 P1（第 5 周）前补装**，避免缓存/状态语义与设计偏离。

```bash
brew install redis
redis-server --daemonize yes   # 或 brew services start redis
redis-cli ping                  # 应输出 PONG
```

---

## 7. 模型凭据：自定义供应商（E-10）

> 按已确认决策：不用固定 Anthropic，而是**通过 LiteLLM 的 OpenAI-compatible 统一网关接入自定义供应商**——你只需配 `base_url` + `model_name`（+ 上游需要的 `api_key` 可选），即可按需切换/调用任意模型。这正符合 TechDesign「模型不锁定」（TDR-010）与 `orchestrator/config/models.yaml` 配置驱动的设计。

### 7.1 环境变量（仓库根 `.env`）

复制仓库根的环境变量模板并填写：

```bash
cp .env.example .env
```

`.env.example` 内容（示例，开箱即用需自行填实际值）：

```dotenv
# ---- 模型供应商（自定义 / OpenAI-compatible 统一网关）----
# 必填：供应商端点。示例任选其一：
#   · 统一代理网关（one-api / new-api / LiteLLM proxy）：http://<gateway>:PORT/v1
#   · 兼容 OpenAI 直连/内网模型：http://<host>:PORT/v1
LLM_BASE_URL=http://127.0.0.1:8787/v1
# 可选：上游需要鉴权时填（统一网关通常使用一个主 key）
LLM_API_KEY=

# ---- 命令行 / CLI 令牌（可无）----
# CLI_TOKEN=...

# ---- 可观测性（P1+ 再填）----
# OTLP_ENDPOINT=http://127.0.0.1:4318
```

### 7.2 模型路由配置 `orchestrator/config/models.yaml`

默认三档路由（`strong` / `default` / `fast`，对应 TechDesign §2.3 表）统一走你的 base_url，只需改 `model` 字段即可切换不同模型：

```yaml
# orchestrator/config/models.yaml
default_provider: custom        # 全部走自定义网关

custom:
  base_url: ${LLM_BASE_URL}     # 读取 .env
  api_key: ${LLM_API_KEY}       # 可选

routing:
  strong:  # 复杂推理：玩法设计、PCG 参数规划、代码生成、评审
    model: ${MODEL_STRONG:-deepseek-reasoner}   # 例：填你的强模型名
    provider: custom
  default: # 主力：多数 Agent 任务、Tool 调用、GDD 撰写
    model: ${MODEL_DEFAULT:-deepseek-chat}       # 例：填你的主力模型名
    provider: custom
  fast:    # 简单/高频：格式化、摘要、分类、命名校验
    model: ${MODEL_FAST:-deepseek-chat}          # 例：填你的轻量模型名
    provider: custom
```

### 7.3 加载方式

- OpenAI-compatible 供应商只用 `base_url + model_name`（+ 可选 `api_key`），正合用户要求：「只配置 base_url 和 model_name 即可按需调用任意模型」。
- 若使用 **LiteLLM proxy 形态**（统一网关），`base_url` 指向代理即可，上游真实供应商由网关侧管理，客户端无关。
- 实现处：`orchestrator/models.py`（LiteLLM 封装 + 三档路由） + `orchestrator/config/models.yaml`。

> 若某模型不自带 function-calling（部分开源/定制模型），Agent 的 Tool 调用需在 `models.py` 走「工具转结构化 JSON 输出」兜底——见 TechDesign §4.1.1 MCP 工具平面。P0 验证 AC-P0-02 `list_tools` 不受影响。

---

## 8. Git 配置（E-09）

> Agent 的 `post-tool` hook 会**自动 commit**（PRD AC-P0-05、TechDesign §9.2）。
> 该项**已完成**：本机已配置 `user.name=mychen-ustc`、`user.email=136499614@qq.com`。
> 如需改、或新机器配置，命令如下：

```bash
# 仓库级（推荐，跟随项目）
git config user.name "mychen-ustc"
git config user.email "136499614@qq.com"
git config --get user.name   # 核对

# 引擎忽略目录已在 .gitignore：DerivedDataCache / Intermediate / Binaries / Saved/.venv
```

---

## 9. Docker（E-11，可选）

- **开发期不需要**；CI 期（GitHub Actions）UE 运行于容器/GitHub Runner 时用（TechDesign §9.3）。
- 本机 Docker 29.6 已就绪，无需操作。届时参考 `.github/workflows/ci.yml`。

---

## 10. 前置准备执行顺序（Checklist）

| 序 | 步骤 | 参考 | 验证 | 状态 |
|---|---|---|---|---|
| 1 | 装完整 Xcode | §3 | `xcodebuild -version` | ❌ 待人工 |
| 2 | 装 UE 5.8（Launcher） | §4.1 | `ls /Users/Shared/UnrealEngine/5.8` | ❌ 待人工 |
| 3 | conda env + 依赖 | §5 | `python -c import ...` | ✅ 已完成 |
| 4 | 装 Redis | §6 | `redis-cli ping` → PONG | ✅ 已完成 |
| 5 | 配模型凭据 | §7 | LiteLLM 能回包 | ✅ 已完成（DeepSeek 实测通过） |
| 6 | 配 git identity | §8 | `git config --get user.name` | ✅ 已完成 |

> 注：Redis 原计划 P1 前装，现已提前装好（P0 直接用）。
>
> **剩余人工项**：步骤 1、2（Xcode / UE 5.8）。完成这两项后即可进入 **P0 地基**（第 1–4 周），对齐 AC-P0-01~06。

---

## 11. 启动研发后的每日运行

```bash
conda activate unreal-agent

# 启动 UE 5.8 编辑器（源码版产物；项目 .uproject，含 MCP Server 绑定 127.0.0.1:8000/mcp）
# 注：带渲染的完整编辑器会话需先补齐 Xcode MetalToolchain 组件（§12.1）
UE_EDITOR=/Users/Shared/UnrealEngine-5.8-source/Engine/Binaries/Mac/UnrealEditor
"$UE_EDITOR" "$PWD/unreal/UnrealAgent.uproject" &

# 运行 Orchestrator（L4）CLI 入口
python -m orchestrator run --task "在关卡中放置一个 Cube"
```

> MCP Server 就绪自检：`curl -s http://127.0.0.1:8000/mcp`（浏览器/UE 面板响应）→ 对应 AC-P0-01。
> 追踪日志落盘 `.logs/trace.jsonl`，已 gitignore，不污染仓库。

---

## 12. 本机差异汇总（当前进度记录）

| 项 | 现状 | 处置 / 状态 |
|---|---|---|
| Xcode | Xcode 26.6（完整版）已装，许可已接受，`xcode-select` 指向 `/Applications/Xcode.app/Contents/Developer`（simulator 组件未装，非阻塞） | ✅ 已完成 |
| UE 5.8 源码 | `EpicGames/UnrealEngine` `5.8` 分支浅克隆到 `/Users/Shared/UnrealEngine-5.8-source`（3.8GB / 223,996 文件，HEAD `ff8421f2`）| ✅ 源码就位 |
| UE 依赖下载 | `./Setup.sh --force` → **100%**（31113/31113 MiB；ThirdParty ≈ 14GB） | ✅ 已完成 |
| UE 生成工程 | `./GenerateProjectFiles.command` → Succeeded | ✅ 已完成 |
| UE 编译 | `Build.sh UnrealEditor Mac Development` → **5726/5726 通过**（2072 引擎+插件模块齐全，dylib 已 marshal） | ✅ 已完成 |
| UE `.modules`/运行 | `UnrealEditor.modules`（2072 模块）已生成；CoreSimulator 已修复，编辑器初始化至 RHI/渲染阶段，**仅 Metal toolchain 组件待补** | 🟡 引擎初始化通过；渲染会话仅待补 MetalToolchain（详见 §12.1） |
| Python env | conda `unreal-agent` = 3.13.14 | ✅ 已创建 |
| 依赖 | langgraph 1.2.11 / litellm 1.98.0 / mcp 2.1.1 / lancedb 0.37.1 / otel 1.44 / pytest / pydantic | ✅ 已装入 `unreal-agent`，import 通过 |
| Redis | v8.10.1 运行中（`127.0.0.1:6379`，无认证） | ✅ 已装并启动，`ping` → PONG |
| 模型凭据 | `.env` 已填 base_url + api_key | ✅ DeepSeek `deepseek-chat` LiteLLM 实测返回成功 |
| git identity | `mychen-ustc` / `136499614@qq.com` | ✅ 已配置 |
| Docker | 29.6 可用 | ✅ 可选（CI 期才用） |
| macOS / HW | M5 / 24GB / 685GB | ✅ 满足基线 |

> **当前状态**：UE 5.8 源码版**编译 + 引擎初始化完成**（5726/5726 通过、2072 模块齐全、`UnrealEditor.modules` 已生成）；CoreSimulator 已修复，**带渲染的编辑器会话仅待补 MetalToolchain 组件**。详见 §12.1。

---

## 12.1 UE 5.8 源码安装：进度记录

> 决策：源码编译安装（§4.1 主路径）。**Xcode 已完成**（26.6 + 许可已接受），Epic GitHub 源码授权已就绪（SSH 可访问）。

| 步骤 | 状态 | 结果 |
|---|---|---|
| 克隆源码 | ✅ 完成 | `5.8` 分支 → `/Users/Shared/UnrealEngine-5.8-source`（HEAD `ff8421f2`） |
| 下载依赖 | ✅ 完成 | `./Setup.sh --force` → **100%**（31113/31113 MiB；`Engine/Binaries/ThirdParty` ≈ 14GB） |
| 生成工程 | ✅ 完成 | `./GenerateProjectFiles.command` → Succeeded（产出 `UE5 (Mac).xcworkspace`） |
| 编译 | ✅ 完成 | `Build.sh UnrealEditor Mac Development` → **5726/5726 全部步骤通过**（567 模块 `.dylib` 均已链接） |
| `.app` 打包 | ✅ 手动完成 | 引擎本体的 UBT「finalize .app」因本机 Xcode simulator 组件缺失而失败；已**手动组装 + ad-hoc 签名** `UnrealEditor.app`（结构/签名校验通过，见下） |
| 验证运行 | ✅ 可运行 | `UnrealEditor-Cmd` 实测启动成功：打开共享内存、fork 并成功启动 Trace 守护进程、spawn `UnrealEditorServices`（见 §12.1 说明） |

> **目标名**：UE 5.8 编辑器 target 为 **`UnrealEditor`**（非 `UE5Editor`），编译命令 `Build.sh UnrealEditor Mac Development`。

**引擎产物**：
```bash
/Users/Shared/UnrealEngine-5.8-source/Engine/Binaries/Mac/UnrealEditor          # 编辑器主程序
/Users/Shared/UnrealEngine-5.8-source/Engine/Binaries/Mac/UnrealEditor-Cmd     # 无头/commandlet 程序
/Users/Shared/UnrealEngine-5.8-source/Engine/Binaries/Mac/UnrealEditor.app     # 已组装+ad-hoc 签名的 .app
/Users/Shared/UnrealEngine-5.8-source/Engine/Binaries/Mac/libUnrealEditor-*.dylib  # 567 个模块动态库
```

**关于 `.app` finalize 与 Xcode 组件**（复检记录）：
- ✅ **CoreSimulator 已修复**（复检）：`/Library/Developer/PrivateFrameworks/CoreSimulator.framework` 现已存在，UBT 的 `.app` finalize 不再因 simulator 插件缺失而失败（`.app` 仍为手动组装+ad-hoc 签名）。
- ❌ **Metal toolchain 组件仍未安装**（复检）：`metal` 仅是 107KB 的 stub，`/Library/Developer/Components/` 仍为空、无 `OSX*.xctoolchain`。编辑器实测仍停在 RHI 阶段报 `cannot execute tool 'metal' due to missing Metal Toolchain`。

**当前引擎运行状态（诚实结论）**：
- ✅ **编译完成**：`Build.sh UnrealEditor Mac Development` → 5726/5726 全部通过，567 引擎 + 1541 插件模块 dylib 齐全、已 marshal 到 `Engine/Binaries/Mac/`。
- ✅ **`UnrealEditor.modules` 完整生成**（2072 模块，引擎+插件），运行时能定位加载全部模块。
- ✅ **引擎初始化深入通过**：插件挂载、模块加载、Slate UI、Metal RHI 加载、`PreRHIInit` 全部通过，直到 GPU/着色器阶段。
- ⚠️ **GPU/渲染初始化被 Metal toolchain 组件缺失阻塞**（复检仍卡此）：编辑器初始化到最后一步 Metal 着色器编译时停住，报 `cannot execute tool 'metal'`。**这是唯一剩余阻塞**；非编译/引擎问题，也非 CoreSimulator 问题（已修复）。

**补齐剩余 Xcode 组件（只有 MetalToolchain 需下载）**：
```bash
# 需 sudo + 网络可达 Apple 域名（若 Clash 代理挡 Apple 下载，请先绕代理 / 加白名单再执行）
sudo xcodebuild -downloadComponent MetalToolchain     # 仅此一项仍缺：补 Metal 着色器工具链
# 完成后再启动编辑器，Metal 检查即通过，可跑通带渲染的完整编辑器会话
```
> 说明：编译日志 `/Users/Shared/ue-build.log`。已在修复 1 处 `-Werror` 编译错误后全部通过。
> 当前引擎产物中 `UnrealEditor.modules`（2072 模块）与 marshal 后的 dylib 已就位，MCP Server 等基于编辑器的工具可在此基础上继续研发；**仅带渲染的完整编辑器会话**待补 MetalToolchain 组件。

---

*维护者：AI 技术专家 · 依据 TechDesign §2.3/§9、PRD §6/§7 编制 · 本机核验日期见仓库 log*
