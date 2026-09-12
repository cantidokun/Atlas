from planning.repository_intelligence.m13_benchmark_diagnostics import diagnose_case, diagnose_results
from planning.repository_intelligence.evaluation import ContextEvaluationResult


def _result(**overrides):
    values = {
        "case_id": "case",
        "selected_paths": ("a.py",),
        "relevant_paths": ("a.py",),
        "required_paths": ("a.py",),
        "true_positive": 1,
        "false_positive": 0,
        "false_negative": 0,
        "required_missing": 0,
        "recall": 1.0,
        "precision": 1.0,
        "f1": 1.0,
        "budget_utilization": 0.1,
        "truncated_files": 0,
        "deterministic": True,
    }
    values.update(overrides)
    return ContextEvaluationResult(**values)


def test_required_context_missing_has_highest_priority():
    result = _result(
        selected_paths=(),
        true_positive=0,
        false_negative=1,
        required_missing=1,
    )
    assert diagnose_case(result).status == "required_context_missing"
    assert diagnose_case(result).missing_required == ("a.py",)


def test_non_determinism_is_reported_before_selection_quality():
    result = _result(deterministic=False)
    assert diagnose_case(result).status == "non_deterministic"


def test_diagnostics_are_sorted_by_case_id():
    results = (_result(case_id="z"), _result(case_id="a"))
    assert [item.case_id for item in diagnose_results(results)] == ["a", "z"]


def test_complete_selection_with_truncation_is_distinguished():
    result = _result(truncated_files=1)
    assert diagnose_case(result).status == "complete_selection_truncated"
    assert diagnose_case(result).truncated_files == ()
