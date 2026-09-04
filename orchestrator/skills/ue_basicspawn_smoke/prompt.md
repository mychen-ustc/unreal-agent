# ue_basicspawn_smoke · 真 UE 冒烟（host→真实 UE MCP）

生产闭环验证：place_cube→list_agent_cubes→remove_cube 走 UeMcpBackend 真调 UE BasicSpawnToolset。
满足「放置→出现→移除」的 AC-P0-06，且只写当前关卡、Agent 标记可查询/回滚。
