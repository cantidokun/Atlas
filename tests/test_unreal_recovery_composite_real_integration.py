"""Real Unreal integration coverage for composite actor-production recovery."""

import pytest

from planning.unreal_adapter_production import create_production_adapter
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_composite_operation import build_composite_actor_operation
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionFailure, UnrealPlanExecutor
from planning.unreal_recovery_sequence import (
    assess_reassessment_sequence,
    build_reassessment_plan,
    build_replacement_plan,
    execute_recovery_sequence,
    issue_replacement_authorization,
)
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner
from planning.unreal_transport_named_pipe import NamedPipeTransportError


pytestmark = pytest.mark.integration

ENTITY_ID = "FIELD_SURFACE"


def _intent(intent_id):
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="real Unreal composite actor-production recovery",
        target_entity_ids=(ENTITY_ID,),
    )


def _inspection_plan(intent):
    return UnrealTaskPlan(
        intent.intent_id,
        (
            UnrealOperation(
                UnrealCapability.INSPECT_ACTOR,
                UnrealOperationKind.READ,
                "inspect_target_actors",
                {"entity_ids": (ENTITY_ID,)},
                (ENTITY_ID,),
            ),
        ),
    )


def _actor_state(evidence):
    return evidence.observed_state[ENTITY_ID]


def _post_write_failure(target_location, target_scale):
    return UnrealPlanExecutionFailure(
        intent_id="real-composite-recovery",
        operation_index=4,
        operation_name="verify_actor_scale",
        completed_evidence=(
            UnrealEvidence(
                "inspect_target_actors",
                (ENTITY_ID,),
                {
                    ENTITY_ID: {
                        "entity_id": ENTITY_ID,
                        "location": dict(target_location),
                        "scale": dict(target_scale),
                    }
                },
                "real-composite-recovery-test",
                False,
            ),
        ),
        error="simulated post-write verification failure",
        operation_entity_ids=(ENTITY_ID,),
        operation_arguments={
            "entity_ids": (ENTITY_ID,),
            "expected_scale": dict(target_scale),
        },
        completed_operation_arguments=(
            {"entity_ids": (ENTITY_ID,)},
            {"entity_ids": (ENTITY_ID,), "location": dict(target_location)},
            {"entity_ids": (ENTITY_ID,), "expected_location": dict(target_location)},
            {"entity_ids": (ENTITY_ID,), "scale": dict(target_scale)},
        ),
    )


def test_real_unreal_composite_recovery_replaces_only_mismatched_prior_write():
    """Exercise live reassessment and selective recovery of a composite mutation."""
    try:
        adapter = create_production_adapter("composite-recovery-integration")
        executor = UnrealPlanExecutor(adapter)
        planner = UnrealTaskPlanner()

        original_result = executor.execute(
            _inspection_plan(_intent("real-composite-recovery-original")),
            "real-composite-recovery-original-auth",
        )
        original = _actor_state(original_result.evidence_ledger[0])
        original_location = dict(original["location"])
        original_scale = dict(original["scale"])

        target_location = dict(original_location)
        target_location["x"] += 25.0
        target_scale = {
            "x": original_scale["x"] * 1.1,
            "y": original_scale["y"] * 1.1,
            "z": original_scale["z"] * 1.1,
        }
        mismatched_scale = {
            "x": original_scale["x"] * 1.2,
            "y": original_scale["y"] * 1.2,
            "z": original_scale["z"] * 1.2,
        }

        composite = build_composite_actor_operation(
            (ENTITY_ID,),
            (
                {"name": "set_actor_location", "location": target_location},
                {"name": "set_actor_scale", "scale": target_scale},
            ),
        )
        write_plan = planner.plan_composite_actor_production(
            _intent("real-composite-recovery-write"),
            composite,
        )
        write_result = executor.execute(
            write_plan,
            "real-composite-recovery-write-auth",
        )
        assert write_result.success is True

        mismatch_plan = planner.plan_actor_scale_write(
            _intent("real-composite-recovery-mismatch"),
            mismatched_scale,
        )
        mismatch_result = executor.execute(
            mismatch_plan,
            "real-composite-recovery-mismatch-auth",
        )
        assert mismatch_result.success is True

        failure = _post_write_failure(target_location, target_scale)
        reassessment_plan = build_reassessment_plan(write_plan, failure)
        reassessment_authorization = UnrealPlanAuthorization.issue(
            reassessment_plan,
            "real-composite-recovery-reassessment-auth",
        )
        reassessment_result = executor.execute_authorized(
            reassessment_plan,
            reassessment_authorization,
        )
        assessment = assess_reassessment_sequence(
            write_plan,
            failure,
            reassessment_result,
        )

        assert assessment.disposition == "replacement_required"
        by_name = {step.operation_name: step for step in assessment.steps}
        assert by_name["set_actor_location"].disposition == "already_applied"
        assert by_name["set_actor_scale"].disposition == "replacement_required"

        replacement_plan = build_replacement_plan(write_plan, assessment)
        assert [operation.name for operation in replacement_plan.operations] == [
            "set_actor_scale",
            "verify_actor_scale",
        ]
        replacement_authorization = issue_replacement_authorization(
            replacement_plan,
            "real-composite-recovery-replacement-auth",
        )

        recovery = execute_recovery_sequence(
            executor,
            write_plan,
            failure,
            reassessment_authorization,
            replacement_authorization,
        )

        assert recovery.assessment.disposition == "replacement_required"
        assert recovery.replacement_plan is not None
        assert [operation.name for operation in recovery.replacement_plan.operations] == [
            "set_actor_scale",
            "verify_actor_scale",
        ]
        assert recovery.replacement_result is not None
        assert recovery.replacement_result.success is True

        final_result = executor.execute(
            _inspection_plan(_intent("real-composite-recovery-final")),
            "real-composite-recovery-final-auth",
        )
        final_state = _actor_state(final_result.evidence_ledger[0])
        assert final_state["location"] == target_location
        assert final_state["scale"] == target_scale

    except NamedPipeTransportError as exc:
        message = str(exc).lower()
        if "not available" in message or "pipe not found" in message:
            pytest.skip("Unreal Editor transport is unavailable")
        raise
    finally:
        try:
            restore_plan = planner.plan_composite_actor_production(
                _intent("real-composite-recovery-restore"),
                build_composite_actor_operation(
                    (ENTITY_ID,),
                    (
                        {"name": "set_actor_location", "location": original_location},
                        {"name": "set_actor_scale", "scale": original_scale},
                    ),
                ),
            )
            restore_result = executor.execute(
                restore_plan,
                "real-composite-recovery-restore-auth",
            )
            assert restore_result.success is True
        except (UnboundLocalError, NameError):
            pass
