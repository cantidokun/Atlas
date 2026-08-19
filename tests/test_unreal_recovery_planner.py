"""Tests for UnrealRecoveryPlanner.

Covers:
- Every evaluation outcome → correct recovery action
- Deterministic identical inputs → identical decisions
- Preservation of intent/entity context
- Retry-limit / exhaustion behaviour
- Malformed input rejection
- Guarantee that the recovery component has no execution side effects
"""

import pytest
from typing import Tuple

from planning.unreal_agent import (
    UnrealCapability,
    UnrealOperation,
    UnrealOperationKind,
    UnrealTaskIntent,
)
from planning.unreal_execution_evaluator import (
    EvaluationOutcome,
    NextAction,
    UnrealExecutionEvaluation,
)
from planning.unreal_recovery_planner import (
    RecoveryAction,
    RecoveryContext,
    RecoveryDecision,
    UnrealRecoveryPlanner,
)
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _intent(
    intent_id: str = "recovery-intent-1",
    targets: Tuple[str, ...] = ("/Game/Mesh_A",),
) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="recovery test",
        target_entity_ids=targets,
    )


def _make_plan(
    intent_id: str = "recovery-intent-1",
    targets: Tuple[str, ...] = ("/Game/Mesh_A",),
) -> UnrealTaskPlan:
    return UnrealTaskPlanner().plan_inspection(
        _intent(intent_id=intent_id, targets=targets)
    )


def _make_material_plan(
    intent_id: str = "recovery-intent-1",
    targets: Tuple[str, ...] = ("/Game/Mesh_A",),
) -> UnrealTaskPlan:
    return UnrealTaskPlanner().plan_material_variant(
        _intent(intent_id=intent_id, targets=targets)
    )


def _evaluation(
    intent_id: str = "recovery-intent-1",
    outcome: EvaluationOutcome = EvaluationOutcome.SATISFIED,
    next_action: NextAction = NextAction.REPORT_SUCCESS,
    reason: str = "test reason",
    operation_count: int = 2,
    evidence_count: int = 2,
    unverified_count: int = 0,
) -> UnrealExecutionEvaluation:
    return UnrealExecutionEvaluation(
        intent_id=intent_id,
        outcome=outcome,
        next_action=next_action,
        reason=reason,
        operation_count=operation_count,
        evidence_count=evidence_count,
        unverified_count=unverified_count,
    )


def _ctx(attempt: int = 1, max_attempts: int = 3) -> RecoveryContext:
    return RecoveryContext(attempt=attempt, max_attempts=max_attempts)


# ---------------------------------------------------------------------------
# RecoveryContext validation
# ---------------------------------------------------------------------------

class TestRecoveryContextValidation:
    def test_valid_context(self):
        ctx = RecoveryContext(attempt=1, max_attempts=3)
        assert ctx.attempt == 1
        assert ctx.max_attempts == 3
        assert ctx.retries_remaining == 2
        assert ctx.exhausted is False

    def test_exhausted_context(self):
        ctx = RecoveryContext(attempt=3, max_attempts=3)
        assert ctx.exhausted is True
        assert ctx.retries_remaining == 0

    def test_attempt_zero_rejected(self):
        with pytest.raises(ValueError, match="attempt"):
            RecoveryContext(attempt=0, max_attempts=3)

    def test_negative_attempt_rejected(self):
        with pytest.raises(ValueError, match="attempt"):
            RecoveryContext(attempt=-1, max_attempts=3)

    def test_max_attempts_zero_rejected(self):
        with pytest.raises(ValueError, match="max_attempts"):
            RecoveryContext(attempt=1, max_attempts=0)

    def test_negative_max_attempts_rejected(self):
        with pytest.raises(ValueError, match="max_attempts"):
            RecoveryContext(attempt=1, max_attempts=-1)

    def test_attempt_exceeds_max_rejected(self):
        with pytest.raises(ValueError, match="must not exceed"):
            RecoveryContext(attempt=4, max_attempts=3)

    def test_frozen(self):
        ctx = RecoveryContext(attempt=1, max_attempts=3)
        with pytest.raises(AttributeError):
            ctx.attempt = 2


# ---------------------------------------------------------------------------
# RecoveryDecision validation
# ---------------------------------------------------------------------------

class TestRecoveryDecisionValidation:
    def test_empty_intent_id_rejected(self):
        with pytest.raises(ValueError, match="intent_id"):
            RecoveryDecision(
                intent_id="",
                entity_ids=("/Game/A",),
                action=RecoveryAction.NO_ACTION,
                reason="ok",
                source_outcome=EvaluationOutcome.SATISFIED,
                attempt=1,
                max_attempts=3,
                retries_remaining=2,
            )

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            RecoveryDecision(
                intent_id="x",
                entity_ids=("/Game/A",),
                action=RecoveryAction.NO_ACTION,
                reason="",
                source_outcome=EvaluationOutcome.SATISFIED,
                attempt=1,
                max_attempts=3,
                retries_remaining=2,
            )

    def test_negative_attempt_rejected(self):
        with pytest.raises(ValueError, match="attempt"):
            RecoveryDecision(
                intent_id="x",
                entity_ids=("/Game/A",),
                action=RecoveryAction.NO_ACTION,
                reason="ok",
                source_outcome=EvaluationOutcome.SATISFIED,
                attempt=-1,
                max_attempts=3,
                retries_remaining=2,
            )

    def test_frozen(self):
        plan = _make_plan()
        ev = _evaluation()
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx())
        with pytest.raises(AttributeError):
            decision.action = RecoveryAction.REQUEST_RECOVERY

    def test_terminal_property_no_action(self):
        plan = _make_plan()
        ev = _evaluation()
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx())
        assert decision.terminal is True

    def test_terminal_property_request_recovery(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.FAILED,
            next_action=NextAction.REPORT_FAILURE,
        )
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx())
        assert decision.terminal is False


# ---------------------------------------------------------------------------
# SATISFIED outcome
# ---------------------------------------------------------------------------

class TestSatisfiedOutcome:
    def test_satisfied_yields_no_action(self):
        plan = _make_plan()
        ev = _evaluation(outcome=EvaluationOutcome.SATISFIED)
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx())

        assert decision.action == RecoveryAction.NO_ACTION
        assert decision.source_outcome == EvaluationOutcome.SATISFIED

    def test_satisfied_reason_non_empty(self):
        plan = _make_plan()
        ev = _evaluation(outcome=EvaluationOutcome.SATISFIED)
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx())

        assert len(decision.reason.strip()) > 0

    def test_satisfied_even_when_exhausted(self):
        plan = _make_plan()
        ev = _evaluation(outcome=EvaluationOutcome.SATISFIED)
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx(3, 3))

        assert decision.action == RecoveryAction.NO_ACTION

    def test_satisfied_is_terminal(self):
        plan = _make_plan()
        ev = _evaluation(outcome=EvaluationOutcome.SATISFIED)
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx())

        assert decision.terminal is True


# ---------------------------------------------------------------------------
# VERIFICATION_REQUIRED outcome
# ---------------------------------------------------------------------------

class TestVerificationRequiredOutcome:
    def test_verification_required_yields_request_verification(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.VERIFICATION_REQUIRED,
            next_action=NextAction.REQUEST_VERIFICATION,
            unverified_count=1,
        )
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx())

        assert decision.action == RecoveryAction.REQUEST_VERIFICATION
        assert decision.source_outcome == EvaluationOutcome.VERIFICATION_REQUIRED

    def test_verification_required_exhausted_yields_review(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.VERIFICATION_REQUIRED,
            next_action=NextAction.REQUEST_VERIFICATION,
            unverified_count=2,
        )
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx(3, 3))

        assert decision.action == RecoveryAction.REQUEST_REVIEW
        assert decision.retries_remaining == 0

    def test_verification_required_not_terminal(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.VERIFICATION_REQUIRED,
            next_action=NextAction.REQUEST_VERIFICATION,
            unverified_count=1,
        )
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx())

        assert decision.terminal is False

    def test_verification_required_exhausted_is_terminal(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.VERIFICATION_REQUIRED,
            next_action=NextAction.REQUEST_VERIFICATION,
            unverified_count=1,
        )
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx(3, 3))

        assert decision.terminal is True


# ---------------------------------------------------------------------------
# FAILED outcome
# ---------------------------------------------------------------------------

class TestFailedOutcome:
    def test_failed_yields_request_recovery(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.FAILED,
            next_action=NextAction.REPORT_FAILURE,
        )
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx())

        assert decision.action == RecoveryAction.REQUEST_RECOVERY
        assert decision.source_outcome == EvaluationOutcome.FAILED

    def test_failed_exhausted_yields_review(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.FAILED,
            next_action=NextAction.REPORT_FAILURE,
        )
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx(3, 3))

        assert decision.action == RecoveryAction.REQUEST_REVIEW
        assert decision.retries_remaining == 0

    def test_failed_never_yields_no_action(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.FAILED,
            next_action=NextAction.REPORT_FAILURE,
        )
        for attempt in range(1, 4):
            decision = UnrealRecoveryPlanner().decide(
                ev, plan, _ctx(attempt, 3)
            )
            assert decision.action != RecoveryAction.NO_ACTION

    def test_failed_not_terminal_when_retries_remain(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.FAILED,
            next_action=NextAction.REPORT_FAILURE,
        )
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx(1, 3))

        assert decision.terminal is False


# ---------------------------------------------------------------------------
# INCOMPLETE outcome
# ---------------------------------------------------------------------------

class TestIncompleteOutcome:
    def test_incomplete_yields_request_recovery(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.INCOMPLETE,
            next_action=NextAction.REQUEST_RETRY,
            evidence_count=1,
        )
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx())

        assert decision.action == RecoveryAction.REQUEST_RECOVERY
        assert decision.source_outcome == EvaluationOutcome.INCOMPLETE

    def test_incomplete_exhausted_yields_review(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.INCOMPLETE,
            next_action=NextAction.REQUEST_RETRY,
            evidence_count=1,
        )
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx(3, 3))

        assert decision.action == RecoveryAction.REQUEST_REVIEW

    def test_incomplete_never_yields_satisfied(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.INCOMPLETE,
            next_action=NextAction.REQUEST_RETRY,
            evidence_count=0,
        )
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx())

        assert decision.action != RecoveryAction.NO_ACTION


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_identical_inputs_produce_identical_decisions(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.FAILED,
            next_action=NextAction.REPORT_FAILURE,
        )
        ctx = _ctx()
        planner = UnrealRecoveryPlanner()

        decision_a = planner.decide(ev, plan, ctx)
        decision_b = planner.decide(ev, plan, ctx)

        assert decision_a == decision_b

    def test_separate_instances_same_result(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.VERIFICATION_REQUIRED,
            next_action=NextAction.REQUEST_VERIFICATION,
            unverified_count=1,
        )
        ctx = _ctx()

        decision_a = UnrealRecoveryPlanner().decide(ev, plan, ctx)
        decision_b = UnrealRecoveryPlanner().decide(ev, plan, ctx)

        assert decision_a == decision_b

    def test_determinism_across_many_invocations(self):
        plan = _make_material_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.INCOMPLETE,
            next_action=NextAction.REQUEST_RETRY,
            operation_count=4,
            evidence_count=2,
        )
        ctx = _ctx(2, 5)
        planner = UnrealRecoveryPlanner()
        reference = planner.decide(ev, plan, ctx)

        for _ in range(20):
            assert planner.decide(ev, plan, ctx) == reference

    def test_satisfied_determinism(self):
        plan = _make_plan()
        ev = _evaluation(outcome=EvaluationOutcome.SATISFIED)
        ctx = _ctx()
        planner = UnrealRecoveryPlanner()

        decision_a = planner.decide(ev, plan, ctx)
        decision_b = planner.decide(ev, plan, ctx)

        assert decision_a == decision_b


# ---------------------------------------------------------------------------
# Preservation of intent/entity context
# ---------------------------------------------------------------------------

class TestContextPreservation:
    def test_intent_id_preserved(self):
        plan = _make_plan(intent_id="my-intent-42")
        ev = _evaluation(intent_id="my-intent-42")
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx())

        assert decision.intent_id == "my-intent-42"

    def test_entity_ids_preserved_single(self):
        targets = ("/Game/Mesh_A",)
        plan = _make_plan(targets=targets)
        ev = _evaluation()
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx())

        assert decision.entity_ids == targets

    def test_entity_ids_preserved_multiple(self):
        targets = ("/Game/Mesh_A", "/Game/Mesh_B")
        plan = _make_plan(targets=targets)
        ev = _evaluation()
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx())

        assert decision.entity_ids == targets

    def test_entity_ids_from_material_plan(self):
        targets = ("/Game/X", "/Game/Y")
        plan = _make_material_plan(targets=targets)
        ev = _evaluation(
            outcome=EvaluationOutcome.FAILED,
            next_action=NextAction.REPORT_FAILURE,
            operation_count=4,
        )
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx())

        assert decision.entity_ids == targets

    def test_attempt_and_max_preserved(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.FAILED,
            next_action=NextAction.REPORT_FAILURE,
        )
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx(2, 5))

        assert decision.attempt == 2
        assert decision.max_attempts == 5
        assert decision.retries_remaining == 3


# ---------------------------------------------------------------------------
# Retry-limit behaviour
# ---------------------------------------------------------------------------

class TestRetryLimitBehaviour:
    def test_single_attempt_budget_failed_yields_review(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.FAILED,
            next_action=NextAction.REPORT_FAILURE,
        )
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx(1, 1))

        assert decision.action == RecoveryAction.REQUEST_REVIEW
        assert decision.retries_remaining == 0

    def test_single_attempt_budget_incomplete_yields_review(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.INCOMPLETE,
            next_action=NextAction.REQUEST_RETRY,
            evidence_count=0,
        )
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx(1, 1))

        assert decision.action == RecoveryAction.REQUEST_REVIEW

    def test_single_attempt_budget_verification_yields_review(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.VERIFICATION_REQUIRED,
            next_action=NextAction.REQUEST_VERIFICATION,
            unverified_count=2,
        )
        decision = UnrealRecoveryPlanner().decide(ev, plan, _ctx(1, 1))

        assert decision.action == RecoveryAction.REQUEST_REVIEW

    def test_progressive_exhaustion_failed(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.FAILED,
            next_action=NextAction.REPORT_FAILURE,
        )
        planner = UnrealRecoveryPlanner()

        d1 = planner.decide(ev, plan, _ctx(1, 3))
        assert d1.action == RecoveryAction.REQUEST_RECOVERY
        assert d1.retries_remaining == 2

        d2 = planner.decide(ev, plan, _ctx(2, 3))
        assert d2.action == RecoveryAction.REQUEST_RECOVERY
        assert d2.retries_remaining == 1

        d3 = planner.decide(ev, plan, _ctx(3, 3))
        assert d3.action == RecoveryAction.REQUEST_REVIEW
        assert d3.retries_remaining == 0

    def test_progressive_exhaustion_verification(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.VERIFICATION_REQUIRED,
            next_action=NextAction.REQUEST_VERIFICATION,
            unverified_count=1,
        )
        planner = UnrealRecoveryPlanner()

        d1 = planner.decide(ev, plan, _ctx(1, 2))
        assert d1.action == RecoveryAction.REQUEST_VERIFICATION

        d2 = planner.decide(ev, plan, _ctx(2, 2))
        assert d2.action == RecoveryAction.REQUEST_REVIEW


# ---------------------------------------------------------------------------
# Malformed input rejection
# ---------------------------------------------------------------------------

class TestMalformedInputRejection:
    def test_non_evaluation_rejected(self):
        plan = _make_plan()
        with pytest.raises(TypeError, match="UnrealExecutionEvaluation"):
            UnrealRecoveryPlanner().decide("not-an-eval", plan, _ctx())

    def test_none_evaluation_rejected(self):
        plan = _make_plan()
        with pytest.raises(TypeError, match="UnrealExecutionEvaluation"):
            UnrealRecoveryPlanner().decide(None, plan, _ctx())

    def test_non_plan_rejected(self):
        ev = _evaluation()
        with pytest.raises(TypeError, match="UnrealTaskPlan"):
            UnrealRecoveryPlanner().decide(ev, "not-a-plan", _ctx())

    def test_none_plan_rejected(self):
        ev = _evaluation()
        with pytest.raises(TypeError, match="UnrealTaskPlan"):
            UnrealRecoveryPlanner().decide(ev, None, _ctx())

    def test_non_context_rejected(self):
        plan = _make_plan()
        ev = _evaluation()
        with pytest.raises(TypeError, match="RecoveryContext"):
            UnrealRecoveryPlanner().decide(ev, plan, "not-a-context")

    def test_none_context_rejected(self):
        plan = _make_plan()
        ev = _evaluation()
        with pytest.raises(TypeError, match="RecoveryContext"):
            UnrealRecoveryPlanner().decide(ev, plan, None)

    def test_intent_id_mismatch_rejected(self):
        plan = _make_plan(intent_id="plan-id")
        ev = _evaluation(intent_id="different-id")
        with pytest.raises(ValueError, match="intent_id"):
            UnrealRecoveryPlanner().decide(ev, plan, _ctx())


# ---------------------------------------------------------------------------
# No execution side effects
# ---------------------------------------------------------------------------

class TestNoSideEffects:
    def test_decide_does_not_modify_evaluation(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.FAILED,
            next_action=NextAction.REPORT_FAILURE,
        )
        ctx = _ctx()

        # Capture original values
        original_outcome = ev.outcome
        original_intent = ev.intent_id

        UnrealRecoveryPlanner().decide(ev, plan, ctx)

        assert ev.outcome == original_outcome
        assert ev.intent_id == original_intent

    def test_decide_does_not_modify_plan(self):
        plan = _make_plan()
        ev = _evaluation()
        ctx = _ctx()

        original_id = plan.intent_id
        original_ops = plan.operations

        UnrealRecoveryPlanner().decide(ev, plan, ctx)

        assert plan.intent_id == original_id
        assert plan.operations == original_ops

    def test_decide_does_not_modify_context(self):
        plan = _make_plan()
        ev = _evaluation()
        ctx = _ctx(2, 5)

        original_attempt = ctx.attempt
        original_max = ctx.max_attempts

        UnrealRecoveryPlanner().decide(ev, plan, ctx)

        assert ctx.attempt == original_attempt
        assert ctx.max_attempts == original_max

    def test_repeated_calls_produce_no_accumulation(self):
        plan = _make_plan()
        ev = _evaluation(
            outcome=EvaluationOutcome.INCOMPLETE,
            next_action=NextAction.REQUEST_RETRY,
            evidence_count=1,
        )
        ctx = _ctx()
        planner = UnrealRecoveryPlanner()

        reference = planner.decide(ev, plan, ctx)
        for _ in range(10):
            assert planner.decide(ev, plan, ctx) == reference

    def test_planner_has_no_mutable_state(self):
        """The planner instance should not accumulate state across calls."""
        planner = UnrealRecoveryPlanner()
        plan = _make_plan()
        ev_fail = _evaluation(
            outcome=EvaluationOutcome.FAILED,
            next_action=NextAction.REPORT_FAILURE,
        )
        ev_ok = _evaluation(outcome=EvaluationOutcome.SATISFIED)

        d_fail = planner.decide(ev_fail, plan, _ctx())
        d_ok = planner.decide(ev_ok, plan, _ctx())

        assert d_fail.action == RecoveryAction.REQUEST_RECOVERY
        assert d_ok.action == RecoveryAction.NO_ACTION

        # Re-check fail hasn't changed
        d_fail_again = planner.decide(ev_fail, plan, _ctx())
        assert d_fail_again == d_fail
