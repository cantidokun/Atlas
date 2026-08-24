import pytest

from planning.recovery_receipt import RecoveryReceipt
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_recovery_execution import UnrealRecoveryExecutionError, resume_replacement
from planning.unreal_task_planner import UnrealTaskPlan


ENTITY_IDS = ("FIELD_SURFACE",)
EVIDENCE_DIGEST = "fresh-evidence-001"
AUTHORIZATION_DIGEST = "recovery-authorization-001"


def _replacement_plan():
    return UnrealTaskPlan(
        "recovery:replacement",
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


class _ExecutorSpy:
    pass


def _executor(monkeypatch):
    from planning.unreal_plan_executor import UnrealPlanExecutor

    executor = object.__new__(UnrealPlanExecutor)
    calls = []

    def execute_authorized(plan, authorization):
        calls.append((plan, authorization))
        return "executed"

    monkeypatch.setattr(executor, "execute_authorized", execute_authorized.__get__(executor, UnrealPlanExecutor))
    return executor, calls


def test_resume_replacement_requires_matching_recovery_receipt(monkeypatch):
    plan = _replacement_plan()
    authorization = UnrealPlanAuthorization.issue(plan, "replacement-auth")
    receipt = RecoveryReceipt(EVIDENCE_DIGEST, authorization.plan_digest, AUTHORIZATION_DIGEST)
    executor, calls = _executor(monkeypatch)

    result = resume_replacement(
        executor,
        plan,
        authorization,
        receipt,
        evidence_digest=EVIDENCE_DIGEST,
        authorization_digest=AUTHORIZATION_DIGEST,
    )

    assert result == "executed"
    assert calls == [(plan, authorization)]


def test_resume_replacement_blocks_stale_evidence_before_execution(monkeypatch):
    plan = _replacement_plan()
    authorization = UnrealPlanAuthorization.issue(plan, "replacement-auth")
    receipt = RecoveryReceipt(EVIDENCE_DIGEST, authorization.plan_digest, AUTHORIZATION_DIGEST)
    executor, calls = _executor(monkeypatch)

    with pytest.raises(UnrealRecoveryExecutionError, match="fresh evidence"):
        resume_replacement(
            executor,
            plan,
            authorization,
            receipt,
            evidence_digest="stale-evidence-999",
            authorization_digest=AUTHORIZATION_DIGEST,
        )

    assert calls == []


def test_resume_replacement_blocks_modified_plan_before_execution(monkeypatch):
    plan = _replacement_plan()
    authorization = UnrealPlanAuthorization.issue(plan, "replacement-auth")
    modified = UnrealTaskPlan(
        plan.intent_id,
        (
            UnrealOperation(
                UnrealCapability.SEQUENCER,
                UnrealOperationKind.WRITE,
                "set_sequencer_playback_range",
                {"entity_ids": ENTITY_IDS, "start_frame": 11, "end_frame": 111},
                ENTITY_IDS,
            ),
            plan.operations[1],
        ),
    )
    receipt = RecoveryReceipt(EVIDENCE_DIGEST, authorization.plan_digest, AUTHORIZATION_DIGEST)
    executor, calls = _executor(monkeypatch)

    with pytest.raises(UnrealRecoveryExecutionError, match="exact replacement plan"):
        resume_replacement(
            executor,
            modified,
            authorization,
            receipt,
            evidence_digest=EVIDENCE_DIGEST,
            authorization_digest=AUTHORIZATION_DIGEST,
        )

    assert calls == []
