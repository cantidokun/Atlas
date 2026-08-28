"""Serializable checkpoints for deterministic Blender controller recovery."""

from copy import deepcopy
from typing import Any, Dict

from controller_state import ControllerState, after_matches_target, required_moves

CHECKPOINT_VERSION = 1


def snapshot_controller_state(state: ControllerState) -> Dict[str, Any]:
    return {
        "version": CHECKPOINT_VERSION,
        "file_name": state.file_name,
        "object_a_name": state.object_a_name,
        "object_b_name": state.object_b_name,
        "before": deepcopy(state.before),
        "target": deepcopy(state.target),
        "writes": deepcopy(state.writes),
        "after": deepcopy(state.after),
    }


def restore_controller_state(payload: Dict[str, Any]) -> ControllerState:
    if not isinstance(payload, dict) or payload.get("version") != CHECKPOINT_VERSION:
        raise ValueError("Unsupported or invalid controller checkpoint.")
    for key in ("file_name", "object_a_name", "object_b_name"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ValueError(f"Controller checkpoint is missing {key}.")

    state = ControllerState(
        file_name=payload["file_name"],
        object_a_name=payload["object_a_name"],
        object_b_name=payload["object_b_name"],
        before=deepcopy(payload.get("before")),
        target=deepcopy(payload.get("target")),
        writes=deepcopy(payload.get("writes", [])),
        after=deepcopy(payload.get("after")),
    )
    if not isinstance(state.writes, list):
        raise ValueError("Controller checkpoint writes must be a list.")
    if state.before is None and (state.target is not None or state.writes or state.after is not None):
        raise ValueError("Controller checkpoint contains progress without BEFORE evidence.")
    if state.before is not None and state.target is None:
        raise ValueError("Controller checkpoint is missing its derived target.")
    if state.after is not None and (required_moves(state) or not after_matches_target(state)):
        raise ValueError("Controller checkpoint contains unverifiable AFTER evidence.")
    return state
