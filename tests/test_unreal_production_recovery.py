"""Production-aware recovery tests for heterogeneous Unreal transactions."""

from dataclasses import replace

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_production_operation import build_unreal_production_plan
from planning.unreal_production_recovery import (
    assess_production_reassessment,
    build_production_reassessment_plan,
    build_production_replacement_plan,
    execute_production_recovery,
    failed_phase,
    issue_production_replacement_authorization,
)
from tests.test_unreal_heterogeneous_production import ProductionTransport, _intent, _spec


class BlueprintMismatchTransport(ProductionTransport):
    def __init__(self, fail_at=None):
        super().__init__(fail_at=fail_at)
        self.state["FIELD_SURFACE"]["blueprint"] = {
            "asset_path": "/Game/AtlasTest/BP_AtlasTest",
            "compile_status": "error",
        }


def _execute_failure(transport, production):
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport, "production-recovery-test"))
    with pytest.raises(UnrealPlanExecutionError) as exc_info:
        executor.execute(production.plan, "production-auth")
    assert exc_info.value.failure is not None
    return executor, exc_info.value.failure


def test_sequencer_failure_gets_fresh_phase_bound_reassessment_and_replacement():
    production = build_unreal_production_plan(_intent(), _spec())
    # Operation 18 is the Sequencer verification; all earlier writes have
    # completed, but the injected failure occurs at verification.
    transport = ProductionTransport(fail_at=18)
    executor, failure = _execute_failure(transport, production)

    assert failed_phase(production, failure) == "sequencer"
    reassessment = build_production_reassessment_plan(production, failure)
    assert [op.name for op in reassessment.operations] == [
        "inspect_blueprint_state",
        "inspect_target_actors",
        "inspect_material_state",
        "inspect_niagara_state",
        "inspect_sequencer_state",
    ]
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment, "sequencer-reassessment-auth")
    reassessment_result = executor.execute_authorized(reassessment, reassessment_auth)
    assessment = assess_production_reassessment(production, failure, reassessment_result)

    assert assessment.disposition == "already_applied"
    assert any(step.phase == "sequencer" and step.operation_name == "set_sequencer_playback_range" for step in assessment.steps)


def test_render_failure_reassesses_all_completed_phases_and_replaces_only_render():
    production = build_unreal_production_plan(_intent(), _spec())
    # Operation 20 is configure_render. The write fails before changing render state.
    transport = ProductionTransport(fail_at=20)
    executor, failure = _execute_failure(transport, production)

    assert failed_phase(production, failure) == "render"
    reassessment = build_production_reassessment_plan(production, failure)
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment, "render-reassessment-auth")
    reassessment_result = executor.execute_authorized(reassessment, reassessment_auth)
    assessment = assess_production_reassessment(production, failure, reassessment_result)

    assert assessment.disposition == "replacement_required"
    replacement_steps = [step for step in assessment.steps if step.disposition == "replacement_required"]
    assert [(step.phase, step.operation_name) for step in replacement_steps] == [("render", "configure_render")]

    replacement_plan = build_production_replacement_plan(production, assessment)
    assert [op.name for op in replacement_plan.operations] == [
        "configure_render",
        "verify_render_state",
    ]
    replacement_auth = issue_production_replacement_authorization(replacement_plan, "render-replacement-auth")
    recovery = execute_production_recovery(
        executor,
        production,
        failure,
        reassessment_auth,
        replacement_auth,
    )
    assert recovery.assessment.disposition == "replacement_required"
    assert recovery.replacement_result is not None
    assert recovery.replacement_result.success is True
    assert transport.state["FIELD_SURFACE"]["render"]["width"] == 1280


def test_blueprint_failure_is_reassessed_and_reauthorized_without_reusing_original_plan():
    production = build_unreal_production_plan(_intent(), _spec())
    # Blueprint compile is operation 1. Start from an explicitly mismatched
    # compile state so fresh evidence forces a replacement rather than guessing.
    transport = BlueprintMismatchTransport(fail_at=1)
    executor, failure = _execute_failure(transport, production)

    assert failed_phase(production, failure) == "blueprint"
    assert len(failure.completed_evidence) == 1
    assert failure.completed_evidence[0].operation_name == "inspect_blueprint_state"

    reassessment = build_production_reassessment_plan(production, failure)
    assert [op.name for op in reassessment.operations] == ["inspect_blueprint_state"]
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment, "blueprint-reassessment-auth")
    reassessment_result = executor.execute_authorized(reassessment, reassessment_auth)
    assessment = assess_production_reassessment(production, failure, reassessment_result)

    assert assessment.disposition == "replacement_required"
    assert assessment.steps[0].phase == "blueprint"
    assert assessment.steps[0].operation_name == "compile_blueprint"

    replacement_plan = build_production_replacement_plan(production, assessment)
    replacement_auth = issue_production_replacement_authorization(replacement_plan, "blueprint-replacement-auth")
    recovery = execute_production_recovery(
        executor,
        production,
        failure,
        reassessment_auth,
        replacement_auth,
    )

    assert recovery.replacement_plan is not None
    assert recovery.replacement_result is not None
    assert recovery.replacement_result.success is True
    assert transport.state["FIELD_SURFACE"]["blueprint"]["compile_status"] == "success"


def test_production_recovery_rejects_reused_original_authorization():
    production = build_unreal_production_plan(_intent(), _spec())
    transport = ProductionTransport(fail_at=20)
    executor, failure = _execute_failure(transport, production)

    reassessment = build_production_reassessment_plan(production, failure)
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment, "reassessment-auth")
    reassessment_result = executor.execute_authorized(reassessment, reassessment_auth)
    assessment = assess_production_reassessment(production, failure, reassessment_result)
    replacement_plan = build_production_replacement_plan(production, assessment)

    original_auth = UnrealPlanAuthorization.issue(production.plan, "original-auth")
    with pytest.raises(ValueError, match="replacement authorization"):
        execute_production_recovery(
            executor,
            production,
            failure,
            reassessment_auth,
            original_auth,
        )

    replacement_auth = issue_production_replacement_authorization(replacement_plan, "replacement-auth")
    assert replacement_auth.matches(replacement_plan)


def test_production_recovery_rejects_tampered_failure_arguments():
    production = build_unreal_production_plan(_intent(), _spec())
    transport = ProductionTransport(fail_at=20)
    executor, failure = _execute_failure(transport, production)

    tampered = replace(
        failure,
        operation_arguments={
            **failure.operation_arguments,
            "width": 9999,
        },
    )

    with pytest.raises(ValueError, match="failure arguments do not match"):
        failed_phase(production, tampered)

    with pytest.raises(ValueError, match="failure arguments do not match"):
        build_production_reassessment_plan(production, tampered)
