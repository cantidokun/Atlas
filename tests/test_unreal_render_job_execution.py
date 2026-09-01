from dataclasses import dataclass

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperationKind
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_task_planner import UnrealTaskIntent, UnrealTaskPlanner
from planning.unreal_transport_contract import UnrealTransportResponse
from planning.unreal_render_job_verifier import verify_render_job_completion


ENTITY_ID = "FIELD_SURFACE"


@dataclass
class RecordingRenderTransport:
    def __post_init__(self):
        self.requests = []

    def send(self, request):
        self.requests.append(request)

        if request.operation_name == "submit_render":
            state = {
                ENTITY_ID: {
                    "render_job": {
                        "job_id": "job-test-123",
                        "status": "queued",
                        "finished": False,
                        "success": False,
                        "failed": False,
                        "output_directory": "Saved/AtlasRenderOutput",
                        "output_format": "png",
                        "output_files": [],
                    }
                }
            }
        elif request.operation_name == "inspect_render_job":
            assert request.arguments["job_id"] == "job-test-123"
            state = {
                ENTITY_ID: {
                    "render_job": {
                        "job_id": "job-test-123",
                        "status": "queued",
                        "finished": False,
                        "success": False,
                        "failed": False,
                        "output_directory": "Saved/AtlasRenderOutput",
                        "output_format": "png",
                        "output_files": [],
                    }
                }
            }
        else:
            raise AssertionError(
                f"unexpected operation: {request.operation_name}"
            )

        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=True,
            observed_state=state,
            error="",
            source="test-render-job-runtime-binding",
        )


def _intent(intent_id):
    return UnrealTaskIntent(
        intent_id,
        "submit and verify a render job",
        (ENTITY_ID,),
    )


def test_render_submission_plan_contains_immediate_dynamic_verification():
    plan = UnrealTaskPlanner().plan_render_submission(
        _intent("render-job-plan"),
        "/Game/AtlasTest/AtlasSequencerFixtureSequence",
    )

    assert [operation.name for operation in plan.operations] == [
        "submit_render",
        "verify_render_job",
    ]

    assert plan.operations[0].kind is UnrealOperationKind.WRITE
    assert plan.operations[1].kind is UnrealOperationKind.VERIFY

    assert (
        plan.operations[1].arguments["job_id"]
        == "$previous.submit_render.job_id"
    )


def test_render_submission_resolves_job_id_from_previous_evidence():
    transport = RecordingRenderTransport()
    executor = UnrealPlanExecutor(
        UnrealAdapterProduction(
            transport,
            "test-render-job-runtime-binding",
        )
    )

    plan = UnrealTaskPlanner().plan_render_submission(
        _intent("render-job-execution"),
        "/Game/AtlasTest/AtlasSequencerFixtureSequence",
    )

    result = executor.execute(
        plan,
        "render-job-runtime-binding-auth",
    )

    assert result.success is True

    assert [
        evidence.operation_name
        for evidence in result.evidence_ledger
    ] == [
        "submit_render",
        "verify_render_job",
    ]

    assert [
        request.operation_name
        for request in transport.requests
    ] == [
        "submit_render",
        "inspect_render_job",
    ]

    assert transport.requests[1].arguments["job_id"] == "job-test-123"
    assert result.evidence_ledger[1].verified is True


def test_render_submission_fails_when_submit_evidence_has_no_job_id():
    @dataclass
    class MissingJobTransport:
        def __post_init__(self):
            self.requests = []

        def send(self, request):
            self.requests.append(request)

            if request.operation_name == "submit_render":
                state = {
                    ENTITY_ID: {
                        "render_job": {
                            "status": "queued",
                        }
                    }
                }
            else:
                raise AssertionError(
                    "inspect_render_job must not execute without job_id"
                )

            return UnrealTransportResponse(
                request_id=request.request_id,
                operation_name=request.operation_name,
                entity_ids=request.entity_ids,
                success=True,
                observed_state=state,
                error="",
                source="test-render-job-missing-id",
            )

    transport = MissingJobTransport()
    executor = UnrealPlanExecutor(
        UnrealAdapterProduction(
            transport,
            "test-render-job-missing-id",
        )
    )

    plan = UnrealTaskPlanner().plan_render_submission(
        _intent("render-job-missing-id"),
        "/Game/AtlasTest/AtlasSequencerFixtureSequence",
    )

    try:
        executor.execute(
            plan,
            "render-job-missing-id-auth",
        )
    except Exception as exc:
        assert "job_id" in str(exc)
    else:
        raise AssertionError(
            "submission without a returned job_id must fail verification"
        )

    assert [
        request.operation_name
        for request in transport.requests
    ] == [
        "submit_render",
    ]


def test_render_job_evidence_keeps_directory_and_artifacts_distinct():
    transport = RecordingRenderTransport()
    executor = UnrealPlanExecutor(
        UnrealAdapterProduction(
            transport,
            "test-render-job-artifacts",
        )
    )

    plan = UnrealTaskPlanner().plan_render_job_inspection(
        _intent("render-job-artifacts"),
        "job-test-123",
    )

    result = executor.execute(
        plan,
        "render-job-artifacts-auth",
    )

    state = result.evidence_ledger[-1].observed_state["FIELD_SURFACE"]["render_job"]

    assert state["output_directory"] == "Saved/AtlasRenderOutput"
    assert state["output_format"] == "png"
    assert state["output_files"] == []


def test_render_job_verifier_rejects_success_without_artifacts():
    evidence = UnrealEvidence(
        operation_name="verify_render_job",
        entity_ids=(ENTITY_ID,),
        observed_state={
            "job_id": "job-test-123",
            "status": "finished",
            "finished": True,
            "success": True,
            "failed": False,
            "output_files": [],
        },
        source="render-job-verifier-test",
    )

    try:
        verify_render_job_completion(evidence)
    except ValueError as exc:
        assert "no output_files" in str(exc)
    else:
        raise AssertionError(
            "successful render without artifacts must fail verification"
        )


def test_render_job_verifier_accepts_existing_nonempty_artifact(tmp_path):
    output = tmp_path / "AtlasRender_0001.png"
    output.write_bytes(b"atlas-render-test")

    evidence = UnrealEvidence(
        operation_name="verify_render_job",
        entity_ids=(ENTITY_ID,),
        observed_state={
            "job_id": "job-test-123",
            "status": "finished",
            "finished": True,
            "success": True,
            "failed": False,
            "output_directory": str(tmp_path),
            "output_format": "png",
            "output_files": [str(output)],
        },
        source="render-job-verifier-test",
    )

    verified = verify_render_job_completion(evidence)

    assert verified is evidence


def test_render_job_verifier_accepts_active_submitted_job():
    evidence = UnrealEvidence(
        operation_name="verify_render_job",
        entity_ids=(ENTITY_ID,),
        observed_state={
            "job_id": "job-test-active",
            "status": "queued",
            "finished": False,
            "success": False,
            "failed": False,
            "output_files": [],
        },
        source="render-job-verifier-test",
    )

    assert verify_render_job_completion(evidence) is evidence
