from action_plan import ActionSpec
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.production_checkpoint_lifecycle import ProductionCheckpointLifecycle


def _registry():
    identity = DigitalTwinIdentity("twin-1", "soccer-field", (IdentityAnchor("field", "venue", "v1"),))
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = DigitalTwinRevision(
        "twin-1", "r1", 1, RevisionKind.RECONSTRUCTION,
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(revision)
    return registry, identity, revision


def test_checkpoint_creation_requires_current_canonical_revision():
    registry, identity, revision = _registry()
    lifecycle = ProductionCheckpointLifecycle(registry)
    checkpoint = lifecycle.create_checkpoint(
        "task-1", revision, (), {"revision": "r1"}, "auth-1"
    )
    assert checkpoint.revision_id == "r1"


def test_checkpoint_serialization_rejects_after_canonical_revision_advances():
    registry, identity, revision = _registry()
    lifecycle = ProductionCheckpointLifecycle(registry)
    checkpoint = lifecycle.create_checkpoint(
        "task-1", revision, (), {"revision": "r1"}, "auth-1"
    )
    revision2 = DigitalTwinRevision(
        "twin-1", "r2", 2, RevisionKind.CLEANUP,
        source_revision_id="r1", source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(revision2)
    try:
        lifecycle.serialize_checkpoint(checkpoint)
    except ValueError as exc:
        assert "current canonical" in str(exc)
    else:
        raise AssertionError("stale checkpoint was serialized after canonical revision advanced")


def test_rehydration_requires_current_canonical_revision_before_digest_validation():
    registry, identity, revision = _registry()
    lifecycle = ProductionCheckpointLifecycle(registry)
    checkpoint = lifecycle.create_checkpoint(
        "task-1", revision,
        (ActionSpec("move_object", {"file_name": "scene.blend", "object_name": "Goal_Left_post", "location": [1, 0, 0]}),),
        {"revision": "r1"}, "auth-1"
    )
    snapshot = checkpoint.snapshot()
    revision2 = DigitalTwinRevision(
        "twin-1", "r2", 2, RevisionKind.CLEANUP,
        source_revision_id="r1", source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(revision2)
    try:
        lifecycle.rehydrate_checkpoint(snapshot, revision)
    except ValueError as exc:
        assert "current canonical" in str(exc)
    else:
        raise AssertionError("stale checkpoint was rehydrated")


def test_rehydration_of_current_checkpoint_preserves_checkpoint_integrity():
    registry, _, revision = _registry()
    lifecycle = ProductionCheckpointLifecycle(registry)
    checkpoint = lifecycle.create_checkpoint(
        "task-1", revision, (), {"revision": "r1"}, "auth-1"
    )
    restored = lifecycle.rehydrate_checkpoint(checkpoint.snapshot(), revision)
    assert restored.checkpoint_digest == checkpoint.checkpoint_digest
    assert restored.authorization_id == checkpoint.authorization_id
