"""跨 Agent Harness 集成：importers/ 层（Agent Harness §12）。

职责：把「能力蒸馏子集」（Distiller 产出，宿主无关）翻译成特定宿主
（Claude Code / Codex / OpenClaw / Hermes / 自宿主）可加载的形式。

边界（§12.1）：
- 只消费 distiller 的蒸馏子集，绝不直接导入完整能力包。
- 导入是纯生成/翻译：不修改源能力包与蒸馏子集；确定性、幂等、回归可测。
"""
from __future__ import annotations

from orchestrator.importers.base import HarnessImporter, ImportBundle  # noqa: F401

__all__ = ["HarnessImporter", "ImportBundle"]
