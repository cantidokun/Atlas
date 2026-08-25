from action_plan import ActionSpec
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_revision import RevisionKind, create_revision
from planning.production_task_checkpoint import ProductionTaskCheckpoint


def _revision():
    identity = DigitalTwinIdentity(
        twin_id="twin:field-001",
        entity_type="soccer_field",
        anchors=(IdentityAnchor("venue", "id", "field-001"),),
    )
    return create_revision(identity, "rev:001", 1, RevisionKind.RECONSTRUCTION)


def _action():
    return ActionSpec(
        tool="move_object",
        arguments={"file_name": "scene.blend", "object_name": "Goal_Left_post", "location": [1, 2, 3]},
    )


def test_checkpoint_is_bound_to_twin_revision_and_evidence():
    evidence = {"revision": "rev:001", "location": [0, 0, 0]}
    checkpoint = ProductionTaskCheckpoint.create(
        "task:001", _revision(), (_action(),), evidence, "auth:001"
    )
    assert checkpoint.twin_id == "twin:field-001"
    assert checkpoint.revision_id == "rev:001"
    assert checkpoint.matches_evidence(evidence)
    assert not checkpoint.matches_evidence({"revision": "rev:001", "location": [9, 9, 9]})


def test_checkpoint_snapshot_preserves_audit_chain():
    checkpoint = ProductionTaskCheckpoint.create(
        "task:001", _revision(), (_action(),), {"state": "observed"}, "auth:001", "parent:digest"
    )
    snapshot = checkpoint.snapshot()
    assert snapshot["checkpoint_digest"] == checkpoint.checkpoint_digest
    assert snapshot["parent_checkpoint_digest"] == "parent:digest"
    assert snapshot["completed_actions"][0]["tool"] == "move_object"
