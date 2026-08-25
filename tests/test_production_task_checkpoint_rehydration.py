from planning.action_plan import ActionSpec
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_revision import RevisionKind, create_revision
from planning.production_task_checkpoint import ProductionTaskCheckpoint


def _revision(twin_id="twin-1"):
    identity = DigitalTwinIdentity(
        twin_id=twin_id,
        entity_type="field",
        anchors=(
            IdentityAnchor("site", "stadium", "stadium-a"),
            IdentityAnchor("site", "field", "field-1"),
        ),
    )
    return create_revision(identity, "r1", 1, RevisionKind.RECONSTRUCTION)


def _checkpoint():
    action = ActionSpec(
        tool="move_object",
        arguments={"file_name": "scene.blend", "object_name": "Goal_Left_post", "location": [1, 2, 3]},
        name="move-goal",
    )
    evidence = {"file_name": "scene.blend", "object_name": "Goal_Left_post", "location": [1, 2, 3]}
    return ProductionTaskCheckpoint.create("task-1", _revision(), (action,), evidence, "lineage-1")


def test_checkpoint_round_trips_through_snapshot():
    checkpoint = _checkpoint()
    restored = ProductionTaskCheckpoint.from_snapshot(checkpoint.snapshot(), _revision())
    assert restored == checkpoint


def test_tampered_checkpoint_digest_is_rejected():
    checkpoint = _checkpoint()
    snapshot = checkpoint.snapshot()
    snapshot["authorization_id"] = "tampered"
    try:
        ProductionTaskCheckpoint.from_snapshot(snapshot, _revision())
    except ValueError as exc:
        assert "digest" in str(exc)
    else:
        raise AssertionError("tampered checkpoint was accepted")


def test_checkpoint_snapshot_cannot_cross_digital_twin_revision():
    checkpoint = _checkpoint()
    try:
        ProductionTaskCheckpoint.from_snapshot(checkpoint.snapshot(), _revision("twin-2"))
    except ValueError as exc:
        assert "different Digital Twin" in str(exc)
    else:
        raise AssertionError("checkpoint was accepted for a different Digital Twin")
