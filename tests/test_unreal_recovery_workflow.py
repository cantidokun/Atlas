import pytest

from planning.recovery_receipt import RecoveryReceipt
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionFailure, UnrealPlanExecutionResult, UnrealPlanExecutor
from planning.unreal_recovery_sequence import UnrealRecoverySequenceAssessment, UnrealRecoverySequenceResult, UnrealRecoveryStepAssessment
from planning.unreal_recovery_workflow import execute_receipt_bound_recovery_sequence
from planning.unreal_task_planner import UnrealTaskPlan


ENTITY_IDS = ("FIELD_SURFACE",)


def _source_plan():
    return UnrealTaskPlan(
        "workflow-source",
        (
            UnrealOperation(
                UnrealCapability.SEQUENCER,
                UnrealOperationKind.WRITE,
                "set_sequencer_playback_range",
                {"entity_ids": ENTITY_IDS, "start_frame": 10, "end_frame": 110},
                ENTITY_IDS,
            ),
            UnrealOperation(
                UnrealCapability.SEQUENCER,
                UnrealOperationKind.VERIFY,
                "verify_sequencer_playback_range",
                {"entity_ids": ENTITY_IDS, "expected_start_frame": 10, "expected_end_frame": 110},
                ENTITY_IDS,
            ),
        ),
    )


def _failure():
    return UnrealPlanExecutionFailure(
        intent_id="workflow-source",
        operation_index=1,
        operation_name="verify_sequencer_playback_range",
        completed_evidence=(),
        error="simulated failure",
        operation_entity_ids=ENTITY_IDS,
        operation_arguments={"entity_ids": ENTITY_IDS},
    )


def _executor(monkeypatch):
    executor = object.__new__(UnrealPlanExecutor)
    calls = []

    def execute_authorized(self, plan, authorization):
        calls.append((plan, authorization))
        return UnrealPlanExecutionResult(plan.intent_id, (), True)

    monkeypatch.setattr(UnrealPlanExecutor, "execute_authorized", execute_authorized)
    return executor, calls


def _assessment(disposition):
    return UnrealRecoverySequenceAssessment((
        UnrealRecoveryStepAssessment(0, "set_sequencer_playback_range", ENTITY_IDS, disposition, "test"),
    ))


def test_receipt_bound_workflow_executes_replacement_only_after_receipt_check(monkeypatch):
    import planning.unreal_recovery_workflow as workflow

    source = _source_plan()
    failure = _failure()
    reassessment = UnrealTaskPlan("reassessment", ())
    replacement = UnrealTaskPlan("replacement", ())
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment, "reassessment-auth")
    replacement_auth = UnrealPlanAuthorization.issue(replacement, "replacement-auth")
    receipt = RecoveryReceipt("evidence-1", replacement_auth.plan_digest, "authorization-1")
    executor, calls = _executor(monkeypatch)
    replacement_calls = []

    monkeypatch.setattr(workflow, "build_reassessment_plan", lambda *_: reassessment)
    monkeypatch.setattr(workflow, "assess_reassessment_sequence", lambda *_: _assessment("replacement_required"))
    monkeypatch.setattr(workflow, "build_replacement_plan", lambda *_: replacement)

    def resume(*args, **kwargs):
        replacement_calls.append((args, kwargs))
        return UnrealPlanExecutionResult(replacement.intent_id, (), True)

    monkeypatch.setattr(workflow, "resume_replacement", resume)

    result = execute_receipt_bound_recovery_sequence(
        executor,
        source,
        failure,
        reassessment_auth,
        replacement_auth,
        receipt,
        evidence_digest="evidence-1",
        authorization_digest="authorization-1",
    )

    assert result.replacement_result is not None
    assert len(calls) == 1
    assert calls[0] == (reassessment, reassessment_auth)
    assert len(replacement_calls) == 1
    assert replacement_calls[0][0][1] is replacement
    assert replacement_calls[0][0][2] is replacement_auth
    assert replacement_calls[0][0][3] is receipt


def test_receipt_bound_workflow_does_not_mutate_when_reassessment_says_already_applied(monkeypatch):
    import planning.unreal_recovery_workflow as workflow

    source = _source_plan()
    failure = _failure()
    reassessment = UnrealTaskPlan("reassessment", ())
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment, "reassessment-auth")
    executor, calls = _executor(monkeypatch)
    monkeypatch.setattr(workflow, "build_reassessment_plan", lambda *_: reassessment)
    monkeypatch.setattr(workflow, "assess_reassessment_sequence", lambda *_: _assessment("already_applied"))

    result = execute_receipt_bound_recovery_sequence(
        executor,
        source,
        failure,
        reassessment_auth,
        None,
        RecoveryReceipt("evidence-1", "unused-plan", "authorization-1"),
        evidence_digest="evidence-1",
        authorization_digest="authorization-1",
    )

    assert result.replacement_plan is None
    assert result.replacement_result is None
    assert calls == [(reassessment, reassessment_auth)]


def test_receipt_bound_workflow_rejects_stale_receipt_before_replacement(monkeypatch):
    import planning.unreal_recovery_workflow as workflow

    source = _source_plan()
    failure = _failure()
    reassessment = UnrealTaskPlan("reassessment", ())
    replacement = UnrealTaskPlan("replacement", ())
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment, "reassessment-auth")
    replacement_auth = UnrealPlanAuthorization.issue(replacement, "replacement-auth")
    stale_receipt = RecoveryReceipt("old-evidence", replacement_auth.plan_digest, "authorization-1")
    executor, calls = _executor(monkeypatch)

    monkeypatch.setattr(workflow, "build_reassessment_plan", lambda *_: reassessment)
    monkeypatch.setattr(workflow, "assess_reassessment_sequence", lambda *_: _assessment("replacement_required"))
    monkeypatch.setattr(workflow, "build_replacement_plan", lambda *_: replacement)

    with pytest.raises(RuntimeError, match="recovery receipt"):
        execute_receipt_bound_recovery_sequence(
            executor,
            source,
            failure,
            reassessment_auth,
            replacement_auth,
            stale_receipt,
            evidence_digest="fresh-evidence",
            authorization_digest="authorization-1",
        )

    assert calls == [(reassessment, reassessment_auth)]
