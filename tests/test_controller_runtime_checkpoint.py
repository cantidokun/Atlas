from controller.controller_runtime import ControllerRuntime
from controller.controller_state import record_before, record_write


def relationship(left=(8.0, 0.0, 0.0), right=(12.0, 0.0, 0.0)):
    return {"object_a": {"name": "Goal_Left_post", "location": list(left)}, "object_b": {"name": "Goal_Right_Post", "location": list(right)}, "midpoint": [(left[i] + right[i]) / 2 for i in range(3)]}


def test_runtime_checkpoint_round_trip():
    runtime = ControllerRuntime("scene.blend")
    record_before(runtime.state, relationship())
    record_write(runtime.state, "Goal_Left_post", [4.0, 0.0, 0.0], {"status": "moved"})

    restored = ControllerRuntime.from_checkpoint(runtime.checkpoint())

    assert restored.state.file_name == "scene.blend"
    assert restored.state.phase == "WRITE"
    assert restored.state.target == runtime.state.target
    assert restored.state.after is None


def test_runtime_restore_does_not_trust_historical_after():
    runtime = ControllerRuntime("scene.blend")
    record_before(runtime.state, relationship())
    record_write(runtime.state, "Goal_Left_post", [4.0, 0.0, 0.0], {"status": "moved"})
    record_write(runtime.state, "Goal_Right_Post", [8.0, 0.0, 0.0], {"status": "moved"})
    runtime.state.after = relationship(left=(4.0, 0.0, 0.0), right=(8.0, 0.0, 0.0))

    restored = ControllerRuntime.from_checkpoint(runtime.checkpoint())

    assert restored.state.after is None
    assert restored.state.phase == "WRITE"


def test_runtime_restore_with_fresh_evidence_reestablishes_reconciliation_without_false_completion():
    runtime = ControllerRuntime("scene.blend")
    record_before(runtime.state, relationship())
    record_write(runtime.state, "Goal_Left_post", [4.0, 0.0, 0.0], {"status": "moved"})
    record_write(runtime.state, "Goal_Right_Post", [8.0, 0.0, 0.0], {"status": "moved"})

    restored = ControllerRuntime.from_checkpoint(
        runtime.checkpoint(),
        fresh_evidence=relationship(left=(4.0, 0.0, 0.0), right=(8.0, 0.0, 0.0)),
    )

    assert restored.state.after is not None
    assert restored.state.recovery_reconciled
    assert not restored.state.complete
