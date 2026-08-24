import pytest

from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_capability_registry import UnrealCapabilityRegistry
from planning.unreal_task_planner import UnrealTaskPlanner


ENTITY_ID = "SHOT_SEQUENCE"


def _intent():
    return UnrealTaskIntent(
        intent_id="sequencer-playback-range",
        description="Set the approved playback range for the shot sequence.",
        target_entity_ids=(ENTITY_ID,),
    )


def test_sequencer_registry_accepts_read_write_and_verify_contracts():
    registry = UnrealCapabilityRegistry()
    registry.validate(UnrealCapability.SEQUENCER, UnrealOperationKind.READ)
    registry.validate(UnrealCapability.SEQUENCER, UnrealOperationKind.WRITE)
    registry.validate(UnrealCapability.SEQUENCER, UnrealOperationKind.VERIFY)

    read = UnrealOperation(
        UnrealCapability.SEQUENCER,
        UnrealOperationKind.READ,
        "inspect_sequencer_state",
        {"entity_ids": (ENTITY_ID,)},
        (ENTITY_ID,),
    )
    write = UnrealOperation(
        UnrealCapability.SEQUENCER,
        UnrealOperationKind.WRITE,
        "set_sequencer_playback_range",
        {"entity_ids": (ENTITY_ID,), "start_frame": 100, "end_frame": 240},
        (ENTITY_ID,),
    )
    verify = UnrealOperation(
        UnrealCapability.SEQUENCER,
        UnrealOperationKind.VERIFY,
        "verify_sequencer_playback_range",
        {"entity_ids": (ENTITY_ID,), "expected_start_frame": 100, "expected_end_frame": 240},
        (ENTITY_ID,),
    )

    assert registry.validate_operation(read) is read
    assert registry.validate_operation(write) is write
    assert registry.validate_operation(verify) is verify


def test_sequencer_planner_emits_read_write_verify_sequence():
    plan = UnrealTaskPlanner().plan_sequencer_playback_range(_intent(), 100, 240)

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
        "entity_ids": (ENTITY_ID,),
        "start_frame": 100,
        "end_frame": 240,
    }
    assert plan.operations[2].arguments == {
        "entity_ids": (ENTITY_ID,),
        "expected_start_frame": 100,
        "expected_end_frame": 240,
    }


@pytest.mark.parametrize(
    "start_frame,end_frame,error",
    [
        (240, 100, "start_frame must not exceed end_frame"),
        (1.5, 20, "start_frame must be an integer"),
        (1, 20.5, "end_frame must be an integer"),
        (True, 20, "start_frame must be an integer"),
    ],
)
def test_sequencer_planner_rejects_invalid_frame_ranges(start_frame, end_frame, error):
    with pytest.raises((TypeError, ValueError), match=error):
        UnrealTaskPlanner().plan_sequencer_playback_range(_intent(), start_frame, end_frame)


def test_sequencer_registry_rejects_malformed_verify_payload():
    operation = UnrealOperation(
        UnrealCapability.SEQUENCER,
        UnrealOperationKind.VERIFY,
        "verify_sequencer_playback_range",
        {"entity_ids": (ENTITY_ID,), "expected_start_frame": 100, "expected_end_frame": "240"},
        (ENTITY_ID,),
    )
    with pytest.raises(TypeError, match="expected_end_frame must be an integer"):
        UnrealCapabilityRegistry().validate_operation(operation)
