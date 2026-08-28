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
    if evidence.get("error") or evidence.get("status") in {"error", "failed", "failure"}:
        raise RuntimeError("Fresh Blender evidence is unavailable.")

    if not state.writes:
        # No successful write was recorded. Fresh evidence cannot manufacture
        # completion; leave the restored plan ready for its normal next action.
        return state

    if required_moves(state):
        # A checkpoint may represent an interrupted multi-write operation. Fresh
        # evidence can be useful, but it cannot close the task while writes remain
        # outstanding. The normal runtime will resume the missing writes.
        record_after(state, deepcopy(evidence))
        return state

    if not record_after(state, deepcopy(evidence)):
        raise ValueError("AFTER evidence does not prove the authorized target state.")
    return state
