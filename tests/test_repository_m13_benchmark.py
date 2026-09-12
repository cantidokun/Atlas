from planning.repository_intelligence.benchmark import ContextBenchmarkResult
from planning.repository_intelligence.evaluation import ContextEvaluationResult
from planning.repository_intelligence.index import GitHistory, RepositoryIndex
from planning.repository_intelligence.m13_benchmark import benchmark_report, load_repository_sources


def _index(*paths: str) -> RepositoryIndex:
    files = tuple(
        {
            "path": path,
            "kind": "python_source" if path.endswith(".py") else "file",
            "language": "python" if path.endswith(".py") else "text",
            "size_bytes": 1,
            "line_count": 1,
            "sha256": "0" * 64,
            "is_test": path.startswith("tests/"),
            "parse_status": "ok" if path.endswith(".py") else "not_applicable",
        }
        for path in paths
    )
    return RepositoryIndex(".", files, (), (), GitHistory(None, ()), "index-fingerprint")


def test_load_repository_sources_excludes_sensitive_paths(tmp_path):
    (tmp_path / "planning").mkdir()
    (tmp_path / "planning" / "context.py").write_text("safe = True\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=do-not-load\n", encoding="utf-8")

    index = _index("planning/context.py", ".env")
    sources = load_repository_sources(tmp_path, index)

    assert sources == {"planning/context.py": "safe = True\n"}


def test_benchmark_report_contains_metrics_but_not_source_content():
    evaluation = ContextEvaluationResult(
        case_id="case",
        selected_paths=("planning/context.py",),
        relevant_paths=("planning/context.py",),
        required_paths=("planning/context.py",),
        true_positive=1,
        false_positive=0,
        false_negative=0,
        required_missing=(),
        recall=1.0,
        precision=1.0,
        f1=1.0,
        budget_utilization=0.25,
        truncated_files=(),
        deterministic=True,
    )
    result = ContextBenchmarkResult((evaluation,), {"recall": 1.0, "precision": 1.0})

    report = benchmark_report(result, index=_index("planning/context.py"))

    assert report["benchmark"] == "M13.7"
    assert report["case_count"] == 1
    assert report["cases"][0]["required_missing"] == []
    assert "content" not in report["cases"][0]
