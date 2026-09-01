# scenes_pcg · 场景/PCG 领域策略（面向宿主 Agent）

按 PRD 参考游戏 §4.2 PCG 场景生成执行。要点：

- Agent 不直接捏造 `.uasset`；产出 PCG 图规格 / 编辑器 Python 脚本，由引擎确定性编译生成（架构文档 §0）。
- 生成的 /Game/Generated/PCG/ 资产进 Git，可 diff、可复现。
- **安全**：只写 `/Game/Generated/`；沙箱白名单按 UE 命名空间判定（SafeguardToolset）。
- **风险**：`pcg_generate_graph` 为 mutating，需审批门；写操作由 Orchestrator 唯一写入者串行执行。
- **验证**：产出后应跑 `pcg_validate`；检查节点参数区间与资产引用存在性（§10.2.1 evals）。
- **Grounding**：对 UE PCG API 的不确定项，先查 RAG 语料（experimental_mcp 标记谨慎处理）。
