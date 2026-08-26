from action_plan import ActionSpec
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask


def _registry():
    identity = DigitalTwinIdentity("twin-1", "soccer-field", (IdentityAnchor("field", "venue", "v1"),))
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = DigitalTwinRevision("twin-1", "r1", 1, RevisionKind.RECONSTRUCTION, source_fingerprint=identity.stable_fingerprint())
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


def test_matching_canonical_revision_allows_durable_rehydration_boundary():
    registry, _, revision = _registry()
    task = _task(_checkpoint(revision), revision, registry)
    assert task.registry is registry


def test_checkpoint_from_older_revision_is_rejected_when_canonical_revision_advanced():
    registry, identity, revision = _registry()
    revision2 = DigitalTwinRevision("twin-1", "r2", 2, RevisionKind.CLEANUP, source_revision_id="r1", source_fingerprint=identity.stable_fingerprint())
    registry.register_revision(revision2)
    try:
        _task(_checkpoint(revision), revision, registry)
    except ValueError as exc:
        assert "current canonical" in str(exc)
    else:
        raise AssertionError("stale canonical revision was accepted")


def test_registry_reload_preserves_canonical_revision_binding():
    registry, _, revision = _registry()
    reloaded = DigitalTwinRegistry.from_snapshot(registry.snapshot())
    reloaded_revision = reloaded.canonical_revision(revision.twin_id)
    assert reloaded_revision.revision_id == revision.revision_id
    _task(_checkpoint(revision), reloaded_revision, reloaded)


def test_registry_advance_during_planning_is_rejected_before_resume_authorization():
    registry, identity, revision = _registry()
    checkpoint = _checkpoint(revision)
    advanced = DigitalTwinRevision(
        "twin-1", "r2", 2, RevisionKind.CLEANUP,
        source_revision_id="r1", source_fingerprint=identity.stable_fingerprint(),
    )
    calls = {"count": 0}

    def plan(evidence):
        calls["count"] += 1
        if calls["count"] == 1:
            registry.register_revision(advanced)
        return [ActionSpec("move_object", {
            "file_name": "scene.blend",
            "object_name": "Goal_Left_post",
            "location": [2, 0, 0],
        })]

    task = DurableResumableCorrectiveTask(
        checkpoint,
        revision,
        lambda: {"revision": revision.revision_id, "location": [1, 0, 0]},
        plan,
        registry=registry,
    )
    try:
        task.issue_resume_authorization({"revision": revision.revision_id, "location": [1, 0, 0]})
    except ValueError as exc:
        assert "current canonical" in str(exc)
    else:
        raise AssertionError("canonical revision advanced during planning but authorization was issued")
