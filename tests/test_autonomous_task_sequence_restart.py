"""Restart-boundary regression coverage for autonomous task sequencing."""

import pytest

from planning.autonomous_task_sequence import (
    AutonomousTaskSequence,
    AutonomousTaskSequenceCheckpoint,
    AutonomousTaskStep,
)
from planning.production_operation_lifecycle import ProductionOperationLifecycle


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

    def operation(name: str) -> ProductionOperationLifecycle:
        return ProductionOperationLifecycle(name=name)

    with pytest.raises(ValueError, match="checkpoint step identity"):
        AutonomousTaskSequence.from_checkpoint(
            (
                AutonomousTaskStep("create", operation("create")),
                AutonomousTaskStep("delete", operation("delete")),
            ),
            restored,
        )


def test_sequence_checkpoint_rejects_out_of_range_resume_position():
    checkpoint = AutonomousTaskSequenceCheckpoint("shot-001", ("create", "move"), 2)
    snapshot = checkpoint.snapshot()
    snapshot["next_step_index"] = 3

    with pytest.raises(ValueError, match="outside"):
        AutonomousTaskSequenceCheckpoint.from_snapshot(snapshot)
