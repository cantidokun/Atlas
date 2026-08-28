import pytest

from controller.controller_checkpoint import restore_controller_state, snapshot_controller_state
from controller.controller_state import ControllerState, record_before


def _relationship(left=(-2.0, 0.0, 0.0), right=(2.0, 0.0, 0.0)):
    return {
        "object_a": {"name": "Goal_Left_post", "location": list(left)},
        "object_b": {"name": "Goal_Right_Post", "location": list(right)},
        "midpoint": [(left[i] + right[i]) / 2 for i in range(3)],
    }


def test_checkpoint_round_trip_preserves_next_required_work():
    state = ControllerState("scene.blend", "Goal_Left_post", "Goal_Right_Post")
    record_before(state, _relationship(left=(8.0, 0.0, 0.0), right=(12.0, 0.0, 0.0)))

    restored = restore_controller_state(snapshot_controller_state(state))

    assert restored.file_name == state.file_name
    assert restored.target == state.target
    assert restored.before == state.before
    assert restored is not state


def test_checkpoint_snapshot_is_detached_from_live_state():
    state = ControllerState("scene.blend", "Goal_Left_post", "Goal_Right_Post")
    record_before(state, _relationship())
    payload = snapshot_controller_state(state)

    payload["before"]["object_a"]["location"][0] = 999

    assert state.before["object_a"]["location"][0] == -2.0


def test_progress_without_before_evidence_is_rejected():
    payload = {
        "version": 1,
        "file_name": "scene.blend",
        "object_a_name": "Goal_Left_post",
        "object_b_name": "Goal_Right_Post",
        "before": None,
        "target": {"midpoint": [0, 0, 0]},
        "writes": [],
        "after": None,
    }

    with pytest.raises(ValueError, match="without BEFORE"):
        restore_controller_state(payload)


def test_unverifiable_after_checkpoint_is_rejected():
    state = ControllerState("scene.blend", "Goal_Left_post", "Goal_Right_Post")
    record_before(state, _relationship())
    payload = snapshot_controller_state(state)
    payload["after"] = _relationship(left=(-3.0, 0.0, 0.0), right=(3.0, 0.0, 0.0))

    with pytest.raises(ValueError, match="unverifiable AFTER"):
        restore_controller_state(payload)
