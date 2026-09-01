"""DAG 引擎：任务依赖图 + 拓扑排序 + stale 传播 + 回退循环。

对齐 TechDesign §6.2（scheduler/编排核心依赖本模块）。

- 节点：Agent 任务（task_id + producer）。
- 边：SharedState 读写依赖（本 P0 简化为显式声明 + 供自动推导的 hook）。
- 失效传播：上游变更 → BFS 标记下游 stale（深度 ≤ 3）。
- 回退循环：得分 < 70 或 critical bug → 定位责任 Agent 重新入队（≤ 3 次）。
"""
from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

log = logging.getLogger(__name__)

MAX_STALE_DEPTH = 3  # PRD §4.1.3
MAX_LOOP = 3
SCORE_THRESHOLD = 70
VERDICTS_TO_REWORK = {"FIX"}
VERDICT_NEEDS_APPROVAL = {"GO", "NO-GO", "PIVOT"}


@dataclass
class DagNode:
    """一个 Skill 内部的步骤 / 子任务（Harness §6.2）。"""

    task_id: str
    producer: str            # Agent / Skill 名
    skill: str = ""          # 所属 Skill，如 "scenes_pcg" / "eval_gameplay"
    step: str = ""           # Skill 内步骤标识，如 "generate" / "audit"
    tier: str = "default"    # fast | default | strong
    severity: str = "read_only"  # read_only | mutating | destructive（风险门禁）
    partition: Optional[str] = None   # 空间分区锁（可选）
    priority: int = 100
    deps: list[str] = field(default_factory=list)   # 依赖的 task_id
    shared_state_refs: list[str] = field(default_factory=list)  # 读/写 shared_state 路径

    # 运行期状态
    stale: bool = False
    dependent_tasks: list[str] = field(default_factory=list, repr=False)
    state: str = "pending"   # pending | ready | running | done | failed | retry | blocked_approval


@dataclass
class DagEdge:
    upstream: str
    downstream: str

    def __str__(self) -> str:
        return f"{self.upstream} → {self.downstream}"


class DagRollbackResult:
    def __init__(self) -> None:
        self.attempts: dict[str, int] = {}   # task_id -> 已重试次数


class DagEngine:
    """自研 DAG 状态机（不依赖框架）。"""

    def __init__(self, max_stale_depth: int = MAX_STALE_DEPTH, max_loop: int = MAX_LOOP) -> None:
        self.nodes: dict[str, DagNode] = {}
        self.adj: dict[str, list[str]] = {}
        self.max_stale_depth = max_stale_depth
        self.max_loop = max_loop
        self.rollback_result = DagRollbackResult()

    # ---- 图构建 ----
    def add_node(self, node: DagNode) -> None:
        self.nodes[node.task_id] = node
        self.adj.setdefault(node.task_id, [])

    def add_edge(self, upstream: str, downstream: str) -> None:
        if upstream not in self.nodes or downstream not in self.nodes:
            raise KeyError(f"edge 引用未知节点: {upstream}->{downstream}")
        self.adj.setdefault(upstream, []).append(downstream)
        # 下游也要记录（供倒序遍历）
        self.nodes[downstream].deps.append(upstream)

    @property
    def edges(self) -> list[DagEdge]:
        return [DagEdge(u, v) for u, vs in self.adj.items() for v in vs]

    # ---- 拓扑排序 ----
    def _indegree(self) -> dict[str, int]:
        deg = {n: 0 for n in self.nodes}
        for vs in self.adj.values():
            for v in vs:
                deg[v] += 1
        return deg

    def topological_order(self) -> list[str]:
        """Kahn 拓扑排序（可并行层由 scheduler 处理）。"""
        indeg = self._indegree()
        known = [n for n, d in indeg.items() if d == 0]
        order: list[str] = []
        while known:
            u = known.pop(0)
            order.append(u)
            for v in self.adj[u]:
                indeg[v] -= 1
                if indeg[v] == 0:
                    known.append(v)
        if len(order) != len(self.nodes):
            raise RuntimeError("DAG 存在环，无法拓扑排序")
        return order

    def ready_nodes(self) -> list[str]:
        """当前可调度（依赖全部完成且未 stale）的节点。"""
        completed = {n for n, nd in self.nodes.items() if nd.state in ("done", "done_approved")}
        return [n for n in self.nodes
                if self.nodes[n].state == "pending"
                and all(d in completed for d in self.nodes[n].deps)
                and not self.nodes[n].stale]

    # ---- stale 传播 ----
    def mark_stale(self, task_id: str) -> list[str]:
        """上游 task_id 变更，BFS 标记下游 stale（深度 ≤ max_stale_depth）。"""
        affected: list[str] = []
        queue: deque[tuple[str, int]] = deque([(task_id, 0)])
        seen: set[str] = {task_id}
        while queue:
            u, depth = queue.popleft()
            if depth >= self.max_stale_depth:
                continue
            for v in self.adj.get(u, []):
                if v not in seen:
                    seen.add(v)
                    self.nodes[v].stale = True
                    if self.nodes[v].state in ("done", "done_approved"):
                        self.nodes[v].state = "stale"  # 下游重跑
                    affected.append(v)
                    queue.append((v, depth + 1))
        log.info("stale 传播：%s -> %s", task_id, affected)
        return affected

    # ---- 回退循环 ----
    def should_rework(self, score: Optional[float], verdict: str = "") -> tuple[bool, str]:
        """判断产物是否需要回退给责任 Agent。"""
        if verdict in VERDICTS_TO_REWORK:
            return True, response_for_verdict(verdict)
        if score is not None and score < SCORE_THRESHOLD:
            return True, f"得分 {score:.0f} < {SCORE_THRESHOLD}"
        return False, ""

    def record_attempt(self, task_id: str) -> int:
        self.rollback_result.attempts[task_id] = self.rollback_result.attempts.get(task_id, 0) + 1
        return self.rollback_result.attempts[task_id]

    def rollback(self, task_id: str, link_back_to: str, reason: str) -> str:
        """把责任 Agent 的某个任务重新入队（≤ max_loop 次），返回新 task_id 或升级人工。"""
        attempts = self.record_attempt(link_back_to)
        if attempts > self.max_loop:
            log.warning("回退次数超限(%d)：%s 升级人工审批", attempts, link_back_to)
            return f"ESCALATE:{link_back_to}"
        new_id = f"{link_back_to}#redo{attempts}"
        # 重建节点，承接同一份依赖/产物
        origin = self.nodes.get(link_back_to)
        if origin is None:
            raise KeyError(f"回退目标不存在: {link_back_to}")
        node = DagNode(
            task_id=new_id,
            producer=origin.producer,
            tier=origin.tier,
            deps=list(origin.deps),
            shared_state_refs=list(origin.shared_state_refs),
        )
        self.add_node(node)
        # 下游接续
        for dv in self.adj.get(link_back_to, []):
            self.add_edge(new_id, dv)
        self.mark_stale(new_id)
        log.info("回退：%s 失败(%s) -> 重建 %s", link_back_to, reason, new_id)
        return new_id

    def propose_links(self, delta: dict) -> list[DagEdge]:
        """[占位] 从 SharedState delta 自动推导依赖边（P1 细化）。"""
        return list(self.edges)


def response_for_verdict(verdict: str) -> str:
    return f"评估结论 {verdict!r} 需要回退重做"
