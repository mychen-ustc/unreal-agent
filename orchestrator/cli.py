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
from orchestrator.mcp_client import McpClient, StubTransport
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
    auto_approve_read_only: bool = typer.Option(True, "--auto-approve-read-only/--require-approval",
                                                help="只读自动放行（默认开）"),
) -> None:
    """编排一次任务，跑通 DAG + Agent + MCP 门 + trace 日志。"""
    dag = DagEngine()
    _populate_dag(dag, task)

    with TraceWriter(DEFAULT_LOG_DIR / "trace.jsonl") as trace:
        # MCP client（唯一写入者）—— 脚手架默认用桩，连真 UE 时用 HTTP
        transport = HttpOrStub(engine_endpoint, use_stub)
        mcp = McpClient(transport=transport)

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
