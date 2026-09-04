"""Deterministic tests for heterogeneous Unreal production orchestration."""

from dataclasses import dataclass

import pytest

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionResult
from planning.unreal_production_executor import UnrealProductionExecutionResult, UnrealProductionExecutor
from planning.unreal_production_operation import UnrealProductionPlan
from planning.unreal_production_workflow import (
    UnrealProductionWorkflow,
    UnrealProductionWorkflowError,
    UnrealProductionWorkflowResult,
)
from planning.unreal_render_receipt import UnrealRenderReceipt
from planning.unreal_render_workflow import (
    UnrealRenderWorkflow,
    UnrealRenderWorkflowResult,
)
from planning.unreal_task_planner import UnrealTaskIntent, UnrealTaskPlanner


class FakeProductionExecutor(UnrealProductionExecutor):
    def __init__(self, *, success=True):
        self.calls = []
        self.success = success

    def execute(self, production, authorization, **kwargs):
        self.calls.append((production, authorization, kwargs))
        initial = UnrealPlanExecutionResult(
            intent_id=production.plan.intent_id,
            evidence_ledger=(),
            success=self.success,
        ) if self.success else None
        return UnrealProductionExecutionResult(
            production=production,
            initial_result=initial,
            failure=None if self.success else object(),
            recovery=None,
        )


class FakeRenderWorkflow(UnrealRenderWorkflow):
    def __init__(self, *, submit_success=True, final_result=None):
        self.submit_calls = []
        self.wait_calls = []
        self.submit_success = submit_success
        self.final_result = final_result

    def submit(self, intent, sequence_asset_path, authorization_factory):
        self.submit_calls.append(
            (intent, sequence_asset_path, authorization_factory)
        )
        if not self.submit_success:
            raise UnrealProductionWorkflowError(
                "render submission failed"
            )
        return _submission_result(intent)

    def wait_for_completion(
        self,
        intent,
        job_id,
        authorization_factory,
    ):
        self.wait_calls.append(
            (intent, job_id, authorization_factory)
        )
        if self.final_result is not None:
            return self.final_result
        return _completed_render(intent)


def _production(intent_id="production-workflow"):
    intent = _intent(intent_id)
    plan = UnrealTaskPlanner().plan_inspection(intent)
    return UnrealProductionPlan(
        plan=plan,
        phases=(("inspection", 0, len(plan.operations)),),
    )


def _intent(intent_id="production-workflow"):
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="deterministic production workflow test",
        target_entity_ids=("FIELD_SURFACE",),
    )


def _authorization(production):
    return UnrealPlanAuthorization.issue(
        production.plan,
        "production-auth",
    )


def _submission_result(intent):
    evidence = UnrealEvidence(
        operation_name="verify_render_job",
        entity_ids=("FIELD_SURFACE",),
        observed_state={
            "FIELD_SURFACE": {
                "render_job": {
                    "job_id": "job-123",
                    "status": "queued",
                    "finished": False,
                    "success": False,
                    "failed": False,
                    "output_files": [],
                }
            }
        },
        source="production-workflow-test",
        verified=True,
    )
    return UnrealPlanExecutionResult(
        intent_id=intent.intent_id,
        evidence_ledger=(evidence,),
        success=True,
    )


def _completed_render(intent):
    evidence = UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=("FIELD_SURFACE",),
        observed_state={
            "job_id": "job-123",
            "sequence_asset_path": "/Game/AtlasTest/AtlasSequencerFixtureSequence",
            "status": "finished",
            "finished": True,
            "success": True,
            "failed": False,
            "output_files": ["Saved/AtlasRenderOutput/AtlasRender_0001.png"],
        },
        source="production-workflow-test",
        verified=True,
    )
    receipt = UnrealRenderReceipt.issue(evidence)
    return UnrealRenderWorkflowResult(
        intent_id=intent.intent_id,
        job_id="job-123",
        final_evidence=evidence,
        receipt=receipt,
        persisted_receipt={
            "job_id": "job-123",
            "sequence_asset_path": receipt.sequence_asset_path,
            "evidence_digest": receipt.evidence_digest,
            "receipt_digest": receipt.receipt_digest,
        },
    )


def _workflow(
    *,
    production_success=True,
    render_submit_success=True,
    final_result=None,
):
    production = FakeProductionExecutor(success=production_success)
    render = FakeRenderWorkflow(
        submit_success=render_submit_success,
        final_result=final_result,
    )
    workflow = UnrealProductionWorkflow(production, render)
    return workflow, production, render


def test_successful_production_then_render_returns_verified_workflow_result():
    workflow, production_executor, render_workflow = _workflow()

    production = _production()
    intent = _intent()
    production_auth = _authorization(production)

    result = workflow.run(
        production,
        production_auth,
        intent,
        "/Game/AtlasTest/AtlasSequencerFixtureSequence",
        lambda plan: UnrealPlanAuthorization.issue(
            plan,
            "render-auth",
        ),
    )

    assert result.success is True
    assert result.verified_render is True
    assert production_executor.calls
    assert len(render_workflow.submit_calls) == 1
    assert len(render_workflow.wait_calls) == 1
    assert render_workflow.submit_calls[0][1] == (
        "/Game/AtlasTest/AtlasSequencerFixtureSequence"
    )
    assert render_workflow.wait_calls[0][1] == "job-123"


def test_workflow_success_requires_verified_render_identity():
    production = FakeProductionExecutor()
    execution = production.execute(
        _production(),
        _authorization(_production()),
    )
    good_render = _completed_render(_intent())
    invalid_render = UnrealRenderWorkflowResult(
        intent_id=good_render.intent_id,
        job_id=good_render.job_id,
        final_evidence=object(),
        receipt=good_render.receipt,
        persisted_receipt=good_render.persisted_receipt,
    )

    result = UnrealProductionWorkflowResult(
        production=execution,
        render=invalid_render,
    )

    assert result.verified_render is False
    assert result.success is False


def test_failed_production_prevents_render_submission():
    workflow, _, render_workflow = _workflow(
        production_success=False,
    )

    with pytest.raises(
        UnrealProductionWorkflowError,
        match="heterogeneous Unreal production did not complete",
    ):
        workflow.run(
            _production(),
            _authorization(_production()),
            _intent(),
            "/Game/AtlasTest/AtlasSequencerFixtureSequence",
            lambda plan: UnrealPlanAuthorization.issue(plan, "render-auth"),
        )

    assert render_workflow.submit_calls == []
    assert render_workflow.wait_calls == []


def test_render_submission_failure_is_propagated_after_successful_production():
    workflow, production_executor, render_workflow = _workflow(
        render_submit_success=False,
    )

    with pytest.raises(
        UnrealProductionWorkflowError,
        match="render submission failed",
    ):
        workflow.run(
            _production(),
            _authorization(_production()),
            _intent(),
            "/Game/AtlasTest/AtlasSequencerFixtureSequence",
            lambda plan: UnrealPlanAuthorization.issue(plan, "render-auth"),
        )

    assert production_executor.calls
    assert len(render_workflow.submit_calls) == 1
    assert render_workflow.wait_calls == []


def test_production_authorization_must_match_exact_plan():
    workflow, production_executor, render_workflow = _workflow()

    production = _production("production-a")
    wrong = _production("production-b")

    with pytest.raises(
        UnrealProductionWorkflowError,
        match="does not match the exact production plan",
    ):
        workflow.run(
            production,
            _authorization(wrong),
            _intent("production-a"),
            "/Game/AtlasTest/AtlasSequencerFixtureSequence",
            lambda plan: UnrealPlanAuthorization.issue(plan, "render-auth"),
        )

    assert production_executor.calls == []
    assert render_workflow.submit_calls == []


def test_empty_sequence_path_is_rejected_before_production_execution():
    workflow, production_executor, render_workflow = _workflow()
    production = _production()

    with pytest.raises(ValueError, match="sequence_asset_path"):
        workflow.run(
            production,
            _authorization(production),
            _intent(),
            "   ",
            lambda plan: UnrealPlanAuthorization.issue(plan, "render-auth"),
        )

    assert production_executor.calls == []
    assert render_workflow.submit_calls == []


def test_render_failure_does_not_reexecute_completed_production():
    completed = _completed_render(_intent())
    workflow, production_executor, render_workflow = _workflow(
        final_result=completed,
    )

    production = _production()
    result = workflow.run(
        production,
        _authorization(production),
        _intent(),
        "/Game/AtlasTest/AtlasSequencerFixtureSequence",
        lambda plan: UnrealPlanAuthorization.issue(plan, "render-auth"),
    )

    assert result.render is completed
    assert len(production_executor.calls) == 1
    assert len(render_workflow.submit_calls) == 1
    assert len(render_workflow.wait_calls) == 1
