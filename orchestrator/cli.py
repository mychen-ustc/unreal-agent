"""CLI 入口（Typer + Rich）· P0 地基。

命令：
    orchestrator run --task "<需求>" [--plan id] [--dry-run] [--auto-approve-read-only]
    orchestrator plan  --task "<需求>"          # 生成 DAG 计划（dry-run 展示）
    orchestrator skills                         # 列出 Skill（含商业分级 tier/distill）
    orchestrator import --target <host> [--skills ...] [--mcp <url>] [--out <dir>]  # 蒸馏子集注入宿主
    orchestrator approve --task-id <id> --allow  # 审批一个挂起任务
    orchestrator rollback --task-id <id>

对齐 TechDesign §6.5（运行入口 / 审批 / 回滚）、§11.3（distiller）与 §12（跨宿主导入）。
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from orchestrator.dag import DagEngine, DagNode
from orchestrator.mcp_client import McpClient, StubTransport, as_approver
from orchestrator.trace import TraceWriter, DEFAULT_LOG_DIR
app = typer.Typer(help="UnrealAgent Orchestrator（P0 地基）")
console = Console()

logging.basicConfig(level=logging.INFO)


# ---- 计划（DAG 构建 + dry-run） ----
@app.command("plan")
def plan(
    task: str = typer.Option(..., "--task", "-t", help="自然语言任务需求"),
    plan_id: Optional[str] = typer.Option(None, "--plan", help="计划 id（默认自动生成）"),
    dry_run: bool = typer.Option(False, "--dry-run", help="只生成计划不执行"),
) -> None:
    """生成 DAG 计划并（dry-run）展示。"""
    dag = DagEngine()
    _populate_dag(dag, task)
    order = dag.topological_order()
    console.print(
        Panel(
            f"[bold cyan]任务[/]: {task}\n"
            f"[bold cyan]拓扑顺序[/]: {' → '.join(order)}\n"
            f"[bold cyan]节点[/]: {len(dag.nodes)}，边：{len(dag.edges)}\n"
            f"[bold cyan]计划 id[/]: {plan_id or auto_plan_id(task)}",
            title="Plan (dry-run)",
        )
    )
    if dry_run:
        console.print("[dim]dry-run：未执行任何 Agent。[dim]")


# ---- 运行 ----
@app.command("run")
def run(
    task: str = typer.Option(..., "--task", "-t", help="自然语言任务需求"),
    skill: Optional[str] = typer.Option(None, "--skill", help="指定 Skill（如 scenes_pcg）；默认自动选型"),
    dry_run: bool = typer.Option(False, "--dry-run", help="只生成计划不执行"),
    engine_endpoint: str = typer.Option("http://127.0.0.1:8000/mcp", "--endpoint", help="UE MCP Server 地址"),
    use_stub: bool = typer.Option(True, "--stub/--no-stub", help="无 UE 时用本地桩（脚手架自检）"),
    approval: str = typer.Option("prompt", "--approval",
                                 help="审批策略：prompt(交互确认,默认) | auto(全放行,自检/CI) | read_only(只读放行)"),
) -> None:
    """编排一次任务，跑通 Skill + DAG 调度 + MCP 工具调用 + 审批门 + trace。"""
    dag = DagEngine()
    _populate_dag(dag, task)

    with TraceWriter(DEFAULT_LOG_DIR / "trace.jsonl") as trace:
        # MCP client（唯一写入者）—— 脚手架默认用桩，连真 UE 时用 HTTP
        transport = HttpOrStub(engine_endpoint, use_stub)
        mcp = McpClient(transport=transport, approver=as_approver(approval))

        # P0：走 Host/Skill 路径（薄宿主选 Skill 并按其 DAG 步骤执行）
        from orchestrator.host import Host

        host = Host(mcp=mcp, trace=trace)
        resolved = skill or host.select_skill(task)
        result = host.run(task, skill_name=resolved)
        console.print(Panel(
            f"[green]Skill 执行完成[/]：{result['skill']}，步骤 {result['steps_executed']}。\n"
            f"[dim]UE endpoint[/]: {engine_endpoint}  (stub={use_stub})",
            title="Run 结果",
        ))
    console.print(f"[dim]trace 日志[/]: {DEFAULT_LOG_DIR / 'trace.jsonl'}")


# ---- 审批 / 回滚（占位脚手架） ----
@app.command("skills")
def skills() -> None:
    """列出已装载的 Skill 及其元数据（含商业分级）。"""
    from orchestrator.skills import get_registry
    from rich.table import Table

    reg = get_registry()
    names = reg.discover()
    table = Table(title="已装载 Skills")
    table.add_column("name")
    table.add_column("model_tier")   # fast/default/strong
    table.add_column("biz_tier")     # 商业分级 0–4
    table.add_column("distill")      # full/lite/hidden
    table.add_column("risk")
    table.add_column("steps")
    for n in names:
        s = reg.load(n)
        spec = s.spec
        table.add_row(
            spec.name,
            spec.default_tier,
            str(spec.tier),
            spec.distill_visibility,
            spec.risk,
            str(len(spec.steps)),
        )
    console.print(table)


@app.command("import")
def import_skills(
    target: str = typer.Option(..., "--target", help="目标宿主：self_hosted|claude_code|codex|openclaw|hermes"),
    skills_list: str = typer.Option("", "--skills", help="逗号分隔的 Skill 名单；空=蒸馏全部 MVP 子集"),
    mcp_url: str = typer.Option("http://127.0.0.1:8000/mcp", "--mcp", help="UE MCP Server 地址"),
    out: Optional[Path] = typer.Option(None, "--out", help="输出目录（默认: dist/<target>）"),
    dry_run: bool = typer.Option(False, "--dry-run", help="只预览不写盘"),
) -> None:
    """能力蒸馏 -> 注入目标宿主（Agent Harness §11.3 / §12）。"""
    from orchestrator.distiller import Distiller
    from orchestrator.importers.registry import get_importer, list_targets

    if target not in list_targets():
        console.print(f"[red]未知宿主 {target!r}；可选：{list_targets()}[/]")
        return

    names = [s.strip() for s in skills_list.split(",") if s.strip()] or None
    subset = Distiller().make_mvp_subset(names)
    if not subset:
        console.print("[yellow]蒸馏子集为空（可能因 tier/visibility 被裁掉）[/]")
        return

    bundle = get_importer(target).generate(subset, mcp_url)
    out_dir = out or (Path.cwd() / "dist" / target)
    console.print(Panel(
        f"[bold cyan]导入目标[/]: {target}\n"
        f"[bold cyan]蒸馏子集[/]: {len(subset)} 个 Skill（{', '.join(s.name for s in subset)}）\n"
        f"[bold cyan]生成文件[/]: {len(bundle.all_files())} 个\n"
        f"[bold cyan]输出目录[/]: {out_dir}",
        title="Import (distill → host)",
    ))
    if dry_run:
        console.print("[dim]dry-run：未写盘。[/]")
        return
    for f in bundle.all_files():
        path = out_dir / f.rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f.content, encoding="utf-8")
    console.print(f"[green]已注入 {target}（{len(bundle.all_files())} 个文件）。[/]")


@app.command("demo-concept")
def demo_concept(
    direction: str = typer.Option(..., "--direction", "-d", help="模糊的游戏方向一句话"),
    persist: bool = typer.Option(True, "--persist/--dry", help="持久化到 shared_state/runs/<runId>（默认开；--dry 仅内存预览）"),
) -> None:
    """演示：多 Skill(S1→S2→S3→S6→Director→E6) 协同产出可持久化的核心玩法提案并评估。

    用真实 LLM（读 .env）。默认按 run-id 版本化落盘到 shared_state/runs/<runId>/ 并写入
    PROPOSAL.md + RUNMANIFEST.json + 各阶段 SharedState 信封（含 parent_hash 链），并把当前
    runId 写进 shared_state/.ACTIVE_RUN，作为后续流程的输入/参考。
    """
    from orchestrator.demo_concept import resolve_active, run_concept, render

    console.print(f"[bold]开始提案管线：{direction}[/]（真实 LLM，约 6 次调用）")
    root = run_concept(direction, do_persist=persist)
    console.print(render(root))
    if persist:
        active = resolve_active()
        console.print(Panel(
            f"[green]已设 ACTIVE run：{active}[/]\n"
            f"信封/提案存于 shared_state/runs/{root.run_id}/（可供后续流程读取）",
            title="持久化位置",
        ))
    else:
        console.print("[dim]--dry：未落盘（仅内存预览）。[/]")


@app.command("demo-active")
def demo_active() -> None:
    """查看当前 ACTIVE 概念 run 及其落盘内容。"""
    from rich.panel import Panel

    from orchestrator.demo_concept import resolve_active
    from orchestrator.shared_state import SharedState

    rid = resolve_active()
    if not rid:
        console.print("[yellow]尚无 ACTIVE run（先跑 demo-concept）[/]")
        return
    base = SharedState().base
    run_dir = base / "runs" / rid
    import json

    manifest = {}
    if (run_dir / "RUNMANIFEST.json").exists():
        manifest = json.loads((run_dir / "RUNMANIFEST.json").read_text(encoding="utf-8"))
    stages = manifest.get("stages", [])
    stage_lines = "\n".join(f"  · {s['name']}  ← {s['producer']}" for s in stages)
    console.print(Panel(
        f"[bold]ACTIVE run[/]: {rid}\n"
        f"方向：{manifest.get('direction', '-')}\n"
        f"阶段:\n{stage_lines or '  (无)'}\n"
        f"PROPOSAL.md: {run_dir}/PROPOSAL.md\n"
        f"信封目录: {run_dir}/",
        title="ACTIVE configuration",
    ))


@app.command("ue-p0")
def ue_p0(
    endpoint: str = typer.Option("http://127.0.0.1:8000/mcp", "--endpoint", help="UE MCP Server 地址"),
    only_discover: bool = typer.Option(False, "--discover", help="只列出工具/自研 toolset 是否可用，不做改动"),
) -> None:
    """AC-P0 真 UE 最小闭环：经会话协议 place_cube→list→remove（需编辑器 -ModelContextProtocolStartServer 在跑）。"""
    from orchestrator.ue_mcp import UeMcpClient

    ue = UeMcpClient(endpoint=endpoint)
    if not ue.ensure_session():
        console.print("[red]连不上 UE MCP（先启动编辑器带 -ModelContextProtocolStartServer 并让 8000 监听）[/]")
        return
    console.print("[green]UE MCP session OK[/]")
    ts_name = ue.find_toolset_containing("BasicSpawn")
    if not ts_name:
        console.print("[yellow]未发现 BasicSpawnToolset（可能本编辑器会话未载入 Python 注册）。[/]")
        console.print("当前可发现工具集：")
        for ln in ue.list_toolsets_text().splitlines():
            if ln.lstrip().startswith("- "):
                console.print("  " + ln.strip()[:120])
        if only_discover:
            return
        console.print("[dim]提示：BasicSpawnToolset 通过项目 Content/Python/init_unreal.py 在启动时注册；"
                      "注册后本工具应出现在 Editor 工具集（也可能需 ModelContextProtocol.RefreshTools）。[/]")
        return
    console.print(f"[bold]自研 toolset 已载入[/]: {ts_name}")
    if only_discover:
        return
    step = console.print
    # place
    step("[cyan]① place_cube(0,0,100, 'AgentCube')[/]")
    r1 = ue.call_tool(ts_name, "place_cube", {"label": "AgentCube", "location_z": 100.0})
    console.print("  → " + r1[:200])
    # list
    step("[cyan]② list_agent_cubes[/]")
    r2 = ue.call_tool(ts_name, "list_agent_cubes", {})
    console.print("  → " + r2[:400])
    # remove
    step("[cyan]③ remove_cube('AgentCube')[/]")
    r3 = ue.call_tool(ts_name, "remove_cube", {"label": "AgentCube"})
    console.print("  → " + r3[:200])


@app.command("approve")
def approve(
    task_id: str = typer.Option(..., "--task-id"),
    allow: bool = typer.Option(True, "--allow/--deny"),
) -> None:
    console.print(f"审批：task={task_id} -> {'允许' if allow else '拒绝'}")
    console.print("[dim]P0 占位：审批门见 mcp_client.py default_approver。[dim]")


@app.command("rollback")
def rollback(
    task_id: str = typer.Option(..., "--task-id"),
) -> None:
    console.print(f"回滚：task={task_id}（post-tool 自动 commit 支持一键 revert）")
    console.print("[dim]P0 占位：回滚语义见 dag.py rollback()。[dim]")


# ---- 内部 helper ----
def _populate_dag(dag: DagEngine, task: str) -> None:
    """[占位] P0 以固定的小 DAG 演示依赖传播；P1 从任务解析/RAG 生成真实 DAG。"""
    dag.add_node(DagNode("gather", producer="general", tier="fast"))
    dag.add_node(DagNode("synthesize", producer="general", tier="default", deps=["gather"]))
    dag.add_node(DagNode("verify", producer="general", tier="strong", deps=["synthesize"], shared_state_refs=["/eval/check.json"]))
    dag.add_edge("gather", "synthesize")
    dag.add_edge("synthesize", "verify")


def auto_plan_id(task: str) -> str:
    import hashlib

    return "plan-" + hashlib.sha1(task.encode("utf-8")).hexdigest()[:8]


def HttpOrStub(endpoint: str, use_stub: bool):
    if use_stub:
        return StubTransport(require_ue=False)
    from orchestrator.mcp_client import HttpTransport

    return HttpTransport(endpoint=endpoint)


if __name__ == "__main__":
    app()
