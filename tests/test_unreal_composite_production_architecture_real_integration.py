"""Live UE5.6 gate for the complete composite Unreal production architecture.

This gate deliberately exercises the real production planner, production executor,
exact authorization, semantic verification, top-level production workflow, and the
existing Movie Render Queue path. It is intentionally integration-only.

The fixture map must be loaded before running the test:
    /Game/AtlasTest/Generated/AtlasRenderFixture
"""

from collections.abc import Mapping

import pytest

from planning.unreal_adapter_production import UnrealAdapterError, create_production_adapter
from planning.unreal_composite_operation import build_composite_actor_operation
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_production_executor import UnrealProductionExecutor
from planning.unreal_production_operation import UnrealProductionSpec, build_unreal_production_plan
from planning.unreal_production_workflow import UnrealProductionWorkflow
from planning.unreal_render_contract import UnrealRenderConfig
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_workflow import UnrealRenderWorkflow
from planning.unreal_task_planner import UnrealTaskIntent
from planning.unreal_transport_named_pipe import NamedPipeTransportError

pytestmark = pytest.mark.integration

TARGET = "FIELD_SURFACE"
SEQUENCE = "/Game/AtlasTest/AtlasSequencerFixtureSequence"
BLUEPRINT = "/Game/AtlasTest/BP_AtlasTest"


def _intent(intent_id: str) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="live composite production architecture gate",
        target_entity_ids=(TARGET,),
    )


def _variant(state: Mapping, key: str) -> dict:
    value = state.get(key, {}).get("variant")
    if not isinstance(value, Mapping):
        raise AssertionError(f"{key}.variant missing from Unreal evidence")
    return dict(value)


def _sequencer_state(state: Mapping) -> dict:
    value = state.get("sequencer", {}).get("playback_range")
    if not isinstance(value, Mapping):
        raise AssertionError("sequencer.playback_range missing from Unreal evidence")
    return dict(value)


def test_live_unreal_composite_production_architecture_gate(tmp_path):
    adapter = None
    original_actor = None
    original_material = None
    original_niagara = None
    original_sequencer = None
    original_render = None

    try:
        adapter = create_production_adapter("composite-production-architecture-live")
        executor = UnrealPlanExecutor(adapter)
        production_executor = UnrealProductionExecutor(executor)
        receipt_store = UnrealRenderReceiptStore(
            tmp_path / "composite-production-architecture-receipt.json"
        )
        render_workflow = UnrealRenderWorkflow(
            executor,
            receipt_store,
            poll_interval_seconds=0.25,
            timeout_seconds=120.0,
        )
        workflow = UnrealProductionWorkflow(production_executor, render_workflow)
        intent = _intent("composite-production-architecture-live")

        original = executor.execute(
            __import__("planning.unreal_task_planner", fromlist=["UnrealTaskPlanner"])
            .UnrealTaskPlanner()
            .plan_inspection(_intent("composite-original")),
            "composite-original-auth",
        )
        original_actor = dict(original.evidence_ledger[0].observed_state[TARGET])

        from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
        from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner

        planner = UnrealTaskPlanner()

        material_plan = UnrealTaskPlan(
            "composite-original-material",
            (
                UnrealOperation(
                    capability=UnrealCapability.MATERIAL,
                    kind=UnrealOperationKind.READ,
                    name="inspect_material_state",
                    arguments={"entity_ids": (TARGET,)},
                    entity_ids=(TARGET,),
                ),
            ),
        )
        material_result = executor.execute(material_plan, "composite-original-material-auth")
        original_material = _variant(
            material_result.evidence_ledger[0].observed_state[TARGET], "material"
        )

        niagara_plan = UnrealTaskPlan(
            "composite-original-niagara",
            (
                UnrealOperation(
                    capability=UnrealCapability.NIAGARA,
                    kind=UnrealOperationKind.READ,
                    name="inspect_niagara_state",
                    arguments={"entity_ids": (TARGET,)},
                    entity_ids=(TARGET,),
                ),
            ),
        )
        niagara_result = executor.execute(niagara_plan, "composite-original-niagara-auth")
        original_niagara = _variant(
            niagara_result.evidence_ledger[0].observed_state[TARGET], "niagara"
        )

        sequencer_plan = UnrealTaskPlan(
            "composite-original-sequencer",
            (
                UnrealOperation(
                    capability=UnrealCapability.SEQUENCER,
                    kind=UnrealOperationKind.READ,
                    name="inspect_sequencer_state",
                    arguments={"entity_ids": (TARGET,)},
                    entity_ids=(TARGET,),
                ),
            ),
        )
        sequencer_result = executor.execute(sequencer_plan, "composite-original-sequencer-auth")
        original_sequencer = _sequencer_state(
            sequencer_result.evidence_ledger[0].observed_state[TARGET]
        )

        render_plan = UnrealTaskPlan(
            "composite-original-render",
            (
                UnrealOperation(
                    capability=UnrealCapability.RENDER,
                    kind=UnrealOperationKind.READ,
                    name="inspect_render_state",
                    arguments={"entity_ids": (TARGET,)},
                    entity_ids=(TARGET,),
                ),
            ),
        )
        render_result = executor.execute(render_plan, "composite-original-render-auth")
        original_render = dict(render_result.evidence_ledger[0].observed_state[TARGET]["render"])

        original_location = dict(original_actor["location"])
        original_rotation = dict(original_actor["rotation"])
        original_scale = dict(original_actor["scale"])

        composite = build_composite_actor_operation(
            [TARGET],
            [
                {
                    "name": "set_actor_location",
                    "entity_ids": (TARGET,),
                    "location": {
                        "x": original_location["x"] + 10.0,
                        "y": original_location["y"] + 5.0,
                        "z": original_location["z"] + 3.0,
                    },
                },
                {
                    "name": "set_actor_rotation",
                    "entity_ids": (TARGET,),
                    "rotation": {
                        "pitch": original_rotation["pitch"],
                        "yaw": original_rotation["yaw"] + 15.0,
                        "roll": original_rotation["roll"],
                    },
                },
                {
                    "name": "set_actor_scale",
                    "entity_ids": (TARGET,),
                    "scale": {
                        "x": original_scale["x"] * 1.02,
                        "y": original_scale["y"] * 1.02,
                        "z": original_scale["z"] * 1.02,
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

        spec = UnrealProductionSpec(
            composite=composite,
            start_frame=1,
            end_frame=2,
            render_config=UnrealRenderConfig(
                width=640,
                height=360,
                start_frame=1,
                end_frame=2,
                output_directory="Saved/AtlasCompositeArchitectureOutput",
                output_format="png",
            ),
            blueprint_asset_path=BLUEPRINT,
        )
        production = build_unreal_production_plan(intent, spec)
        production_authorization = UnrealPlanAuthorization.issue(
            production.plan,
            "composite-production-architecture-live-auth",
        )

        result = workflow.run(
            production,
            production_authorization,
            intent,
            SEQUENCE,
            lambda plan: UnrealPlanAuthorization.issue(
                plan,
                "composite-production-architecture-render-auth",
            ),
        )

        assert result.success is True
        assert result.production.success is True
        assert result.render.intent_id == intent.intent_id
        assert result.render.job_id == result.render.receipt.job_id
        assert result.render.final_evidence.verified is True
        assert receipt_store.load() == result.render.receipt

        production_evidence = result.production.initial_result.evidence_ledger
        expected = [
            "inspect_blueprint_state", "compile_blueprint", "verify_blueprint_state",
            "inspect_target_actors", "set_actor_location", "verify_actor_location",
            "set_actor_rotation", "verify_actor_rotation", "set_actor_scale", "verify_actor_scale",
            "inspect_material_state", "apply_material_variant", "verify_material_variant",
            "inspect_niagara_state", "apply_niagara_variant", "verify_niagara_variant",
            "inspect_sequencer_state", "set_sequencer_playback_range", "verify_sequencer_playback_range",
            "inspect_render_state", "configure_render", "verify_render_state",
        ]
        assert [entry.operation_name for entry in production_evidence] == expected
        assert all(
            entry.verified is True
            for entry in production_evidence
            if entry.operation_name.startswith("verify_")
        )
        assert production_evidence[-1].verified is True

        final_actor = result.production.initial_result.evidence_ledger[6].observed_state[TARGET]
        assert final_actor["location"] == {
            "x": original_location["x"] + 10.0,
            "y": original_location["y"] + 5.0,
            "z": original_location["z"] + 3.0,
        }
        assert final_actor["rotation"]["yaw"] == original_rotation["yaw"] + 15.0
        assert final_actor["scale"]["x"] == original_scale["x"] * 1.02

        final_material = result.production.initial_result.evidence_ledger[12].observed_state[TARGET]
        assert _variant(final_material, "material")["name"] == "liquid_surface"

        final_niagara = result.production.initial_result.evidence_ledger[16].observed_state[TARGET]
        assert _variant(final_niagara, "niagara")["name"] == "goal_burst"

        final_render = result.production.initial_result.evidence_ledger[21].observed_state[TARGET]["render"]
        assert final_render["width"] == 640
        assert final_render["height"] == 360
        assert final_render["start_frame"] == 1
        assert final_render["end_frame"] == 2

        job_state = result.render.final_evidence.observed_state
        if TARGET in job_state:
            job_state = job_state[TARGET]["render_job"]
        assert job_state["finished"] is True
        assert job_state["success"] is True
        assert job_state["failed"] is False
        assert job_state["job_id"] == result.render.job_id
        assert job_state["output_files"]

    except (NamedPipeTransportError, UnrealAdapterError) as exc:
        message = str(exc).lower()
        if any(token in message for token in ("not available", "pipe not found", "disconnected")):
            pytest.skip(f"Unreal transport unavailable: {exc}")
        raise

    finally:
        if adapter is not None and original_actor is not None:
            restore = UnrealTaskPlanner()
            restore_intent = _intent("composite-production-architecture-restore")
            restore_composite = build_composite_actor_operation(
                [TARGET],
                [
                    {"name": "set_actor_location", "entity_ids": (TARGET,), "location": original_location},
                    {"name": "set_actor_rotation", "entity_ids": (TARGET,), "rotation": original_rotation},
                    {"name": "set_actor_scale", "entity_ids": (TARGET,), "scale": original_scale},
                    {"name": "apply_material_variant", "entity_ids": (TARGET,), "variant": original_material["name"]},
                    {"name": "apply_niagara_variant", "entity_ids": (TARGET,), "variant": original_niagara["name"]},
                ],
            )
            executor.execute(
                restore.plan_composite_actor_production(restore_intent, restore_composite),
                "composite-production-architecture-restore-auth",
            )
            executor.execute(
                restore.plan_sequencer_playback_range(
                    restore_intent,
                    int(original_sequencer["start_frame"]),
                    int(original_sequencer["end_frame"]),
                ),
                "composite-production-architecture-restore-sequencer-auth",
            )
            executor.execute(
                restore.plan_render_configuration(restore_intent, original_render),
                "composite-production-architecture-restore-render-auth",
            )
