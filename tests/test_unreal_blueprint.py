import pytest

from planning.unreal_agent import UnrealCapability, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_blueprint_verifier import verify_blueprint_state
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_task_planner import UnrealTaskPlanner


def test_blueprint_compile_plan_is_read_write_verify():
    plan = UnrealTaskPlanner().plan_blueprint_compile(
        UnrealTaskIntent("bp-1", "compile field blueprint", ("FIELD_BLUEPRINT",)),
        "/Game/Atlas/Blueprints/BP_Field.BP_Field",
    )
    assert [op.kind for op in plan.operations] == [
        UnrealOperationKind.READ,
        UnrealOperationKind.WRITE,
        UnrealOperationKind.VERIFY,
    ]
    assert [op.name for op in plan.operations] == [
        "inspect_blueprint_state",
        "compile_blueprint",
        "verify_blueprint_state",
    ]
    assert all(op.capability is UnrealCapability.BLUEPRINT for op in plan.operations)
    assert all(op.entity_ids == ("FIELD_BLUEPRINT",) for op in plan.operations)
    assert plan.operations[0].arguments["asset_path"] == "/Game/Atlas/Blueprints/BP_Field.BP_Field"
    assert plan.operations[2].arguments["expected_compile_status"] == "success"


def test_blueprint_compile_rejects_non_package_asset_path():
    with pytest.raises(ValueError, match="Unreal package path"):
        UnrealTaskPlanner().plan_blueprint_compile(
            UnrealTaskIntent("bp-2", "compile field blueprint", ("FIELD_BLUEPRINT",)),
            "BP_Field",
        )


def test_blueprint_compile_rejects_empty_target_ids():
    with pytest.raises(ValueError):
        UnrealTaskPlanner().plan_blueprint_compile(
            UnrealTaskIntent("bp-3", "compile field blueprint", ()),
            "/Game/Atlas/Blueprints/BP_Field.BP_Field",
        )


def test_blueprint_verifier_accepts_successful_evidence():
    evidence = UnrealEvidence(
        operation_name="verify_blueprint_state",
        entity_ids=("FIELD_BLUEPRINT",),
        observed_state={
            "FIELD_BLUEPRINT": {
                "blueprint": {
                    "asset_path": "/Game/Atlas/Blueprints/BP_Field.BP_Field",
                    "compile_status": "success",
                }
            }
        },
        source="atlas-test",
    )
    verify_blueprint_state(evidence, "success")


def test_blueprint_verifier_rejects_failed_compilation():
    evidence = UnrealEvidence(
        operation_name="verify_blueprint_state",
        entity_ids=("FIELD_BLUEPRINT",),
        observed_state={
            "FIELD_BLUEPRINT": {
                "blueprint": {
                    "asset_path": "/Game/Atlas/Blueprints/BP_Field.BP_Field",
                    "compile_status": "error",
                }
            }
        },
        source="atlas-test",
    )
    with pytest.raises(ValueError, match="does not match"):
        verify_blueprint_state(evidence, "success")
