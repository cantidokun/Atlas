from planning.action_plan import ActionSpec
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_revision import RevisionKind, create_revision
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask


def _identity(twin_id="twin-soccer-1"):
    return DigitalTwinIdentity(
        twin_id=twin_id,
        entity_type="field",
        anchors=(
            IdentityAnchor("test", "anchor_a", "A"),
            IdentityAnchor("test", "anchor_b", "B"),
        ),
    )


def _revision(twin_id="twin-soccer-1"):
    return create_revision(_identity(twin_id), "r1", 1, RevisionKind.RECONSTRUCTION)


def _checkpoint(revision, evidence):
    action = ActionSpec(tool="move_object", arguments={"file_name": "scene.blend", "object_name": "Goal_Left_post", "location": [1, 2, 3]})
    return ProductionTaskCheckpoint.create(
        "task-1", revision, (action,), evidence, "authorization-lineage-1"
    )


def test_fresh_evidence_issues_new_resume_authorization():
    revision = _revision()
    checkpoint = _checkpoint(revision, {"revision": "r1", "location": [0, 0, 0]})
    task = DurableResumableCorrectiveTask(
        checkpoint,
        revision,
        lambda: {"revision": "r1", "location": [1, 0, 0]},
        lambda evidence: [ActionSpec(tool="move_object", arguments={"file_name": "scene.blend", "object_name": "Goal_Left_post", "location": [2, 0, 0]})],
    )
    authorization = task.issue_resume_authorization({"revision": "r1", "location": [1, 0, 0]})
    assert authorization.authorization_id != checkpoint.authorization_id


def test_stale_evidence_cannot_issue_resume_authorization():
    revision = _revision()
    evidence = {"revision": "r1", "location": [0, 0, 0]}
    checkpoint = _checkpoint(revision, evidence)
    task = DurableResumableCorrectiveTask(
        checkpoint, revision, lambda: evidence, lambda _: [ActionSpec(tool="move_object", arguments={"x": 1})]
    )
    try:
        task.issue_resume_authorization(evidence)
    except RuntimeError as exc:
        assert "fresh evidence" in str(exc)
    else:
        raise AssertionError("stale checkpoint evidence was accepted")


def test_checkpoint_must_match_canonical_revision():
    revision = _revision()
    other_revision = _revision("other")
    checkpoint = _checkpoint(revision, {"state": 1})
    try:
        DurableResumableCorrectiveTask(checkpoint, other_revision, lambda: {}, lambda _: [])
    except ValueError as exc:
        assert "different Digital Twin" in str(exc)
    else:
        raise AssertionError("checkpoint was accepted for a different Digital Twin")
