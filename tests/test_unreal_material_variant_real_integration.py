"""Real-Unreal gate for explicit material-variant execution."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_adapter_production import UnrealAdapterError
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_named_pipe import NamedPipeTransportError, create_named_pipe_transport
from planning.unreal_agent import UnrealTaskIntent


TARGET_ENTITY_ID = "FIELD_SURFACE"


def _intent(intent_id):
    return UnrealTaskIntent(
        intent_id,
        "apply explicit material variant to field surface",
        (TARGET_ENTITY_ID,),
    )


def _variant_from_state(evidence):
    state = evidence.observed_state[TARGET_ENTITY_ID]
    material = state.get("material")
    if not isinstance(material, dict) or not isinstance(material.get("variant"), dict):
        pytest.skip(
            "Unreal FIELD_SURFACE fixture does not expose material.variant in live evidence"
        )
    return dict(material["variant"])


def test_real_unreal_material_variant_applies_verifies_and_restores():
    """Prove material mutation and semantic verification against real Unreal.

    The current Python adapter defines the material operation contract, but the
    existing Unreal harness may not yet expose ``inspect_material_state`` or
    ``apply_material_variant``. Those runtime capability gaps are an external
    Unreal fixture boundary, not a reason to weaken the Atlas-side contract.
    """
    transport = create_named_pipe_transport()
    adapter = UnrealAdapterProduction(transport, "material-variant-integration")
    executor = UnrealPlanExecutor(adapter)
    planner = UnrealTaskPlanner()

    try:
        original_result = executor.execute(
            planner.plan_material_variant(_intent("material-original-read"), {"name": "default"}),
            "material-original-read-auth",
        )
    except (UnrealAdapterError, NamedPipeTransportError, Exception) as exc:
        message = str(exc).lower()
        if "unsupported operation_name: inspect_material_state" in message:
            pytest.skip("Unreal transport does not yet expose inspect_material_state")
        if "unsupported operation_name: apply_material_variant" in message:
            pytest.skip("Unreal transport does not yet expose apply_material_variant")
        if "not available" in message:
            pytest.skip("Unreal Editor transport is unavailable")
        raise

    original_variant = _variant_from_state(original_result.evidence_ledger[1])
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
        assert _variant_from_state(result.evidence_ledger[2]) == target_variant
        assert _variant_from_state(result.evidence_ledger[3]) == target_variant
    except UnrealAdapterError as exc:
        message = str(exc).lower()
        if "unsupported operation_name: apply_material_variant" in message:
            pytest.skip("Unreal transport does not yet expose apply_material_variant")
        raise
    finally:
        try:
            restore_plan = planner.plan_material_variant(
                _intent("material-restore"),
                original_variant,
            )
            executor.execute(restore_plan, "material-restore-auth")
        except Exception:
            if "original_variant" in locals():
                raise
