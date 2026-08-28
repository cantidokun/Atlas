"""End-to-end in-memory tests for heterogeneous Unreal production plans."""

from typing import Optional

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_composite_operation import build_composite_actor_operation
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_production_operation import UnrealProductionSpec, build_unreal_production_plan
from planning.unreal_render_contract import UnrealRenderConfig
from planning.unreal_task_planner import UnrealTaskIntent
from planning.unreal_transport_contract import UnrealTransportRequest, UnrealTransportResponse

TARGET = "FIELD_SURFACE"


class ProductionTransport:
    def __init__(self, fail_at: Optional[int] = None):
        self.calls = []
        self.fail_at = fail_at
        self.state = {
            TARGET: {
                "location": {"x": 0.0, "y": 0.0, "z": 0.0},
                "rotation": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
                "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
                "material": {"variant": {"name": "default"}},
                "niagara": {"variant": {"name": "none"}},
                "sequencer": {"playback_range": {"start_frame": 0, "end_frame": 0}},
                "blueprint": {"asset_path": "/Game/AtlasTest/BP_AtlasTest", "compile_status": "success"},
                "render": {
                    "width": 640, "height": 360, "start_frame": 0, "end_frame": 0,
                    "output_directory": "Saved/Default", "output_format": "png",
                },
            }
        }

    def _observe(self, request):
        return {entity_id: dict(self.state[entity_id]) for entity_id in request.entity_ids}

    def send(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        index = len(self.calls)
        self.calls.append(request)
        if self.fail_at == index:
            return UnrealTransportResponse(
                request_id=request.request_id,
                operation_name=request.operation_name,
                entity_ids=request.entity_ids,
                success=False,
                error="injected production failure",
                observed_state={},
                source="heterogeneous-production-test",
            )

        args = request.arguments
        for entity_id in request.entity_ids:
            state = self.state[entity_id]
            if request.operation_name == "set_actor_location":
                state["location"] = dict(args["location"])
            elif request.operation_name == "set_actor_rotation":
                state["rotation"] = dict(args["rotation"])
            elif request.operation_name == "set_actor_scale":
                state["scale"] = dict(args["scale"])
            elif request.operation_name == "apply_material_variant":
                state["material"] = {"variant": dict(args["material_variant"])}
            elif request.operation_name == "apply_niagara_variant":
                state["niagara"] = {"variant": dict(args["niagara_variant"])}
            elif request.operation_name == "set_sequencer_playback_range":
                state["sequencer"] = {"playback_range": {
                    "start_frame": args["start_frame"], "end_frame": args["end_frame"]
                }}
            elif request.operation_name == "compile_blueprint":
                state["blueprint"] = {"asset_path": args["asset_path"], "compile_status": "success"}
            elif request.operation_name == "configure_render":
                state["render"] = {key: args[key] for key in (
                    "width", "height", "start_frame", "end_frame", "output_directory", "output_format"
                )}

        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=True,
            error="",
            observed_state=self._observe(request),
            source="heterogeneous-production-test",
        )


def _intent():
    return UnrealTaskIntent("production-roundtrip", "full heterogeneous production", (TARGET,))


def _spec():
    return UnrealProductionSpec(
        composite=build_composite_actor_operation([TARGET], [
            {"name": "set_actor_location", "location": {"x": 10.0, "y": 20.0, "z": 30.0}},
            {"name": "set_actor_rotation", "rotation": {"pitch": 0.0, "yaw": 15.0, "roll": 0.0}},
            {"name": "set_actor_scale", "scale": {"x": 1.1, "y": 1.1, "z": 1.1}},
            {"name": "apply_material_variant", "variant": "liquid_surface"},
            {"name": "apply_niagara_variant", "variant": "goal_burst"},
        ]),
        start_frame=1,
        end_frame=24,
        render_config=UnrealRenderConfig(
            width=1280, height=720, start_frame=1, end_frame=24,
            output_directory="Saved/AtlasProductionOutput", output_format="png",
        ),
        blueprint_asset_path="/Game/AtlasTest/BP_AtlasTest",
    )


def test_full_heterogeneous_production_roundtrip():
    transport = ProductionTransport()
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport, "heterogeneous-production-test"))
    production = build_unreal_production_plan(_intent(), _spec())

    result = executor.execute(production.plan, "production-roundtrip-auth")

    assert result.success is True
    assert len(result.evidence_ledger) == len(production.plan.operations)
    assert result.evidence_ledger[-1].verified is True
    assert [name for name, _, _ in production.phases] == ["blueprint", "actor_composite", "sequencer", "render"]
    assert transport.state[TARGET]["material"]["variant"]["name"] == "liquid_surface"
    assert transport.state[TARGET]["niagara"]["variant"]["name"] == "goal_burst"
    assert transport.state[TARGET]["sequencer"]["playback_range"] == {"start_frame": 1, "end_frame": 24}
    assert transport.state[TARGET]["render"]["width"] == 1280
    assert transport.state[TARGET]["render"]["height"] == 720


def test_failure_boundary_preserves_completed_evidence():
    # Operation 11 is apply_material_variant. Blueprint and actor phases have
    # completed, and material inspection has completed, before the mutation fails.
    transport = ProductionTransport(fail_at=11)
    executor = UnrealPlanExecutor(UnrealAdapterProduction(transport, "heterogeneous-failure-test"))
    production = build_unreal_production_plan(_intent(), _spec())

    with pytest.raises(UnrealPlanExecutionError) as exc_info:
        executor.execute(production.plan, "production-failure-auth")

    failure = exc_info.value.failure
    assert failure is not None
    assert failure.operation_index == 11
    assert failure.operation_name == "apply_material_variant"
    assert len(failure.completed_evidence) == 11
    assert failure.completed_evidence[-1].operation_name == "inspect_material_state"
    assert len(failure.completed_operation_arguments) == 11
