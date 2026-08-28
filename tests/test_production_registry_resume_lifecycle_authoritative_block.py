from __future__ import annotations

from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.production_operation_lifecycle import ProductionOperationState
from planning.production_registry_resume_lifecycle import ProductionRegistryResumeLifecycle
from planning.production_task_checkpoint import ProductionTaskCheckpoint


def _registry_and_revision():
    identity = DigitalTwinIdentity(
        twin_id="block-twin",
        entity_type="reconstruction",
        anchors=(IdentityAnchor("scene", "source", "scene-1"),),
    )
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = DigitalTwinRevision(
        twin_id="block-twin",
        revision_id="r1",
        sequence=1,
        kind=RevisionKind.RECONSTRUCTION,
        source_revision_id=None,
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(revision)
    return registry, revision


def _checkpoint_snapshot(revision):
    return ProductionTaskCheckpoint.create(
        "task-block", revision, (), {"checkpoint": True}, "authorization-1"
    ).snapshot()


def test_registry_resume_blocks_on_wrong_authoritative_state_without_completion_receipt():
    registry, revision = _registry_and_revision()
    task_result = CorrectiveTaskResult(
        receipts=(object(),),
        final_evidence={"authoritative": "wrong"},
        converged=True,
    )

    lifecycle = ProductionRegistryResumeLifecycle.from_registry_snapshot(
        registry.snapshot(),
        _checkpoint_snapshot(revision),
        revision,
        observe=lambda: {"fresh": True},
        plan=lambda _: [],
        verify_final=lambda _evidence: False,
    )
    lifecycle.task.resume = lambda max_steps=16: task_result

    terminal = lifecycle.run(max_steps=1)

    assert terminal.state is ProductionOperationState.BLOCKED
    assert terminal.receipt is None
    assert lifecycle.lifecycle.receipt is None
