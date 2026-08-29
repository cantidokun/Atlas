"""Fail-closed recovery helpers for the Atlas Blender controller."""

from copy import deepcopy
from typing import Any, Callable, Dict

from .controller_checkpoint import restore_controller_state, snapshot_controller_state
from .controller_state import ControllerState, record_after, required_moves

EvidenceReader = Callable[[str, str, str], Dict[str, Any]]


def checkpoint(state: ControllerState) -> Dict[str, Any]:
    """Return a detached checkpoint suitable for durable storage."""
    return snapshot_controller_state(state)


def recover_and_reconcile(payload: Dict[str, Any], read_evidence: EvidenceReader) -> ControllerState:
    """Restore history, discard historical completion, and reconcile fresh state."""
    state = restore_controller_state(payload)
    state.after = None
    state.write_retry_pending = False

    evidence = read_evidence(
        state.file_name,
        state.object_a_name,
        state.object_b_name,
    )
    if not isinstance(evidence, dict):
        raise RuntimeError("Fresh Blender evidence must be an object.")
    if evidence.get("error") or evidence.get("status") in {"error", "failed", "failure"} or evidence.get("ok") is False:
        raise RuntimeError("Fresh Blender evidence is unavailable.")

    if not state.writes:
        return state

    if required_moves(state):
        # A partial-write checkpoint remains incomplete. Fresh evidence is
        # useful only when it proves the recorded writes; otherwise leave the
        # state untouched and resume the normal write path.
        try:
            record_after(state, deepcopy(evidence))
        except ValueError:
            state.after = None
        else:
            state.after = None
        return state

    record_after(state, deepcopy(evidence))
    return state
