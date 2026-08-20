"""Bounded model-turn supervision for the controller communication bridge.

The controller must not assume that a remote reasoning model will always
return promptly.  This module provides a transport-neutral state machine for
one model turn so a host can impose a deadline, accept heartbeats while the
model is working, and recover deterministically when the turn expires.

It deliberately does not start a subprocess, call an LLM, sleep, or retry.
The transport/host owns those concerns and drives this state machine with
explicit events.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from time import monotonic
from typing import Optional

from controller.communication_gateway import CommunicationProtocolError


class TurnState(str, Enum):
    """Terminal and active states for one supervised model turn."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    TIMED_OUT = "timed_out"
    FAILED = "failed"
    CANCELLED = "cancelled"


_TERMINAL_STATES = {
    TurnState.COMPLETED,
    TurnState.TIMED_OUT,
    TurnState.FAILED,
    TurnState.CANCELLED,
}


@dataclass(frozen=True)
class TurnSnapshot:
    """Immutable view of the current model-turn boundary."""

    turn_id: Optional[str]
    state: TurnState
    deadline: Optional[float]
    last_heartbeat: Optional[float]
    error: Optional[str]

    @property
    def expired(self) -> bool:
        """Whether the turn is currently past its deadline."""
        return self.state == TurnState.TIMED_OUT


class ModelTurnSupervisor:
    """Supervise sequential bounded model turns without blocking the host."""

    def __init__(self, *, clock=monotonic):
        self._clock = clock
        self._turn_id: Optional[str] = None
        self._state = TurnState.IDLE
        self._deadline: Optional[float] = None
        self._last_heartbeat: Optional[float] = None
        self._error: Optional[str] = None

    def begin(self, turn_id: str, timeout_seconds: float) -> TurnSnapshot:
        """Start the next turn with an explicit finite positive deadline.

        A controller session may contain many sequential model turns.  A
        completed, failed, cancelled, or timed-out turn therefore becomes the
        terminal record for that turn only; it does not permanently disable
        the supervisor.  Turn IDs remain unique within the supervisor so a
        stale retry cannot be mistaken for a new turn.
        """
        if self._state == TurnState.RUNNING:
            raise CommunicationProtocolError("a model turn is already running")
        if not isinstance(turn_id, str) or not turn_id:
            raise CommunicationProtocolError("turn_id must be a non-empty string")
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not math.isfinite(float(timeout_seconds))
            or timeout_seconds <= 0
        ):
            raise CommunicationProtocolError(
                "timeout_seconds must be a finite positive number"
            )
        if self._turn_id == turn_id:
            raise CommunicationProtocolError("turn_id has already been used")

        now = self._clock()
        self._turn_id = turn_id
        self._state = TurnState.RUNNING
        self._deadline = now + float(timeout_seconds)
        self._last_heartbeat = now
        self._error = None
        return self.snapshot()

    def heartbeat(self, turn_id: str) -> TurnSnapshot:
        """Record model activity without extending the original deadline."""
        self._require_running(turn_id)
        self._expire_if_needed()
        if self._state == TurnState.TIMED_OUT:
            return self.snapshot()
        self._last_heartbeat = self._clock()
        return self.snapshot()

    def complete(self, turn_id: str) -> TurnSnapshot:
        """Mark the active turn complete if it has not already timed out."""
        self._require_running(turn_id)
        self._expire_if_needed()
        if self._state == TurnState.TIMED_OUT:
            return self.snapshot()
        self._state = TurnState.COMPLETED
        return self.snapshot()

    def fail(self, turn_id: str, error: str) -> TurnSnapshot:
        """Terminate the active turn with an explicit failure reason."""
        self._require_running(turn_id)
        if not isinstance(error, str) or not error:
            raise CommunicationProtocolError("error must be a non-empty string")
        self._state = TurnState.FAILED
        self._error = error
        return self.snapshot()

    def timeout(self, turn_id: str, error: str = "model turn deadline exceeded") -> TurnSnapshot:
        """Explicitly terminate the active turn as timed out.

        Hosts use this when an underlying model process reports its own hard
        timeout before the supervisor clock is observed again.  This keeps a
        provider timeout represented as ``TIMED_OUT`` rather than incorrectly
        classifying it as a generic failure.
        """
        self._require_running(turn_id)
        if not isinstance(error, str) or not error:
            raise CommunicationProtocolError("error must be a non-empty string")
        self._state = TurnState.TIMED_OUT
        self._error = error
        return self.snapshot()

    def cancel(self, turn_id: str) -> TurnSnapshot:
        """Cancel the active turn without retrying or extending its deadline."""
        self._require_running(turn_id)
        self._state = TurnState.CANCELLED
        return self.snapshot()

    def poll(self) -> TurnSnapshot:
        """Refresh timeout state and return the current immutable snapshot."""
        self._expire_if_needed()
        return self.snapshot()

    def snapshot(self) -> TurnSnapshot:
        """Return the current immutable turn state."""
        return TurnSnapshot(
            turn_id=self._turn_id,
            state=self._state,
            deadline=self._deadline,
            last_heartbeat=self._last_heartbeat,
            error=self._error,
        )

    def _require_running(self, turn_id: str) -> None:
        if self._state != TurnState.RUNNING:
            if self._state in _TERMINAL_STATES:
                raise CommunicationProtocolError(
                    f"model turn is already {self._state.value}"
                )
            raise CommunicationProtocolError("no model turn is running")
        if turn_id != self._turn_id:
            raise CommunicationProtocolError("turn_id does not match the active model turn")

    def _expire_if_needed(self) -> None:
        if self._state != TurnState.RUNNING or self._deadline is None:
            return
        if self._clock() >= self._deadline:
            self._state = TurnState.TIMED_OUT
            self._error = "model turn deadline exceeded"
