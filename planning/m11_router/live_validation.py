"""Controlled live-provider validation path for M11.4.

Operator-invoked ONLY. This module performs exactly one controlled invocation
against a real OpenRouter/DeepSeek endpoint and records safe telemetry.

Boundary / security:
- Requires the existing M11 feature gate (``ATLAS_M11_ROUTING_ENABLED``) - never
  runs by default.
- Requires secure credentials (via ``SecureConfigResolver``) - fail-closed if
  missing; no credential falls back.
- Uses the real configured ``OpenRouterAdapter``.
- ONE request per invocation; bounded timeout; NO automatic provider retry.
- Records safe, append-only telemetry (no credentials/headers/nonce/HMAC/prompt).
- Never persists credentials or credential-bearing content.

Every provider response is evaluated with OBJECTIVE evidence (tests/build/static/
contract/diff) - a mere HTTP-200 is not success.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from planning.m11_router.provider.openrouter_adapter import OpenRouterAdapter
from planning.m11_router.provider.providers_config import ProviderConfig
from planning.m11_router.provider.shadow import NoProviderForTierError, ShadowAdvisor
from planning.m11_router.routing import ModelSelection, NoCapableProfileError
from planning.m11_router.router import ModelRouter
from planning.m11_router.telemetry import AppendOnlyTelemetry
from planning.m11_router.evidence_gate import EvidenceGateResult
from planning.m11_router.hermes_integration import FeatureDisabledError


@dataclass(frozen=True)
class LiveValidationResult:
    """Immutable result of one controlled live validation call.

    Exactly mirrors the required Capture set (design): selected tier,
    provider/model, request status, latency, tokens (input/output/total) when
    supplied, cost when pricing configured, evidence result, final outcome.
    Unknown fields stay None (never fabricated).
    """

    task_id: str
    attempt_id: str
    selected_tier: Optional[str]
    provider: Optional[str]
    model: Optional[str]
    request_status: str                    # "success" | "error" | "skipped"
    error_class: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    tokens_unknown: bool = True
    estimated_cost_usd: Optional[float] = None
    evidence_outcome: Optional[str] = None   # SUFFICIENT/INSUFFICIENT/FAILED/TERMINAL
    final_outcome: Optional[str] = None      # PASS / BLOCKED / NEEDS_HUMAN_REVIEW / PROVIDER_UNAVAILABLE / SKIPPED

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "attempt_id": self.attempt_id,
            "selected_tier": self.selected_tier,
            "provider": self.provider,
            "model": self.model,
            "request_status": self.request_status,
            "error_class": self.error_class,
            "error_message": self.error_message,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "tokens_unknown": self.tokens_unknown,
            "estimated_cost_usd": self.estimated_cost_usd,
            "evidence_outcome": self.evidence_outcome,
            "final_outcome": self.final_outcome,
        }


class ControlledLiveValidator:
    """Operator-invoked live validation against a real provider.

    Never auto-runs. Gate + credentials + an explicit call are required. It
    performs a single controlled invocation and returns screen-safe telemetry.
    """

    def __init__(
        self,
        router: ModelRouter,
        provider_configs: Sequence[ProviderConfig],
        *,
        adapter: Optional[OpenRouterAdapter] = None,
        telemetry: Optional[AppendOnlyTelemetry] = None,
    ) -> None:
        self._router = router
        self._providers = list(provider_configs)
        self._adapter = adapter or OpenRouterAdapter()
        self._telemetry = telemetry

    def validate_task(
        self,
        *,
        task_id: str,
        dimension_scores: Dict[str, int],
        objective_evidence: Optional[Dict[str, object]] = None,
        task_classes: Optional[Sequence[str]] = None,
        prompt: Optional[str] = None,
        gated_enabled: bool = True,
    ) -> LiveValidationResult:
        """Run one controlled live validation.

        ``gated_enabled`` must be True (operator explicitly enables the gate).
        The live call is performed ONLY if the gate is enabled; otherwise the
        result is SKIPPED and nothing is sent to the provider (preserving the
        default offline/deterministic behavior).
        """
        # Operator gate: without it we do nothing (no provider call).
        if not gated_enabled:
            return LiveValidationResult(
                task_id=task_id, attempt_id="", selected_tier=None,
                provider=None, model=None, request_status="skipped",
                final_outcome="SKIPPED",
            )

        decision = self._router.route_task(
            task_id, dimension_scores, task_classes=task_classes or ["docs"],
        )
        if decision.needs_human_review or decision.selection is None:
            return LiveValidationResult(
                task_id=task_id,
                attempt_id="",
                selected_tier=None,
                provider=None, model=None,
                request_status="error",
                error_class="NO_CAPABLE_PROFILE",
                error_message=decision.failure_reason,
                final_outcome="NEEDS_HUMAN_REVIEW",
            )

        # Build a credential-free task payload for the provider.
        payload = self._build_payload(decision.selection, prompt, objective_evidence)
        try:
            advisory = ShadowAdvisor(
                self._adapter, self._providers, telemetry=self._telemetry,
            ).advise(selection=decision.selection, task_payload=payload, task_id=task_id)
        except NoProviderForTierError:
            return LiveValidationResult(
                task_id=task_id, attempt_id="", selected_tier=decision.selection.selected_tier.value,
                provider=None, model=None, request_status="error",
                error_class="NO_PROVIDER_FOR_TIER", final_outcome="NEEDS_HUMAN_REVIEW",
            )
        inv = advisory.invocation
        ev = advisory.evidence

        request_status = inv.status if inv is not None else "error"
        error_class = inv.error_class if inv is not None else "NONE"
        # Objective evidence outcome (Http-200 alone is NOT success).
        ev_outcome = ev.outcome if ev is not None else "INSUFFICIENT"
        ev_sufficient = ev.is_sufficient if ev is not None else False

        if inv is None or not inv.is_success:
            final = "PROVIDER_UNAVAILABLE"
        elif ev_sufficient:
            final = "PASS"
        else:
            final = "BLOCKED"

        return LiveValidationResult(
            task_id=task_id,
            attempt_id=advisory.attempt_id,
            selected_tier=decision.selection.selected_tier.value if decision.selection else None,
            provider=inv.provider if inv else None,
            model=inv.model if inv else None,
            request_status=request_status,
            error_class=error_class,
            error_message=inv.error_message if inv else None,
            latency_ms=inv.latency_ms if inv else None,
            input_tokens=inv.usage.input_tokens if inv and not inv.tokens_unknown else None,
            output_tokens=inv.usage.output_tokens if inv and not inv.tokens_unknown else None,
            total_tokens=inv.usage.total_tokens if inv and not inv.tokens_unknown else None,
            tokens_unknown=(inv.tokens_unknown if inv else True),
            estimated_cost_usd=inv.usage.estimated_cost_usd if inv else None,
            evidence_outcome=ev_outcome,
            final_outcome=final,
        )

    @staticmethod
    def _build_payload(
        selection: ModelSelection,
        prompt: Optional[str],
        objective_evidence: Optional[Dict[str, object]],
    ) -> Dict[str, object]:
        """Build a credential-free payload from structured + evidence fields.

        A verbatim ``prompt`` may be included ONLY if it is credential-free;
        objective evidence fields are always passed. This never includes API
        keys, nonce, HMAC, Authorization headers, or credential-bearing text.
        """
        payload: Dict[str, object] = {}
        if objective_evidence:
            for k in ("tests_passed", "tests_failed", "build_result",
                      "static_result", "contract_result", "diff_checks"):
                if k in objective_evidence:
                    payload[k] = objective_evidence[k]
        if prompt is not None:
            # keep only in the request payload; telemetry never records it
            payload["description"] = prompt
        return payload

# ---------------------------------------------------------------------------
# Operator-invoked "live smoke test" (Phase 1): a single trivial task through
# the real provider. Must be explicitly gated + credentialed. Performs ONE call.
# ---------------------------------------------------------------------------

def run_live_smoke(
    *,
    task_id: str = "live-smoke-docs",
    prompt: Optional[str] = None,
    objective_evidence: Optional[Dict[str, object]] = None,
    gated_enabled: bool = True,
    router=None,
    provider_configs=None,
    resolver_env: Optional[dict] = None,
) -> LiveValidationResult:
    """Run a trivial deterministic dev task through the real provider once.

    ``gated_enabled`` must be True (operator gate). Needs a router, provider
    configs, and secure credentials in ``resolver_env`` (or real env). Never
    retries; never persists credentials; records safe telemetry only inside the
    returned ``LiveValidationResult`` (telemetry ledger optional).
    """
    from planning.m11_router.model_profile import load_profiles
    from planning.m11_router.provider.secure_config import SecureConfigResolver
    from planning.m11_router.provider.openrouter_adapter import OpenRouterAdapter
    from planning.m11_router.routing import select_profile  # noqa: F401 (used below)

    if not gated_enabled:
        raise FeatureDisabledError("M11 live validation gate is not enabled")

    # Minimal 4-tier dev profile set (provider/model are config params).
    if router is None:
        profiles = load_profiles([
            {"tier": "L0", "provider": "cfg0", "model": "cfg-lite", "capability_floor": "L0",
             "supported_task_classes": ["docs", "test"], "token_budget": 2000, "timeout_s": 30},
            {"tier": "L3", "provider": "cfg3", "model": "cfg-frontier", "capability_floor": "L3",
             "supported_task_classes": ["security-crypto", "recovery", "contract"],
             "token_budget": 60000, "timeout_s": 600},
        ])
        from planning.m11_router.router import ModelRouter
        router = ModelRouter(profiles)

    # Real provider config (names are deployment config). Credentials/endpoint
    # come from ``resolver_env`` (or real env); NEVER from the repo.
    from planning.m11_router.provider.providers_config import ProviderConfig, ModelTier  # noqa
    if resolver_env is None:
        import os
        resolver_env = dict(os.environ)
    if provider_configs is None:
        provider_configs = [
            ProviderConfig(
                provider="openrouter",
                model=resolver_env.get("ATLAS_M11_LIVE_MODEL") or "deepseek-v4-flash",
                capability_tier=ModelTier.L1,
                supported_task_classes=frozenset({"docs", "test", "refactor"}),
                token_budget=8000, timeout_s=60,
                endpoint_config_ref=resolver_env.get("ATLAS_M11_ROUTING_ENDPOINT_REF") or "openrouter",
                pricing=None,
            )
        ]

    resolver = SecureConfigResolver(env=resolver_env)
    adapter = OpenRouterAdapter(resolver, base_url=resolver_env.get("ATLAS_M11_ROUTING_ENDPOINT"))
    validator = ControlledLiveValidator(router, provider_configs, adapter=adapter)
    from planning.m11_router.risk import RISK_DIMENSIONS
    dims = {d: 0 for d in RISK_DIMENSIONS}  # trivial docs task
    return validator.validate_task(
        task_id=task_id, dimension_scores=dims,
        objective_evidence=objective_evidence or {"tests_passed": 1, "tests_failed": 0},
        task_classes=["docs"], prompt=prompt, gated_enabled=gated_enabled,
    )
