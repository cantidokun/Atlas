"""Restart-boundary regression coverage for autonomous task sequencing."""

import json
from unittest.mock import MagicMock

import pytest

from planning.autonomous_task_sequence import (
    AutonomousTaskSequence,
    AutonomousTaskSequenceCheckpoint,
    AutonomousTaskStep,
)
from planning.production_operation_lifecycle import (
    ProductionOperationLifecycle,
    ProductionOperationResult,
    ProductionOperationState,
)


def test_sequence_checkpoint_round_trips_json_native_state():
    checkpoint = AutonomousTaskSequenceCheckpoint(
        "shot-001",
        ("create_collection", "move_object", "verify_render"),
        2,
    )

    restored = AutonomousTaskSequenceCheckpoint.from_snapshot(checkpoint.snapshot())

    assert restored == checkpoint
    assert restored.step_names == ("create_collection", "move_object", "verify_render")
    assert restored.next_step_index == 2


def test_sequence_checkpoint_rejects_changed_step_identity():
    checkpoint = AutonomousTaskSequenceCheckpoint("shot-001", ("create", "move"), 1)
    restored = AutonomousTaskSequenceCheckpoint.from_snapshot(checkpoint.snapshot())

    def operation() -> ProductionOperationLifecycle:
        return MagicMock(spec=ProductionOperationLifecycle)

    with pytest.raises(ValueError, match="checkpoint step identity"):
        AutonomousTaskSequence.from_checkpoint(
            (
                AutonomousTaskStep("create", operation()),
                AutonomousTaskStep("delete", operation()),
            ),
            restored,
        )


def test_sequence_checkpoint_rejects_out_of_range_resume_position():
    checkpoint = AutonomousTaskSequenceCheckpoint("shot-001", ("create", "move"), 2)
    snapshot = checkpoint.snapshot()
    snapshot["next_step_index"] = 3

    with pytest.raises(ValueError, match="outside"):
        AutonomousTaskSequenceCheckpoint.from_snapshot(snapshot)


def test_sequence_resumes_after_json_process_boundary_without_replaying_completed_step():
    first_operation = MagicMock(spec=ProductionOperationLifecycle)
    second_operation = MagicMock(spec=ProductionOperationLifecycle)
    first_operation.run.return_value = MagicMock()
    second_operation.run.return_value = ProductionOperationResult(
        state=ProductionOperationState.COMPLETED,
        task_result=MagicMock(),
        reason="authoritative verification accepted final evidence",
        receipt=MagicMock(),
    )

    original = AutonomousTaskSequence(
        (
            AutonomousTaskStep("create", first_operation),
            AutonomousTaskStep("move", second_operation),
        ),
        sequence_id="shot-001",
    )
    original.next_step_index = 1

    # Simulate the actual process boundary: only JSON-native checkpoint state
    # crosses from the first runtime into a fresh runtime.
    persisted = json.loads(json.dumps(original.checkpoint().snapshot()))
    restored_checkpoint = AutonomousTaskSequenceCheckpoint.from_snapshot(persisted)

    resumed = AutonomousTaskSequence.from_checkpoint(
        (
            AutonomousTaskStep("create", first_operation),
            AutonomousTaskStep("move", second_operation),
        ),
        restored_checkpoint,
    )
    result = resumed.run()

    assert result.completed
    assert result.completed_steps == ("create", "move")
    assert result.next_step_index == 2
    first_operation.run.assert_not_called()
    second_operation.run.assert_called_once()
