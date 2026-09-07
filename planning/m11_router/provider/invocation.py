"""Controlled model-invocation contract for the M11.2 router.

Implements design §2 (model invocation), §3 (token/cost accounting), §6
(provider failure handling).

Provider adapters are injected (vendor-agnostic boundary). The router never
calls a provider directly; it always goes through a ``ProviderAdapter`` that
returns a structured, immutable ``ModelResult``. Self-reported confidence is
never treated as evidence.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Protocol

from planning.m11_router.model_profile import ModelTier
from planning.m11_router.provider.providers_config import ProviderConfig, ProviderUsage


class InvocationErrorKind(str, Enum):
    NONE = "NONE"
    TIMEOUT = "TIMEOUT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    AUTH_ERROR = "AUTH_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    REQUEST_ERROR = "REQUEST_ERROR"


@dataclass(frozen=True)
class ModelResult:
    """Immutable structured result of a model invocation (design §2)."""

    task_id: str
    attempt_id: str
    selected_tier: ModelTier
    provider: Optional[str]
    model: Optional[str]
    requested_token_budget: Optional[int]
    status: str                       # "success" | "error"
    usage: ProviderUsage = ProviderUsage()
    latency_ms: Optional[int] = None
    response: Optional[Any] = None    # structured model response (dict/list/str), NOT raw prompt
    error_class: str = InvocationErrorKind.NONE.value
    error_message: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.status == "success" and self.error_class == InvocationErrorKind.NONE.value

    @property
    def tokens_unknown(self) -> bool:
        return self.usage.usage_unknown

    @property
    def cost_unknown(self) -> bool:
        return self.usage.estimated_cost_usd is None

class ProviderAdapter(Protocol):
    """Boundary every provider must implement (vendor-agnostic)."""

    def invoke(
        self,
        *,
        provider_config: ProviderConfig,
        task_payload: Dict[str, object],
        token_budget: Optional[int],
        timeout_s: Optional[int],
    ) -> ModelResult:
        """Perform one model invocation against the configured provider.

        Implementations are responsible for vendor SDK handling, error
        classification, timeout enforcement, and usage extraction. They MUST
        NOT be called with (or allow returning) any secret/credential/ATLAS
        attempt_nonce content in the recorded result.
        """
        ...


@dataclass(frozen=True)
class ProviderInvocation:
    """A single controlled invocation request (design §2)."""

    task_id: str
    attempt_id: str
    selected_tier: ModelTier
    provider_config: ProviderConfig
    task_payload: Dict[str, object]
    requested_token_budget: Optional[int] = None
    timeout_s: Optional[int] = None


class ProviderInvocationError(RuntimeError):
    """Raised when no provider adapter is available or a required signal is absent."""


OVERRIDE_TIMEOUT_DEFAULT = 300


def invoke_model(
    request: ProviderInvocation,
    adapter: ProviderAdapter,
    *,
    timeout_s: Optional[int] = None,
) -> ModelResult:
    """Synchronously invoke a provider adapter through the controlled boundary.

    Returns an immutable ``ModelResult``. Provider failures (timeout,
    unavailable, malformed, auth, rate-limit, request error) are classified and
    returned as an error result — they are never interpreted as evidence and
    never trigger an uncontrolled retry (escalation is bounded by M11.1).
    """
    cfg = request.provider_config
    eff_timeout = timeout_s if timeout_s is not None else (cfg.timeout_s if cfg.timeout_s else OVERRIDE_TIMEOUT_DEFAULT)
    eff_budget = request.requested_token_budget if request.requested_token_budget is not None else cfg.token_budget
    start = time.monotonic()
    try:
        result = adapter.invoke(
            provider_config=cfg,
            task_payload=dict(request.task_payload),
            token_budget=eff_budget,
            timeout_s=eff_timeout,
        )
    except TimeoutError:
        return ModelResult(
            task_id=request.task_id,
            attempt_id=request.attempt_id,
            selected_tier=request.selected_tier,
            provider=cfg.provider,
            model=cfg.model,
            requested_token_budget=eff_budget,
            status="error",
            latency_ms=_elapsed_ms(start),
            error_class=InvocationErrorKind.TIMEOUT.value,
            error_message="provider invocation timed out",
        )
    except Exception as exc:  # provider adapter raised unexpectedly
        return ModelResult(
            task_id=request.task_id,
            attempt_id=request.attempt_id,
            selected_tier=request.selected_tier,
            provider=cfg.provider,
            model=cfg.model,
            requested_token_budget=eff_budget,
            status="error",
            latency_ms=_elapsed_ms(start),
            error_class=InvocationErrorKind.PROVIDER_UNAVAILABLE.value,
            error_message=f"provider adapter raised: {type(exc).__name__}: {exc}",
        )
    if result is None or not isinstance(result, ModelResult):
        return ModelResult(
            task_id=request.task_id,
            attempt_id=request.attempt_id,
            selected_tier=request.selected_tier,
            provider=cfg.provider,
            model=cfg.model,
            requested_token_budget=eff_budget,
            status="error",
            latency_ms=_elapsed_ms(start),
            error_class=InvocationErrorKind.MALFORMED_RESPONSE.value,
            error_message="provider adapter returned a non-ModelResult",
        )
    # Fill latency if adapter didn't set it.
    if result.latency_ms is None:
        result = _with_latency(result, _elapsed_ms(start))
    return result


def _elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _with_latency(result: ModelResult, latency_ms: int) -> ModelResult:
    from dataclasses import replace
    return replace(result, latency_ms=latency_ms)
