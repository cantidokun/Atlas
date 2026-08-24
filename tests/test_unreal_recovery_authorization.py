import pytest

from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_recovery_sequence import issue_replacement_authorization
from planning.unreal_task_planner import UnrealTaskPlan


ENTITY_IDS = ("FIELD_SURFACE",)


def _replacement_plan():
    return UnrealTaskPlan(
        "sequencer-recovery:replacement",
        (
            UnrealOperation(
                UnrealCapability.SEQUENCER,
                UnrealOperationKind.WRITE,
                "set_sequencer_playback_range",
                {
                    "entity_ids": ENTITY_IDS,
                    "start_frame": 10,
                    "end_frame": 110,
                },
                ENTITY_IDS,
            ),
            UnrealOperation(
                UnrealCapability.SEQUENCER,
                UnrealOperationKind.VERIFY,
                "verify_sequencer_playback_range",
                {
                    "entity_ids": ENTITY_IDS,
                    "expected_start_frame": 10,
                    "expected_end_frame": 110,
                },
                ENTITY_IDS,
            ),
        ),
    )


def test_replacement_authorization_binds_to_exact_replacement_plan():
    plan = _replacement_plan()
    authorization = issue_replacement_authorization(plan, "recovery-replacement-auth")

    assert isinstance(authorization, UnrealPlanAuthorization)
    assert authorization.authorization_id == "recovery-replacement-auth"
    assert authorization.matches(plan)


def test_replacement_authorization_does_not_authorize_a_modified_plan():
    plan = _replacement_plan()
    authorization = issue_replacement_authorization(plan, "recovery-replacement-auth")
    modified = UnrealTaskPlan(
        plan.intent_id,
        (
            UnrealOperation(
                UnrealCapability.SEQUENCER,
                UnrealOperationKind.WRITE,
                "set_sequencer_playback_range",
                {
                    "entity_ids": ENTITY_IDS,
                    "start_frame": 11,
                    "end_frame": 111,
                },
                ENTITY_IDS,
            ),
            plan.operations[1],
        ),
    )

    assert authorization.matches(modified) is False


def test_replacement_authorization_cannot_be_reused_for_reassessment_plan():
    replacement = _replacement_plan()
    replacement_authorization = issue_replacement_authorization(
        replacement,
        "recovery-replacement-auth",
    )
    reassessment = UnrealTaskPlan(
        "sequencer-recovery:reassess-sequence",
        (
            UnrealOperation(
                UnrealCapability.SEQUENCER,
                UnrealOperationKind.READ,
                "inspect_sequencer_state",
                {"entity_ids": ENTITY_IDS},
                ENTITY_IDS,
            ),
        ),
    )

    assert replacement_authorization.matches(reassessment) is False
