import pytest

from planning.unreal_agent import UnrealCapability, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_capability_registry import UnrealCapabilityRegistry
from planning.unreal_task_planner import UnrealTaskPlanner


ENTITY_ID = "FIELD_SURFACE"


def _intent(intent_id="sequencer-contract"):
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="Control the playback range of the authorized Unreal sequence.",
        target_entity_ids=(ENTITY_ID,),
    )


def test_sequencer_playback_range_plan_is_read_write_verify():
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


def test_sequencer_playback_range_plan_binds_expected_verification_values():
    plan = UnrealTaskPlanner().plan_sequencer_playback_range(_intent(), 100, 240)
    write, verify = plan.operations[1:]

    assert write.arguments == {
        "entity_ids": (ENTITY_ID,),
        "start_frame": 100,
        "end_frame": 240,
    }
    assert verify.arguments == {
        "entity_ids": (ENTITY_ID,),
        "expected_start_frame": 100,
        "expected_end_frame": 240,
    }


def test_sequencer_rejects_inverted_or_non_integer_frame_ranges():
    planner = UnrealTaskPlanner()

    with pytest.raises(ValueError, match="start_frame must not exceed end_frame"):
        planner.plan_sequencer_playback_range(_intent(), 240, 100)

    with pytest.raises(TypeError, match="start_frame must be an integer"):
        planner.plan_sequencer_playback_range(_intent(), 100.0, 240)

    with pytest.raises(TypeError, match="end_frame must be an integer"):
        planner.plan_sequencer_playback_range(_intent(), 100, 240.0)


def test_sequencer_registry_rejects_malformed_write_and_verify_payloads():
    registry = UnrealCapabilityRegistry()

    with pytest.raises(ValueError, match="capability schema"):
        registry.validate_operation(
            __import__("planning.unreal_agent", fromlist=["UnrealOperation"]).UnrealOperation(
                capability=UnrealCapability.SEQUENCER,
                kind=UnrealOperationKind.WRITE,
                name="set_sequencer_playback_range",
                arguments={"entity_ids": (ENTITY_ID,), "start_frame": 100},
                entity_ids=(ENTITY_ID,),
            )
        )

    with pytest.raises(TypeError, match="expected_start_frame must be an integer"):
        registry.validate_operation(
            __import__("planning.unreal_agent", fromlist=["UnrealOperation"]).UnrealOperation(
                capability=UnrealCapability.SEQUENCER,
                kind=UnrealOperationKind.VERIFY,
                name="verify_sequencer_playback_range",
                arguments={
                    "entity_ids": (ENTITY_ID,),
                    "expected_start_frame": 100.0,
                    "expected_end_frame": 240,
                },
                entity_ids=(ENTITY_ID,),
            )
        )
