"""Synthetic host-level proof for workflow-backed Unreal result contracts."""

from controller.agent_controller_host import AgentControllerHost
from controller.agent_task_request import AgentTaskRequest
from controller.trusted_unreal_context import TrustedUnrealContext
from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration
from planning.unreal_production_operation import build_unreal_production_plan
from planning.unreal_production_planning_boundary import authorize_production_plan
from planning.unreal_production_executor import UnrealProductionExecutor
from planning.unreal_production_runtime_adapter import UnrealProductionRuntimeAdapter
from planning.unreal_production_workflow import UnrealProductionWorkflow
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_render_receipt import UnrealRenderReceipt
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_workflow import UnrealRenderWorkflow, UnrealRenderWorkflowResult
from planning.unreal_plan_executor import UnrealPlanExecutionResult
from planning.unreal_task_planner import UnrealTaskIntent
from tests.test_unreal_heterogeneous_production import ProductionTransport, _spec


class FakeProductionExecutor(UnrealProductionExecutor):
    """Complete the production phase without contacting Unreal."""

    def __init__(self) -> None:
        self.calls = []

    def execute(self, production, authorization, **kwargs):
        self.calls.append((production, authorization, kwargs))
        return type(self)._result(production)

    @staticmethod
    def _result(production):
        from planning.unreal_production_executor import UnrealProductionExecutionResult

        return UnrealProductionExecutionResult(
            production=production,
            initial_result=UnrealPlanExecutionResult(
                intent_id=production.plan.intent_id,
                evidence_ledger=(),
                success=True,
            ),
            failure=None,
            recovery=None,
        )


def _intent():
    return UnrealTaskIntent(
        intent_id="host-workflow-result-contract",
        description="synthetic host workflow result contract",
        target_entity_ids=("FIELD_SURFACE",),
    )


def _verified_render(intent_id: str = "host-workflow-result-contract") -> UnrealRenderWorkflowResult:
    evidence = UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=("FIELD_SURFACE",),
        observed_state={
            "job_id": "host-workflow-job-1",
            "sequence_asset_path": "/Game/Trusted/Sequence",
            "status": "finished",
            "finished": True,
            "success": True,
            "failed": False,
            "output_files": ["Saved/AtlasRenderOutput/AtlasRender_0001.png"],
        },
        verified=True,
        source="synthetic-host-workflow-result-contract",
    )
    receipt = UnrealRenderReceipt.issue(evidence)
    return UnrealRenderWorkflowResult(
        intent_id=intent_id,
        job_id=receipt.job_id,
        final_evidence=evidence,
        receipt=receipt,
        persisted_receipt={
            "job_id": receipt.job_id,
            "sequence_asset_path": receipt.sequence_asset_path,
            "evidence_digest": receipt.evidence_digest,
            "receipt_digest": receipt.receipt_digest,
        },
    )


def _host(tmp_path):
    intent = _intent()
    production = build_unreal_production_plan(intent, _spec())
    authorized = authorize_production_plan(production, "host-workflow-production-auth")
    trusted = TrustedUnrealContext(
        authorized_production=authorized,
        intent=intent,
        sequence_asset_path="/Game/Trusted/Sequence",
    )

    raw_executor = UnrealPlanExecutor(
        UnrealAdapterProduction(ProductionTransport(), "host-workflow-result-contract")
    )
    runtime = UnrealProductionRuntimeAdapter(raw_executor)

    production_executor = FakeProductionExecutor()
    render_workflow = UnrealRenderWorkflow(
        raw_executor,
        UnrealRenderReceiptStore(tmp_path / "host-workflow-result-receipt.json"),
    )
    final_render = _verified_render(intent.intent_id)
    render_workflow.submit = lambda intent, sequence_asset_path, authorization_factory: (
        UnrealPlanExecutionResult(
            intent_id=intent.intent_id,
            evidence_ledger=(
                UnrealEvidence(
                    operation_name="submit_render_job",
                    entity_ids=("FIELD_SURFACE",),
                    observed_state={"job_id": final_render.job_id},
                    verified=True,
                    source="synthetic-host-workflow-submit",
                ),
            ),
            success=True,
        )
    )
    render_workflow.wait_for_completion = lambda intent, job_id, authorization_factory: final_render

    workflow = UnrealProductionWorkflow(production_executor, render_workflow)
    integration = UnrealProductionControllerIntegration(
        runtime,
        workflow=workflow,
        render_authorization_factory=lambda plan: UnrealPlanAuthorization.issue(
            plan,
            "host-workflow-render-auth",
        ),
    )

    return (
        AgentControllerHost.for_unreal_production(integration, trusted),
        production_executor,
    )


def test_host_exposes_verified_workflow_render_contract(tmp_path):
    host, production_executor = _host(tmp_path)

    result = host.dispatch(
        AgentTaskRequest(
            capability="production",
            provider="unreal",
            context={"production": True},
            intent="model-declared-intent",
        )
    )

    assert result.controller_executed is True
    assert result.result is not None
    assert result.result.capability_name == "unreal_production"
    assert result.result_contract is not None
    assert result.result_contract.success is True
    assert result.result_contract.intent_id == "host-workflow-result-contract"
    assert result.result_contract.job_id == "host-workflow-job-1"
    assert result.result_contract.verified_render is True
    assert result.result_contract.final_evidence.verified is True
    assert result.result_contract.receipt.job_id == "host-workflow-job-1"
    assert len(production_executor.calls) == 1
