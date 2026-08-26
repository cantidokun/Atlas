"""Unit coverage for the Blueprint planning and validation contract."""

import pytest

from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_capability_registry import UnrealCapabilityRegistry
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_tool_schema import validate_unreal_tool_call


ENTITY_ID = "ATLAS_BLUEPRINT_TEST"
ASSET_PATH = "/Game/AtlasTest/BP_AtlasTest.BP_AtlasTest"


def _intent(intent_id="blueprint-plan"):
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="Blueprint planning contract",
        target_entity_ids=(ENTITY_ID,),
    )


def test_blueprint_compile_plan_has_explicit_read_write_verify_boundary():
    plan = UnrealTaskPlanner().plan_blueprint_compile(_intent(), ASSET_PATH)

    assert [operation.name for operation in plan.operations] == [
        "inspect_blueprint_state",
        "compile_blueprint",
        "verify_blueprint_state",
    ]
    assert [operation.kind for operation in plan.operations] == [
        UnrealOperationKind.READ,
        UnrealOperationKind.WRITE,
        UnrealOperationKind.VERIFY,
    ]
    assert all(operation.capability is UnrealCapability.BLUEPRINT for operation in plan.operations)
    assert plan.operations[1].arguments["asset_path"] == ASSET_PATH
    assert plan.operations[2].arguments["expected_compile_status"] == "success"


def test_blueprint_planner_rejects_non_package_paths():
    with pytest.raises(ValueError, match="asset_path"):
        UnrealTaskPlanner().plan_blueprint_compile(_intent(), "BP_AtlasTest")


def test_blueprint_registry_requires_compile_status_for_verification():
    operation = UnrealOperation(
        capability=UnrealCapability.BLUEPRINT,
        kind=UnrealOperationKind.VERIFY,
        name="verify_blueprint_state",
        arguments={"entity_ids": (ENTITY_ID,), "asset_path": ASSET_PATH},
        entity_ids=(ENTITY_ID,),
    )

    with pytest.raises(ValueError, match="expected_compile_status"):
        UnrealCapabilityRegistry().validate_operation(operation)


def test_blueprint_tool_schema_rejects_invalid_asset_path():
    with pytest.raises(ValueError, match="asset_path"):
        validate_unreal_tool_call(
            "inspect_blueprint_state",
            {
                "entity_ids": (ENTITY_ID,),
                "authorization_id": "blueprint-schema-auth",
                "asset_path": "relative/BP_AtlasTest",
            },
        )
