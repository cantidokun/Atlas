"""Real Unreal integration coverage for the Blueprint production boundary."""

import os

import pytest

from planning.unreal_adapter_production import create_production_adapter
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner
from planning.unreal_transport_named_pipe import NamedPipeTransportError


pytestmark = pytest.mark.integration

ENTITY_ID = "ATLAS_BLUEPRINT_TEST"
ASSET_PATH = os.environ.get("ATLAS_TEST_BLUEPRINT_ASSET", "/Game/AtlasTest/BP_AtlasTest.BP_AtlasTest")


def _intent(intent_id: str) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="real Unreal Blueprint production integration",
        target_entity_ids=(ENTITY_ID,),
    )


def _inspection_plan(intent: UnrealTaskIntent) -> UnrealTaskPlan:
    operation = UnrealOperation(
        capability=UnrealCapability.BLUEPRINT,
        kind=UnrealOperationKind.READ,
        name="inspect_blueprint_state",
        arguments={"entity_ids": (ENTITY_ID,), "asset_path": ASSET_PATH},
        entity_ids=(ENTITY_ID,),
    )
    return UnrealTaskPlan(intent.intent_id, (operation,))


def _blueprint_state(evidence):
    return evidence.observed_state[ENTITY_ID]["blueprint"]


def test_real_unreal_blueprint_compile_and_verify():
    """Compile a real Blueprint asset and independently verify its live state."""
    try:
        adapter = create_production_adapter("blueprint-integration")
        executor = UnrealPlanExecutor(adapter)
        planner = UnrealTaskPlanner()

        original_result = executor.execute(
            _inspection_plan(_intent("real-blueprint-original")),
            "real-blueprint-original-auth",
        )
        original_state = _blueprint_state(original_result.evidence_ledger[0])

        plan = planner.plan_blueprint_compile(
            _intent("real-blueprint-compile"),
            ASSET_PATH,
        )
        assert [operation.name for operation in plan.operations] == [
            "inspect_blueprint_state",
            "compile_blueprint",
            "verify_blueprint_state",
        ]

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
        message = str(exc).lower()
        if "not available" in message or "pipe not found" in message:
            pytest.skip("Unreal Editor transport is unavailable")
        if "blueprint" in message and ("not found" in message or "asset" in message):
            pytest.skip(
                "Set ATLAS_TEST_BLUEPRINT_ASSET to a Blueprint asset available in the Unreal fixture"
            )
        raise
