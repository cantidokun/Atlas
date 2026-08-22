"""Real-Unreal gate for explicit material-variant execution."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_named_pipe import create_named_pipe_transport
from planning.unreal_agent import UnrealTaskIntent


TARGET_ENTITY_ID = "FIELD_SURFACE"


def _intent(intent_id):
    return UnrealTaskIntent(
        intent_id,
        "apply explicit material variant to field surface",
        (TARGET_ENTITY_ID,),
    )


def _variant(evidence):
    return evidence.observed_state[TARGET_ENTITY_ID]["material"]["variant"]


def test_real_unreal_material_variant_applies_verifies_and_restores():
    """Prove material mutation and semantic verification against real Unreal."""
    transport = create_named_pipe_transport()
    adapter = UnrealAdapterProduction(transport, "material-variant-integration")
    executor = UnrealPlanExecutor(adapter)
    planner = UnrealTaskPlanner()

    original_result = executor.execute(
        planner.plan_inspection(_intent("material-original-read")),
        "material-original-read-auth",
    )
    original_variant = dict(_variant(original_result.evidence_ledger[0]))
    target_variant = dict(original_variant)
    target_variant["name"] = "liquid_surface"

    try:
        plan = planner.plan_material_variant(_intent("material-live-variant"), target_variant)
        result = executor.execute(plan, "material-live-variant-auth")

        assert result.success is True
        assert [e.operation_name for e in result.evidence_ledger] == [
            "inspect_target_actors",
            "inspect_material_state",
            "apply_material_variant",
            "verify_material_variant",
        ]
        assert _variant(result.evidence_ledger[2]) == target_variant
        assert _variant(result.evidence_ledger[3]) == target_variant
    finally:
        restore_plan = planner.plan_material_variant(
            _intent("material-restore"),
            original_variant,
        )
        executor.execute(restore_plan, "material-restore-auth")
