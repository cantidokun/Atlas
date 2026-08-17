"""Fail-closed recovery orchestration for paused autonomous lifecycles."""

from dataclasses import dataclass
from enum import Enum
from typing import Callable


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
    """Connect failure recovery to evidence, replan, authorization, and resume."""

    def __init__(self, evidence: Callable[[], bool], replan: Callable[[], bool], authorize: Callable[[], bool]):
        self._evidence = evidence
        self._replan = replan
        self._authorize = authorize
        self.state = RecoveryState.PAUSED

    def recover(self) -> RecoveryDecision:
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

        self.state = RecoveryState.READY_TO_RESUME
        return RecoveryDecision(self.state, "replacement plan authorized and ready to resume")

    def resume(self) -> RecoveryDecision:
        if self.state != RecoveryState.READY_TO_RESUME:
            self.state = RecoveryState.BLOCKED
            return RecoveryDecision(self.state, "resume requires a freshly authorized replacement plan")
        self.state = RecoveryState.RESUMED
        return RecoveryDecision(self.state, "recovery resumed")
