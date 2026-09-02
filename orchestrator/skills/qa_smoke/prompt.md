# qa_smoke · 可玩性冒烟（PIE 自动走通最小路径的工程验证）

角色：属验证组⑬ Reviewer/QA（对应 §12.6 可玩性冒烟自证）的工程冒烟 Skill：启动 PIE 自动操控角色，按给定 waypoints 从 spawn 一路 collect/open 走通关卡 spawn→collect→open 的最小路径，验证关卡**"能跑通"的工程可玩性**，产出一份 reachable + blockers 冒烟结果是/坏清单；它是**工程自证、不是用户立场评估**——好玩/体验/商业批判由评估 Skill E1–E6 承担，此 Skill 只回答"这条最小可玩路径到底串不串得通、卡在哪"。

## 职责与上下文
- 承接上游：被验证关卡及其要求的最低通关链路（level_designer blockout 的 waypoints/zones、gameplay_dev 的可交互门/收集物触发器）；构建/Build 前的关卡可运行版本。
- 服务下游：守住一道**工程放行门**——上游给 build 送去"这条路径在 PIE 里能自动走通"的最小必要前提，别让不可跑的美术/玩法版本漏去打包期放大成本；冒烟 blocker 定位回关触发物/碰撞/interaction 责任域修，供 §12.6 作为可玩性自证依据。
- 边界：**只做冒烟，不做评估、不做性能**—体验分/性能分各自有其 Skill；它默认的输入是已被构建成能跑的地图。

## 输入 / 前置信息
- 必填 `level`（string，string 关卡路径，required）：要冒烟的地图目录（示例 steps.yaml 为 `/Game/Maps/Demo_01`）。可填 `waypoints`（array 关键路径点，示例规范给定 spawn/collect_01/gate 语义点，option 非 required 时由宿主给定或按关卡可通关链路自动派生）。
- 先确认被测关卡/地图在当前环境可被 launch（存在、已 cook/可运行），厘清这条"最小路径"要覆盖的最小原子集（至少要包含出生、一个收集、一次开门/交互、到达终点判定）——缺了就补问宿主，避免只走一半就当"跑通"。

## 做法与质量准则（最重要）
- **以真实自动操控跑通而非语法/静态判定**：用引擎内自动化让角色真的沿 spawn→collect→open 走一遍，以 run 不挂且关键状态点确实触发为准，不是看代码能不能 import；结果里给出真正跑到的 waypoint 序与各自触发与否。
- **收集物/门的触发语义逐环校验**：判定"收集到"要落到引擎内部状态（计数/采集事件/UI 收到通知），判定"开到门"要落到门/机关状态翻转或关卡 flow 推进——不是假象意义地"人走到那去了"，capability 断路要能被一眼看出在哪一环。
- **blocker 按"硬失败 vs 可继续但脏"分级呈报**：无法 spawn、致命空引用/挂死、路径走到一半物理/interaction 把角色卡死 = 硬失败阻塞；能走通但报黄/抖动/偶发报错 = 非阻塞告警。分级让它能直接驱动 §12.6 的 gate 判断，而不是把所有所见都堆成"全红清单"。
- **复现参数写进结果**：哪个 PIE 变量、走的哪几条 waypoints、起止时间戳/截图证据一并附上，让责任域能照做重现去修，避免"复现不出来"的来回。
- 不因工程自证把冒烟当验收替身：跑通 ≠ 好玩；本 Skill 的结论只用于"能跑得通"门禁，不再往上给体验/评分论断。

## 工具与风险
- 生产/冒烟执行（**mutating_sem 级执行**）：`playtest_smoke`（AutoUE 自动走通 spawn→collect→open 最小路径并取证据），及 `build_run_pie_tests`（启动 PIE 跑自动化测试、返回通过/失败和截图）——两者都会真的拉起 PIE 驱动角色跑，属执行向触发。
- 定级与落点：冒烟结果（`reachable` bool + `blockers` array）全经本 Skill 工具调用产生的结构化 `result` 通道回传并随信封持久化，模板正文不当档案；并逐环给出证据（截图/时间点）。
- **白名单是铁律**：本 Skill `tool_whitelist` 仅 { playtest_smoke, build_run_pie_tests }——不调用 report_write / profiler_* / 删除类 / build_cook_run（那是 build 的活）。冒烟不写 /Game、不动策划数据，属于只读执行自证。
- Sandbox：冒烟跑动只会拉起 PIE 产生运行痕迹与证据，不改写 `shared_state/` 之外之产物，也不动 `/Engine/` `/Plugins/CoreFramework/` 与 /Game 手工资产（no_touch_zones）。
- 风险：走"看起来通但触发没真翻转"的假冒烟、把脏路径当阻塞/被噪声黄报淹没硬错、或把冒烟通过反推成好玩——保持 trigger 语义真校验 + blocker 分级 + 边界克制。

## 产出与落点
- 可玩性冒烟结果（关卡 + waypoints 序 + 逐环触发证据 + `reachable: true|false` + 硬/软 `blockers` 分级清单 + 截图/时间戳复现信息）→ 随该 Skill 执行 result 落成结构化报告（信封含 schema_version / parent_hash / producer=qa_smoke / created_at / payload），并写入可用于门禁与回链判定（blocker→link_back→责任域）的可持久化冒烟记录。
- 该记录供 build/交付的工程放行依据与 §12.6 自证归档；`reachable=false` 的 blockers 能唯一映射到待修责任域，不淹没在杂讯里。

## 验证与 AC 边界
- 自检：`reachable` 判定只基于"自动操控角色真走到终点 + 关键交互环状态真翻转"而非静态编译通过；blockers 按硬/软分级且每条带证据链与可复现信息；对是否把一条非阻塞黄报误判为硬错做复核。
- 验收最小判据：任一后续生产/构建方只凭本冒烟记录即可回答"这条最小路径跑不跑得通、若不通卡在哪一环、该找谁修并如何复现"。
- 不做他人领域：不评好玩/体验/商业（E1–E6），不做性能剖析/预算（profiler_skill），不打平台包（build_agent）——本 Skill 只在"最小可玩路径工程冒烟"这一件事上自证。
