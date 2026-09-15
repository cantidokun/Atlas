from planning.repository_intelligence.benchmark import ContextBenchmarkCase, ContextBenchmarkResult
from planning.repository_intelligence.evaluation import ContextEvaluationResult
from planning.repository_intelligence.index import GitHistory, RepositoryIndex
from planning.repository_intelligence.m13_rank_diagnostics import diagnose_rankings, ranking_diagnostic_report
from planning.repository_intelligence.relevance import RelevanceQuery


def _index(*paths: str) -> RepositoryIndex:
    files = tuple(
        {
            "path": path,
            "kind": "python_source",
            "language": "python",
            "size_bytes": 1,
            "line_count": 1,
            "sha256": "0" * 64,
            "is_test": path.startswith("tests/"),
            "parse_status": "ok",
            "content_terms": (),
        }
        for path in paths
    )
    return RepositoryIndex(".", files, (), (), GitHistory(None, ()), "fingerprint")


def _case() -> ContextBenchmarkCase:
    return ContextBenchmarkCase(
        "ranking-case",
        "bug_fix",
        "Explain ranking behavior.",
        RelevanceQuery.from_values(
            text="fix repository relevance scoring",
            paths=["planning/repository_intelligence/context.py"],
        ),
        frozenset(
            {
                "planning/repository_intelligence/context.py",
                "planning/repository_intelligence/relevance.py",
            }
        ),
        frozenset({"planning/repository_intelligence/relevance.py"}),
    )


def test_diagnose_rankings_exposes_score_rank_and_reasons_for_missing_required_path():
    case = _case()
    result = ContextBenchmarkResult(
        (
            ContextEvaluationResult(
                case.case_id,
                ("planning/repository_intelligence/context.py",),
                tuple(case.relevant_paths),
                tuple(case.required_paths),
                1,
                1,
                0,
                0,
                1.0,
                0.5,
                0.6666666667,
                1.0,
                0,
                True,
            ),
        ),
        {},
    )
    diagnostics = diagnose_rankings(
        _index(
            "planning/repository_intelligence/context.py",
            "planning/repository_intelligence/relevance.py",
        ),
        (case,),
        result,
    )
    relevance = next(item for item in diagnostics[0].paths if item.path.endswith("relevance.py"))
    assert relevance.required is True
    assert relevance.selected is False
    assert relevance.rank is not None
    assert relevance.score > 0
    assert relevance.reasons


def test_ranking_diagnostic_report_contains_no_source_content():
    case = _case()
    result = ContextBenchmarkResult(
        (
            ContextEvaluationResult(
                case.case_id,
                ("planning/repository_intelligence/context.py",),
                tuple(case.relevant_paths),
                tuple(case.required_paths),
                1,
                1,
                0,
                0,
                1.0,
                0.5,
                0.6666666667,
                1.0,
                0,
                True,
            ),
        ),
        {},
    )
    report = ranking_diagnostic_report(
        diagnose_rankings(
            _index(
                "planning/repository_intelligence/context.py",
                "planning/repository_intelligence/relevance.py",
            ),
            (case,),
            result,
        )
    )
    assert report[0]["case_id"] == "ranking-case"
    assert "content" not in report[0]
    assert "reasons" in report[0]["paths"][0]
