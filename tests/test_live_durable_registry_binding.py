from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import RevisionKind, create_revision
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
from action_plan import ActionSpec


def _registry():
    identity = DigitalTwinIdentity("twin-1", "soccer-field", (IdentityAnchor("field", "venue", "v1"),))
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = create_revision(identity, "r1", 1, RevisionKind.RECONSTRUCTION)
    registry.register_revision(revision)
    return registry, identity, revision


def _checkpoint(revision):
    return ProductionTaskCheckpoint.create("task-1", revision, (), {"revision": revision.revision_id, "location": [0, 0, 0]}, "auth-1")


def _task(checkpoint, revision, registry):
    return DurableResumableCorrectiveTask(
        checkpoint, revision,
        lambda: {"revision": revision.revision_id, "location": [1, 0, 0]},
        lambda evidence: [ActionSpec("move_object", {"file_name": "scene.blend", "object_name": "Goal_Left_post", "location": [2, 0, 0]})],
        registry=registry,
    )


def test_rehydrated_registry_accepts_matching_checkpoint_revision():
    registry, _, revision = _registry()
    reloaded = DigitalTwinRegistry.from_snapshot(registry.snapshot())
    task = _task(_checkpoint(revision), revision, reloaded)
    assert task.registry is reloaded


def test_advanced_canonical_revision_rejects_checkpoint_before_resume():
    registry, identity, revision = _registry()
    checkpoint = _checkpoint(revision)
    advanced = create_revision(identity, "r2", 2, RevisionKind.CLEANUP, source_revision=revision)
    registry.register_revision(advanced)
    try:
        _task(checkpoint, revision, registry)
    except ValueError as exc:
        assert "current canonical" in str(exc)
    else:
        raise AssertionError("stale checkpoint crossed the canonical revision boundary")


def test_registry_snapshot_tampering_cannot_cross_resume_boundary():
    registry, _, _ = _registry()
    snapshot = registry.snapshot()
    snapshot["revisions"]["twin-1"][0]["revision_id"] = "tampered"
    try:
        DigitalTwinRegistry.from_snapshot(snapshot)
    except ValueError as exc:
        assert "digest" in str(exc)
    else:
        raise AssertionError("tampered registry snapshot was accepted")
