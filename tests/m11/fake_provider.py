"""Mock provider adapter for M11.2 deterministic tests (never hits a live API)."""

import time
from typing import Any, Dict, Optional

from planning.m11_router.model_profile import ModelTier
from planning.m11_router.provider.invocation import (
    InvocationErrorKind,
    ModelResult,
    ProviderAdapter,
)
from planning.m11_router.provider.providers_config import (
    ProviderConfig,
    ProviderUsage,
    try_estimate_cost,
)


class FakeAdapter(ProviderAdapter):
    """Deterministic in-process provider adapter for tests.

    Failures/usage are configured per-call; no network I/O.
    """

    def __init__(
        self,
        *,
        status: str = "success",
        usage: Optional[ProviderUsage] = None,
        error_class: str = InvocationErrorKind.NONE.value,
        response_text: str = "ok",
        raise_timeout: bool = False,
    ) -> None:
        self._status = status
        self._usage = usage
        self._error_class = error_class
        self._response_text = response_text
        self._raise_timeout = raise_timeout

    def invoke(
        self,
        *,
        provider_config: ProviderConfig,
        task_payload: Dict[str, object],
        token_budget: Optional[int],
        timeout_s: Optional[int],
    ) -> ModelResult:
        if self._raise_timeout:
            raise TimeoutError("fake timeout")
        usage = self._usage
        if usage is None:
            # Default cheap usage with cost from pricing.
            usage = ProviderUsage(input_tokens=10, output_tokens=10, total_tokens=20)
            price = provider_config.pricing
            est = try_estimate_cost(usage, price) if price else None
            usage = ProviderUsage(
                input_tokens=10, output_tokens=10, total_tokens=20,
                estimated_cost_usd=est,
                pricing_source=provider_config.pricing_source_id,
            )
        return ModelResult(
            task_id=str(task_payload.get("_task_id", "t")),
            attempt_id="fake-attempt",
            selected_tier=ModelTier.L0,
            provider=provider_config.provider,
            model=provider_config.model,
            requested_token_budget=token_budget,
            status=self._status,
            usage=usage,
            latency_ms=1,
            response=self._response_text,
            error_class=self._error_class,
            error_message=("fake error" if self._status != "success" else None),
        )


def pricing_dict():
    return {"input_per_1k": 0.0005, "output_per_1k": 0.0015}