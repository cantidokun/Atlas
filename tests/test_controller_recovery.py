import pytest

from controller.controller_checkpoint import snapshot_controller_state
from controller.controller_recovery import recover_and_reconcile
from controller.controller_state import ControllerState, record_before, record_write


def relationship(left=(-2.0, 0.0, 0.0), right=(2.0, 0.0, 0.0)):
    return {"object_a": {"name": "Goal_Left_post", "location": list(left)}, "object_b": {"name": "Goal_Right_Post", "location": list(right)}, "midpoint": [(left[i] + right[i]) / 2 for i in range(3)]}


def test_recovery_reconciles_fresh_evidence_against_recorded_writes():
    state = ControllerState("scene.blend", "Goal_Left_post", "Goal_Right_Post")
    record_before(state, relationship(left=(8.0, 0.0, 0.0), right=(12.0, 0.0, 0.0)))
    record_write(state, "Goal_Left_post", [4.0, 0.0, 0.0], {"status": "moved"})
    payload = snapshot_controller_state(state)

    recovered = recover_and_reconcile(payload, lambda *_: relationship(left=(4.0, 0.0, 0.0), right=(8.0, 0.0, 0.0)))

    assert recovered.after is not None
    assert recovered.recovery_reconciled
    assert not recovered.complete


def test_recovery_rejects_stale_scene_evidence():
    state = ControllerState("scene.blend", "Goal_Left_post", "Goal_Right_Post")
    record_before(state, relationship(left=(8.0, 0.0, 0.0), right=(12.0, 0.0, 0.0)))
    record_write(state, "Goal_Left_post", [4.0, 0.0, 0.0], {"status": "moved"})
    record_write(state, "Goal_Right_Post", [8.0, 0.0, 0.0], {"status": "moved"})
    payload = snapshot_controller_state(state)

    with pytest.raises(ValueError, match="AFTER evidence"):
        recover_and_reconcile(payload, lambda *_: relationship(left=(5.0, 0.0, 0.0), right=(9.0, 0.0, 0.0)))
