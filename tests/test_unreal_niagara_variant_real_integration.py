"""Real-Unreal gate for deterministic Niagara variant execution."""

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_named_pipe import create_named_pipe_transport
from planning.unreal_agent import UnrealTaskIntent


TARGET_ENTITY_ID = "FIELD_SURFACE"


def _intent(intent_id):
    return UnrealTaskIntent(intent_id, "apply explicit Niagara variant to field surface", (TARGET_ENTITY_ID,))


def _variant_from_state(evidence):
    return dict(evidence.observed_state[TARGET_ENTITY_ID]["niagara"]["variant"])


def test_real_unreal_niagara_variant_applies_verifies_and_restores():
    transport = create_named_pipe_transport()
    adapter = UnrealAdapterProduction(transport, "niagara-variant-integration")
    executor = UnrealPlanExecutor(adapter)
    planner = UnrealTaskPlanner()

    original_result = executor.execute(
        planner.plan_niagara_variant(_intent("niagara-original-read"), {"name": "default"}),
        "niagara-original-read-auth",
    )
    original_variant = _variant_from_state(original_result.evidence_ledger[1])
    target_variant = {"name": "goal_burst"}

    try:
        result = executor.execute(
            planner.plan_niagara_variant(_intent("niagara-live-variant"), target_variant),
            "niagara-live-variant-auth",
        )
        assert result.success is True
        assert [e.operation_name for e in result.evidence_ledger] == [
            "inspect_target_actors", "inspect_niagara_state", "apply_niagara_variant", "verify_niagara_variant"
        ]
        assert _variant_from_state(result.evidence_ledger[2]) == target_variant
        assert _variant_from_state(result.evidence_ledger[3]) == target_variant
    finally:
        executor.execute(
            planner.plan_niagara_variant(_intent("niagara-restore"), original_variant),
            "niagara-restore-auth",
        )
