"""Fail-closed recovery orchestration with authoritative receipt state."""

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
    """Run recovery gates and make the resulting receipt the resume authority."""

    def __init__(self, evidence: Callable[[], bool], replan: Callable[[], bool], authorize: Callable[[], bool]):
        self._evidence = evidence
        self._replan = replan
        self._authorize = authorize
        self.state = RecoveryState.PAUSED
        self._receipt: Optional[RecoveryReceipt] = None

    @property
    def receipt(self) -> Optional[RecoveryReceipt]:
        """The current immutable receipt, if recovery reached authorization."""
        return self._receipt

    def recover(self, evidence_digest=None, plan_digest=None, authorization_digest=None) -> RecoveryDecision:
        # Never carry an old receipt across a new recovery attempt.
        self._receipt = None
        self.state = RecoveryState.EVIDENCE_REQUIRED
        if not self._evidence():
            return self._block("fresh recovery evidence unavailable")

        self.state = RecoveryState.REPLAN_REQUIRED
        if not self._replan():
            return self._block("recovery replan rejected")

        self.state = RecoveryState.AUTHORIZATION_REQUIRED
        if not self._authorize():
            return self._block("replacement plan not authorized")

        if not all(isinstance(value, str) and value for value in (
            evidence_digest, plan_digest, authorization_digest
        )):
            return self._block("recovery identities required")

        try:
            receipt = RecoveryReceipt(evidence_digest, plan_digest, authorization_digest)
        except (TypeError, ValueError):
            return self._block("recovery identities are invalid")

        self._receipt = receipt
        self.state = RecoveryState.READY_TO_RESUME
        return RecoveryDecision(self.state, "replacement plan authorized and receipt-bound")

    def resume(self, evidence_digest: str, plan_digest: str, authorization_digest: str) -> RecoveryDecision:
        receipt = self._receipt
        if self.state != RecoveryState.READY_TO_RESUME or receipt is None:
            return self._block("resume requires a freshly authorized recovery receipt")
        if not receipt.matches(evidence_digest, plan_digest, authorization_digest):
            return self._block("recovery receipt identity mismatch")
        self.state = RecoveryState.RESUMED
        return RecoveryDecision(self.state, "recovery resumed with matching receipt")

    def _block(self, reason: str) -> RecoveryDecision:
        self.state = RecoveryState.BLOCKED
        self._receipt = None
        return RecoveryDecision(self.state, reason)
