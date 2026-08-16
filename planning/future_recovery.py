"""Fail-closed recovery decisions for deterministic Atlas futures.

A failed future step never silently retries or mutates the authorized plan.
Recovery first requires fresh authoritative evidence. Only then may a higher-level
planner produce a replacement plan that must pass authorization again.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from planning.future_execution import FutureExecutionController


class RecoveryDisposition(str, Enum):
    REACQUIRE_EVIDENCE = "REACQUIRE_EVIDENCE"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    ABORT = "ABORT"


@dataclass(frozen=True)
class RecoveryDecision:
    disposition: RecoveryDisposition
    reason: str
    failed_step: Optional[Dict[str, Any]] = None
    requires_fresh_evidence: bool = True

    def snapshot(self) -> Dict[str, Any]:
        return {
            "disposition": self.disposition.value,
            "reason": self.reason,
            "failed_step": dict(self.failed_step) if self.failed_step else None,
            "requires_fresh_evidence": self.requires_fresh_evidence,
        }


class FutureRecoveryGate:
    """Decide whether a failed deterministic future may proceed.

    The policy is intentionally conservative:
    * no failure is automatically retried;
    * no failed action is silently removed or replaced;
    * fresh evidence is required before any replan decision;
    * a replacement plan must be independently authorized by the caller.
    """

    def __init__(self, controller: FutureExecutionController):
        self.controller = controller
        self._decision: Optional[RecoveryDecision] = None
        self._fresh_evidence: Any = None

    @property
    def decision(self) -> Optional[RecoveryDecision]:
        return self._decision

    @property
    def fresh_evidence_acquired(self) -> bool:
        return self._fresh_evidence is not None

    @property
    def blocked(self) -> bool:
        return self.controller.blocked and not self.fresh_evidence_acquired

    def classify_failure(self) -> RecoveryDecision:
        if not self.controller.blocked:
            raise RuntimeError("Recovery can only classify a failed future.")
        failure = self.controller.failed or {}
        phase = failure.get("phase")
        if phase == "VERIFICATION":
            decision = RecoveryDecision(
                RecoveryDisposition.REPLAN_REQUIRED,
                "Postcondition verification failed; acquire fresh evidence and require a new authorized plan.",
                failure,
            )
        elif phase == "ACTION":
            decision = RecoveryDecision(
                RecoveryDisposition.REACQUIRE_EVIDENCE,
                "Action execution failed; acquire fresh authoritative evidence before considering any recovery.",
                failure,
            )
        else:
            decision = RecoveryDecision(
                RecoveryDisposition.ABORT,
                "Future failed outside an actionable recovery phase; terminate rather than guessing.",
                failure,
            )
        self._decision = decision
        return decision

    def record_fresh_evidence(self, evidence: Any) -> Any:
        if self._decision is None:
            raise RuntimeError("Classify the failure before recording recovery evidence.")
        if self._decision.disposition == RecoveryDisposition.ABORT:
            raise RuntimeError("This failure is terminal; recovery evidence cannot reopen it.")
        if evidence is None:
            raise ValueError("Fresh recovery evidence cannot be None.")
        self._fresh_evidence = evidence
        return evidence

    def advance_after_fresh_evidence(self) -> RecoveryDecision:
        """Move an evidence-gated failure to an explicit replan decision."""
        if not self.fresh_evidence_acquired:
            raise RuntimeError("Fresh authoritative evidence is required first.")
        if self._decision is None:
            raise RuntimeError("No recovery decision exists.")
        if self._decision.disposition == RecoveryDisposition.ABORT:
            raise RuntimeError("A terminal failure cannot transition to replanning.")
        if self._decision.disposition == RecoveryDisposition.REPLAN_REQUIRED:
            return self._decision
        self._decision = RecoveryDecision(
            RecoveryDisposition.REPLAN_REQUIRED,
            "Fresh authoritative evidence was acquired; a replacement plan must be produced and independently authorized.",
            self._decision.failed_step,
            requires_fresh_evidence=False,
        )
        return self._decision

    def authorize_replan(self) -> Any:
        if self._decision is None:
            raise RuntimeError("No recovery decision exists.")
        if self._decision.disposition != RecoveryDisposition.REPLAN_REQUIRED:
            raise RuntimeError("Recovery must reach REPLAN_REQUIRED before replanning.")
        if not self.fresh_evidence_acquired:
            raise RuntimeError("Fresh authoritative evidence is required before replanning.")
        return self._fresh_evidence

    def authorize_retry(self) -> None:
        raise RuntimeError("Automatic retry is prohibited; recovery requires fresh evidence and explicit re-authorization.")

    def snapshot(self) -> Dict[str, Any]:
        return {
            "blocked": self.blocked,
            "fresh_evidence_acquired": self.fresh_evidence_acquired,
            "decision": self._decision.snapshot() if self._decision else None,
        }
