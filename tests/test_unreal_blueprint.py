import pytest

from planning.unreal_agent import UnrealCapability, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_blueprint_verifier import verify_blueprint_state
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_task_planner import UnrealTaskPlanner


BLUEPRINT_ASSET = "/Game/Atlas/Blueprints/BP_Field.BP_Field"


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
    verify_blueprint_state(evidence, "success", BLUEPRINT_ASSET)


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
        verify_blueprint_state(evidence, "success", BLUEPRINT_ASSET)
def _blueprint_evidence(blueprint):
    return UnrealEvidence(
        operation_name="verify_blueprint_state",
        entity_ids=("FIELD_BLUEPRINT",),
        observed_state={"FIELD_BLUEPRINT": {"blueprint": blueprint}},
        source="atlas-test",
    )


def test_blueprint_verifier_accepts_authorized_metadata_and_tolerates_unrelated_keys():
    evidence = _blueprint_evidence(
        {
            "asset_path": BLUEPRINT_ASSET,
            "compile_status": "success",
            "metadata": {
                "AtlasMutation": "production-boundary-1",
                "AtlasTestMarker": "transport-validated",
            },
        }
    )

    assert (
        verify_blueprint_state(
            evidence,
            "success",
            BLUEPRINT_ASSET,
            {"metadata_key": "AtlasMutation", "metadata_value": "production-boundary-1"},
        )
        is evidence
    )


def test_blueprint_verifier_normalizes_only_the_authorized_expectation():
    evidence = _blueprint_evidence(
        {
            "asset_path": BLUEPRINT_ASSET,
            "compile_status": "success",
            "metadata": {"AtlasMutation": "production-boundary-1"},
        }
    )

    assert (
        verify_blueprint_state(
            evidence,
            " SUCCESS ",
            f"  {BLUEPRINT_ASSET}  ",
            {"metadata_key": " AtlasMutation ", "metadata_value": " production-boundary-1 "},
        )
        is evidence
    )


def test_blueprint_verifier_does_not_normalize_observed_values():
    evidence = _blueprint_evidence(
        {
            "asset_path": BLUEPRINT_ASSET,
            "compile_status": "success",
            "metadata": {"AtlasMutation": " production-boundary-1 "},
        }
    )

    with pytest.raises(ValueError, match="does not match expected"):
        verify_blueprint_state(
            evidence,
            "success",
            BLUEPRINT_ASSET,
            {"metadata_key": "AtlasMutation", "metadata_value": "production-boundary-1"},
        )


def test_blueprint_verifier_rejects_missing_metadata_mapping():
    evidence = _blueprint_evidence({"asset_path": BLUEPRINT_ASSET, "compile_status": "success"})

    with pytest.raises(ValueError, match="missing blueprint metadata"):
        verify_blueprint_state(
            evidence,
            "success",
            BLUEPRINT_ASSET,
            {"metadata_key": "AtlasMutation", "metadata_value": "production-boundary-1"},
        )


def test_blueprint_verifier_rejects_missing_authorized_key():
    evidence = _blueprint_evidence(
        {"asset_path": BLUEPRINT_ASSET, "compile_status": "success", "metadata": {"Other": "value"}}
    )

    with pytest.raises(ValueError, match="missing the authorized metadata key"):
        verify_blueprint_state(
            evidence,
            "success",
            BLUEPRINT_ASSET,
            {"metadata_key": "AtlasMutation", "metadata_value": "production-boundary-1"},
        )


def test_blueprint_verifier_rejects_non_string_observed_metadata_value():
    evidence = _blueprint_evidence(
        {"asset_path": BLUEPRINT_ASSET, "compile_status": "success", "metadata": {"AtlasMutation": 42}}
    )

    with pytest.raises(ValueError, match="must be a string"):
        verify_blueprint_state(
            evidence,
            "success",
            BLUEPRINT_ASSET,
            {"metadata_key": "AtlasMutation", "metadata_value": "production-boundary-1"},
        )


def test_blueprint_verifier_rejects_malformed_expected_metadata():
    evidence = _blueprint_evidence(
        {
            "asset_path": BLUEPRINT_ASSET,
            "compile_status": "success",
            "metadata": {"AtlasMutation": "production-boundary-1"},
        }
    )

    with pytest.raises(ValueError, match="expected_metadata must contain exactly"):
        verify_blueprint_state(evidence, "success", BLUEPRINT_ASSET, {"metadata_key": "AtlasMutation"})
    with pytest.raises(ValueError, match="metadata_value must be a non-empty string"):
        verify_blueprint_state(
            evidence, "success", BLUEPRINT_ASSET, {"metadata_key": "AtlasMutation", "metadata_value": " "}
        )


def test_blueprint_verifier_rejects_unauthorized_asset_identity():
    evidence = _blueprint_evidence(
        {"asset_path": "/Game/Atlas/Blueprints/BP_Other.BP_Other", "compile_status": "success"}
    )

    with pytest.raises(ValueError, match="does not match the authorized asset path"):
        verify_blueprint_state(evidence, "success", BLUEPRINT_ASSET)


def test_blueprint_verifier_requires_an_authorized_asset_path():
    evidence = _blueprint_evidence({"asset_path": BLUEPRINT_ASSET, "compile_status": "success"})

    with pytest.raises(ValueError, match="expected_asset_path must be a non-empty Unreal package path"):
        verify_blueprint_state(evidence, "success", None)
