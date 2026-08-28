"""Fail-closed recovery helpers for the Atlas Blender controller."""

from copy import deepcopy
from typing import Any, Callable, Dict

from controller_checkpoint import restore_controller_state, snapshot_controller_state
from controller_state import ControllerState

EvidenceReader = Callable[[str, str, str], Dict[str, Any]]


def checkpoint(state: ControllerState) -> Dict[str, Any]:
    """Return a detached checkpoint suitable for durable storage."""
    return snapshot_controller_state(state)


def recover_and_reconcile(payload: Dict[str, Any], read_evidence: EvidenceReader) -> ControllerState:
    """Restore controller history, then reconcile it against fresh Blender evidence.

    Historical AFTER evidence is never trusted as proof of current Blender state.
    Recovery therefore clears stale AFTER state and requires a fresh verification
    read before the controller can declare completion.
    """
    state = restore_controller_state(payload)
    state.after = None

    evidence = read_evidence(
        state.file_name,
        state.object_a_name,
        state.object_b_name,
    )
    if not isinstance(evidence, dict):
        raise RuntimeError("Fresh Blender evidence must be an object.")
    if evidence.get("error") or evidence.get("status") in {"error", "failed", "failure"}:
        raise RuntimeError("Fresh Blender evidence is unavailable.")

    # A fresh read is intentionally retained only as verification input. It must
    # pass through the same state validator used by normal completion.
    from controller_state import record_after
    if not state.writes:
        return state
    record_after(state, deepcopy(evidence))
    return state
