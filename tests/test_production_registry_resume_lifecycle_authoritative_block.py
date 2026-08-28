from __future__ import annotations

from action_plan import ActionSpec
from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.production_completion_receipt import ProductionCompletionReceipt
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
    state = {"value": "old"}
    writes = []

    def observe():
        return dict(state)

    def plan(evidence):
        if evidence["value"] == "new":
            return []
        return [ActionSpec("test.move", {"target": "new"})]

    def executor(tool, arguments):
        writes.append((tool, arguments))
        return {
            "ok": True,
            "state": {"value": "new"},
            "details": {"executor": "accepted"},
        }

    lifecycle = ProductionRegistryResumeLifecycle.from_registry_snapshot(
        registry.snapshot(),
        _checkpoint_snapshot(revision),
        revision,
        observe=observe,
        plan=plan,
        verify_final=lambda _evidence: False,
        executor=executor,
    )

    # Executor reports success, but authoritative verification deliberately rejects.
    def fake_resume(max_steps=16):
        result = lifecycle.task.resume(max_steps=max_steps)
        state["value"] = "new"
        return CorrectiveTaskResult(result.receipts, {"authoritative": "wrong"}, True)

    lifecycle.task.resume = fake_resume
    result = lifecycle.run()

    assert result.state is ProductionOperationState.BLOCKED
    assert result.receipt is None
    assert not lifecycle.lifecycle.receipt
    assert isinstance(writes, list)
    assert len(writes) == 1
