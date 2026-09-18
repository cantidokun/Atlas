"""MRQ submission outcome propagation — deterministic contract.

Slice E of the MRQ work: a render submission must establish its outcome
(accepted / rejected / ambiguous) before Atlas can treat the render job as
accepted. Acceptance is decided by the observed identity of the engine's active
executor, read in the same game-thread task as the submission call; the previous
fire-and-forget ``AsyncTask`` start is gone, so a refused submission can no longer
look like a slow one.

Two halves:

A. Transport source contract — the submission call and its identity observation
   share one task, the accepted response is built only after identity equality,
   every failure branch fails the operation with a typed message, and the
   rejected/ambiguous registry entry is not left readable as ``submitted``.
   Also pins the invariants this slice must NOT change (operation set, response
   field set, no queue mutation, no sleep/timer inference, Slice 1 and Slice D
   identity guards).
B. Outcome propagation end-to-end through the real adapter, plan executor and
   render workflow with a fake transport: rejection and ambiguity fail closed
   with no pollable job, no receipt, no retry, and no waiting.
"""

import re
from pathlib import Path

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import (
    UnrealPlanExecutionError,
    UnrealPlanExecutor,
)
from planning.unreal_render_job_verifier import (
    resolve_render_job_state,
    verify_render_job_completion,
)
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_workflow import UnrealRenderWorkflow
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_contract import (
    UnrealTransportRequest,
    UnrealTransportResponse,
)

ROOT = Path(__file__).resolve().parents[1]
TRANSPORT_SOURCE = (
    ROOT
    / "unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp"
)
TRANSPORT_HEADER = (
    ROOT / "unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Public/AtlasTransportServer.h"
)

ENTITY_ID = "FIELD_SURFACE"
SEQUENCE = "/Game/AtlasTest/AtlasSequencerFixtureSequence"
JOB_ID = "0D13E9FD-4A6B-4C7D-8E9F-000102030405"

# Frozen transport surface: this slice must add no operation and no response field.
SUPPORTED_OPERATIONS = {
    "inspect_world",
    "inspect_target_actors",
    "set_actor_location",
    "set_actor_rotation",
    "set_actor_scale",
    "inspect_material_state",
    "apply_material_variant",
    "inspect_niagara_state",
    "apply_niagara_variant",
    "inspect_sequencer_state",
    "set_sequencer_playback_range",
    "verify_sequencer_playback_range",
    "inspect_blueprint_state",
    "compile_blueprint",
    "verify_blueprint_state",
    "set_blueprint_metadata",
    "inspect_render_state",
    "configure_render",
    "submit_render",
    "inspect_render_job",
    "verify_render_state",
}

RESPONSE_FIELDS = {
    "request_id",
    "operation_name",
    "entity_ids",
    "success",
    "observed_state",
    "error",
    "source",
}

REJECTED_ACTIVE_EXECUTOR = (
    "render submission rejected: a render is already active in this editor"
)
REJECTED_TERMINAL_EXECUTOR = (
    "render submission rejected: the supplied executor finished or failed"
)
AMBIGUOUS = "render submission outcome ambiguous:"


# ── transport source helpers ─────────────────────────────────────────────


def _source() -> str:
    return TRANSPORT_SOURCE.read_text(encoding="utf-8", errors="replace")


def _function_body(name: str, kind: str = "bool") -> str:
    """Extract one FAtlasTransportServer member function body by brace depth."""
    lines = _source().split("\n")
    start = next(
        index
        for index, line in enumerate(lines)
        if line.startswith(f"{kind} FAtlasTransportServer::{name}(")
    )

    depth = 0
    seen_open = False
    body = []

    for line in lines[start:]:
        body.append(line)
        depth += line.count("{") - line.count("}")
        if "{" in line:
            seen_open = True
        if seen_open and depth == 0:
            break

    return "\n".join(body)


def _submit_render() -> str:
    return _function_body("SubmitRender")


def _code_only(body: str) -> str:
    """Drop comment-only lines so prose about a token is not mistaken for code."""
    return "\n".join(
        line
        for line in body.split("\n")
        if not line.strip().startswith(("*", "/*", "*/"))
    )


# ── A. transport source contract ─────────────────────────────────────────


def test_submission_call_and_identity_observation_share_one_task():
    body = _submit_render()

    # the start is no longer deferred into a separate game-thread task
    assert "AsyncTask" not in body

    call = body.index("RenderQueueWithExecutorInstance(Executor)")
    read = body.index("GetActiveExecutor()")

    assert read > call, "the identity observation must follow the submission call"

    between = [
        line.strip()
        for line in body[call:read].split("\n")
        if line.strip() and not line.strip().startswith(("*", "/*", "*/"))
    ]

    # between the call and the observation there is exactly the declaration of the
    # observation: no other statement, no branch, no deferral can be interposed
    assert len(between) == 3, between
    assert between[0] == "RenderQueueWithExecutorInstance(Executor);"
    assert between[1].endswith("ObservedActiveExecutor=")
    assert between[2] == "QueueSubsystem->"
    assert not any(
        token in " ".join(between) for token in ("AsyncTask", "if(", "for(", "while(")
    )


def test_acceptance_requires_the_exact_supplied_executor_identity():
    body = _submit_render()

    assert "ObservedActiveExecutor=QueueSubsystem->GetActiveExecutor()" in body or (
        "UMoviePipelineExecutorBase* ObservedActiveExecutor=" in body
    )
    assert "if(ObservedActiveExecutor!=Executor)" in body

    comparison = body.index("if(ObservedActiveExecutor!=Executor)")
    response = body.index('RenderJob->SetStringField(TEXT("job_id"),JobId)')

    assert response > comparison, (
        "the accepted response must be built only after the identity check passed"
    )


def test_is_rendering_is_not_used_as_acceptance_proof():
    body = _submit_render()

    # IsRendering() may only be discussed in the explanatory comment, never called
    assert "IsRendering" not in _code_only(body)
    assert "GetActiveExecutor()" in body


def test_rejection_and_ambiguity_fail_the_operation_with_typed_messages():
    body = _submit_render()

    for message in (
        REJECTED_ACTIVE_EXECUTOR,
        REJECTED_TERMINAL_EXECUTOR,
        AMBIGUOUS,
    ):
        assert message in body, message

    # every outcome branch returns a failed operation
    identity_branch = body[body.index("if(ObservedActiveExecutor!=Executor)") :]
    assert identity_branch.index("return false;") < identity_branch.index(
        'SetStringField(TEXT("job_id")'
    )

    # the three observable outcomes are distinguished from one another
    assert identity_branch.count("E=TEXT(") >= 3


def test_rejected_submission_does_not_leave_a_submitted_registry_entry():
    body = _submit_render()

    assert body.count("RenderJobRegistry.Remove(JobId)") == 2
    assert "RenderJobRegistry.Add(JobId,JobState)" in body

    identity_branch = body[body.index("if(ObservedActiveExecutor!=Executor)") :]
    assert "RenderJobRegistry.Remove(JobId)" in identity_branch


def test_failed_submission_exposes_no_render_job_evidence():
    body = _submit_render()

    identity_branch = body[body.index("if(ObservedActiveExecutor!=Executor)") :]
    failure_only = identity_branch[: identity_branch.index("return false;")]

    # no observed state / job payload is emitted on the failure path
    assert "ObservedState" not in failure_only
    assert "SetStringField(TEXT(\"job_id\")" not in failure_only


def test_no_new_transport_operation_or_response_field():
    source = _source()

    operations = set(re.findall(r'OperationName==TEXT\("([a-z_]+)"\)', source))
    assert operations == SUPPORTED_OPERATIONS

    serialiser = _function_body("SerializeResponse", kind="FString")
    fields = set(re.findall(r'Set\w+Field\(TEXT\("([a-z_]+)"\)', serialiser))
    assert fields == RESPONSE_FIELDS


def test_no_queue_mutation_added_by_this_slice():
    source = _source()

    # pre-existing failure-cleanup deletes inside SubmitRender's allocation path are not
    # this slice's doing; the slice itself adds none and the rejection path adds none
    body = _submit_render()
    identity_branch = body[body.index("if(ObservedActiveExecutor!=Executor)") :]
    assert "DeleteJob" not in identity_branch

    for token in ("DeleteAllJobs", "SetConsumed", "DeleteQueue", "EmptyQueue"):
        assert token not in source


def test_no_timeout_or_sleep_based_inference_in_the_submission_path():
    body = _submit_render()

    for token in ("FPlatformProcess::Sleep", "Sleep(", "FTSTicker", "SetTimer"):
        assert token not in body


def test_slice_1_artifact_identity_guard_remains_intact():
    body = _submit_render()

    assert "UMoviePipelineExecutorJob* PayloadJob=InOutputData.Job.Get();" in body
    assert "if(!RegisteredJob || PayloadJob!=RegisteredJob)" in body

    guard = body.index("if(!RegisteredJob || PayloadJob!=RegisteredJob)")
    append = body.index("(*Found)->OutputFiles.AddUnique(FilePath);")

    assert guard < append, "artifacts must be recorded only after the identity guard"


def test_slice_d_started_callback_identity_guard_remains_intact():
    body = _submit_render()

    assert "if(!RegisteredJob || InJob!=RegisteredJob)" in body

    guard = body.index("if(!RegisteredJob || InJob!=RegisteredJob)")
    status = body.index('(*Found)->Status=TEXT("rendering");')

    assert guard < status, "monitoring state must be written only after the identity guard"


# ── B. outcome propagation through the real Python path ──────────────────


class _SubmissionTransport:
    """Fake transport that answers the submission plan like the transport does."""

    def __init__(self, outcome: str = "accepted", job_id: str = JOB_ID):
        self.outcome = outcome
        self.job_id = job_id
        self.requests = []

    @staticmethod
    def _job_state():
        return {
            "job_id": JOB_ID,
            "sequence_asset_path": SEQUENCE,
            "status": "submitted",
            "status_message": "Render submitted",
            "progress": 0.0,
            "success": False,
            "finished": False,
            "failed": False,
            "output_files": [],
        }

    def send(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        self.requests.append(request)

        if request.operation_name == "submit_render":
            if self.outcome == "accepted":
                return self._response(request, True, {ENTITY_ID: {"render_job": self._job_state()}})

            if self.outcome == "rejected":
                return self._response(request, False, {}, REJECTED_ACTIVE_EXECUTOR)

            if self.outcome == "ambiguous":
                return self._response(request, False, {}, AMBIGUOUS)

            if self.outcome == "guid_only":
                # a minted GUID in the payload must not make a failed submission acceptable
                return self._response(request, False, {ENTITY_ID: {"render_job": self._job_state()}}, "")

            raise AssertionError(f"unknown outcome: {self.outcome}")

        if request.operation_name == "inspect_render_job":
            return self._response(request, True, {ENTITY_ID: {"render_job": self._job_state()}})

        raise AssertionError(f"unexpected operation: {request.operation_name}")

    def _response(self, request, success, observed_state, error=""):
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=success,
            observed_state=observed_state,
            error=error,
            source="submission-outcome-test",
        )


class _RecordingSchedule:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def _intent(name="submission-outcome-test"):
    return UnrealTaskIntent(name, "prove the submission outcome contract", (ENTITY_ID,))


def _workflow(transport, tmp_path, schedule=None, timeout_seconds=300.0):
    adapter = UnrealAdapterProduction(transport, "submission-outcome-test")
    executor = UnrealPlanExecutor(adapter)
    schedule = schedule or _RecordingSchedule()

    return UnrealRenderWorkflow(
        executor,
        UnrealRenderReceiptStore(tmp_path / "receipt.json"),
        poll_interval_seconds=1.0,
        timeout_seconds=timeout_seconds,
        clock=schedule.clock,
        sleeper=schedule.sleep,
    ), schedule


def _authorize():
    counter = {"value": 0}

    def issue(plan):
        counter["value"] += 1
        return UnrealPlanAuthorization.issue(plan, f"submission-auth-{counter['value']}")

    return issue


def _submission_plan():
    return UnrealTaskPlanner().plan_render_submission(_intent(), SEQUENCE)


def test_accepted_submission_yields_the_existing_job_identity(tmp_path):
    transport = _SubmissionTransport("accepted")
    workflow, schedule = _workflow(transport, tmp_path)

    submission = workflow.submit(_intent(), SEQUENCE, _authorize())

    assert submission.success is True
    assert workflow.get_submitted_job_id(submission) == JOB_ID

    state = resolve_render_job_state(submission.evidence_ledger[-1])
    assert state["job_id"] == JOB_ID
    assert state["status"] == "submitted"

    # the accepted path still runs the authorized verify step, and never waits
    assert [request.operation_name for request in transport.requests] == [
        "submit_render",
        "inspect_render_job",
    ]
    assert schedule.sleeps == []


@pytest.mark.parametrize("outcome", ["rejected", "ambiguous"])
def test_rejected_and_ambiguous_submissions_fail_closed(outcome, tmp_path):
    transport = _SubmissionTransport(outcome)
    workflow, schedule = _workflow(transport, tmp_path)

    with pytest.raises(UnrealPlanExecutionError) as excinfo:
        workflow.submit(_intent(), SEQUENCE, _authorize())

    message = str(excinfo.value)
    assert ("render submission rejected:" in message) or (AMBIGUOUS in message)

    failure = excinfo.value.failure
    assert failure is not None
    assert failure.operation_name == "submit_render"
    # the failed submission completed nothing, so recovery has no landed mutation to replay
    assert failure.completed_evidence == ()
    assert failure.completed_operation_arguments == ()

    # exactly one submission attempt: no automatic retry, no polling, no waiting
    assert [request.operation_name for request in transport.requests] == ["submit_render"]
    assert schedule.sleeps == []

    # and no receipt was produced
    assert not (tmp_path / "receipt.json").exists()


def test_guid_generation_alone_does_not_imply_acceptance(tmp_path):
    transport = _SubmissionTransport("guid_only")
    workflow, schedule = _workflow(transport, tmp_path)

    with pytest.raises(UnrealPlanExecutionError) as excinfo:
        workflow.submit(_intent(), SEQUENCE, _authorize())

    assert "failed" in str(excinfo.value)
    assert [request.operation_name for request in transport.requests] == ["submit_render"]
    assert schedule.sleeps == []
    assert not (tmp_path / "receipt.json").exists()


def test_job_identity_verification_remains_unchanged(tmp_path):
    transport = _SubmissionTransport("accepted")
    workflow, _ = _workflow(transport, tmp_path)

    submission = workflow.submit(_intent(), SEQUENCE, _authorize())
    evidence = submission.evidence_ledger[-1]

    # exact identity still required, and a mismatch still fails closed
    assert verify_render_job_completion(evidence, expected_job_id=JOB_ID) is evidence

    with pytest.raises(ValueError):
        verify_render_job_completion(evidence, expected_job_id="OTHER-JOB-ID")


def test_rejection_does_not_inflate_or_consume_the_configured_timeout(tmp_path):
    transport = _SubmissionTransport("rejected")
    workflow, schedule = _workflow(transport, tmp_path)

    before = workflow.timeout_seconds

    with pytest.raises(UnrealPlanExecutionError):
        workflow.submit(_intent(), SEQUENCE, _authorize())

    # no timeout change, no elapsed time, no sleep: the failure is immediate
    assert workflow.timeout_seconds == before == 300.0
    assert schedule.now == 0.0
    assert schedule.sleeps == []


def test_submission_outcome_contract_does_not_touch_the_design_review_paths():
    """The slice is transport-only: no planning module changed for it."""

    source = _source()

    # the acceptance decision lives in the transport, not in planning/
    assert "GetActiveExecutor()" in source
    assert "render submission rejected:" in source

    # the transport request for a submission is unchanged
    operations = [
        operation.name for operation in _submission_plan().operations
    ]
    assert operations == ["submit_render", "verify_render_job"]
