"""Real-Unreal gate for heterogeneous failure reassessment and replacement."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterError, UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_composite_operation import build_composite_actor_operation
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_recovery_sequence import (
    build_reassessment_plan,
    build_replacement_plan,
    assess_reassessment_sequence,
    execute_recovery_sequence,
    issue_replacement_authorization,
)
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner
from planning.unreal_transport_named_pipe import NamedPipeTransportError, create_named_pipe_transport

pytestmark = pytest.mark.integration

TARGET_ENTITY_ID = "FIELD_SURFACE"
FAILURE_AUTHORIZATION_ID = "real-heterogeneous-recovery-failure-auth"


def _intent(intent_id):
    return UnrealTaskIntent(
        intent_id,
        "real Unreal heterogeneous recovery integration",
        (TARGET_ENTITY_ID,),
    )


def _state(evidence):
    return evidence.observed_state[TARGET_ENTITY_ID]


def _variant(state, key):
    value = state.get(key, {}).get("variant")
    if not isinstance(value, dict):
        raise AssertionError(f"Unreal FIELD_SURFACE evidence missing {key}.variant")
    return dict(value)


def _read_variant_plan(intent_id, capability, operation_name):
    operation = UnrealOperation(
        capability=capability,
        kind=UnrealOperationKind.READ,
        name=operation_name,
        arguments={"entity_ids": (TARGET_ENTITY_ID,)},
        entity_ids=(TARGET_ENTITY_ID,),
    )
    return UnrealTaskPlan(intent_id, (operation,))


def test_real_unreal_heterogeneous_recovery_reassesses_and_replaces_only_niagara():
    """Prove live transform/material state survives a failed Niagara domain."""
    transport = create_named_pipe_transport()
    executor = UnrealPlanExecutor(
        UnrealAdapterProduction(transport, "heterogeneous-recovery-integration")
    )
    planner = UnrealTaskPlanner()

    try:
        original = executor.execute(
            planner.plan_inspection(_intent("heterogeneous-original")),
            "heterogeneous-original-auth",
        )
        original_state = _state(original.evidence_ledger[0])
        original_location = dict(original_state["location"])
        original_rotation = dict(original_state["rotation"])
        original_scale = dict(original_state["scale"])

        material_original = executor.execute(
            _read_variant_plan(
                "heterogeneous-original-material",
                UnrealCapability.MATERIAL,
                "inspect_material_state",
            ),
            "heterogeneous-original-material-auth",
        )
        original_material = _variant(_state(material_original.evidence_ledger[0]), "material")

        niagara_original = executor.execute(
            _read_variant_plan(
                "heterogeneous-original-niagara",
                UnrealCapability.NIAGARA,
                "inspect_niagara_state",
            ),
            "heterogeneous-original-niagara-auth",
        )
        original_niagara = _variant(_state(niagara_original.evidence_ledger[0]), "niagara")
    except (UnrealAdapterError, NamedPipeTransportError) as exc:
        pytest.skip(f"Unreal heterogeneous fixture unavailable: {exc}")

    composite = build_composite_actor_operation(
        [TARGET_ENTITY_ID],
        [
            {
                "name": "set_actor_location",
                "entity_ids": (TARGET_ENTITY_ID,),
                "location": {
                    "x": original_location["x"] + 20,
                    "y": original_location["y"] + 10,
                    "z": original_location["z"] + 5,
                },
            },
            {
                "name": "set_actor_rotation",
                "entity_ids": (TARGET_ENTITY_ID,),
                "rotation": {
                    "pitch": original_rotation["pitch"],
                    "yaw": original_rotation["yaw"] + 20,
                    "roll": original_rotation["roll"],
                },
            },
            {
                "name": "set_actor_scale",
                "entity_ids": (TARGET_ENTITY_ID,),
                "scale": {
                    "x": original_scale["x"] * 1.05,
                    "y": original_scale["y"] * 1.05,
                    "z": original_scale["z"] * 1.05,
                },
            },
            {
                "name": "apply_material_variant",
                "entity_ids": (TARGET_ENTITY_ID,),
                "variant": "liquid_surface",
            },
            {
                "name": "apply_niagara_variant",
                "entity_ids": (TARGET_ENTITY_ID,),
                "variant": "goal_burst",
            },
        ],
    )
    plan = planner.plan_composite_actor_production(_intent("heterogeneous-live"), composite)

    try:
        with pytest.raises(UnrealPlanExecutionError) as exc_info:
            executor.execute(plan, FAILURE_AUTHORIZATION_ID)

        failure = exc_info.value.failure
        assert failure is not None
        assert failure.operation_name == "apply_niagara_variant"
        assert failure.operation_index == 11

        reassessment = build_reassessment_plan(plan, failure)
        reassessment_auth = UnrealPlanAuthorization.issue(
            reassessment,
            "heterogeneous-reassessment-auth",
        )
        reassessment_result = executor.execute_authorized(
            reassessment,
            reassessment_auth,
        )
        assessment = assess_reassessment_sequence(
            plan,
            failure,
            reassessment_result,
        )

        assert [step.operation_name for step in assessment.steps] == [
            "set_actor_location",
            "set_actor_rotation",
            "set_actor_scale",
            "apply_material_variant",
            "apply_niagara_variant",
        ]
        assert [step.disposition for step in assessment.steps] == [
            "already_applied",
            "already_applied",
            "already_applied",
            "already_applied",
            "replacement_required",
        ]

        replacement = build_replacement_plan(plan, assessment)
        assert [operation.name for operation in replacement.operations] == [
            "apply_niagara_variant",
            "verify_niagara_variant",
        ]
        replacement_auth = issue_replacement_authorization(
            replacement,
            "heterogeneous-replacement-auth",
        )

        result = execute_recovery_sequence(
            executor,
            plan,
            failure,
            reassessment_auth,
            replacement_auth,
        )
        assert result.assessment.disposition == "replacement_required"
        assert result.replacement_plan == replacement
        assert result.replacement_result is not None
        assert result.replacement_result.success is True
        assert [e.operation_name for e in result.replacement_result.evidence_ledger] == [
            "apply_niagara_variant",
            "verify_niagara_variant",
        ]
        assert result.replacement_result.evidence_ledger[1].verified is True
        assert _variant(
            _state(result.replacement_result.evidence_ledger[1]),
            "niagara",
        )["name"] == "goal_burst"

        live_final = executor.execute(
            _read_variant_plan(
                "heterogeneous-live-final",
                UnrealCapability.NIAGARA,
                "inspect_niagara_state",
            ),
            "heterogeneous-live-final-auth",
        )
        assert _variant(_state(live_final.evidence_ledger[0]), "niagara")["name"] == "goal_burst"
    finally:
        restore = build_composite_actor_operation(
            [TARGET_ENTITY_ID],
            [
                {
                    "name": "set_actor_location",
                    "entity_ids": (TARGET_ENTITY_ID,),
                    "location": original_location,
                },
                {
                    "name": "set_actor_rotation",
                    "entity_ids": (TARGET_ENTITY_ID,),
                    "rotation": original_rotation,
                },
                {
                    "name": "set_actor_scale",
                    "entity_ids": (TARGET_ENTITY_ID,),
                    "scale": original_scale,
                },
                {
                    "name": "apply_material_variant",
                    "entity_ids": (TARGET_ENTITY_ID,),
                    "variant": original_material["name"],
                },
                {
                    "name": "apply_niagara_variant",
                    "entity_ids": (TARGET_ENTITY_ID,),
                    "variant": original_niagara["name"],
                },
            ],
        )
        executor.execute(
            planner.plan_composite_actor_production(_intent("heterogeneous-restore"), restore),
            "heterogeneous-restore-auth",
        )
