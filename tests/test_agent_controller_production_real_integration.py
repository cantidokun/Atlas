"""Live Unreal validation for an agent-originated production request."""

import pytest

from controller.agent_entrypoint_contract import AgentControllerHandoff
from controller.agent_entrypoint_runtime import AtlasAgentEntrypointRuntime
from controller.agent_process_runtime import AtlasAgentProcessRuntime
from planning.agent_controller_production_request import AgentControllerProductionRequest
from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_composite_operation import build_composite_actor_operation
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration
from planning.unreal_production_operation import UnrealProductionSpec, build_unreal_production_plan
from planning.unreal_production_planning_boundary import authorize_production_plan
from planning.unreal_production_runtime_adapter import UnrealProductionRuntimeAdapter
from planning.unreal_production_executor import UnrealProductionExecutor
from planning.unreal_production_workflow import UnrealProductionWorkflow
from planning.unreal_render_contract import UnrealRenderConfig
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_workflow import UnrealRenderWorkflow
from planning.unreal_transport_named_pipe import NamedPipeTransportError, WindowsNamedPipeTransport
from planning.unreal_task_planner import UnrealTaskIntent, UnrealTaskPlan, UnrealTaskPlanner


pytestmark = pytest.mark.integration

ENTITY_ID = "FIELD_SURFACE"


def _intent(intent_id: str) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="agent-originated Unreal production request",
        target_entity_ids=(ENTITY_ID,),
    )


def _spec() -> UnrealProductionSpec:
    return UnrealProductionSpec(
        composite=build_composite_actor_operation(
            [ENTITY_ID],
            [
                {"name": "set_actor_location", "location": {"x": 10.0, "y": 20.0, "z": 30.0}},
                {"name": "set_actor_rotation", "rotation": {"pitch": 0.0, "yaw": 15.0, "roll": 0.0}},
                {"name": "set_actor_scale", "scale": {"x": 1.1, "y": 1.1, "z": 1.1}},
                {"name": "apply_material_variant", "variant": "liquid_surface"},
                {"name": "apply_niagara_variant", "variant": "goal_burst"},
            ],
        ),
        start_frame=1,
        end_frame=24,
        render_config=UnrealRenderConfig(
            width=1280,
            height=720,
            start_frame=1,
            end_frame=24,
            output_directory="Saved/AtlasProductionOutput",
            output_format="png",
        ),
    )


def _integration(tmp_path):
    adapter = UnrealAdapterProduction(
        WindowsNamedPipeTransport(),
        "agent-controller-real-integration",
    )
    raw_executor = UnrealPlanExecutor(adapter)
    runtime = UnrealProductionRuntimeAdapter(raw_executor)
    production_executor = UnrealProductionExecutor(raw_executor)

    render_workflow = UnrealRenderWorkflow(
        raw_executor,
        UnrealRenderReceiptStore(
            tmp_path / "agent-controller-production-render-receipt.json"
        ),
        poll_interval_seconds=0.25,
        timeout_seconds=120.0,
    )

    workflow = UnrealProductionWorkflow(
        production_executor,
        render_workflow,
    )

    integration = UnrealProductionControllerIntegration(
        runtime,
        workflow=workflow,
        render_authorization_factory=lambda plan: UnrealPlanAuthorization.issue(
            plan,
            "agent-controller-real-render-auth",
        ),
    )
    return integration, raw_executor


def _state(evidence):
    return evidence.observed_state[ENTITY_ID]


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
        arguments={"entity_ids": (ENTITY_ID,)},
        entity_ids=(ENTITY_ID,),
    )
    return UnrealTaskPlan(intent.intent_id, (operation,))


def _render_inspection_plan(intent):
    operation = UnrealOperation(
        capability=UnrealCapability.RENDER,
        kind=UnrealOperationKind.READ,
        name="inspect_render_state",
        arguments={"entity_ids": (ENTITY_ID,)},
        entity_ids=(ENTITY_ID,),
    )
    return UnrealTaskPlan(intent.intent_id, (operation,))


def _read_variant_plan(intent_id, capability, operation_name):
    operation = UnrealOperation(
        capability=capability,
        kind=UnrealOperationKind.READ,
        name=operation_name,
        arguments={"entity_ids": (ENTITY_ID,)},
        entity_ids=(ENTITY_ID,),
    )
    return UnrealTaskPlan(intent_id, (operation,))


def _assert_transport_available(exc: Exception) -> None:
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


def test_real_agent_originated_unreal_request_reaches_live_production_boundary(tmp_path):
    """Send an explicit agent handoff through the controller and into live Unreal."""
    integration = None
    raw_executor = None
    original_state = None
    original_material = None
    original_niagara = None
    original_render_state = None
    original_sequencer_state = None

    try:
        integration, raw_executor = _integration(tmp_path)
        planner = UnrealTaskPlanner()

        original = raw_executor.execute(
            planner.plan_inspection(_intent("real-agent-production-original")),
            "real-agent-production-original-auth",
        )
        original_state = _state(original.evidence_ledger[0])

        original_material_result = raw_executor.execute(
            _read_variant_plan(
                "real-agent-production-original-material",
                UnrealCapability.MATERIAL,
                "inspect_material_state",
            ),
            "real-agent-production-original-material-auth",
        )
        original_material = _variant(original_material_result.evidence_ledger[0], "material")

        original_niagara_result = raw_executor.execute(
            _read_variant_plan(
                "real-agent-production-original-niagara",
                UnrealCapability.NIAGARA,
                "inspect_niagara_state",
            ),
            "real-agent-production-original-niagara-auth",
        )
        original_niagara = _variant(original_niagara_result.evidence_ledger[0], "niagara")

        original_render = raw_executor.execute(
            _render_inspection_plan(_intent("real-agent-production-original-render")),
            "real-agent-production-original-render-auth",
        )
        original_render_state = _state(original_render.evidence_ledger[0])["render"]

        original_sequencer = raw_executor.execute(
            _sequencer_inspection_plan(_intent("real-agent-production-original-sequencer")),
            "real-agent-production-original-sequencer-auth",
        )
        original_sequencer_state = _state(original_sequencer.evidence_ledger[0])["sequencer"]

        production_intent = _intent("real-agent-production")
        production = build_unreal_production_plan(production_intent, _spec())
        authorized = authorize_production_plan(production, "real-agent-production-auth")

        process = AtlasAgentProcessRuntime(unreal_production=integration)
        entrypoint = AtlasAgentEntrypointRuntime(process)
        handoff = AgentControllerHandoff.from_fields(
            capability="production",
            provider="unreal",
            target_entity_ids=(ENTITY_ID,),
            intent_id="real-agent-production",
            description="agent-originated live Unreal production request",
            context={
                "production": True,
                "authorized_production": authorized,
                "intent": production_intent,
                "sequence_asset_path": "/Game/AtlasTest/AtlasSequencerFixtureSequence",
            },
        )

        execution = AgentControllerProductionRequest(entrypoint).submit(handoff)

        assert execution.controller_executed is True
        assert execution.result is not None
        assert execution.result.capability_name == "unreal_production"

        event = execution.result.value
        assert event.operation == "start"
        assert event.snapshot.state == "complete"
        assert event.workflow_result is not None

        workflow_result = event.workflow_result
        assert workflow_result.success is True
        assert workflow_result.production.success is True
        assert workflow_result.render.job_id == workflow_result.render.receipt.job_id
        assert (
            workflow_result.render.receipt.sequence_asset_path
            == "/Game/AtlasTest/AtlasSequencerFixtureSequence"
        )
        assert workflow_result.render.final_evidence.verified is True
        assert workflow_result.render.persisted_receipt["job_id"] == workflow_result.render.job_id
        assert workflow_result.render.persisted_receipt["receipt_digest"]

        assert integration.complete is True

    except NamedPipeTransportError as exc:
        _assert_transport_available(exc)
        raise

    finally:
        if raw_executor is not None and original_state is not None:
            restore_intent = _intent("real-agent-production-restore")

            restore_composite = build_composite_actor_operation(
                [ENTITY_ID],
                [
                    {
                        "name": "set_actor_location",
                        "entity_ids": (ENTITY_ID,),
                        "location": dict(original_state["location"]),
                    },
                    {
                        "name": "set_actor_rotation",
                        "entity_ids": (ENTITY_ID,),
                        "rotation": dict(original_state["rotation"]),
                    },
                    {
                        "name": "set_actor_scale",
                        "entity_ids": (ENTITY_ID,),
                        "scale": dict(original_state["scale"]),
                    },
                    {
                        "name": "apply_material_variant",
                        "entity_ids": (ENTITY_ID,),
                        "variant": original_material["name"],
                    },
                    {
                        "name": "apply_niagara_variant",
                        "entity_ids": (ENTITY_ID,),
                        "variant": original_niagara["name"],
                    },
                ],
            )

            raw_executor.execute(
                planner.plan_composite_actor_production(
                    restore_intent,
                    restore_composite,
                ),
                "real-agent-production-restore-auth",
            )

            if original_sequencer_state is not None:
                raw_executor.execute(
                    planner.plan_sequencer_playback_range(
                        restore_intent,
                        int(original_sequencer_state["start_frame"]),
                        int(original_sequencer_state["end_frame"]),
                    ),
                    "real-agent-production-restore-sequencer-auth",
                )

            if original_render_state is not None:
                raw_executor.execute(
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
                    "real-agent-production-restore-render-auth",
                )
