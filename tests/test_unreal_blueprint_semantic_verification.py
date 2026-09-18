"""Deterministic coverage for Blueprint semantic verification (frozen design contract).

Proves the contract frozen in the Blueprint semantic verification design gate:
T1-T4 positive proofs, N1-N8 fail-closed proofs, G1-G3 contract guards.

No engine is involved: the adapter is a recording stub, every expected value is
plan-derived, and every observation is a fresh stub read. Nothing here is live.
"""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_capability_registry import UnrealCapabilityRegistry
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner
from planning.unreal_tool_schema import validate_unreal_tool_call

ENTITY_ID = "ATLAS_BLUEPRINT_TEST"
OTHER_ENTITY_ID = "ATLAS_BLUEPRINT_OTHER"
ASSET_PATH = "/Game/AtlasTest/BP_AtlasTest.BP_AtlasTest"
OTHER_ASSET_PATH = "/Game/AtlasTest/BP_Other.BP_Other"
KEY = "AtlasMutation"
VALUE = "production-boundary-1"
UNRELATED_KEY = "AtlasTestMarker"  # fixture-owned key: authorized by nobody, must be tolerated


def _intent(intent_id):
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="Blueprint semantic verification",
        target_entity_ids=(ENTITY_ID,),
    )


def _observed(metadata=None, asset_path=ASSET_PATH, compile_status="success"):
    """Observed Blueprint state as fresh engine evidence would present it."""
    blueprint = {"asset_path": asset_path, "compile_status": compile_status, "is_up_to_date": True}
    if metadata is not None:
        blueprint["metadata"] = dict(metadata)
    return blueprint


class RecordingBlueprintAdapter(UnrealAdapterProduction):
    """Records every adapter call, returns one fresh observation per call."""

    def __init__(self, blueprint):
        super().__init__(transport=object(), source_tag="blueprint-semantic-test")
        self.calls = []
        self.blueprint = dict(blueprint)

    def _observe(self, operation):
        self.calls.append(operation.name)
        blueprint = dict(self.blueprint)
        metadata = blueprint.get("metadata")
        if isinstance(metadata, dict):
            metadata = dict(metadata)
            metadata["_observation"] = f"read-{len(self.calls)}"  # unrelated key, tolerated
            blueprint["metadata"] = metadata
        return UnrealEvidence(
            operation_name=operation.name,
            entity_ids=tuple(operation.entity_ids),
            observed_state={ENTITY_ID: {"entity_id": ENTITY_ID, "blueprint": blueprint}},
            source="blueprint-semantic-test",
            verified=False,
        )

    def inspect(self, operation, authorization_id):
        return self._observe(operation)

    def apply_authorized(self, operation, authorization_id):
        return self._observe(operation)

    def verify(self, operation, authorization_id):
        return self._observe(operation)


def _metadata_plan(intent_id, key=KEY, value=VALUE, asset_path=ASSET_PATH, entity_id=ENTITY_ID):
    plan = UnrealTaskPlanner().plan_blueprint_metadata_mutation(
        UnrealTaskIntent(intent_id, "Blueprint semantic verification", (entity_id,)),
        asset_path,
        key,
        value,
    )
    return plan


def _operation(name, kind, arguments, entity_ids=(ENTITY_ID,)):
    return UnrealOperation(
        capability=UnrealCapability.BLUEPRINT,
        kind=kind,
        name=name,
        arguments={"entity_ids": tuple(entity_ids), **arguments},
        entity_ids=tuple(entity_ids),
    )


# --------------------------------------------------------------------------- T
def test_t1_metadata_mutation_plan_marks_only_the_verification_evidence_verified():
    adapter = RecordingBlueprintAdapter(_observed(metadata={KEY: VALUE, UNRELATED_KEY: "transport-validated"}))
    plan = _metadata_plan("t1")
    result = UnrealPlanExecutor(adapter).execute(plan, "t1-auth")

    assert result.success is True
    assert [evidence.operation_name for evidence in result.evidence_ledger] == [
        "inspect_blueprint_state",
        "set_blueprint_metadata",
        "compile_blueprint",
        "verify_blueprint_state",
    ]
    assert [evidence.verified for evidence in result.evidence_ledger] == [False, False, False, True]
    assert result.evidence_ledger[3].verified is True


def test_t2_compile_only_plan_verifies_without_metadata():
    adapter = RecordingBlueprintAdapter(_observed())
    plan = UnrealTaskPlanner().plan_blueprint_compile(_intent("t2"), ASSET_PATH)
    result = UnrealPlanExecutor(adapter).execute(plan, "t2-auth")

    assert result.success is True
    assert [evidence.verified for evidence in result.evidence_ledger] == [False, False, True]
    assert result.evidence_ledger[2].verified is True
    assert "metadata" not in result.evidence_ledger[2].observed_state[ENTITY_ID]["blueprint"]


def test_t3_expected_metadata_comes_from_the_plan_not_the_evidence():
    """Identical fresh evidence must pass or fail purely on the authorized expectation."""
    observed = _observed(metadata={KEY: VALUE})
    authorized = _metadata_plan("t3-authorized", value=VALUE)
    model_proposed = _metadata_plan("t3-model-proposed", value="model-proposed-value")

    authorized_result = UnrealPlanExecutor(RecordingBlueprintAdapter(observed)).execute(
        authorized, "t3-authorized-auth"
    )
    assert authorized_result.success is True
    assert authorized_result.evidence_ledger[3].verified is True

    with pytest.raises(UnrealPlanExecutionError, match="does not match expected"):
        UnrealPlanExecutor(RecordingBlueprintAdapter(observed)).execute(model_proposed, "t3-model-proposed-auth")


def test_t4_verification_reads_fresh_engine_state():
    adapter = RecordingBlueprintAdapter(_observed(metadata={KEY: VALUE}))
    plan = _metadata_plan("t4")
    result = UnrealPlanExecutor(adapter).execute(plan, "t4-auth")

    assert adapter.calls == [
        "inspect_blueprint_state",
        "set_blueprint_metadata",
        "compile_blueprint",
        "verify_blueprint_state",
    ]
    verify_evidence = result.evidence_ledger[3]
    assert verify_evidence.observed_state[ENTITY_ID]["blueprint"]["metadata"]["_observation"] == "read-4"
    assert len({id(evidence) for evidence in result.evidence_ledger}) == 4


# --------------------------------------------------------------------------- N
NEGATIVES = (
    ("n1_wrong_metadata_value", _observed(metadata={KEY: "tampered-by-engine"}), "does not match expected"),
    ("n2_missing_metadata_mapping", _observed(), "missing blueprint metadata"),
    ("n3_missing_authorized_key", _observed(metadata={"Unrelated": VALUE}), "missing the authorized metadata key"),
    (
        "n4_wrong_observed_asset",
        _observed(metadata={KEY: VALUE}, asset_path=OTHER_ASSET_PATH),
        "does not match the authorized asset path",
    ),
    ("n5_non_string_observed_value", _observed(metadata={KEY: 42}), "must be a string"),
    (
        "n6_compile_status_mismatch",
        _observed(metadata={KEY: VALUE}, compile_status="error"),
        "does not match the requested compile status",
    ),
)


@pytest.mark.parametrize("label,blueprint,message", NEGATIVES, ids=[case[0] for case in NEGATIVES])
def test_n1_to_n6_fail_closed_with_a_failure_record(label, blueprint, message):
    adapter = RecordingBlueprintAdapter(blueprint)
    plan = _metadata_plan(label)

    with pytest.raises(UnrealPlanExecutionError, match=message) as excinfo:
        UnrealPlanExecutor(adapter).execute(plan, f"{label}-auth")

    failure = excinfo.value.failure
    assert failure is not None
    assert failure.intent_id == label
    assert failure.operation_index == 3
    assert failure.operation_name == "verify_blueprint_state"
    assert failure.operation_entity_ids == (ENTITY_ID,)
    assert len(failure.completed_evidence) == 3
    assert [evidence.operation_name for evidence in failure.completed_evidence] == [
        "inspect_blueprint_state",
        "set_blueprint_metadata",
        "compile_blueprint",
    ]
    assert isinstance(failure.operation_arguments, dict)


def test_n7_metadata_write_for_a_different_asset_is_rejected_before_dispatch():
    adapter = RecordingBlueprintAdapter(_observed(metadata={KEY: VALUE}))
    plan = UnrealTaskPlan(
        "n7",
        (
            _operation("set_blueprint_metadata", UnrealOperationKind.WRITE,
                       {"asset_path": ASSET_PATH, "metadata_key": KEY, "metadata_value": VALUE}),
            _operation("compile_blueprint", UnrealOperationKind.WRITE, {"asset_path": OTHER_ASSET_PATH}),
            _operation("verify_blueprint_state", UnrealOperationKind.VERIFY,
                       {"asset_path": OTHER_ASSET_PATH, "expected_compile_status": "success"}),
        ),
    )

    with pytest.raises(UnrealPlanExecutionError, match="same asset"):
        UnrealPlanExecutor(adapter).execute(plan, "n7-auth")

    assert adapter.calls == []


def test_n8_metadata_write_for_different_entities_is_rejected_before_dispatch():
    adapter = RecordingBlueprintAdapter(_observed(metadata={KEY: VALUE}))
    plan = UnrealTaskPlan(
        "n8",
        (
            _operation("set_blueprint_metadata", UnrealOperationKind.WRITE,
                       {"asset_path": ASSET_PATH, "metadata_key": KEY, "metadata_value": VALUE}),
            _operation("compile_blueprint", UnrealOperationKind.WRITE, {"asset_path": ASSET_PATH},
                       entity_ids=(OTHER_ENTITY_ID,)),
            _operation("verify_blueprint_state", UnrealOperationKind.VERIFY,
                       {"asset_path": ASSET_PATH, "expected_compile_status": "success"},
                       entity_ids=(OTHER_ENTITY_ID,)),
        ),
    )

    with pytest.raises(UnrealPlanExecutionError, match="same entities"):
        UnrealPlanExecutor(adapter).execute(plan, "n8-auth")

    assert adapter.calls == []


# --------------------------------------------------------------------------- G
def test_g1_blueprint_verify_argument_key_set_is_unchanged():
    registry = UnrealCapabilityRegistry()
    allowed = _operation("verify_blueprint_state", UnrealOperationKind.VERIFY,
                         {"asset_path": ASSET_PATH, "expected_compile_status": "success"})
    assert registry.validate_operation(allowed) is allowed

    for extra_key in ("expected_metadata_key", "expected_metadata_value", "expected_asset_path", "metadata"):
        rejected = _operation("verify_blueprint_state", UnrealOperationKind.VERIFY,
                              {"asset_path": ASSET_PATH, "expected_compile_status": "success", extra_key: "x"})
        with pytest.raises(ValueError, match="do not match the capability schema"):
            registry.validate_operation(rejected)


def test_g2_registration_cannot_create_a_vacuous_pass():
    adapter = RecordingBlueprintAdapter(_observed(metadata={KEY: "contradicts-the-plan"}))
    plan = _metadata_plan("g2")

    assert UnrealPlanExecutor._is_semantically_verified(_operation(
        "verify_blueprint_state", UnrealOperationKind.VERIFY,
        {"asset_path": ASSET_PATH, "expected_compile_status": "success"}), None) is True

    with pytest.raises(UnrealPlanExecutionError, match="does not match expected"):
        UnrealPlanExecutor(adapter).execute(plan, "g2-auth")

    assert "verify_blueprint_state" in adapter.calls


def test_g3_existing_blueprint_planning_schema_and_registry_contracts_unchanged():
    planner = UnrealTaskPlanner()
    compile_plan = planner.plan_blueprint_compile(_intent("g3-compile"), ASSET_PATH)
    metadata_plan = planner.plan_blueprint_metadata_mutation(_intent("g3-metadata"), ASSET_PATH, KEY, VALUE)

    assert [operation.name for operation in compile_plan.operations] == [
        "inspect_blueprint_state",
        "compile_blueprint",
        "verify_blueprint_state",
    ]
    assert [operation.name for operation in metadata_plan.operations] == [
        "inspect_blueprint_state",
        "set_blueprint_metadata",
        "compile_blueprint",
        "verify_blueprint_state",
    ]
    assert metadata_plan.operations[3].arguments == {
        "entity_ids": (ENTITY_ID,),
        "asset_path": ASSET_PATH,
        "expected_compile_status": "success",
    }

    snapshot = validate_unreal_tool_call(
        "verify_blueprint_state",
        {
            "entity_ids": (ENTITY_ID,),
            "authorization_id": "g3-auth",
            "asset_path": f"  {ASSET_PATH}  ",
            "expected_compile_status": " success ",
        },
    )
    assert snapshot == {
        "entity_ids": (ENTITY_ID,),
        "authorization_id": "g3-auth",
        "asset_path": ASSET_PATH,
        "expected_compile_status": "success",
    }

    incomplete = _operation("verify_blueprint_state", UnrealOperationKind.VERIFY, {"asset_path": ASSET_PATH})
    with pytest.raises(ValueError, match="do not match the capability schema"):
        UnrealCapabilityRegistry().validate_operation(incomplete)
