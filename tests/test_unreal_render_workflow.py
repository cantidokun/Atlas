from dataclasses import dataclass
from pathlib import Path

import pytest

from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionResult
from planning.unreal_render_job_verifier import verify_render_job_completion
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_workflow import (
    UnrealRenderWorkflow,
    UnrealRenderWorkflowError,
)
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner


ENTITY_ID = "FIELD_SURFACE"
SEQUENCE = "/Game/AtlasTest/AtlasSequencerFixtureSequence"
CONFIG = {
    "width": 640,
    "height": 360,
    "start_frame": 1,
    "end_frame": 2,
    "output_directory": "Saved/AtlasRenderOutput",
    "output_format": "png",
}


def _intent(name="workflow-test"):
    return UnrealTaskIntent(
        name,
        "test complete render workflow",
        (ENTITY_ID,),
    )


def _evidence(state):
    return UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=(ENTITY_ID,),
        observed_state=state,
        verified=True,
        source="render-workflow-test",
    )


@dataclass
class FakeExecutor:
    states: list

    def __post_init__(self):
        self.calls = []

    def execute_authorized(self, plan, authorization):
        self.calls.append((plan, authorization))
        operation = plan.operations[0].name

        if operation == "inspect_render_state":
            return UnrealPlanExecutionResult(
                plan.intent_id,
                (_evidence({
                    ENTITY_ID: {
                        "render": dict(CONFIG),
                    }
                }),),
                True,
            )

        if operation == "configure_render":
            return UnrealPlanExecutionResult(
                plan.intent_id,
                (_evidence({
                    ENTITY_ID: {
                        "render": dict(CONFIG),
                    }
                }),),
                True,
            )

        if operation == "submit_render":
            return UnrealPlanExecutionResult(
                plan.intent_id,
                (_evidence({
                    ENTITY_ID: {
                        "render_job": {
                            "job_id": "job-workflow-1",
                            "sequence_asset_path": SEQUENCE,
                            "status": "queued",
                            "finished": False,
                            "success": False,
                            "failed": False,
                            "output_files": [],
                        }
                    }
                }),),
                True,
            )

        if operation == "inspect_render_job":
            state = self.states.pop(0)
            return UnrealPlanExecutionResult(
                plan.intent_id,
                (_evidence(dict(state)),),
                True,
            )

        raise AssertionError(f"unexpected operation: {operation}")


class RecordingClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def _authorization_factory():
    counter = {"value": 0}

    def issue(plan):
        counter["value"] += 1
        return UnrealPlanAuthorization.issue(
            plan,
            f"workflow-auth-{counter['value']}",
        )

    return issue, counter


def test_get_submitted_job_id_extracts_job_id():
    workflow = UnrealRenderWorkflow(
        FakeExecutor([]),
        UnrealRenderReceiptStore(Path("receipt-job-id.json")),
    )

    submission = UnrealPlanExecutionResult(
        "job-id-test",
        (
            _evidence({
                ENTITY_ID: {
                    "render_job": {
                        "job_id": "job-workflow-1",
                        "sequence_asset_path": SEQUENCE,
                        "status": "queued",
                        "finished": False,
                        "success": False,
                        "failed": False,
                        "output_files": [],
                    }
                }
            }),
        ),
        True,
    )

    assert workflow.get_submitted_job_id(submission) == "job-workflow-1"


def test_get_submitted_job_id_rejects_unsuccessful_submission(tmp_path):
    workflow = UnrealRenderWorkflow(
        FakeExecutor([]),
        UnrealRenderReceiptStore(tmp_path / "receipt-job-id.json"),
    )

    submission = UnrealPlanExecutionResult(
        "job-id-test",
        (),
        False,
    )

    with pytest.raises(
        UnrealRenderWorkflowError,
        match="render submission did not produce successful evidence",
    ):
        workflow.get_submitted_job_id(submission)


def test_workflow_polls_until_completed_and_persists_receipt(tmp_path):
    clock = RecordingClock()
    executor = FakeExecutor([
        {
            "job_id": "job-workflow-1",
            "sequence_asset_path": SEQUENCE,
            "status": "queued",
            "finished": False,
            "success": False,
            "failed": False,
            "output_files": [],
        },
        {
            "job_id": "job-workflow-1",
            "sequence_asset_path": SEQUENCE,
            "status": "rendering",
            "finished": False,
            "success": False,
            "failed": False,
            "output_files": [],
        },
        {
            "job_id": "job-workflow-1",
            "sequence_asset_path": SEQUENCE,
            "status": "finished",
            "finished": True,
            "success": True,
            "failed": False,
            "sequence_asset_path": SEQUENCE,
            "output_directory": "Saved/AtlasRenderOutput",
            "output_format": "png",
            "output_files": [
                str(tmp_path / "AtlasRender_0001.png"),
            ],
        },
    ])

    (tmp_path / "AtlasRender_0001.png").write_bytes(b"atlas-render")

    authorizer, counter = _authorization_factory()
    store = UnrealRenderReceiptStore(tmp_path / "receipt.json")

    workflow = UnrealRenderWorkflow(
        executor,
        store,
        poll_interval_seconds=2.0,
        timeout_seconds=10.0,
        clock=clock.clock,
        sleeper=clock.sleep,
    )

    result = workflow.run(
        _intent(),
        CONFIG,
        SEQUENCE,
        authorizer,
    )

    assert result.job_id == "job-workflow-1"
    assert result.receipt.job_id == "job-workflow-1"
    assert store.load() == result.receipt
    assert counter["value"] == 5
    assert clock.sleeps == [2.0, 2.0]


def test_workflow_stops_on_failed_job(tmp_path):
    clock = RecordingClock()
    executor = FakeExecutor([
        {
            "job_id": "job-failed",
            "sequence_asset_path": SEQUENCE,
            "status": "failed",
            "finished": False,
            "success": False,
            "failed": True,
            "output_files": [],
        },
    ])

    authorizer, _ = _authorization_factory()
    workflow = UnrealRenderWorkflow(
        executor,
        UnrealRenderReceiptStore(tmp_path / "receipt.json"),
        clock=clock.clock,
        sleeper=clock.sleep,
    )

    with pytest.raises(UnrealRenderWorkflowError, match="render job failed"):
        workflow.wait_for_completion(_intent(), "job-failed", authorizer)


def test_workflow_times_out_without_busy_waiting(tmp_path):
    clock = RecordingClock()
    executor = FakeExecutor([
        {
            "job_id": "job-timeout",
            "sequence_asset_path": SEQUENCE,
            "status": "rendering",
            "finished": False,
            "success": False,
            "failed": False,
            "output_files": [],
        }
    ] * 10)

    authorizer, _ = _authorization_factory()
    workflow = UnrealRenderWorkflow(
        executor,
        UnrealRenderReceiptStore(tmp_path / "receipt.json"),
        poll_interval_seconds=2.0,
        timeout_seconds=5.0,
        clock=clock.clock,
        sleeper=clock.sleep,
    )

    with pytest.raises(UnrealRenderWorkflowError, match="did not complete"):
        workflow.wait_for_completion(_intent(), "job-timeout", authorizer)

    assert clock.sleeps == [2.0, 2.0, 1.0]


def test_workflow_rejects_success_without_artifacts(tmp_path):
    clock = RecordingClock()
    executor = FakeExecutor([
        {
            "job_id": "job-no-artifacts",
            "sequence_asset_path": SEQUENCE,
            "status": "finished",
            "finished": True,
            "success": True,
            "failed": False,
            "output_directory": "Saved/AtlasRenderOutput",
            "output_format": "png",
            "output_files": [],
        },
    ])

    authorizer, _ = _authorization_factory()
    workflow = UnrealRenderWorkflow(
        executor,
        UnrealRenderReceiptStore(tmp_path / "receipt.json"),
        clock=clock.clock,
        sleeper=clock.sleep,
    )

    with pytest.raises(
        UnrealRenderWorkflowError,
        match="no output_files",
    ):
        workflow.wait_for_completion(_intent(), "job-no-artifacts", authorizer)


def test_workflow_never_acts_as_authority(tmp_path):
    executor = FakeExecutor([
        {
            "job_id": "job-auth",
            "sequence_asset_path": SEQUENCE,
            "status": "finished",
            "finished": True,
            "success": True,
            "failed": False,
            "output_directory": "Saved/AtlasRenderOutput",
            "output_format": "png",
            "output_files": [],
        },
    ])

    workflow = UnrealRenderWorkflow(
        executor,
        UnrealRenderReceiptStore(tmp_path / "receipt.json"),
    )

    with pytest.raises(TypeError, match="authorization_factory"):
        workflow.wait_for_completion(
            _intent("authority-test"),
            "job-auth",
            lambda plan: object(),
        )
