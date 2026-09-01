"""CLI 入口（Typer + Rich）· P0 地基。

命令：
    orchestrator run --task "<需求>" [--plan id] [--dry-run] [--auto-approve-read-only]
    orchestrator plan  --task "<需求>"          # 生成 DAG 计划（dry-run 展示）
    orchestrator approve --task-id <id> --allow  # 审批一个挂起任务
    orchestrator rollback --task-id <id>

对齐 TechDesign §6.5（运行入口 / 审批 / 回滚）与 §9.1 仓库结构。
"""
from __future__ import annotations

import asyncio
import json
import logging
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
    """列出已装载的 Skill 及其元数据。"""
    from orchestrator.skills import get_registry
    from rich.table import Table

    reg = get_registry()
    names = reg.discover()
    table = Table(title="已装载 Skills")
    table.add_column("name")
    table.add_column("tier")
    table.add_column("risk")
    table.add_column("steps")
    for n in names:
        s = reg.load(n)
        spec = s.spec
        table.add_row(spec.name, spec.default_tier, spec.risk, str(len(spec.steps)))
    console.print(table)


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
