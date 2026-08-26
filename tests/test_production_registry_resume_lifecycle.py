from action_plan import ActionSpec
from planning.digital_twin_identity import DigitalTwinIdentity
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.production_operation_lifecycle import ProductionOperationState
from planning.production_registry_resume_lifecycle import ProductionRegistryResumeLifecycle
from planning.production_task_checkpoint import ProductionTaskCheckpoint


def _registry_and_revision():
    identity = DigitalTwinIdentity(twin_id="twin-1", entity_type="soccer_field", anchors=())
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = DigitalTwinRevision(
        twin_id="twin-1",
        revision_id="r1",
        sequence=1,
        kind=RevisionKind.INITIAL,
        source_revision_id=None,
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(revision)
    return registry, revision


def _checkpoint(registry, revision):
    from planning.production_checkpoint_lifecycle import ProductionCheckpointLifecycle

    return ProductionCheckpointLifecycle(registry).create_checkpoint(
        "task-1",
        revision,
        (),
        {"revision": "r1", "location": [0, 0, 0]},
        "authorization-1",
    )


def _build(registry, revision, checkpoint, observed, verified):
    return ProductionRegistryResumeLifecycle(
        registry,
        checkpoint.snapshot(),
        revision,
        observe=lambda: observed,
        plan=lambda evidence: [
            ActionSpec(
                tool="move_object",
                arguments={"object_name": "Goal_Left_post", "location": [2, 0, 0]},
            )
        ],
        verify_final=lambda evidence: verified,
        executor=lambda action: {"ok": True, "state": "ok"},
    )


def test_registry_resume_rehydrates_and_completes_only_after_authoritative_verification():
    registry, revision = _registry_and_revision()
    checkpoint = _checkpoint(registry, revision)
    lifecycle = _build(
        registry,
        revision,
        checkpoint,
        {"revision": "r1", "location": [1, 0, 0]},
        True,
    )

    result = lifecycle.run()

    assert result.state is ProductionOperationState.COMPLETED
    assert result.completed is True


def test_registry_resume_blocks_when_authoritative_verification_rejects():
    registry, revision = _registry_and_revision()
    checkpoint = _checkpoint(registry, revision)
    lifecycle = _build(
        registry,
        revision,
        checkpoint,
        {"revision": "r1", "location": [1, 0, 0]},
        False,
    )

    result = lifecycle.run()

    assert result.state is ProductionOperationState.BLOCKED
    assert result.completed is False


def test_registry_resume_rejects_checkpoint_after_canonical_revision_advances():
    registry, revision = _registry_and_revision()
    checkpoint = _checkpoint(registry, revision)
    advanced = DigitalTwinRevision(
        twin_id="twin-1",
        revision_id="r2",
        sequence=2,
        kind=RevisionKind.CLEANUP,
        source_revision_id="r1",
        source_fingerprint=revision.source_fingerprint,
    )
    registry.register_revision(advanced)

    try:
        _build(
            registry,
            revision,
            checkpoint,
            {"revision": "r1", "location": [1, 0, 0]},
            True,
        )
    except ValueError as exc:
        assert "canonical" in str(exc).lower()
    else:
        raise AssertionError("stale checkpoint must be rejected")
