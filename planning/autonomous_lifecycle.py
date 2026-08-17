"""Fail-closed autonomous lifecycle coordinator."""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional


class LifecycleState(str, Enum):
    READY = "ready"
    CHECKPOINTED = "checkpointed"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    PAUSED = "paused"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass(frozen=True)
class LifecycleDecision:
    state: LifecycleState
    reason: str


class AutonomousLifecycle:
    """Coordinate safe continuation without allowing state invention."""

    def __init__(self, admission_gate: Callable[[], bool]):
        self._admission_gate = admission_gate
        self.state = LifecycleState.READY

    def admit(self) -> LifecycleDecision:
        if not self._admission_gate():
            self.state = LifecycleState.PAUSED
            return LifecycleDecision(self.state, "runtime admission rejected")
        self.state = LifecycleState.CHECKPOINTED
        return LifecycleDecision(self.state, "runtime admitted")

    def begin_execution(self) -> LifecycleDecision:
        if self.state != LifecycleState.CHECKPOINTED:
            self.state = LifecycleState.FAILED
            return LifecycleDecision(self.state, "execution requires an admitted checkpoint")
        self.state = LifecycleState.EXECUTING
        return LifecycleDecision(self.state, "execution started")

    def begin_verification(self) -> LifecycleDecision:
        if self.state != LifecycleState.EXECUTING:
            self.state = LifecycleState.FAILED
            return LifecycleDecision(self.state, "verification requires execution")
        self.state = LifecycleState.VERIFYING
        return LifecycleDecision(self.state, "verification started")

    def finalize(self, verified: bool) -> LifecycleDecision:
        if self.state != LifecycleState.VERIFYING:
            self.state = LifecycleState.FAILED
            return LifecycleDecision(self.state, "finalization requires verification")
        self.state = LifecycleState.COMPLETE if verified else LifecycleState.PAUSED
        return LifecycleDecision(
            self.state,
            "verification accepted" if verified else "verification failed; execution paused",
        )
