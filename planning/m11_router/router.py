"""High-level M11 router facade.

Ties classification -> routing -> escalation -> telemetry -> evidence gate into
one deterministic, dev-tooling-only workflow.

AUTHORITY ISOLATION (non-negotiable): this facade has NO imports from Atlas
production modules (no ``planning.unreal_render_*``, no receipt store, no
authorization). It cannot call ``apply_authorized``, ``submit_render``,
``reconcile_render_jobs``, schedule production work, or issue receipts. Its
persistence is confined to the ``m11_router`` telemetry ledger. ``route_task``
returns pure decisions; execution orchestration is out of scope for M11.1.
"""

from __future__ import annotations

import uuid

from typing import List, Optional, Sequence

from planning.m11_router.evidence_gate import EvidenceGate, EvidenceGateResult
from planning.m11_router.escalation import EscalationController
from planning.m11_router.model_profile import ModelProfile, ModelTier
from planning.m11_router.risk import RiskAssessment, classify_task
from planning.m11_router.routing import NoCapableProfileError, RouterDecision, select_profile
from planning.m11_router.telemetry import AppendOnlyTelemetry, RouterTelemetryRecord


class ModelRouter:
    """A minimal, deterministic development-model router.

    M11.1 scope: classification + profile-selection + escalation state +
    telemetry + evidence gate. Model execution/retry orchestration is NOT part
    of this milestone.
    """

    def __init__(
        self,
        profiles: Sequence[ModelProfile],
        *,
        escalation_max: int = 3,
        evidence_gate: Optional[EvidenceGate] = None,
        telemetry: Optional[AppendOnlyTelemetry] = None,
    ) -> None:
        self._profiles = list(profiles)
        self._escalator = EscalationController(max_escalations=escalation_max)
        self._evidence_gate = evidence_gate or EvidenceGate(require_tests=True)
        self._telemetry = telemetry

    @property
    def profiles(self) -> List[ModelProfile]:
        return list(self._profiles)

    def route_task(
        self,
        task_id: str,
        dimension_scores: dict,
        *,
        task_classes: Optional[Sequence[str]] = None,
        confidence: Optional[object] = None,  # documented, always ignored
    ) -> RouterDecision:
        """Deterministically classify and select a model for a task.

        Returns a ``RouterDecision``. On any failure that cannot be safely
        resolved (no capable profile, malformed profile, etc.) the decision is
        ``needs_human_review=True`` rather than raising — the router fails
        closed to a human-review terminal, never guessing.
        """
        decision = None
        try:
            risk = classify_task(
                task_id, dimension_scores, task_classes=task_classes, confidence=confidence
            )
        except (ValueError, TypeError) as exc:
            return RouterDecision(task_id=task_id, risk=None, needs_human_review=True, failure_reason=str(exc))

        try:
            selection = select_profile(task_id, risk, self._profiles)
        except NoCapableProfileError as exc:
            return RouterDecision(
                task_id=task_id, risk=risk, selection=None, needs_human_review=True,
                failure_reason=str(exc),
            )

        if self._telemetry is not None:
            self._record_attempt(risk, selection, task_id, outcome="ROUTED")
        return RouterDecision(task_id=task_id, risk=risk, selection=selection, needs_human_review=False)

    def evaluate_evidence(self, gate_result: Optional[EvidenceGateResult] = None, **signals) -> EvidenceGateResult:
        """Evaluate objective evidence via the gate; free-form claims are ignored."""
        if gate_result is not None:
            return gate_result
        return self._evidence_gate.evaluate(**signals)

    def _record_attempt(
        self,
        risk: RiskAssessment,
        selection,
        task_id: str,
        outcome: str = "ROUTED",
    ) -> None:
        rec = RouterTelemetryRecord(
            task_id=task_id,
            attempt_id=uuid.uuid4().hex[:16],
            record_type="attempt",
            task_classes=risk.task_classes,
            risk_dimension_scores=dict(risk.dimension_scores),
            risk_tier=risk.final_tier.value,
            selected_provider=None,
            selected_model=selection.selected_model_id,
            requested_token_budget=selection.profile.token_budget if selection.profile else None,
            final_outcome=outcome,
            selection_reason="|".join(selection.reasons),
        )
        # __post_init__ already rejects any sensitive payload; a failure to
        # append fails closed (never claims success without a durable record).
        if self._telemetry is not None:
            self._telemetry.append(rec)