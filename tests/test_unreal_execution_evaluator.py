"""Tests for UnrealExecutionEvaluator.

Covers:
- Successful completion (all verified)
- Failed execution
- Incomplete evidence (fewer entries than operations)
- Verification-required outcomes (unverified evidence)
- Deterministic identical inputs → identical evaluations
- Rejection of malformed / mismatched execution results
- Evidence–operation name mismatch detection
- Intent-id mismatch rejection
"""

import pytest
from typing import Tuple

from planning.unreal_agent import (
    UnrealCapability,
    UnrealOperation,
    UnrealOperationKind,
    UnrealTaskIntent,
)
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_execution_evaluator import (
    EvaluationOutcome,
    NextAction,
    UnrealExecutionEvaluation,
    UnrealExecutionEvaluator,
)
from planning.unreal_plan_executor import UnrealPlanExecutionResult
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _intent(
    intent_id: str = "eval-intent-1",
    targets: Tuple[str, ...] = ("/Game/Mesh_A",),
) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="evaluator test",
        target_entity_ids=targets,
    )


def _evidence(
    operation_name: str,
    entity_ids: Tuple[str, ...] = ("/Game/Mesh_A",),
    verified: bool = False,
    source: str = "test",
) -> UnrealEvidence:
    return UnrealEvidence(
        operation_name=operation_name,
        entity_ids=entity_ids,
        observed_state={"status": "ok"},
        source=source,
        verified=verified,
    )


def _make_inspection_plan(
    intent_id: str = "eval-intent-1",
    targets: Tuple[str, ...] = ("/Game/Mesh_A",),
) -> UnrealTaskPlan:
    return UnrealTaskPlanner().plan_inspection(
        _intent(intent_id=intent_id, targets=targets)
    )


def _make_material_plan(
    intent_id: str = "eval-intent-1",
    targets: Tuple[str, ...] = ("/Game/Mesh_A",),
) -> UnrealTaskPlan:
    return UnrealTaskPlanner().plan_material_variant(
        _intent(intent_id=intent_id, targets=targets)
    )


def _full_verified_ledger(plan: UnrealTaskPlan) -> Tuple[UnrealEvidence, ...]:
    """Build a ledger where every operation has verified evidence."""
    return tuple(
        _evidence(
            operation_name=op.name,
            entity_ids=tuple(op.entity_ids),
            verified=True,
        )
        for op in plan.operations
    )


def _full_unverified_ledger(plan: UnrealTaskPlan) -> Tuple[UnrealEvidence, ...]:
    """Build a ledger where every operation has unverified evidence."""
    return tuple(
        _evidence(
            operation_name=op.name,
            entity_ids=tuple(op.entity_ids),
            verified=False,
        )
        for op in plan.operations
    )


def _success_result(
    plan: UnrealTaskPlan,
    ledger: Tuple[UnrealEvidence, ...],
) -> UnrealPlanExecutionResult:
    return UnrealPlanExecutionResult(
        intent_id=plan.intent_id,
        evidence_ledger=ledger,
        success=True,
    )


def _failed_result(
    plan: UnrealTaskPlan,
    ledger: Tuple[UnrealEvidence, ...] = (),
) -> UnrealPlanExecutionResult:
    return UnrealPlanExecutionResult(
        intent_id=plan.intent_id,
        evidence_ledger=ledger,
        success=False,
    )


# ---------------------------------------------------------------------------
# Successful completion
# ---------------------------------------------------------------------------

class TestSuccessfulCompletion:
    def test_all_verified_yields_satisfied(self):
        plan = _make_inspection_plan()
        ledger = _full_verified_ledger(plan)
        result = _success_result(plan, ledger)

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert evaluation.outcome == EvaluationOutcome.SATISFIED
        assert evaluation.next_action == NextAction.REPORT_SUCCESS
        assert evaluation.unverified_count == 0

    def test_material_variant_all_verified_yields_satisfied(self):
        plan = _make_material_plan()
        ledger = _full_verified_ledger(plan)
        result = _success_result(plan, ledger)

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert evaluation.outcome == EvaluationOutcome.SATISFIED
        assert evaluation.evidence_count == 4
        assert evaluation.operation_count == 4

    def test_satisfied_intent_id_matches(self):
        plan = _make_inspection_plan(intent_id="my-id")
        ledger = _full_verified_ledger(plan)
        result = _success_result(plan, ledger)

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert evaluation.intent_id == "my-id"

    def test_satisfied_reason_is_non_empty(self):
        plan = _make_inspection_plan()
        ledger = _full_verified_ledger(plan)
        result = _success_result(plan, ledger)

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert len(evaluation.reason.strip()) > 0


# ---------------------------------------------------------------------------
# Failed execution
# ---------------------------------------------------------------------------

class TestFailedExecution:
    def test_failed_result_yields_failed_outcome(self):
        plan = _make_inspection_plan()
        result = _failed_result(plan)

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert evaluation.outcome == EvaluationOutcome.FAILED
        assert evaluation.next_action == NextAction.REPORT_FAILURE

    def test_failed_with_partial_ledger(self):
        plan = _make_material_plan()
        partial = (_evidence(plan.operations[0].name),)
        result = UnrealPlanExecutionResult(
            intent_id=plan.intent_id,
            evidence_ledger=partial,
            success=False,
        )

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert evaluation.outcome == EvaluationOutcome.FAILED
        assert evaluation.evidence_count == 1

    def test_failed_never_returns_satisfied(self):
        plan = _make_inspection_plan()
        # Even with a full verified ledger, success=False must yield FAILED
        ledger = _full_verified_ledger(plan)
        result = UnrealPlanExecutionResult(
            intent_id=plan.intent_id,
            evidence_ledger=ledger,
            success=False,
        )

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert evaluation.outcome == EvaluationOutcome.FAILED
        assert evaluation.outcome != EvaluationOutcome.SATISFIED


# ---------------------------------------------------------------------------
# Incomplete evidence
# ---------------------------------------------------------------------------

class TestIncompleteEvidence:
    def test_fewer_evidence_than_operations_yields_incomplete(self):
        plan = _make_material_plan()
        # Only provide 2 of 4 expected evidence entries
        partial = tuple(
            _evidence(op.name, tuple(op.entity_ids))
            for op in plan.operations[:2]
        )
        result = _success_result(plan, partial)

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert evaluation.outcome == EvaluationOutcome.INCOMPLETE
        assert evaluation.next_action == NextAction.REQUEST_RETRY
        assert evaluation.evidence_count == 2
        assert evaluation.operation_count == 4

    def test_empty_ledger_yields_incomplete(self):
        plan = _make_inspection_plan()
        result = _success_result(plan, ())

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert evaluation.outcome == EvaluationOutcome.INCOMPLETE

    def test_one_short_yields_incomplete(self):
        plan = _make_inspection_plan()
        # Inspection has 2 ops; provide only 1
        partial = (_evidence(plan.operations[0].name),)
        result = _success_result(plan, partial)

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert evaluation.outcome == EvaluationOutcome.INCOMPLETE
        assert evaluation.evidence_count == 1


# ---------------------------------------------------------------------------
# Verification required
# ---------------------------------------------------------------------------

class TestVerificationRequired:
    def test_all_unverified_yields_verification_required(self):
        plan = _make_inspection_plan()
        ledger = _full_unverified_ledger(plan)
        result = _success_result(plan, ledger)

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert evaluation.outcome == EvaluationOutcome.VERIFICATION_REQUIRED
        assert evaluation.next_action == NextAction.REQUEST_VERIFICATION
        assert evaluation.unverified_count == len(plan.operations)

    def test_one_unverified_yields_verification_required(self):
        plan = _make_inspection_plan()
        ledger = (
            _evidence(plan.operations[0].name, verified=True),
            _evidence(plan.operations[1].name, verified=False),
        )
        result = _success_result(plan, ledger)

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert evaluation.outcome == EvaluationOutcome.VERIFICATION_REQUIRED
        assert evaluation.unverified_count == 1

    def test_material_variant_mixed_verification(self):
        plan = _make_material_plan()
        ledger = tuple(
            _evidence(
                op.name,
                tuple(op.entity_ids),
                verified=(i % 2 == 0),
            )
            for i, op in enumerate(plan.operations)
        )
        result = _success_result(plan, ledger)

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert evaluation.outcome == EvaluationOutcome.VERIFICATION_REQUIRED
        assert evaluation.unverified_count == 2


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_identical_inputs_produce_identical_evaluations(self):
        plan = _make_material_plan()
        ledger = _full_unverified_ledger(plan)
        result = _success_result(plan, ledger)

        evaluator = UnrealExecutionEvaluator()
        eval_a = evaluator.evaluate(plan, result)
        eval_b = evaluator.evaluate(plan, result)

        assert eval_a == eval_b

    def test_separate_evaluator_instances_same_result(self):
        plan = _make_inspection_plan()
        ledger = _full_verified_ledger(plan)
        result = _success_result(plan, ledger)

        eval_a = UnrealExecutionEvaluator().evaluate(plan, result)
        eval_b = UnrealExecutionEvaluator().evaluate(plan, result)

        assert eval_a == eval_b

    def test_determinism_across_many_invocations(self):
        plan = _make_material_plan()
        ledger = _full_verified_ledger(plan)
        result = _success_result(plan, ledger)

        evaluator = UnrealExecutionEvaluator()
        reference = evaluator.evaluate(plan, result)
        for _ in range(20):
            assert evaluator.evaluate(plan, result) == reference

    def test_failed_determinism(self):
        plan = _make_inspection_plan()
        result = _failed_result(plan)

        evaluator = UnrealExecutionEvaluator()
        eval_a = evaluator.evaluate(plan, result)
        eval_b = evaluator.evaluate(plan, result)

        assert eval_a == eval_b


# ---------------------------------------------------------------------------
# Malformed / invalid input rejection
# ---------------------------------------------------------------------------

class TestMalformedInputRejection:
    def test_non_plan_rejected(self):
        result = UnrealPlanExecutionResult(
            intent_id="x", evidence_ledger=(), success=True,
        )
        with pytest.raises(TypeError, match="UnrealTaskPlan"):
            UnrealExecutionEvaluator().evaluate("not-a-plan", result)

    def test_non_result_rejected(self):
        plan = _make_inspection_plan()
        with pytest.raises(TypeError, match="UnrealPlanExecutionResult"):
            UnrealExecutionEvaluator().evaluate(plan, "not-a-result")

    def test_none_plan_rejected(self):
        result = UnrealPlanExecutionResult(
            intent_id="x", evidence_ledger=(), success=True,
        )
        with pytest.raises(TypeError, match="UnrealTaskPlan"):
            UnrealExecutionEvaluator().evaluate(None, result)

    def test_none_result_rejected(self):
        plan = _make_inspection_plan()
        with pytest.raises(TypeError, match="UnrealPlanExecutionResult"):
            UnrealExecutionEvaluator().evaluate(plan, None)

    def test_intent_id_mismatch_rejected(self):
        plan = _make_inspection_plan(intent_id="plan-id")
        result = UnrealPlanExecutionResult(
            intent_id="different-id",
            evidence_ledger=(),
            success=True,
        )
        with pytest.raises(ValueError, match="intent_id"):
            UnrealExecutionEvaluator().evaluate(plan, result)


# ---------------------------------------------------------------------------
# Evidence–operation name mismatch
# ---------------------------------------------------------------------------

class TestEvidenceOperationMismatch:
    def test_wrong_operation_name_yields_incomplete(self):
        plan = _make_inspection_plan()
        ledger = (
            _evidence("wrong_name_1"),
            _evidence("wrong_name_2"),
        )
        result = _success_result(plan, ledger)

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert evaluation.outcome == EvaluationOutcome.INCOMPLETE
        assert evaluation.next_action == NextAction.REQUEST_RETRY

    def test_partial_name_mismatch_yields_incomplete(self):
        plan = _make_inspection_plan()
        ledger = (
            _evidence(plan.operations[0].name),  # correct
            _evidence("totally_wrong"),            # wrong
        )
        result = _success_result(plan, ledger)

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert evaluation.outcome == EvaluationOutcome.INCOMPLETE

    def test_swapped_operation_names_yields_incomplete(self):
        plan = _make_inspection_plan()
        # Swap the two operation names
        ledger = (
            _evidence(plan.operations[1].name),
            _evidence(plan.operations[0].name),
        )
        result = _success_result(plan, ledger)

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert evaluation.outcome == EvaluationOutcome.INCOMPLETE


# ---------------------------------------------------------------------------
# Evaluation dataclass validation
# ---------------------------------------------------------------------------

class TestEvaluationDataclassValidation:
    def test_empty_intent_id_rejected(self):
        with pytest.raises(ValueError, match="intent_id"):
            UnrealExecutionEvaluation(
                intent_id="",
                outcome=EvaluationOutcome.SATISFIED,
                next_action=NextAction.REPORT_SUCCESS,
                reason="ok",
                operation_count=1,
                evidence_count=1,
                unverified_count=0,
            )

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            UnrealExecutionEvaluation(
                intent_id="x",
                outcome=EvaluationOutcome.SATISFIED,
                next_action=NextAction.REPORT_SUCCESS,
                reason="",
                operation_count=1,
                evidence_count=1,
                unverified_count=0,
            )

    def test_negative_operation_count_rejected(self):
        with pytest.raises(ValueError, match="operation_count"):
            UnrealExecutionEvaluation(
                intent_id="x",
                outcome=EvaluationOutcome.SATISFIED,
                next_action=NextAction.REPORT_SUCCESS,
                reason="ok",
                operation_count=-1,
                evidence_count=1,
                unverified_count=0,
            )

    def test_negative_evidence_count_rejected(self):
        with pytest.raises(ValueError, match="evidence_count"):
            UnrealExecutionEvaluation(
                intent_id="x",
                outcome=EvaluationOutcome.SATISFIED,
                next_action=NextAction.REPORT_SUCCESS,
                reason="ok",
                operation_count=1,
                evidence_count=-1,
                unverified_count=0,
            )

    def test_negative_unverified_count_rejected(self):
        with pytest.raises(ValueError, match="unverified_count"):
            UnrealExecutionEvaluation(
                intent_id="x",
                outcome=EvaluationOutcome.SATISFIED,
                next_action=NextAction.REPORT_SUCCESS,
                reason="ok",
                operation_count=1,
                evidence_count=1,
                unverified_count=-1,
            )

    def test_frozen_evaluation(self):
        plan = _make_inspection_plan()
        ledger = _full_verified_ledger(plan)
        result = _success_result(plan, ledger)
        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        with pytest.raises(AttributeError):
            evaluation.outcome = EvaluationOutcome.FAILED


# ---------------------------------------------------------------------------
# Priority ordering: failed > incomplete > verification_required > satisfied
# ---------------------------------------------------------------------------

class TestOutcomePriority:
    """Verify that failure always dominates, even with full verified evidence."""

    def test_failed_dominates_full_verified_ledger(self):
        plan = _make_inspection_plan()
        ledger = _full_verified_ledger(plan)
        result = UnrealPlanExecutionResult(
            intent_id=plan.intent_id,
            evidence_ledger=ledger,
            success=False,
        )

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert evaluation.outcome == EvaluationOutcome.FAILED

    def test_incomplete_dominates_unverified(self):
        """If evidence is both incomplete and unverified, INCOMPLETE wins."""
        plan = _make_material_plan()
        partial = (_evidence(plan.operations[0].name, verified=False),)
        result = _success_result(plan, partial)

        evaluation = UnrealExecutionEvaluator().evaluate(plan, result)

        assert evaluation.outcome == EvaluationOutcome.INCOMPLETE
