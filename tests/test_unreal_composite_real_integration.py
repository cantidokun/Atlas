"""Real-Unreal gate for the complete composite production path."""

import pytest

from planning.unreal_adapter_production import UnrealAdapterError, UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_composite_operation import build_composite_actor_operation
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner
from planning.unreal_transport_named_pipe import NamedPipeTransportError, create_named_pipe_transport

TARGET_ENTITY_ID = "FIELD_SURFACE"


def _intent(intent_id):
    return UnrealTaskIntent(intent_id, "prepare field surface composite production state", (TARGET_ENTITY_ID,))


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


def test_real_unreal_composite_production_applies_verifies_and_restores():
    """Prove the complete composite planner/executor path against real Unreal."""
    transport = create_named_pipe_transport()
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport, "composite-production-integration"))
    planner = UnrealTaskPlanner()

    try:
        original = executor.execute(planner.plan_inspection(_intent("composite-original")), "composite-original-auth")
        original_state = _state(original.evidence_ledger[0])
        original_location = dict(original_state["location"])
        original_rotation = dict(original_state["rotation"])
        original_scale = dict(original_state["scale"])

        material_original = executor.execute(
            _read_variant_plan("composite-original-material", UnrealCapability.MATERIAL, "inspect_material_state"),
            "composite-original-material-auth",
        )
        original_material = _variant(_state(material_original.evidence_ledger[0]), "material")

        niagara_original = executor.execute(
            _read_variant_plan("composite-original-niagara", UnrealCapability.NIAGARA, "inspect_niagara_state"),
            "composite-original-niagara-auth",
        )
        original_niagara = _variant(_state(niagara_original.evidence_ledger[0]), "niagara")
    except (UnrealAdapterError, NamedPipeTransportError) as exc:
        pytest.skip(f"Unreal composite fixture unavailable: {exc}")

    composite = build_composite_actor_operation(
        [TARGET_ENTITY_ID],
        [
            {"name": "set_actor_location", "entity_ids": (TARGET_ENTITY_ID,), "location": {"x": original_location["x"] + 10, "y": original_location["y"], "z": original_location["z"]}},
            {"name": "set_actor_rotation", "entity_ids": (TARGET_ENTITY_ID,), "rotation": {"pitch": original_rotation["pitch"], "yaw": original_rotation["yaw"] + 15, "roll": original_rotation["roll"]}},
            {"name": "set_actor_scale", "entity_ids": (TARGET_ENTITY_ID,), "scale": {"x": original_scale["x"] * 1.1, "y": original_scale["y"] * 1.1, "z": original_scale["z"] * 1.1}},
            {"name": "apply_material_variant", "entity_ids": (TARGET_ENTITY_ID,), "variant": "liquid_surface"},
            {"name": "apply_niagara_variant", "entity_ids": (TARGET_ENTITY_ID,), "variant": "goal_burst"},
        ],
    )

    try:
        result = executor.execute(
            planner.plan_composite_actor_production(_intent("composite-live"), composite),
            "composite-live-auth",
        )
        assert result.success is True
        assert [e.operation_name for e in result.evidence_ledger] == [
            "inspect_target_actors",
            "set_actor_location", "verify_target_actor_mapping",
            "set_actor_rotation", "verify_target_actor_mapping",
            "set_actor_scale", "verify_target_actor_mapping",
            "inspect_material_state", "apply_material_variant", "verify_material_variant",
            "inspect_niagara_state", "apply_niagara_variant", "verify_niagara_variant",
        ]
        assert result.evidence_ledger[2].verified is True
        assert result.evidence_ledger[4].verified is True
        assert result.evidence_ledger[6].verified is True
        assert result.evidence_ledger[9].verified is True
        assert result.evidence_ledger[12].verified is True
    finally:
        restore = build_composite_actor_operation(
            [TARGET_ENTITY_ID],
            [
                {"name": "set_actor_location", "entity_ids": (TARGET_ENTITY_ID,), "location": original_location},
                {"name": "set_actor_rotation", "entity_ids": (TARGET_ENTITY_ID,), "rotation": original_rotation},
                {"name": "set_actor_scale", "entity_ids": (TARGET_ENTITY_ID,), "scale": original_scale},
                {"name": "apply_material_variant", "entity_ids": (TARGET_ENTITY_ID,), "variant": original_material["name"]},
                {"name": "apply_niagara_variant", "entity_ids": (TARGET_ENTITY_ID,), "variant": original_niagara["name"]},
            ],
        )
        executor.execute(planner.plan_composite_actor_production(_intent("composite-restore"), restore), "composite-restore-auth")
