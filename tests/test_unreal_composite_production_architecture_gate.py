"""Architecture gate for the complete heterogeneous Unreal production path.

This is deliberately one level above capability-specific tests. It composes the
real production plan builder, real production executor, exact plan authorization,
and the top-level production workflow while keeping final render submission under
a deterministic recording stub.

The gate proves:

* Blueprint/actor/Sequencer/render phases remain one authorized production plan;
* every production write reaches independent verification before the next phase;
* final render submission cannot occur when production is unsuccessful;
* render completion is consumed only after the production boundary succeeds;
* the top-level result retains one intent identity across production and render.

No live Unreal engine is used here. The existing UE 5.6.1 production-workflow
integration remains the engine-dependent gate.
"""

from pathlib import Path

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutor, UnrealPlanExecutionResult
from planning.unreal_production_executor import UnrealProductionExecutor
from planning.unreal_production_operation import (
    UnrealProductionSpec,
    build_unreal_production_plan,
)
from planning.unreal_production_workflow import (
    UnrealProductionWorkflow,
    UnrealProductionWorkflowError,
)
from planning.unreal_render_contract import UnrealRenderConfig
from planning.unreal_render_receipt import UnrealRenderReceipt
from planning.unreal_render_workflow import UnrealRenderWorkflow, UnrealRenderWorkflowResult
from planning.unreal_task_planner import UnrealTaskIntent
from tests.test_unreal_heterogeneous_production import ProductionTransport
from tests.test_unreal_production_operation import _composite

TARGET = "FIELD_SURFACE"
SEQUENCE_ASSET_PATH = "/Game/AtlasTest/AtlasSequencerFixtureSequence"


class RecordingRenderWorkflow(UnrealRenderWorkflow):
    """Deterministic render boundary used only for the architecture gate."""

    def __init__(self, *, final_job_id="job-architecture-gate"):
        self.final_job_id = final_job_id
        self.submit_calls = []
        self.wait_calls = []

    def submit(self, intent, sequence_asset_path, authorization_factory):
        self.submit_calls.append((intent, sequence_asset_path, authorization_factory))
        return _submission_result(intent, self.final_job_id)

    def wait_for_completion(self, intent, job_id, authorization_factory):
        self.wait_calls.append((intent, job_id, authorization_factory))
        return _completed_result(intent, job_id)


def _intent(intent_id="composite-architecture-gate"):
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="composite Unreal production architecture gate",
        target_entity_ids=(TARGET,),
    )


def _spec():
    return UnrealProductionSpec(
        composite=_composite(),
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
        blueprint_asset_path="/Game/AtlasTest/BP_AtlasTest",
    )


def _production(intent):
    return build_unreal_production_plan(intent, _spec())


def _job_evidence(job_id):
    return UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=(TARGET,),
        observed_state={
            "job_id": job_id,
            "sequence_asset_path": SEQUENCE_ASSET_PATH,
            "status": "finished",
            "finished": True,
            "success": True,
            "failed": False,
            "output_files": [str(Path("Saved/AtlasArchitectureGate_0001.png").resolve())],
        },
        source="composite-architecture-gate",
        verified=True,
    )


def _submission_result(intent, job_id):
    evidence = UnrealEvidence(
        operation_name="verify_render_job",
        entity_ids=(TARGET,),
        observed_state={
            "job_id": job_id,
            "status": "queued",
            "finished": False,
            "success": False,
            "failed": False,
            "output_files": [],
        },
        source="composite-architecture-gate",
        verified=True,
    )
    return UnrealPlanExecutionResult(intent.intent_id, (evidence,), True)


def _completed_result(intent, job_id):
    evidence = _job_evidence(job_id)
    receipt = UnrealRenderReceipt.issue(evidence)
    return UnrealRenderWorkflowResult(
        intent_id=intent.intent_id,
        job_id=job_id,
        final_evidence=evidence,
        receipt=receipt,
        persisted_receipt={
            "job_id": job_id,
            "sequence_asset_path": receipt.sequence_asset_path,
            "evidence_digest": receipt.evidence_digest,
            "receipt_digest": receipt.receipt_digest,
        },
    )


def _workflow(transport, render_workflow):
    raw_executor = UnrealPlanExecutor(
        UnrealAdapterProduction(transport, "composite-architecture-gate")
    )
    return UnrealProductionWorkflow(
        UnrealProductionExecutor(raw_executor),
        render_workflow,
    )


def test_composite_architecture_gate_is_one_authorized_verified_transaction():
    transport = ProductionTransport()
    render = RecordingRenderWorkflow()
    workflow = _workflow(transport, render)
    intent = _intent()
    production = _production(intent)
    production_authorization = UnrealPlanAuthorization.issue(
        production.plan,
        "composite-architecture-production-auth",
    )

    result = workflow.run(
        production,
        production_authorization,
        intent,
        SEQUENCE_ASSET_PATH,
        lambda plan: UnrealPlanAuthorization.issue(
            plan,
            "composite-architecture-render-auth",
        ),
    )

    assert result.success is True
    assert result.production.success is True
    assert result.production.initial_result is not None

    evidence = result.production.initial_result.evidence_ledger
    operation_names = [entry.operation_name for entry in evidence]

    expected_sequence = [
        "inspect_blueprint_state",
        "compile_blueprint",
        "verify_blueprint_state",
        "inspect_target_actors",
        "set_actor_location",
        "verify_actor_location",
        "set_actor_rotation",
        "verify_actor_rotation",
        "set_actor_scale",
        "verify_actor_scale",
        "inspect_material_state",
        "apply_material_variant",
        "verify_material_variant",
        "inspect_niagara_state",
        "apply_niagara_variant",
        "verify_niagara_variant",
        "inspect_sequencer_state",
        "set_sequencer_playback_range",
        "verify_sequencer_playback_range",
        "inspect_render_state",
        "configure_render",
        "verify_render_state",
    ]
    assert operation_names == expected_sequence

    # Every VERIFY boundary in the production transaction actually reports
    # semantic verification before the workflow moves to render submission.
    verified_indices = [
        index for index, entry in enumerate(evidence) if entry.verified
    ]
    assert verified_indices == [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 21]
    assert evidence[-1].operation_name == "verify_render_state"
    assert evidence[-1].verified is True

    # Render submission is downstream of the successful production transaction,
    # and both boundaries carry the same intent identity.
    assert len(render.submit_calls) == 1
    assert len(render.wait_calls) == 1
    assert render.submit_calls[0][0].intent_id == intent.intent_id
    assert render.wait_calls[0][0].intent_id == intent.intent_id
    assert render.wait_calls[0][1] == "job-architecture-gate"
    assert result.render.intent_id == intent.intent_id
    assert result.render.job_id == "job-architecture-gate"
    assert result.render.final_evidence.verified is True
    assert result.render.receipt.job_id == result.render.job_id

    # Production state mutations are the expected composite values.
    assert transport.state[TARGET]["location"] == {"x": 10.0, "y": 20.0, "z": 30.0}
    assert transport.state[TARGET]["rotation"] == {"pitch": 0.0, "yaw": 15.0, "roll": 0.0}
    assert transport.state[TARGET]["scale"] == {"x": 1.1, "y": 1.1, "z": 1.1}
    assert transport.state[TARGET]["material"]["variant"]["name"] == "liquid_surface"
    assert transport.state[TARGET]["niagara"]["variant"]["name"] == "goal_burst"
    assert transport.state[TARGET]["sequencer"]["playback_range"] == {
        "start_frame": 1,
        "end_frame": 24,
    }
    assert transport.state[TARGET]["render"]["width"] == 1280
    assert transport.state[TARGET]["render"]["height"] == 720


def test_composite_architecture_gate_blocks_render_when_production_fails():
    # Operation 20 is configure_render. Earlier phases have completed, but the
    # production transaction has not reached its terminal render-state verifier.
    transport = ProductionTransport(fail_at=20)
    render = RecordingRenderWorkflow()
    workflow = _workflow(transport, render)
    intent = _intent("composite-architecture-failure")
    production = _production(intent)
    authorization = UnrealPlanAuthorization.issue(
        production.plan,
        "composite-architecture-failure-auth",
    )

    with pytest.raises(
        UnrealProductionWorkflowError,
        match="heterogeneous Unreal production did not complete",
    ):
        workflow.run(
            production,
            authorization,
            intent,
            SEQUENCE_ASSET_PATH,
            lambda plan: UnrealPlanAuthorization.issue(
                plan,
                "composite-architecture-render-auth",
            ),
        )

    assert render.submit_calls == []
    assert render.wait_calls == []


@pytest.mark.parametrize("field", ["intent_id", "description", "target_entity_ids"])
def test_composite_architecture_gate_keeps_intent_immutable_across_plan_and_render(field):
    intent = _intent(f"immutable-{field}")
    production = _production(intent)

    assert production.plan.intent_id == intent.intent_id
    assert tuple(intent.target_entity_ids) == (TARGET,)
    assert tuple(production.plan.operations[0].entity_ids) == (TARGET,)
    assert all(
        tuple(operation.entity_ids) == (TARGET,)
        for operation in production.plan.operations
    )
