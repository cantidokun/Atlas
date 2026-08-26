from dataclasses import replace

import pytest

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


def _checkpoint(lifecycle, revision, task_id="task-1", authorization_id="auth-1", parent=None):
    return lifecycle.create_checkpoint(
        task_id,
        revision,
        (),
        {"revision": revision.revision_id},
        authorization_id,
        parent_checkpoint=parent,
    )


def test_checkpoint_creation_requires_current_canonical_revision():
    registry, _, revision = _registry()
    lifecycle = ProductionCheckpointLifecycle(registry)
    checkpoint = _checkpoint(lifecycle, revision)
    assert checkpoint.revision_id == "r1"


def test_checkpoint_serialization_rejects_after_canonical_revision_advances():
    registry, identity, revision = _registry()
    lifecycle = ProductionCheckpointLifecycle(registry)
    checkpoint = _checkpoint(lifecycle, revision)
    revision2 = DigitalTwinRevision(
        "twin-1", "r2", 2, RevisionKind.CLEANUP,
        source_revision_id="r1", source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(revision2)
    with pytest.raises(ValueError, match="current canonical"):
        lifecycle.serialize_checkpoint(checkpoint)


def test_serialization_rejects_tampered_in_memory_checkpoint():
    registry, _, revision = _registry()
    lifecycle = ProductionCheckpointLifecycle(registry)
    checkpoint = _checkpoint(lifecycle, revision)
    tampered = replace(checkpoint, authorization_id="forged-auth")
    with pytest.raises(ValueError, match="integrity|digest"):
        lifecycle.serialize_checkpoint(tampered)


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
    with pytest.raises(ValueError, match="current canonical"):
        lifecycle.rehydrate_checkpoint(snapshot, revision)


def test_rehydration_of_current_checkpoint_preserves_checkpoint_integrity():
    registry, _, revision = _registry()
    lifecycle = ProductionCheckpointLifecycle(registry)
    checkpoint = _checkpoint(lifecycle, revision)
    restored = lifecycle.rehydrate_checkpoint(checkpoint.snapshot(), revision)
    assert restored.checkpoint_digest == checkpoint.checkpoint_digest
    assert restored.authorization_id == checkpoint.authorization_id


def test_validate_checkpoint_rejects_stale_revision_before_integrity_validation():
    registry, identity, revision = _registry()
    lifecycle = ProductionCheckpointLifecycle(registry)
    checkpoint = _checkpoint(lifecycle, revision)
    revision2 = DigitalTwinRevision(
        "twin-1", "r2", 2, RevisionKind.CLEANUP,
        source_revision_id="r1", source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(revision2)
    with pytest.raises(ValueError, match="current canonical"):
        lifecycle.validate_checkpoint(checkpoint, revision)


def test_validate_checkpoint_preserves_immutable_checkpoint_identity():
    registry, _, revision = _registry()
    lifecycle = ProductionCheckpointLifecycle(registry)
    checkpoint = _checkpoint(lifecycle, revision)
    restored = lifecycle.validate_checkpoint(checkpoint, revision)
    assert restored is not checkpoint
    assert restored.checkpoint_digest == checkpoint.checkpoint_digest
    assert restored.authorization_id == checkpoint.authorization_id


def test_valid_parent_checkpoint_establishes_lineage():
    registry, _, revision = _registry()
    lifecycle = ProductionCheckpointLifecycle(registry)
    parent = _checkpoint(lifecycle, revision, task_id="task-1", authorization_id="auth-parent")
    child = _checkpoint(lifecycle, revision, task_id="task-1", authorization_id="auth-child", parent=parent)
    assert child.parent_checkpoint_digest == parent.checkpoint_digest
    validated = lifecycle.validate_checkpoint(child, revision, parent_checkpoint=parent)
    assert validated.checkpoint_digest == child.checkpoint_digest


def test_wrong_parent_checkpoint_is_rejected():
    registry, _, revision = _registry()
    lifecycle = ProductionCheckpointLifecycle(registry)
    parent = _checkpoint(lifecycle, revision, authorization_id="auth-parent")
    wrong_parent = _checkpoint(lifecycle, revision, authorization_id="auth-wrong")
    child = _checkpoint(lifecycle, revision, authorization_id="auth-child", parent=parent)
    with pytest.raises(ValueError, match="parent checkpoint does not match"):
        lifecycle.validate_checkpoint(child, revision, parent_checkpoint=wrong_parent)


def test_cross_twin_parent_checkpoint_is_rejected():
    registry, identity, revision = _registry()
    lifecycle = ProductionCheckpointLifecycle(registry)
    parent = _checkpoint(lifecycle, revision, authorization_id="auth-parent")
    other_identity = DigitalTwinIdentity("twin-2", "soccer-field", (IdentityAnchor("field", "venue", "v2"),))
    registry.register_identity(other_identity)
    other_revision = DigitalTwinRevision(
        "twin-2", "r1", 1, RevisionKind.RECONSTRUCTION,
        source_fingerprint=other_identity.stable_fingerprint(),
    )
    registry.register_revision(other_revision)
    other_lifecycle = ProductionCheckpointLifecycle(registry)
    other_parent = _checkpoint(other_lifecycle, other_revision, task_id="task-1", authorization_id="auth-other")
    child = _checkpoint(lifecycle, revision, authorization_id="auth-child", parent=parent)
    with pytest.raises(ValueError, match="different Digital Twin"):
        lifecycle.validate_checkpoint(child, revision, parent_checkpoint=other_parent)


def test_cross_revision_parent_checkpoint_is_rejected():
    registry, identity, revision = _registry()
    lifecycle = ProductionCheckpointLifecycle(registry)
    parent = _checkpoint(lifecycle, revision, authorization_id="auth-parent")
    revision2 = DigitalTwinRevision(
        "twin-1", "r2", 2, RevisionKind.CLEANUP,
        source_revision_id="r1", source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(revision2)
    child = lifecycle.create_checkpoint(
        "task-1", revision2, (), {"revision": "r2"}, "auth-child", parent_checkpoint=parent
    )
    with pytest.raises(ValueError, match="current canonical"):
        lifecycle.validate_checkpoint(child, revision2, parent_checkpoint=parent)


def test_arbitrary_parent_digest_cannot_establish_lineage():
    registry, _, revision = _registry()
    lifecycle = ProductionCheckpointLifecycle(registry)
    with pytest.raises(ValueError, match="parent checkpoint object"):
        lifecycle.create_checkpoint(
            "task-1", revision, (), {"revision": "r1"}, "auth-child",
            parent_checkpoint_digest="forged-parent-digest",
        )
