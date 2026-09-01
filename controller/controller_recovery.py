"""Fail-closed recovery helpers for the Atlas Blender controller."""

from copy import deepcopy
from typing import Any, Callable, Dict

from .controller_checkpoint import restore_controller_state, snapshot_controller_state
from .controller_state import ControllerState, record_reconciled_after

EvidenceReader = Callable[[str, str, str], Dict[str, Any]]


def checkpoint(state: ControllerState) -> Dict[str, Any]:
    """Return a detached checkpoint suitable for durable storage."""
    return snapshot_controller_state(state)


def recover_and_reconcile(payload: Dict[str, Any], read_evidence: EvidenceReader) -> ControllerState:
    """Restore history, discard historical completion, and reconcile fresh state."""
    state = restore_controller_state(payload)
    state.after = None
    state.write_retry_pending = False
    state.recovery_reconciled = False

    evidence = read_evidence(state.file_name, state.object_a_name, state.object_b_name)
    if not isinstance(evidence, dict):
        raise RuntimeError("Fresh Blender evidence must be an object.")
    if evidence.get("error") or evidence.get("status") in {"error", "failed", "failure"} or evidence.get("ok") is False:
        raise RuntimeError("Fresh Blender evidence is unavailable.")

    if not state.writes:
        return state

    if state.writes:
        try:
            record_reconciled_after(state, deepcopy(evidence))
        except ValueError:
            if not state.writes:
                raise
            state.after = None
            state.recovery_reconciled = False
            if len(state.writes) < 2:
                return state
            raise
    return state
