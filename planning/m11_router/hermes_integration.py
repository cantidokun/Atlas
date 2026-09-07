"""Controlled Hermes integration for M11 routing (SHADOW/ADVISORY feature gate).

Security boundary (non-negotiable):
- This is an advisory integration point. It routes a development task, may
  invoke a selected provider in shadow mode, and returns advisory metrics so the
  caller can COMPARE against the authoritative path.
- The authoritative Hermes execution path is UNCHANGED by default. A feature
  flag must be explicitly enabled to turn on shadow invocation.
- No second scheduler, retry controller, authorization layer, or persistence
  authority is introduced. It reads configuration and invokes providers through
  the M11.2 ProviderAdapter boundary only.
- No credentials, provider headers, or credential-bearing prompts are logged,
  persisted, or returned.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence


class FeatureDisabledError(RuntimeError):
    """Raised when an operation requires the M11 routing feature to be enabled."""


class FeatureConfigError(ValueError):
    """Raised when the M11 routing feature configuration is invalid (fail closed)."""


@dataclass(frozen=True)
class M11FeatureConfig:
    """Explicit feature-gate + mode configuration for M11 Hermes integration."""

    enabled: bool = False
    mode: str = "off"                 # "off" | "shadow" | "advisory"
    endpoint_config_ref: Optional[str] = None

    def __post_init__(self) -> None:
        if self.mode not in ("off", "shadow", "advisory"):
            raise FeatureConfigError(f"invalid M11 mode: {self.mode!r}")
        if not self.enabled and self.mode != "off":
            raise FeatureConfigError("cannot set a non-off mode while M11 routing is disabled")


def load_feature_config(
    *,
    enabled: Optional[bool] = None,
    mode: Optional[str] = None,
    endpoint_config_ref: Optional[str] = None,
    env: Optional[dict] = None,
) -> M11FeatureConfig:
    """Load the M11 feature gate from explicit args or environment.

    Default (no args, no env): DISABLED / mode="off" — preserves current behavior.
    Env overrides: ATLAS_M11_ROUTING_ENABLED (1/true), ATLAS_M11_ROUTING_MODE
    (off/shadow/advisory), ATLAS_M11_ROUTING_ENDPOINT_REF.
    Fails closed on invalid input.
    """
    e = env if env is not None else os.environ
    if enabled is None:
        v = e.get("ATLAS_M11_ROUTING_ENABLED")
        enabled = False
        if v is not None:
            enabled = str(v).strip().lower() in ("1", "true", "yes", "on")
    if mode is None:
        mode = str(e.get("ATLAS_M11_ROUTING_MODE", "off")).strip().lower() or "off"
    if endpoint_config_ref is None:
        endpoint_config_ref = e.get("ATLAS_M11_ROUTING_ENDPOINT_REF")
    return M11FeatureConfig(
        enabled=bool(enabled),
        mode=mode,
        endpoint_config_ref=endpoint_config_ref,
    )


class ShadowRoutedExecutor:
    """Advisory-only executor that routes a dev task and MAY invoke a provider.

    When ``config.enabled`` is False (default), ``execute`` returns a disabled
    marker AND does nothing — the authoritative Hermes path runs unchanged.

    When enabled in ``shadow``/``advisory`` mode, it routes the task through the
    M11 router, invokes the selected provider via an injected ``adapter`` (never
    modifying Hermes execution), and returns advisory metrics for comparison. It
    never replaces the actual development work, never calls Atlas production
    authority, and never writes to a second authority ledger.
    """

    def __init__(
        self,
        config: M11FeatureConfig,
        router,
        adapter,
        provider_configs: Optional[Sequence] = None,
        *,
        telemetry=None,
    ) -> None:
        self._config = config
        self._router = router
        self._adapter = adapter
        self._providers = list(provider_configs) if provider_configs else []
        self._telemetry = telemetry

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def mode(self) -> str:
        return self._config.mode

    def execute(self, *, task_id: str, dimension_scores: Dict[str, int],
                task_classes: Optional[Sequence[str]] = None,
                task_payload: Optional[Dict[str, object]] = None) -> dict:
        """Route (and optionally invoke, in shadow mode) returning advisory metrics.

        Returns:
          {"enabled": bool, "mode": str, "routed": bool, "disabled_reason": str?,
           "recommendation": {...}, "invocation": {...}? }

        Never raises for provider problems (they are captured as advisory fields);
        the authoritative path is never affected.
        """
        if not self._config.enabled:
            return {
                "enabled": False,
                "mode": "off",
                "routed": False,
                "disabled_reason": "M11 routing disabled; authoritative Hermes path unchanged",
            }

        decision = self._router.route_task(
            task_id, dimension_scores, task_classes=task_classes or ["docs"],
        )
        payload = dict(task_payload or {})
        recommendation = None
        if decision.selection is not None:
            recommendation = {
                "task_id": task_id,
                "selected_tier": decision.selection.selected_tier.value,
                "selected_model": decision.selection.selected_model_id,
                "reasons": list(decision.selection.reasons),
            }
        if decision.needs_human_review:
            return {
                "enabled": self._config.enabled,
                "mode": self._config.mode,
                "routed": True,
                "recommendation": recommendation,
                "needs_human_review": True,
                "failure": decision.failure_reason,
            }

        # Shadow/advisory: invoke via the injected adapter (never replaces work).
        usage = tokens = cost = latency = status = None
        if self._config.mode in ("shadow", "advisory") and self._adapter is not None:
            inv = self._invoke(decision.selection, task_id, payload)
            if inv is not None:
                status = inv.status
                tokens = inv.usage.total_tokens if not inv.tokens_unknown else None
                cost = inv.usage.estimated_cost_usd
                latency = inv.latency_ms
                usage = {
                    "input": inv.usage.input_tokens,
                    "output": inv.usage.output_tokens,
                    "total": inv.usage.total_tokens,
                }

        return {
            "enabled": True,
            "mode": self._config.mode,
            "routed": True,
            "recommendation": recommendation,
            "invocation": {
                "status": status,
                "tokens": tokens,
                "cost_usd": cost,
                "latency_ms": latency,
                "usage": usage,
                "advisory_only": True,
            },
        }

    def _invoke(self, selection, task_id, payload):
        from planning.m11_router.provider.shadow import ShadowAdvisor, NoProviderForTierError

        if not self._providers:
            return None  # no provider configured; advisory skip (do not guess)
        # Ensure the selected tier has a configured provider; else advisory skip.
        try:
            advisor = ShadowAdvisor(self._adapter, self._providers, telemetry=self._telemetry)
            advisory = advisor.advise(selection=selection, task_payload=payload, task_id=task_id)
            return advisory.invocation
        except NoProviderForTierError:
            return None
        except Exception:
            return None  # provider failures are advisory-only, never propagated