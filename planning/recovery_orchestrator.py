"""Fail-closed recovery orchestration with receipt-bound resume."""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from planning.recovery_receipt import RecoveryReceipt


class RecoveryState(str, Enum):
    PAUSED = "paused"
    EVIDENCE_REQUIRED = "evidence_required"
    REPLAN_REQUIRED = "replan_required"
    AUTHORIZATION_REQUIRED = "authorization_required"
    READY_TO_RESUME = "ready_to_resume"
    RESUMED = "resumed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class RecoveryDecision:
    state: RecoveryState
    reason: str


class RecoveryOrchestrator:
    """Require fresh evidence, replan, authorization, and receipt-bound resume."""

    def __init__(self, evidence: Callable[[], bool], replan: Callable[[], bool], authorize: Callable[[], bool]):
        self._evidence = evidence
        self._replan = replan
        self._authorize = authorize
        self.state = RecoveryState.PAUSED
        self._receipt: Optional[RecoveryReceipt] = None

    def recover(self, evidence_digest=None, plan_digest=None, authorization_digest=None) -> RecoveryDecision:
        self.state = RecoveryState.EVIDENCE_REQUIRED
        if not self._evidence():
            self.state = RecoveryState.BLOCKED
            return RecoveryDecision(self.state, "fresh recovery evidence unavailable")
        self.state = RecoveryState.REPLAN_REQUIRED
        if not self._replan():
            self.state = RecoveryState.BLOCKED
            return RecoveryDecision(self.state, "recovery replan rejected")
        self.state = RecoveryState.AUTHORIZATION_REQUIRED
        if not self._authorize():
            self.state = RecoveryState.BLOCKED
            return RecoveryDecision(self.state, "replacement plan not authorized")
        if None in (evidence_digest, plan_digest, authorization_digest):
            self.state = RecoveryState.BLOCKED
            return RecoveryDecision(self.state, "recovery identities required")
        try:
            self._receipt = RecoveryReceipt(evidence_digest, plan_digest, authorization_digest)
        except (TypeError, ValueError):
            self.state = RecoveryState.BLOCKED
            return RecoveryDecision(self.state, "recovery identities are invalid")
        self.state = RecoveryState.READY_TO_RESUME
        return RecoveryDecision(self.state, "replacement plan authorized and receipt-bound")

    def resume(self, evidence_digest: str, plan_digest: str, authorization_digest: str) -> RecoveryDecision:
        if self.state != RecoveryState.READY_TO_RESUME or self._receipt is None:
            self.state = RecoveryState.BLOCKED
            return RecoveryDecision(self.state, "resume requires a freshly authorized recovery receipt")
        if not self._receipt.matches(evidence_digest, plan_digest, authorization_digest):
            self.state = RecoveryState.BLOCKED
            return RecoveryDecision(self.state, "recovery receipt identity mismatch")
        self.state = RecoveryState.RESUMED
        return RecoveryDecision(self.state, "recovery resumed with matching receipt")
