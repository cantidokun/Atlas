"""Deterministic coverage for render-job identity semantic verification (frozen contract).

Proves the contract frozen in the render-job identity design gate (CLEAR WITH MINOR
FINDINGS): R-J1 positive submission/verification, R-J2 wrong returned job id,
R-J3 authorized read answered with another job id, R-J4 anti-forgery /
anti-self-comparison, R-J5 expectation provenance, R-J6 blank/missing expected id,
R-J7 preserved status/completion/artifact behaviour, R-J8 registry/shape/receipt/
result regression guards.

No engine is involved: the transport is a recording stub, every expected identity is
plan-derived (never read back from the observation), and every observation is a fresh
stub read. Nothing here is live.
"""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_capability_registry import UnrealCapabilityRegistry
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_production_result_contract import UnrealProductionResultContract
from planning.unreal_production_runtime_adapter import UnrealProductionRuntimeSnapshot
from planning.unreal_render_job_verifier import verify_render_job_completion
from planning.unreal_render_receipt import UnrealRenderReceipt
from planning.unreal_task_planner import UnrealTaskIntent, UnrealTaskPlan, UnrealTaskPlanner
from planning.unreal_tool_schema import validate_unreal_tool_call
from planning.unreal_transport_contract import UnrealTransportResponse

ENTITY_ID = "ATLAS_RENDER_TEST"
SEQUENCE_ASSET_PATH = "/Game/AtlasTest/AtlasSequencerFixtureSequence"
SOURCE = "render-job-semantic-test"
JOB_ID = "job-authorized-1"
DYNAMIC_JOB_REFERENCE = "$previous.submit_render.job_id"


def _render_job(
    job_id,
    *,
    status="queued",
    finished=False,
    success=False,
    failed=False,
    output_files=(),
    sequence_asset_path=SEQUENCE_ASSET_PATH,
):
    """One render-job state as the engine reports it."""
    return {
        "job_id": job_id,
        "status": status,
        "finished": finished,
        "success": success,
        "failed": failed,
        "sequence_asset_path": sequence_asset_path,
        "output_directory": "Saved/AtlasRenderOutput",
        "output_format": "png",
        "output_files": list(output_files),
    }


def _envelope(job_state):
    """Standard entity envelope: {entity_id: {"render_job": {...}}}."""
    return {ENTITY_ID: {"render_job": dict(job_state)}}


def _artifact(directory):
    output = directory / "AtlasRender_0001.png"
    output.write_bytes(b"atlas-render-test")
    return output


class RecordingRenderJobTransport:
    """Deterministic stand-in for the production transport (no engine involved).

    ``submit_job_id`` is the identity the engine returns from ``submit_render``.
    ``reported_job_id`` is the identity present in the state returned for an
    ``inspect_render_job`` read: ``None`` echoes the id that was actually requested
    (what a correct engine does), any other value simulates an engine answering about
    a different render job. ``reported_state`` bypasses both with an exact state.
    """

    def __init__(
        self,
        *,
        submit_job_id=JOB_ID,
        reported_job_id=None,
        reported_state=None,
        submit_state=None,
        omit_submit_job_id=False,
    ):
        self.requests = []
        self.submit_job_id = submit_job_id
        self.reported_job_id = reported_job_id
        self.reported_state = reported_state
        self.submit_state = submit_state
        self.omit_submit_job_id = omit_submit_job_id

    def send(self, request):
        self.requests.append(request)

        if request.operation_name == "submit_render":
            if self.submit_state is not None:
                state = self.submit_state
            else:
                job_state = _render_job(self.submit_job_id)
                if self.omit_submit_job_id:
                    job_state.pop("job_id")
                state = _envelope(job_state)
        elif request.operation_name == "inspect_render_job":
            if self.reported_state is not None:
                state = self.reported_state
            else:
                reported = (
                    request.arguments["job_id"]
                    if self.reported_job_id is None
                    else self.reported_job_id
                )
                state = _envelope(_render_job(reported))
        else:
            raise AssertionError(f"unexpected operation: {request.operation_name}")

        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=True,
            observed_state=state,
            error="",
            source=SOURCE,
        )

    @property
    def dispatched(self):
        return [request.operation_name for request in self.requests]

    @property
    def requested_job_ids(self):
        return [
            request.arguments["job_id"]
            for request in self.requests
            if "job_id" in request.arguments
        ]


def _executor(transport):
    return UnrealPlanExecutor(UnrealAdapterProduction(transport, SOURCE))


def _intent(intent_id):
    return UnrealTaskIntent(intent_id, "render job identity semantic verification", (ENTITY_ID,))


def _submission_plan(intent_id, job_reference=DYNAMIC_JOB_REFERENCE, sequence=SEQUENCE_ASSET_PATH):
    plan = UnrealTaskPlanner().plan_render_submission(_intent(intent_id), sequence)
    if job_reference == DYNAMIC_JOB_REFERENCE:
        return plan
    return _plan_with_verify(intent_id, {"job_id": job_reference})


def _inspection_plan(intent_id, job_id):
    return UnrealTaskPlanner().plan_render_job_inspection(_intent(intent_id), job_id)


def _plan_with_verify(intent_id, verify_arguments, *, verify_name="verify_render_job"):
    """Hand-built plan: the planner's authorized WRITE plus an exact VERIFY argument set."""
    base = UnrealTaskPlanner().plan_render_submission(
        _intent(intent_id), SEQUENCE_ASSET_PATH
    )
    verify = UnrealOperation(
        capability=UnrealCapability.RENDER,
        kind=UnrealOperationKind.VERIFY,
        name=verify_name,
        arguments={"entity_ids": (ENTITY_ID,), **dict(verify_arguments)},
        entity_ids=(ENTITY_ID,),
    )
    return UnrealTaskPlan(intent_id, (base.operations[0], verify))


def _operation(name, kind, arguments, entity_ids=(ENTITY_ID,)):
    return UnrealOperation(
        capability=UnrealCapability.RENDER,
        kind=kind,
        name=name,
        arguments={"entity_ids": tuple(entity_ids), **arguments},
        entity_ids=tuple(entity_ids),
    )


def _authorized_execute(transport, plan, intent_id):
    executor = _executor(transport)
    return executor.execute_authorized(
        plan, UnrealPlanAuthorization.issue(plan, f"{intent_id}-auth")
    )


def _job_evidence(job_state, *, operation_name="verify_render_job", verified=False):
    return UnrealEvidence(
        operation_name=operation_name,
        entity_ids=(ENTITY_ID,),
        observed_state=_envelope(job_state),
        source=SOURCE,
        verified=verified,
    )


# --------------------------------------------------------------------------- R-J1
def test_rj1_successful_submission_and_verification_bind_the_submitted_identity():
    transport = RecordingRenderJobTransport(submit_job_id="job-submitted-1")
    plan = _submission_plan("rj1")
    result = _authorized_execute(transport, plan, "rj1")

    assert result.success is True
    assert [e.operation_name for e in result.evidence_ledger] == [
        "submit_render",
        "verify_render_job",
    ]
    assert [e.verified for e in result.evidence_ledger] == [False, True]
    assert transport.dispatched == ["submit_render", "inspect_render_job"]

    job_state = result.evidence_ledger[1].observed_state[ENTITY_ID]["render_job"]
    assert job_state["job_id"] == "job-submitted-1"
    assert job_state["status"] == "queued"


def test_rj1_dispatch_uses_the_resolved_submitted_job_id():
    transport = RecordingRenderJobTransport(submit_job_id="job-submitted-2")
    plan = _submission_plan("rj1-dispatch")
    _authorized_execute(transport, plan, "rj1-dispatch")

    assert transport.requested_job_ids == ["job-submitted-2"]
    assert DYNAMIC_JOB_REFERENCE not in transport.requested_job_ids
    assert plan.operations[1].arguments["job_id"] == DYNAMIC_JOB_REFERENCE


def test_rj1_verification_uses_a_fresh_read_never_the_submission_evidence():
    transport = RecordingRenderJobTransport(submit_job_id="job-submitted-3")
    plan = _submission_plan("rj1-fresh")
    result = _authorized_execute(transport, plan, "rj1-fresh")

    submission, verification = result.evidence_ledger
    assert verification is not submission
    assert verification.operation_name == "verify_render_job"
    assert transport.dispatched.count("inspect_render_job") == 1
    assert all(e.verified is False for e in result.evidence_ledger[:1])


def test_rj1_defensive_strip_accepts_the_resolved_identity():
    transport = RecordingRenderJobTransport(
        submit_job_id="job-padded-1", reported_job_id=" job-padded-1 "
    )
    plan = _submission_plan("rj1-strip")
    result = _authorized_execute(transport, plan, "rj1-strip")

    assert result.success is True
    assert result.evidence_ledger[1].verified is True
    assert transport.requested_job_ids == ["job-padded-1"]


# --------------------------------------------------------------------------- R-J2
def test_rj2_verification_answered_with_another_job_fails_closed():
    transport = RecordingRenderJobTransport(
        submit_job_id=JOB_ID, reported_job_id="job-somewhere-else"
    )
    plan = _submission_plan("rj2")

    with pytest.raises(UnrealPlanExecutionError) as caught:
        _authorized_execute(transport, plan, "rj2")

    failure = caught.value.failure
    assert failure.operation_index == 1
    assert failure.operation_name == "verify_render_job"
    assert [e.operation_name for e in failure.completed_evidence] == ["submit_render"]
    assert [e.verified for e in failure.completed_evidence] == [False]
    assert "render job identity mismatch" in failure.error
    assert JOB_ID in failure.error
    assert "job-somewhere-else" in failure.error
    assert failure.operation_arguments["job_id"] == JOB_ID
    assert transport.dispatched == ["submit_render", "inspect_render_job"]


def test_rj2_flagged_evidence_is_never_produced_for_a_mismatched_job():
    transport = RecordingRenderJobTransport(
        submit_job_id=JOB_ID, reported_job_id="job-somewhere-else"
    )
    plan = _submission_plan("rj2-flags")

    with pytest.raises(UnrealPlanExecutionError) as caught:
        _authorized_execute(transport, plan, "rj2-flags")

    assert all(e.verified is False for e in caught.value.failure.completed_evidence)
    assert caught.value.failure.completed_operation_arguments == (
        {"entity_ids": (ENTITY_ID,), "sequence_asset_path": SEQUENCE_ASSET_PATH},
    )


# --------------------------------------------------------------------------- R-J3
def test_rj3_job_addressed_read_answered_with_another_job_fails_closed():
    transport = RecordingRenderJobTransport(reported_job_id="job-other")
    plan = _inspection_plan("rj3", "job-requested")

    with pytest.raises(UnrealPlanExecutionError) as caught:
        _authorized_execute(transport, plan, "rj3")

    failure = caught.value.failure
    assert failure.operation_index == 0
    assert failure.operation_name == "inspect_render_job"
    assert failure.completed_evidence == ()
    assert "render job identity mismatch" in failure.error
    assert "job-requested" in failure.error
    assert "job-other" in failure.error
    assert transport.requested_job_ids == ["job-requested"]


def test_rj3_job_addressed_read_answered_with_the_requested_job_is_verified():
    transport = RecordingRenderJobTransport()
    plan = _inspection_plan("rj3-ok", "job-requested")
    result = _authorized_execute(transport, plan, "rj3-ok")

    assert result.success is True
    assert result.evidence_ledger[0].operation_name == "inspect_render_job"
    assert result.evidence_ledger[0].verified is True
    assert transport.requested_job_ids == ["job-requested"]


def test_rj3_read_without_a_job_identity_is_rejected_before_dispatch():
    plan = UnrealTaskPlan(
        "rj3-not-addressed",
        (_operation("inspect_render_job", UnrealOperationKind.READ, {}),),
    )

    with pytest.raises(UnrealPlanExecutionError, match="failed preflight"):
        _authorized_execute(RecordingRenderJobTransport(), plan, "rj3-not-addressed")


# --------------------------------------------------------------------------- R-J4
def test_rj4_forged_completion_with_the_wrong_identity_fails_closed(tmp_path):
    forged = _job_evidence(
        _render_job(
            "job-forged",
            status="finished",
            finished=True,
            success=True,
            output_files=(str(_artifact(tmp_path)),),
        )
    )

    with pytest.raises(ValueError, match="render job identity mismatch") as caught:
        verify_render_job_completion(forged, expected_job_id=JOB_ID)

    assert "job-forged" in str(caught.value)
    assert JOB_ID in str(caught.value)


def test_rj4_the_same_forged_completion_passes_with_the_authorized_identity(tmp_path):
    authorized = _job_evidence(
        _render_job(
            JOB_ID,
            status="finished",
            finished=True,
            success=True,
            output_files=(str(_artifact(tmp_path)),),
        )
    )

    assert verify_render_job_completion(authorized, expected_job_id=JOB_ID) is authorized


def test_rj4_forged_completion_answered_for_another_job_fails_closed(tmp_path):
    transport = RecordingRenderJobTransport(
        submit_job_id=JOB_ID,
        reported_state=_envelope(
            _render_job(
                "job-forged",
                status="finished",
                finished=True,
                success=True,
                output_files=(str(_artifact(tmp_path)),),
            )
        ),
    )
    plan = _submission_plan("rj4-forged")

    with pytest.raises(UnrealPlanExecutionError, match="render job identity mismatch"):
        _authorized_execute(transport, plan, "rj4-forged")


def test_rj4_self_consistent_completion_for_the_authorized_job_still_passes(tmp_path):
    transport = RecordingRenderJobTransport(
        submit_job_id=JOB_ID,
        reported_state=_envelope(
            _render_job(
                JOB_ID,
                status="finished",
                finished=True,
                success=True,
                output_files=(str(_artifact(tmp_path)),),
            )
        ),
    )
    plan = _submission_plan("rj4-authorized")
    result = _authorized_execute(transport, plan, "rj4-authorized")

    assert result.success is True
    assert result.evidence_ledger[1].verified is True


# --------------------------------------------------------------------------- R-J5
def test_rj5_expectation_is_the_authorized_verify_argument():
    # The authorized VERIFY names its own job; the authorized submission produced another.
    transport = RecordingRenderJobTransport(
        submit_job_id="job-returned", reported_job_id="job-declared"
    )
    plan = _plan_with_verify("rj5", {"job_id": "job-declared"})
    result = _authorized_execute(transport, plan, "rj5")

    assert transport.requested_job_ids == ["job-declared"]
    assert result.success is True
    assert result.evidence_ledger[1].verified is True


def test_rj5_write_and_verify_disagreement_fails_closed():
    # Every read answers with the identity the authorized submission produced, so a
    # verifier that compared the observation with itself would pass vacuously.
    transport = RecordingRenderJobTransport(
        submit_job_id="job-returned", reported_job_id="job-returned"
    )
    plan = _plan_with_verify("rj5-mismatch", {"job_id": "job-declared"})

    with pytest.raises(UnrealPlanExecutionError, match="render job identity mismatch") as caught:
        _authorized_execute(transport, plan, "rj5-mismatch")

    failure = caught.value.failure
    assert "job-declared" in failure.error  # authorized VERIFY argument
    assert "job-returned" in failure.error  # the observed/submitted identity
    assert failure.operation_arguments["job_id"] == "job-declared"


def test_rj5_missing_submit_evidence_prevents_verification_dispatch():
    transport = RecordingRenderJobTransport(omit_submit_job_id=True)
    plan = _submission_plan("rj5-missing")

    with pytest.raises(ValueError, match="submit_render evidence did not contain a non-empty job_id"):
        _authorized_execute(transport, plan, "rj5-missing")

    assert transport.dispatched == ["submit_render"]


def test_rj5_blank_submitted_identity_prevents_verification_dispatch():
    transport = RecordingRenderJobTransport(submit_job_id="   ")
    plan = _submission_plan("rj5-blank")

    with pytest.raises(ValueError, match="submit_render evidence did not contain a non-empty job_id"):
        _authorized_execute(transport, plan, "rj5-blank")

    assert transport.dispatched == ["submit_render"]


# --------------------------------------------------------------------------- R-J6
@pytest.mark.parametrize("blank", ["", "   ", None])
def test_rj6_blank_expected_job_id_fails_closed_before_dispatch(blank):
    transport = RecordingRenderJobTransport()
    plan = _plan_with_verify(f"rj6-{blank!r}", {"job_id": blank})

    with pytest.raises(UnrealPlanExecutionError, match="failed preflight"):
        _authorized_execute(transport, plan, f"rj6-{blank!r}")

    assert transport.requests == []


def test_rj6_missing_expected_job_id_key_fails_closed_before_dispatch():
    transport = RecordingRenderJobTransport()
    plan = _plan_with_verify("rj6-missing", {})

    with pytest.raises(UnrealPlanExecutionError, match="failed preflight"):
        _authorized_execute(transport, plan, "rj6-missing")

    assert transport.requests == []


def test_rj6_blank_read_identity_fails_closed_before_dispatch():
    transport = RecordingRenderJobTransport()
    plan = UnrealTaskPlan(
        "rj6-read",
        (_operation("inspect_render_job", UnrealOperationKind.READ, {"job_id": "   "}),),
    )

    with pytest.raises(UnrealPlanExecutionError, match="failed preflight"):
        _authorized_execute(transport, plan, "rj6-read")

    assert transport.requests == []


@pytest.mark.parametrize("blank", ["", "   ", 17, b"job"])
def test_rj6_verifier_rejects_a_blank_or_non_string_expectation(blank):
    evidence = _job_evidence(_render_job(JOB_ID))

    with pytest.raises(ValueError, match="requires a non-empty expected job_id"):
        verify_render_job_completion(evidence, expected_job_id=blank)


def test_rj6_executor_gate_rejects_a_blank_or_missing_authorized_identity():
    verify_operation = _submission_plan("rj6-gate").operations[1]
    assert UnrealPlanExecutor._authorized_job_id(verify_operation) == DYNAMIC_JOB_REFERENCE

    for arguments in ({"job_id": "   "}, {"job_id": ""}, {"job_id": None}, {}):
        operation = _operation("verify_render_job", UnrealOperationKind.VERIFY, arguments)
        with pytest.raises(ValueError, match="requires an authorized non-empty job_id"):
            UnrealPlanExecutor._authorized_job_id(operation)


# --------------------------------------------------------------------------- R-J7
@pytest.mark.parametrize("status", ["submitted", "queued", "rendering"])
def test_rj7_active_statuses_remain_accepted(status):
    evidence = _job_evidence(
        _render_job(JOB_ID, status=status, finished=False, failed=False)
    )

    assert verify_render_job_completion(evidence, expected_job_id=JOB_ID) is evidence


def test_rj7_finished_success_with_existing_artifacts_remains_accepted(tmp_path):
    evidence = _job_evidence(
        _render_job(
            JOB_ID,
            status="finished",
            finished=True,
            success=True,
            output_files=(str(_artifact(tmp_path)),),
        )
    )

    compared = verify_render_job_completion(evidence, expected_job_id=JOB_ID)

    assert compared is evidence
    assert compared.verified is False  # the executor, never the verifier, produces the flag


def test_rj7_flat_engine_state_remains_accepted(tmp_path):
    evidence = UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=(ENTITY_ID,),
        observed_state=_render_job(
            JOB_ID,
            status="completed",
            finished=True,
            success=True,
            output_files=(str(_artifact(tmp_path)),),
        ),
        source=SOURCE,
    )

    assert verify_render_job_completion(evidence, expected_job_id=JOB_ID) is evidence


def test_rj7_failed_render_remains_rejected():
    evidence = _job_evidence(
        _render_job(JOB_ID, status="failed", finished=True, failed=True)
    )

    with pytest.raises(ValueError, match="failed=True"):
        verify_render_job_completion(evidence, expected_job_id=JOB_ID)


def test_rj7_invalid_inactive_status_remains_rejected():
    evidence = _job_evidence(_render_job(JOB_ID, status="cancelled", finished=False))

    with pytest.raises(ValueError, match="neither finished nor in a valid active state"):
        verify_render_job_completion(evidence, expected_job_id=JOB_ID)


def test_rj7_missing_job_id_remains_rejected():
    job_state = _render_job(JOB_ID)
    job_state.pop("job_id")

    with pytest.raises(ValueError, match="non-empty job_id"):
        verify_render_job_completion(
            _job_evidence(job_state), expected_job_id=JOB_ID
        )


def test_rj7_finished_without_artifacts_remains_rejected():
    evidence = _job_evidence(
        _render_job(
            JOB_ID,
            status="finished",
            finished=True,
            success=True,
            output_files=(),
        )
    )

    with pytest.raises(ValueError, match="no output_files"):
        verify_render_job_completion(evidence, expected_job_id=JOB_ID)


def test_rj7_declared_artifacts_that_are_missing_or_empty_remain_rejected(tmp_path):
    missing = _job_evidence(
        _render_job(
            JOB_ID,
            status="finished",
            finished=True,
            success=True,
            output_files=(str(tmp_path / "absent.png"),),
        )
    )
    with pytest.raises(ValueError, match="do not exist"):
        verify_render_job_completion(missing, expected_job_id=JOB_ID)

    empty_path = tmp_path / "empty.png"
    empty_path.write_bytes(b"")
    empty = _job_evidence(
        _render_job(
            JOB_ID,
            status="finished",
            finished=True,
            success=True,
            output_files=(str(empty_path),),
        )
    )
    with pytest.raises(ValueError, match="are empty"):
        verify_render_job_completion(empty, expected_job_id=JOB_ID)


def test_rj7_finished_without_success_remains_rejected():
    evidence = _job_evidence(
        _render_job(JOB_ID, status="finished", finished=True, success=False)
    )

    with pytest.raises(ValueError, match="did not report success"):
        verify_render_job_completion(evidence, expected_job_id=JOB_ID)


def test_rj7_legacy_direct_call_shape_is_unchanged():
    # Direct callers (the production workflow re-verifies inspect evidence itself) keep
    # the historical call shape with no identity binding.
    evidence = _job_evidence(_render_job(JOB_ID), operation_name="inspect_render_job")

    assert verify_render_job_completion(evidence) is evidence
    assert verify_render_job_completion(evidence, require_artifacts=False) is evidence


# --------------------------------------------------------------------------- R-J8
def test_rj8_execution_shape_declares_the_render_job_verifier():
    plan = _submission_plan("rj8-shape")

    assert UnrealPlanExecutor._expected_verifier(plan.operations[0]) == "verify_render_job"
    assert plan.operations[0].name == "submit_render"
    assert plan.operations[1].name == "verify_render_job"


def test_rj8_submit_render_must_be_followed_by_the_render_job_verifier():
    transport = RecordingRenderJobTransport()
    plan = _plan_with_verify(
        "rj8-shape-negative", {"job_id": JOB_ID}, verify_name="verify_render_state"
    )

    with pytest.raises(
        UnrealPlanExecutionError, match="must be followed by 'verify_render_job'"
    ):
        _authorized_execute(transport, plan, "rj8-shape-negative")

    assert transport.requests == []


def test_rj8_render_job_allowed_key_sets_are_unchanged():
    registry = UnrealCapabilityRegistry()

    for name, kind in (
        ("inspect_render_job", UnrealOperationKind.READ),
        ("verify_render_job", UnrealOperationKind.VERIFY),
    ):
        allowed = _operation(name, kind, {"job_id": JOB_ID})
        assert registry.validate_operation(allowed) is allowed

        for extra_key in (
            "sequence_asset_path",
            "expected_job_id",
            "render_job_id",
            "job",
            "width",
            "asset_path",
        ):
            rejected = _operation(name, kind, {"job_id": JOB_ID, extra_key: "x"})
            with pytest.raises(ValueError, match="do not match the capability schema"):
                registry.validate_operation(rejected)


def test_rj8_render_job_tool_call_snapshot_is_unchanged():
    for name in ("inspect_render_job", "verify_render_job"):
        snapshot = validate_unreal_tool_call(
            name,
            {"entity_ids": (ENTITY_ID,), "authorization_id": "rj8-auth", "job_id": JOB_ID},
        )
        assert snapshot["job_id"] == JOB_ID
        assert snapshot["entity_ids"] == (ENTITY_ID,)


def test_rj8_registry_membership_cannot_create_a_vacuous_pass():
    submission = _submission_plan("rj8-vacuous")
    read = _inspection_plan("rj8-vacuous-read", JOB_ID)
    assert UnrealPlanExecutor._is_semantically_verified(submission.operations[1], None) is True
    assert UnrealPlanExecutor._is_semantically_verified(read.operations[0], None) is True

    transport = RecordingRenderJobTransport(
        submit_job_id=JOB_ID, reported_job_id="job-other"
    )
    with pytest.raises(UnrealPlanExecutionError, match="render job identity mismatch"):
        _authorized_execute(transport, submission, "rj8-vacuous")

    read_transport = RecordingRenderJobTransport(reported_job_id="job-other")
    with pytest.raises(UnrealPlanExecutionError, match="render job identity mismatch"):
        _authorized_execute(read_transport, read, "rj8-vacuous-read")


def test_rj8_receipt_still_requires_verified_inspect_render_job_evidence(tmp_path):
    completed = _render_job(
        JOB_ID,
        status="finished",
        finished=True,
        success=True,
        output_files=(str(_artifact(tmp_path)),),
    )

    unverified = UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=(ENTITY_ID,),
        observed_state=dict(completed),
        source=SOURCE,
    )
    with pytest.raises(ValueError, match="requires verified render-job evidence"):
        UnrealRenderReceipt.issue(unverified)

    flagged_verify_evidence = UnrealEvidence(
        operation_name="verify_render_job",
        entity_ids=(ENTITY_ID,),
        observed_state=dict(completed),
        source=SOURCE,
        verified=True,
    )
    with pytest.raises(ValueError, match="must be issued from inspect_render_job evidence"):
        UnrealRenderReceipt.issue(flagged_verify_evidence)


def test_rj8_receipt_mismatch_detection_is_unchanged(tmp_path):
    completed = _render_job(
        JOB_ID,
        status="finished",
        finished=True,
        success=True,
        output_files=(str(_artifact(tmp_path)),),
    )
    evidence = UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=(ENTITY_ID,),
        observed_state=dict(completed),
        source=SOURCE,
        verified=True,
    )
    receipt = UnrealRenderReceipt.issue(evidence)
    assert receipt.job_id == JOB_ID
    assert receipt.matches(evidence) is True

    drifted = UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=(ENTITY_ID,),
        observed_state=dict(completed, job_id="job-other"),
        source=SOURCE,
        verified=True,
    )
    assert receipt.matches(drifted) is False


def test_rj8_production_result_job_id_mismatch_protection_is_unchanged(tmp_path):
    snapshot = UnrealProductionRuntimeSnapshot(
        state="complete",
        phase="complete",
        waiting_for_reassessment=False,
        waiting_for_replacement=False,
        failure=None,
        recovery=None,
        required_authorizations=(),
    )
    evidence = UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=(ENTITY_ID,),
        observed_state=_render_job(
            "job-observed",
            status="finished",
            finished=True,
            success=True,
            output_files=(str(_artifact(tmp_path)),),
        ),
        source=SOURCE,
        verified=True,
    )

    with pytest.raises(ValueError, match="job_id does not match final_evidence"):
        UnrealProductionResultContract(
            operation="start",
            snapshot=snapshot,
            success=True,
            job_id="job-declared",
            final_evidence=evidence,
        )

    matched = UnrealProductionResultContract(
        operation="start",
        snapshot=snapshot,
        success=True,
        job_id="job-observed",
        final_evidence=evidence,
    )
    assert matched.job_id == "job-observed"
