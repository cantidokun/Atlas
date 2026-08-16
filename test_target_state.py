import pytest

from planning.target_state import (
    StateInvariant,
    TargetStateEvaluationError,
    TargetStateEvaluator,
)


def test_all_invariants_must_pass():
    evaluator = TargetStateEvaluator(
        [
            StateInvariant("left", lambda evidence: evidence["left"] == 1),
            StateInvariant("right", lambda evidence: evidence["right"] == 2),
        ]
    )

    result = evaluator.evaluate({"left": 1, "right": 2})

    assert result.satisfied is True
    assert result.failed == []
    assert result.snapshot()["invariants"] == {"left": True, "right": True}


def test_single_failed_invariant_prevents_noop():
    evaluator = TargetStateEvaluator(
        [
            StateInvariant("left", lambda evidence: evidence["left"] == 1),
            StateInvariant("right", lambda evidence: evidence["right"] == 2),
        ]
    )

    result = evaluator.evaluate({"left": 1, "right": 3})

    assert result.satisfied is False
    assert result.failed == ["right"]


def test_invariant_errors_fail_closed():
    evaluator = TargetStateEvaluator(
        [StateInvariant("required", lambda evidence: evidence["missing"] == 1)]
    )

    with pytest.raises(TargetStateEvaluationError, match="could not be evaluated"):
        evaluator.evaluate({})


def test_non_boolean_invariant_result_is_rejected():
    evaluator = TargetStateEvaluator(
        [StateInvariant("bad", lambda evidence: "yes")]
    )

    with pytest.raises(TargetStateEvaluationError, match="must return bool"):
        evaluator.evaluate({})


def test_empty_evaluator_is_rejected():
    with pytest.raises(ValueError, match="At least one"):
        TargetStateEvaluator([])


def test_duplicate_invariant_names_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        TargetStateEvaluator(
            [
                StateInvariant("same", lambda evidence: True),
                StateInvariant("same", lambda evidence: True),
            ]
        )
