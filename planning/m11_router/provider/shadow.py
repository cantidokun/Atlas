"""Shadow/advisory execution mode for the M11.2 router.

Implements design §4 (shadow/advisory mode) and §9 (separation of concerns).

The router RECOMMENDS and INVOKES a development model, records result telemetry
and evidence outcome, and compares against the existing (authoritative) path —
but it NEVER silently replaces the Hermes execution path and NEVER mutates Atlas
production authority. Atlas production execution is completely untouched.

Boundary: shadow mode is advisory. The existing Hermes execution path remains
authoritative for performing development work. Provider results / model self
-report are never evidence; only objective independently-verified signals
(tests/build/static/contract/diff via the M11 evidence gate) may classify an
attempt as successful.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence

from planning.m11_router.evidence_gate import EvidenceGate, EvidenceGateResult
from planning.m11_router.escalation import EscalationController, EscalationState
from planning.m11_router.model_profile import ModelTier, tier_index
from planning.m11_router.provider.invocation import (
    ModelResult,
    ProviderAdapter,
    ProviderInvocation,
    invoke_model,
)
from planning.m11_router.provider.providers_config import (
    ProviderConfig,
    try_estimate_cost,
)
from planning.m11_router.routing import ModelSelection
from planning.m11_router.telemetry import (
    AppendOnlyTelemetry,
    RouterTelemetryRecord,
    TelemetryValidationError,
)


@dataclass(frozen=True)
class ShadowAdvisory:
    """Immutable advisory record produced by a shadow-mode run."""

    task_id: str
    attempt_id: str
    selected_tier: ModelTier
    recommendation: Optional[ModelSelection] = None
    provider_config: Optional[ProviderConfig] = None
    invocation: Optional[ModelResult] = None
    evidence: Optional[EvidenceGateResult] = None
    escalation: Optional[EscalationState] = None
    telemetry_written: bool = False
    failure_reason: Optional[str] = None

    @property
    def match_evidence(self) -> bool:
        """True when the invocation succeeded AND objective evidence passed."""
        return (
            self.invocation is not None
            and self.invocation.is_success
            and self.evidence is not None
            and self.evidence.is_sufficient
        )

    @property
    def needs_human_review(self) -> bool:
        return self.escalation is not None and getattr(self.escalation, "terminal", False)


class NoProviderForTierError(ValueError):
    """No configured provider satisfies the selected tier (fail closed)."""


class ShadowAdvisor:
    """Drives a shadow-model-invocation + evidence + escalation cycle.

    ``shadow=True`` (default): the returned advisory is for comparison only; the
    caller owns whether to act. The authoritative Hermes path is never bypassed.
    """

    def __init__(
        self,
        adapter: ProviderAdapter,
        provider_configs: Sequence[ProviderConfig],
        *,
        telemetry: Optional[AppendOnlyTelemetry] = None,
        evidence_gate: Optional[EvidenceGate] = None,
        escalation: Optional[EscalationController] = None,
        shadow: bool = True,
    ) -> None:
        self._adapter = adapter
        self._providers = list(provider_configs)
        self._telemetry = telemetry
        self._gate = evidence_gate or EvidenceGate(require_tests=True, require_build=True)
        self._escalator = escalation or EscalationController()
        self._shadow = shadow

    def _resolve_provider(self, selection: ModelSelection) -> ProviderConfig:
        """Pick the configured provider whose capability_tier is the selected tier.

        Fails closed: if none matches (or config is malformed), raise
        ``NoProviderForTierError`` so the caller routes to NEEDS_HUMAN_REVIEW.
        """
        # Lowest-capable tier >= selected tier; prefer an exact tier match.
        candidates = [
            p for p in self._providers
            if tier_index(p.capability_tier) >= tier_index(selection.selected_tier)
        ]
        if not candidates:
            raise NoProviderForTierError(
                f"no configured provider for tier {selection.selected_tier.value}"
            )
        # Cheapest capable: exact tier first, then lowest index, then provider name.
        candidates.sort(key=lambda p: (tier_index(p.capability_tier), p.provider))
        return candidates[0]

    def advise(
        self,
        *,
        selection: ModelSelection,
        task_payload: Dict[str, object],
        task_id: Optional[str] = None,
        attempt_id: Optional[str] = None,
    ) -> ShadowAdvisory:
        """Execute one advisory model invocation against the selected provider.

        Records telemetry (if a ledger is supplied), evaluates objective evidence,
        and returns an immutable ``ShadowAdvisory``. Provider failure alone never
        escalates uncontrolled; the bounded M11.1 escalation governs next steps.

        ``task_payload`` MUST NOT contain secrets/credentials/attempt_nonce. If a
        telemetry ledger is present, any disallowed field is rejected by the
        record's privacy allow-list (fail-closed).
        """
        pid = task_id or (selection.task_id or "unknown")
        aid = attempt_id or _default_attempt_id(pid, selection)
        try:
            cfg = self._resolve_provider(selection)
        except NoProviderForTierError as exc:
            if self._telemetry is not None:
                self._record_no_provider(pid, aid, selection, str(exc))
            return ShadowAdvisory(
                task_id=pid, attempt_id=aid, selected_tier=selection.selected_tier,
                recommendation=selection, failure_reason=str(exc),
            )

        request = ProviderInvocation(
            task_id=pid,
            attempt_id=aid,
            selected_tier=selection.selected_tier,
            provider_config=cfg,
            task_payload=task_payload,
            requested_token_budget=selection.profile.token_budget if selection.profile else None,
        )
        inv_result = invoke_model(request, self._adapter)

        evidence = self._gate.evaluate(
            tests_passed=task_payload.get("tests_passed"),
            tests_failed=task_payload.get("tests_failed"),
            build_result=task_payload.get("build_result"),
            static_result=task_payload.get("static_result"),
            contract_result=task_payload.get("contract_result"),
            diff_checks=task_payload.get("diff_checks"),
        )

        telemetry_written = False
        if self._telemetry is not None:
            try:
                self._telemetry.append(self._attempt_record(pid, aid, selection, cfg, inv_result, evidence))
                telemetry_written = True
            except TelemetryValidationError:
                telemetry_written = False  # privacy violation / write failure -> fail closed

        # Determine advisory (not authoritative) outcome and optional escalation hint.
        escalation = None
        if not evidence.is_sufficient:
            escalation = self._escalator.initial(pid, selection.selected_tier, aid)

        return ShadowAdvisory(
            task_id=pid,
            attempt_id=aid,
            selected_tier=selection.selected_tier,
            recommendation=selection,
            provider_config=cfg,
            invocation=inv_result,
            evidence=evidence,
            escalation=escalation,
            telemetry_written=telemetry_written,
            failure_reason=("provider unavailable" if not inv_result.is_success else None),
        )

    def _record_no_provider(self, pid, aid, selection, reason) -> None:
        rec = RouterTelemetryRecord(
            task_id=pid,
            attempt_id=aid,
            record_type="attempt",
            risk_tier=selection.selected_tier.value if selection.selected_tier else None,
            selected_model=selection.selected_model_id,
            final_outcome="NEEDS_HUMAN_REVIEW",
            selection_reason=reason,
        )
        try:
            self._telemetry.append(rec)
        except TelemetryValidationError:
            pass

    def _attempt_record(self, pid, aid, selection, cfg, inv_result, evidence) -> RouterTelemetryRecord:
        cost = inv_result.usage.estimated_cost_usd
        # Cost metadata is configuration-driven; unknown stays None (explicit UNKNOWN).
        if cost is None and inv_result.usage.total_tokens is not None:
            cost = try_estimate_cost2(inv_result.usage, cfg.pricing)
        return RouterTelemetryRecord(
            task_id=pid,
            attempt_id=aid,
            record_type="attempt",
            task_classes=selection.task_classes,
            risk_dimension_scores=dict(selection.risk.dimension_scores) if selection.risk else {},
            risk_tier=selection.selected_tier.value if selection.selected_tier else None,
            selected_provider=inv_result.provider,
            selected_model=inv_result.model,
            requested_token_budget=inv_result.requested_token_budget,
            actual_token_usage=inv_result.usage.total_tokens,
            estimated_cost_usd=cost,
            latency_ms=inv_result.latency_ms,
            tests_passed=evidence.tests_passed,
            tests_failed=evidence.tests_failed,
            build_result=evidence.build_result,
            static_result=evidence.static_result,
            contract_result=evidence.contract_result,
            final_outcome="SUCCESS" if evidence.is_sufficient else "BLOCKED",
            selection_reason="|".join(selection.reasons) if selection.reasons else None,
        )


def try_estimate_cost2(usage, pricing):
    """Local alias for try_estimate_cost (keeps shadow module import surface small)."""
    return try_estimate_cost(usage, pricing)


def _default_attempt_id(task_id, selection) -> str:
    import hashlib
    return hashlib.sha256(f"{task_id}:{selection.selected_model_id}".encode()).hexdigest()[:16]