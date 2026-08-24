import pytest

from planning.unreal_agent import UnrealCapability, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_task_planner import UnrealTaskPlanner


def test_sequencer_playback_range_is_inspect_write_verify():
    plan = UnrealTaskPlanner().plan_sequencer_playback_range(
        UnrealTaskIntent("sequencer-1", "set production playback range", ("FIELD_SURFACE",)),
        10,
        120,
    )

    assert [operation.name for operation in plan.operations] == [
        "inspect_sequencer_state",
        "set_sequencer_playback_range",
        "verify_sequencer_playback_range",
    ]
    assert [operation.kind for operation in plan.operations] == [
        UnrealOperationKind.READ,
        UnrealOperationKind.WRITE,
        UnrealOperationKind.VERIFY,
    ]
    assert all(operation.capability is UnrealCapability.SEQUENCER for operation in plan.operations)
    assert plan.operations[1].arguments == {
        "entity_ids": ("FIELD_SURFACE",),
        "start_frame": 10,
        "end_frame": 120,
    }
    assert plan.operations[2].arguments == {
        "entity_ids": ("FIELD_SURFACE",),
        "expected_start_frame": 10,
        "expected_end_frame": 120,
    }


def test_sequencer_playback_range_rejects_reversed_range():
    with pytest.raises(ValueError, match="must not exceed"):
        UnrealTaskPlanner().plan_sequencer_playback_range(
            UnrealTaskIntent("sequencer-2", "set production playback range", ("FIELD_SURFACE",)),
            120,
            10,
        )


def test_sequencer_playback_range_rejects_non_integer_frames():
    with pytest.raises(TypeError, match="start_frame must be an integer"):
        UnrealTaskPlanner().plan_sequencer_playback_range(
            UnrealTaskIntent("sequencer-3", "set production playback range", ("FIELD_SURFACE",)),
            10.0,
            120,
        )


def test_sequencer_playback_range_requires_explicit_targets():
    with pytest.raises(ValueError):
        UnrealTaskPlanner().plan_sequencer_playback_range(
            UnrealTaskIntent("sequencer-4", "set production playback range", ()),
            10,
            120,
        )
