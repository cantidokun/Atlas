from planning.repository_intelligence.evaluation import (
    ContextEvaluationCase,
    aggregate_evaluations,
    evaluate_context,
    repeat_context,
)


def test_evaluation_reports_recall_precision_and_required_paths():
    case = ContextEvaluationCase(
        "case-1",
        frozenset({"src/a.py", "src/b.py"}),
        frozenset({"src/a.py"}),
    )
    result = evaluate_context(case, _context(["src/a.py", "tests/test_a.py"]))
    assert result.true_positive == 1
    assert result.false_positive == 1
    assert result.false_negative == 1
    assert result.required_missing == 0
    assert result.recall == 0.5
    assert result.precision == 0.5
    assert result.f1 == 0.5


def test_evaluation_uses_actual_context_budget():
    context = _context(["src/a.py"], max_context_chars=100)
    result = evaluate_context(ContextEvaluationCase("case-2", frozenset({"src/a.py"})), context)
    assert result.budget_utilization == len("content") / 100


def test_repeat_context_requires_identical_package_output():
    context = _context(["src/a.py"])
    identical = _context(["src/a.py"])
    different = _context(["src/b.py"])
    assert repeat_context(context, identical) is True
    assert repeat_context(context, different) is False


def test_evaluation_can_accept_explicit_determinism_result():
    case = ContextEvaluationCase("case-3", frozenset({"src/a.py"}))
    context = _context(["src/a.py"])
    result = evaluate_context(case, context, deterministic=False)
    assert result.deterministic is False


def test_aggregate_empty_and_nonempty():
    assert aggregate_evaluations([])["cases"] == 0
    case = ContextEvaluationCase("case-4", frozenset({"src/a.py"}))
    result = evaluate_context(case, _context(["src/a.py"]))
    aggregate = aggregate_evaluations([result])
    assert aggregate["cases"] == 1
    assert aggregate["recall"] == 1.0
    assert aggregate["required_missing"] == 0


def _context(paths, max_context_chars=48000):
    from planning.repository_intelligence.context import ContextFile, ContextPackage
    from planning.repository_intelligence.relevance import RelevanceQuery

    included = tuple(ContextFile(path, 1, ("test",), "content") for path in paths)
    return ContextPackage(
        query=RelevanceQuery.from_values(),
        repository_fingerprint="repo",
        included=included,
        excluded_paths=(),
        stable_instructions="",
        dynamic_state={},
        fingerprint="|".join(paths),
        max_context_chars=max_context_chars,
        max_file_chars=16000,
    )
