"""importers 宿主 Adapter 注册表：按 target 选择实现（Agent Harness §12.2）。
"""
from __future__ import annotations

from orchestrator.importers.base import HarnessImporter
from orchestrator.importers.self_hosted import SelfHostedImporter

# 初始注册：self_hosted 为参考实现；claude_code/codex/openclaw/hermes 按文档 §12.4 后续补。
_ADAPTERS: dict[str, type[HarnessImporter]] = {
    "self_hosted": SelfHostedImporter,
}


def register_adapter(target: str, cls: type[HarnessImporter]) -> None:
    _ADAPTERS[target] = cls


def get_importer(target: str) -> HarnessImporter:
    if target not in _ADAPTERS:
        raise KeyError(
            f"没有 target={target!r} 的 importer；可选：{sorted(_ADAPTERS)}"
        )
    return _ADAPTERS[target]()


def list_targets() -> list[str]:
    return sorted(_ADAPTERS)
