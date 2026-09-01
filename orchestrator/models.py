"""LiteLLM 封装 + 三档模型路由（fast / default / strong）。

对齐 TechDesign §2.3 模型路由 与 §6.X 编排；TDR-010。
配置来源优先级：环境变量 > config/models.yaml 默认。
供应商走 OpenAI-compatible 统一网关：base_url + model_name（+ 可选 api_key）。

用法：:

    from orchestrator.models import ModelRouter
    router = ModelRouter()
    text = await router.complete("hello", tier="default")
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG = _REPO_ROOT / "orchestrator" / "config" / "models.yaml"


def _expand(val: Optional[str]) -> Optional[str]:
    """展开 ${VAR:-default} 环境变量引用。"""
    import re

    if not val:
        return val

    pat = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?}")

    def repl(m: re.Match) -> str:
        name, default = m.group(1), m.group(2)
        return os.environ.get(name, default if default is not None else "")

    return pat.sub(repl, val)  # type: ignore[return-value]


@dataclass
class ModelConfig:
    """单个档位的 LiteLLM 调用配置。"""

    provider: str
    model: str
    base_url: Optional[str]
    api_key: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 8192
    timeout_seconds: int = 90
    max_attempts: int = 3
    backoff_base_seconds: float = 1.5


class ModelRouter:
    """LiteLLM 统一路由，档位默认映射到 config/models.yaml 的 routing。"""

    _TARGET_MODEL_CLASS_CACHE: dict = {}

    def __init__(self, config_path: Path = _DEFAULT_CONFIG) -> None:
        load_dotenv(_REPO_ROOT / ".env")
        self._cfg = self._load(config_path)
        self._tiers: dict[str, ModelConfig] = {}

    @staticmethod
    def _load(config_path: Path) -> dict:
        if not config_path.exists():
            return {}
        with open(config_path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        # 展开所有 ${VAR} 引用
        return _expand_dict(raw)

    @property
    def tiers(self) -> dict[str, ModelConfig]:
        if not self._tiers:
            cfg = self._cfg
            supplier = cfg.get("supplier", {})
            provider = _expand(supplier.get("name")) or "deepseek"
            base_url = _expand(supplier.get("base_url"))
            api_key = _expand(supplier.get("api_key"))
            gen = cfg.get("generation", {})
            retry = cfg.get("retry", {})

            for tier, entry in (cfg.get("routing") or {}).items():
                model = _expand(entry.get("model"))
                self._tiers[tier] = ModelConfig(
                    provider=provider,
                    model=model,
                    base_url=base_url,
                    api_key=api_key,
                    temperature=float(gen.get("temperature", 0.3)),
                    max_tokens=int(gen.get("max_tokens", 8192)),
                    timeout_seconds=int(gen.get("timeout_seconds", 90)),
                    max_attempts=int(retry.get("max_attempts", 3)),
                    backoff_base_seconds=float(retry.get("backoff_base_seconds", 1.5)),
                )
        return self._tiers

    def tier(self, name: str = "default") -> ModelConfig:
        tiers = self.tiers
        if name not in tiers:
            raise KeyError(f"未知档位 {name!r}；可选：{sorted(tiers)}")
        return tiers[name]

    # ---- LiteLLM 调用 ----
    def _completion(self, mc: ModelConfig, messages: list[dict], **kwargs):
        # 延迟导入：litellm 较重，按需加载
        from litellm import completion

        target = f"{mc.provider}/{mc.model}"
        params = dict(
            model=target,
            messages=messages,
            temperature=kwargs.pop("temperature", mc.temperature),
            max_tokens=kwargs.pop("max_tokens", mc.max_tokens),
            timeout=kwargs.pop("timeout", mc.timeout_seconds),
            **kwargs,
        )
        if mc.base_url:
            params["api_base"] = mc.base_url
        if mc.api_key:
            params["api_key"] = mc.api_key
        return completion(**params)

    async def complete(
        self,
        prompt: str,
        tier: str = "default",
        system: Optional[str] = None,
        **kwargs,
    ) -> str:
        """同步完成一段 LLM 文本（按档位路由；失败自动退避重试）。"""
        mc = self.tier(tier)
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        return await asyncio.to_thread(self._complete_sync, mc, messages, **kwargs)

    def _complete_sync(self, mc: ModelConfig, messages: list[dict], **kwargs) -> str:
        attempt = 0
        last_exc: Exception | None = None
        while True:
            attempt += 1
            try:
                resp = self._completion(mc, messages, **kwargs)
                return resp.choices[0].message.content or ""
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt >= mc.max_attempts:
                    break
                delay = mc.backoff_base_seconds * (2 ** (attempt - 1))
                log.warning("LLM 调用失败(%s) 第%d次，%.1fs 后重试: %s", mc.model, attempt, delay, exc)
                _sleep_sync(delay)
        raise LLMError(f"{mc.model} 调用失败: {last_exc}") from last_exc


def _sleep_sync(seconds: float) -> None:
    import time

    time.sleep(seconds)


def _expand_dict(obj):
    from typing import Mapping

    if isinstance(obj, Mapping):
        return {k: _expand_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_dict(i) for i in obj]
    if isinstance(obj, str):
        return _expand(obj)
    return obj


class LLMError(RuntimeError):
    """LLM 调用错误。"""


_default_router: ModelRouter | None = None


def get_router() -> ModelRouter:
    global _default_router
    if _default_router is None:
        _default_router = ModelRouter()
    return _default_router
