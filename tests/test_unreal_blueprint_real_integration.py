"""Real Unreal integration coverage for the Blueprint production boundary."""

import os

import pytest

from planning.unreal_adapter_production import create_production_adapter
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_transport_named_pipe import NamedPipeTransportError
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner


pytestmark = pytest.mark.integration

ENTITY_ID = "ATLAS_BLUEPRINT_TEST"
ASSET_PATH = os.environ.get("ATLAS_TEST_BLUEPRINT_ASSET", "/Game/AtlasTest/BP_AtlasTest.BP_AtlasTest")
MISSING_ASSET_PATH = "/Game/AtlasTest/BP_AtlasTest_Missing.BP_AtlasTest_Missing"
METADATA_KEY = "AtlasMutation"
METADATA_VALUE = "production-boundary-1"


def _intent(intent_id: str) -> UnrealTaskIntent:
    return UnrealTaskIntent(intent_id=intent_id, description="real Unreal Blueprint production integration", target_entity_ids=(ENTITY_ID,))


def _inspection_plan(intent: UnrealTaskIntent, asset_path: str = ASSET_PATH) -> UnrealTaskPlan:
    operation = UnrealOperation(capability=UnrealCapability.BLUEPRINT, kind=UnrealOperationKind.READ, name="inspect_blueprint_state", arguments={"entity_ids": (ENTITY_ID,), "asset_path": asset_path}, entity_ids=(ENTITY_ID,))
    return UnrealTaskPlan(intent.intent_id, (operation,))


def _blueprint_state(evidence):
    return evidence.observed_state[ENTITY_ID]["blueprint"]


def _assert_transport_available(exc: Exception) -> None:
    """Skip when Unreal is unavailable, including wrapped transport failures."""
    current = exc
    messages = []
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        messages.append(str(current).lower())
        current = current.__cause__ or current.__context__
    message = " | ".join(messages)
    if "not available" in message or "pipe not found" in message or "disconnected" in message:
        pytest.skip("Unreal Editor transport is unavailable")


def test_real_unreal_blueprint_compile_and_verify():
    """Compile a real Blueprint asset and independently verify its live state."""
    try:
        adapter = create_production_adapter("blueprint-integration")
        executor = UnrealPlanExecutor(adapter)
        planner = UnrealTaskPlanner()
        original_result = executor.execute(_inspection_plan(_intent("real-blueprint-original")), "real-blueprint-original-auth")
        original_state = _blueprint_state(original_result.evidence_ledger[0])
        plan = planner.plan_blueprint_compile(_intent("real-blueprint-compile"), ASSET_PATH)
        assert [operation.name for operation in plan.operations] == ["inspect_blueprint_state", "compile_blueprint", "verify_blueprint_state"]
        result = executor.execute(plan, "real-blueprint-compile-auth")
        assert result.success is True
        assert result.evidence_ledger[0].operation_name == "inspect_blueprint_state"
        assert result.evidence_ledger[1].operation_name == "compile_blueprint"
        assert result.evidence_ledger[2].operation_name == "verify_blueprint_state"
        assert _blueprint_state(result.evidence_ledger[1])["compile_status"].lower() == "success"
        assert _blueprint_state(result.evidence_ledger[2])["compile_status"].lower() == "success"
        assert _blueprint_state(original_result.evidence_ledger[0])["asset_path"] == ASSET_PATH
        assert original_state["asset_path"] == ASSET_PATH
    except NamedPipeTransportError as exc:
        _assert_transport_available(exc)
        if "blueprint" in str(exc).lower() and ("not found" in str(exc).lower() or "asset" in str(exc).lower()):
            pytest.skip("Set ATLAS_TEST_BLUEPRINT_ASSET to a Blueprint asset available in the Unreal fixture")
        raise
    except UnrealPlanExecutionError as exc:
        _assert_transport_available(exc)
        if "blueprint" in str(exc).lower() and ("not found" in str(exc).lower() or "asset" in str(exc).lower()):
            pytest.skip("Set ATLAS_TEST_BLUEPRINT_ASSET to a Blueprint asset available in the Unreal fixture")
        raise


def test_real_unreal_blueprint_metadata_mutation_persists_after_compile():
    """Mutate real Blueprint metadata, compile it, and independently inspect the persisted asset."""
    try:
        adapter = create_production_adapter("blueprint-metadata-integration")
        executor = UnrealPlanExecutor(adapter)
        planner = UnrealTaskPlanner()
        original_result = executor.execute(_inspection_plan(_intent("real-blueprint-metadata-original")), "real-blueprint-metadata-original-auth")
        original_state = _blueprint_state(original_result.evidence_ledger[0])
        assert original_state["asset_path"] == ASSET_PATH
        plan = planner.plan_blueprint_metadata_mutation(_intent("real-blueprint-metadata-mutation"), ASSET_PATH, METADATA_KEY, f"  {METADATA_VALUE}  ")
        assert [operation.name for operation in plan.operations] == ["inspect_blueprint_state", "set_blueprint_metadata", "compile_blueprint", "verify_blueprint_state"]
        result = executor.execute(plan, "real-blueprint-metadata-auth")
        assert result.success is True
        assert _blueprint_state(result.evidence_ledger[1])["metadata"][METADATA_KEY] == METADATA_VALUE
        assert _blueprint_state(result.evidence_ledger[2])["metadata"][METADATA_KEY] == METADATA_VALUE
        assert _blueprint_state(result.evidence_ledger[3])["metadata"][METADATA_KEY] == METADATA_VALUE
        assert _blueprint_state(result.evidence_ledger[3])["compile_status"].lower() == "success"
        fresh_result = executor.execute(_inspection_plan(_intent("real-blueprint-metadata-fresh-inspection")), "real-blueprint-metadata-fresh-auth")
        assert _blueprint_state(fresh_result.evidence_ledger[0])["metadata"][METADATA_KEY] == METADATA_VALUE
    except NamedPipeTransportError as exc:
        _assert_transport_available(exc)
        if "blueprint" in str(exc).lower() and ("not found" in str(exc).lower() or "asset" in str(exc).lower()):
            pytest.skip("Set ATLAS_TEST_BLUEPRINT_ASSET to a Blueprint asset available in the Unreal fixture")
        raise
    except UnrealPlanExecutionError as exc:
        _assert_transport_available(exc)
        if "blueprint" in str(exc).lower() and ("not found" in str(exc).lower() or "asset" in str(exc).lower()):
            pytest.skip("Set ATLAS_TEST_BLUEPRINT_ASSET to a Blueprint asset available in the Unreal fixture")
        raise


def test_real_unreal_blueprint_missing_asset_fails_at_production_boundary():
    """A missing Blueprint must fail through the production boundary with useful context."""
    try:
        adapter = create_production_adapter("blueprint-integration-missing-asset")
        executor = UnrealPlanExecutor(adapter)
        try:
            executor.execute(_inspection_plan(_intent("real-blueprint-missing"), MISSING_ASSET_PATH), "real-blueprint-missing-auth")
        except (NamedPipeTransportError, UnrealPlanExecutionError) as exc:
            _assert_transport_available(exc)
            message = str(exc)
            assert "inspect_blueprint_state" in message
            assert "Blueprint not found" in message
            assert MISSING_ASSET_PATH in message
            return
        pytest.fail("Missing Blueprint unexpectedly succeeded through the production boundary")
    except NamedPipeTransportError as exc:
        _assert_transport_available(exc)
        raise
