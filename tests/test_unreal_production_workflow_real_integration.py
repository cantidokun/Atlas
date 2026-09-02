"""Real UE5.6 integration coverage for the top-level Unreal production workflow."""

import pytest

from planning.unreal_adapter_production import create_production_adapter
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_production_executor import UnrealProductionExecutor
from planning.unreal_production_operation import (
    UnrealProductionSpec,
    build_unreal_production_plan,
)
from planning.unreal_production_workflow import (
    UnrealProductionWorkflow,
)
from planning.unreal_render_contract import UnrealRenderConfig
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_workflow import UnrealRenderWorkflow
from planning.unreal_task_planner import UnrealTaskIntent, UnrealTaskPlanner
from planning.unreal_composite_operation import build_composite_actor_operation
from planning.unreal_transport_named_pipe import NamedPipeTransportError
from planning.unreal_adapter_production import UnrealAdapterError


pytestmark = pytest.mark.integration

TARGET = "FIELD_SURFACE"
SEQUENCE_ASSET_PATH = "/Game/AtlasTest/AtlasSequencerFixtureSequence"


def _intent(intent_id):
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="real UE5.6 heterogeneous production workflow integration",
        target_entity_ids=(TARGET,),
    )


def _state(evidence):
    return evidence.observed_state[TARGET]


def _variant(evidence, key):
    value = _state(evidence).get(key, {}).get("variant")
    if not isinstance(value, dict):
        raise AssertionError(f"{key}.variant missing from Unreal evidence")
    return dict(value)


def _sequencer_inspection_plan(intent):
    operation = UnrealOperation(
        capability=UnrealCapability.SEQUENCER,
        kind=UnrealOperationKind.READ,
        name="inspect_sequencer_state",
        arguments={"entity_ids": (TARGET,)},
        entity_ids=(TARGET,),
    )
    from planning.unreal_task_planner import UnrealTaskPlan
    return UnrealTaskPlan(intent.intent_id, (operation,))


def _sequencer_state(evidence):
    state = evidence.observed_state[TARGET]
    return dict(state["sequencer"])


def _render_inspection_plan(intent):
    operation = UnrealOperation(
        capability=UnrealCapability.RENDER,
        kind=UnrealOperationKind.READ,
        name="inspect_render_state",
        arguments={"entity_ids": (TARGET,)},
        entity_ids=(TARGET,),
    )
    from planning.unreal_task_planner import UnrealTaskPlan
    return UnrealTaskPlan(intent.intent_id, (operation,))


def _render_state(evidence):
    state = evidence.observed_state[TARGET]
    return dict(state["render"])


def _read_variant_plan(intent_id, capability, operation_name):
    from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
    from planning.unreal_task_planner import UnrealTaskPlan

    operation = UnrealOperation(
        capability=capability,
        kind=UnrealOperationKind.READ,
        name=operation_name,
        arguments={"entity_ids": (TARGET,)},
        entity_ids=(TARGET,),
    )
    return UnrealTaskPlan(intent_id, (operation,))


def test_real_unreal_production_workflow_executes_render_and_persists_receipt(tmp_path):
    adapter = None
    original_state = None
    original_sequencer_state = None
    original_material = None
    original_niagara = None
    original_render_state = None

    try:
        adapter = create_production_adapter("production-workflow-real-integration")
        raw_executor = UnrealPlanExecutor(adapter)
        production_executor = UnrealProductionExecutor(raw_executor)
        render_workflow = UnrealRenderWorkflow(
            raw_executor,
            UnrealRenderReceiptStore(
                tmp_path / "production-workflow-render-receipt.json"
            ),
            poll_interval_seconds=0.25,
            timeout_seconds=120.0,
        )
        workflow = UnrealProductionWorkflow(
            production_executor,
            render_workflow,
        )
        planner = UnrealTaskPlanner()

        original = raw_executor.execute(
            planner.plan_inspection(_intent("production-workflow-original")),
            "production-workflow-original-auth",
        )
        original_state = _state(original.evidence_ledger[0])

        original_sequencer = raw_executor.execute(
            _sequencer_inspection_plan(_intent("production-workflow-original-sequencer")),
            "production-workflow-original-sequencer-auth",
        )
        original_sequencer_state = _sequencer_state(original_sequencer.evidence_ledger[0])

        material_original = raw_executor.execute(
            _read_variant_plan(
                "production-workflow-original-material",
                __import__("planning.unreal_agent", fromlist=["UnrealCapability"]).UnrealCapability.MATERIAL,
                "inspect_material_state",
            ),
            "production-workflow-original-material-auth",
        )
        original_material = _variant(material_original.evidence_ledger[0], "material")

        niagara_original = raw_executor.execute(
            _read_variant_plan(
                "production-workflow-original-niagara",
                __import__("planning.unreal_agent", fromlist=["UnrealCapability"]).UnrealCapability.NIAGARA,
                "inspect_niagara_state",
            ),
            "production-workflow-original-niagara-auth",
        )
        original_niagara = _variant(niagara_original.evidence_ledger[0], "niagara")

        original_render = raw_executor.execute(
            _render_inspection_plan(_intent("production-workflow-original-render")),
            "production-workflow-original-render-auth",
        )
        original_render_state = _render_state(original_render.evidence_ledger[0])

        composite = build_composite_actor_operation(
            [TARGET],
            [
                {
                    "name": "set_actor_location",
                    "entity_ids": (TARGET,),
                    "location": {
                        "x": original_state["location"]["x"] + 10.0,
                        "y": original_state["location"]["y"] + 5.0,
                        "z": original_state["location"]["z"] + 3.0,
                    },
                },
                {
                    "name": "set_actor_rotation",
                    "entity_ids": (TARGET,),
                    "rotation": {
                        "pitch": original_state["rotation"]["pitch"],
                        "yaw": original_state["rotation"]["yaw"] + 15.0,
                        "roll": original_state["rotation"]["roll"],
                    },
                },
                {
                    "name": "set_actor_scale",
                    "entity_ids": (TARGET,),
                    "scale": {
                        "x": original_state["scale"]["x"] * 1.02,
                        "y": original_state["scale"]["y"] * 1.02,
                        "z": original_state["scale"]["z"] * 1.02,
                    },
                },
                {
                    "name": "apply_material_variant",
                    "entity_ids": (TARGET,),
                    "variant": "liquid_surface",
                },
                {
                    "name": "apply_niagara_variant",
                    "entity_ids": (TARGET,),
                    "variant": "goal_burst",
                },
            ],
        )

        intent = _intent("production-workflow-live")
        spec = UnrealProductionSpec(
            composite=composite,
            start_frame=1,
            end_frame=2,
            render_config=UnrealRenderConfig(
                width=640,
                height=360,
                start_frame=1,
                end_frame=2,
                output_directory="Saved/AtlasProductionWorkflowOutput",
                output_format="png",
            ),
            blueprint_asset_path=None,
        )
        production = build_unreal_production_plan(intent, spec)
        production_authorization = UnrealPlanAuthorization.issue(
            production.plan,
            "production-workflow-live-auth",
        )

        result = workflow.run(
            production,
            production_authorization,
            intent,
            SEQUENCE_ASSET_PATH,
            lambda plan: UnrealPlanAuthorization.issue(
                plan,
                "production-workflow-render-auth",
            ),
        )

        assert result.success is True
        assert result.production.success is True
        assert result.render.receipt.job_id == result.render.job_id
        assert result.render.receipt.sequence_asset_path == SEQUENCE_ASSET_PATH
        assert result.render.final_evidence.verified is True
        assert result.render.final_evidence.observed_state
        assert result.render.persisted_receipt["job_id"] == result.render.job_id
        assert render_workflow.receipt_store.exists() is True
        assert render_workflow.receipt_store.load() == result.render.receipt

        final_state = result.render.final_evidence.observed_state
        job_state = final_state
        if TARGET in final_state:
            job_state = final_state[TARGET]["render_job"]

        assert job_state["finished"] is True
        assert job_state["success"] is True
        assert job_state["failed"] is False
        assert job_state["output_files"]

    except (NamedPipeTransportError, UnrealAdapterError) as exc:
        message = str(exc).lower()
        if any(token in message for token in ("not available", "pipe not found", "disconnected")):
            pytest.skip("Unreal Editor transport is unavailable")
        if "not found" in message:
            pytest.skip("Required Unreal production fixture is unavailable")
        raise

    finally:
        if adapter is not None and original_state is not None:
            restore_executor = UnrealPlanExecutor(adapter)
            restore_intent = _intent("production-workflow-restore")

            restore_composite = build_composite_actor_operation(
                [TARGET],
                [
                    {
                        "name": "set_actor_location",
                        "entity_ids": (TARGET,),
                        "location": dict(original_state["location"]),
                    },
                    {
                        "name": "set_actor_rotation",
                        "entity_ids": (TARGET,),
                        "rotation": dict(original_state["rotation"]),
                    },
                    {
                        "name": "set_actor_scale",
                        "entity_ids": (TARGET,),
                        "scale": dict(original_state["scale"]),
                    },
                    {
                        "name": "apply_material_variant",
                        "entity_ids": (TARGET,),
                        "variant": original_material["name"],
                    },
                    {
                        "name": "apply_niagara_variant",
                        "entity_ids": (TARGET,),
                        "variant": original_niagara["name"],
                    },
                ],
            )

            restore_executor.execute(
                planner.plan_composite_actor_production(
                    restore_intent,
                    restore_composite,
                ),
                "production-workflow-restore-auth",
            )

            restore_executor.execute(
                planner.plan_sequencer_playback_range(
                    restore_intent,
                    int(original_sequencer_state["start_frame"]),
                    int(original_sequencer_state["end_frame"]),
                ),
                "production-workflow-restore-sequencer-auth",
            )

            if original_render_state is not None:
                restore_executor.execute(
                    planner.plan_render_configuration(
                        restore_intent,
                        {
                            "width": original_render_state["width"],
                        "height": original_render_state["height"],
                        "start_frame": original_render_state["start_frame"],
                        "end_frame": original_render_state["end_frame"],
                        "output_directory": original_render_state["output_directory"],
                        "output_format": original_render_state["output_format"],
                    },
                ),
                "production-workflow-restore-render-auth",
            )
