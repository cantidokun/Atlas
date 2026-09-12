"""Tests for the curated M13 repository-context benchmark corpus."""

import pytest

from planning.repository_intelligence.benchmark import (
    ContextBenchmarkCase,
    curated_context_benchmark_cases,
    run_context_benchmark,
    validate_benchmark_corpus,
    validate_benchmark_inputs,
)
from planning.repository_intelligence.index import RepositoryIndex
from planning.repository_intelligence.relevance import RelevanceQuery


def test_curated_context_benchmark_has_required_coverage() -> None:
    cases = curated_context_benchmark_cases()
    validate_benchmark_corpus(cases)
    assert len(cases) >= 10
    assert len({case.case_id for case in cases}) == len(cases)


def test_curated_context_benchmark_ground_truth_is_structurally_valid() -> None:
    cases = curated_context_benchmark_cases()
    for case in cases:
        assert case.required_paths
        assert case.required_paths.issubset(case.relevant_paths)
        assert case.max_context_chars > 0
        assert case.max_file_chars > 0
        assert case.query.task_classes


def test_curated_context_benchmark_has_no_sensitive_ground_truth_paths() -> None:
    cases = curated_context_benchmark_cases()
    sensitive_fragments = (".env", ".pem", ".key", ".p12", ".pfx", "/credentials/", "/secrets/", "/secret/")
    for case in cases:
        for path in case.relevant_paths | case.required_paths:
            lowered = f"/{path.lower()}"
            assert not any(fragment in lowered for fragment in sensitive_fragments)


def test_benchmark_input_validation_rejects_missing_indexed_paths() -> None:
    case = _case("case", required={"src/required.py"}, relevant={"src/required.py"})
    index = _index(["src/other.py"])
    with pytest.raises(ValueError, match="missing indexed paths"):
        validate_benchmark_inputs(index, [case], {"src/required.py": "source"})


def test_benchmark_input_validation_rejects_missing_required_source() -> None:
    case = _case("case", required={"src/required.py"}, relevant={"src/required.py"})
    index = _index(["src/required.py"])
    with pytest.raises(ValueError, match="missing required source"):
        validate_benchmark_inputs(index, [case], {})


def test_benchmark_input_validation_rejects_sensitive_ground_truth() -> None:
    case = _case("case", required={"config/secrets.py"}, relevant={"config/secrets.py"})
    index = _index(["config/secrets.py"])
    with pytest.raises(ValueError, match="sensitive ground-truth paths"):
        validate_benchmark_inputs(index, [case], {"config/secrets.py": "secret"})


def test_benchmark_runner_validates_before_compilation() -> None:
    case = _case("case", required={"src/missing.py"}, relevant={"src/missing.py"})
    with pytest.raises(ValueError, match="missing indexed paths"):
        run_context_benchmark(_index([]), [case], {})


def _case(case_id: str, *, required: set[str], relevant: set[str]) -> ContextBenchmarkCase:
    return ContextBenchmarkCase(
        case_id=case_id,
        task_class="docs",
        description="test case",
        query=RelevanceQuery.from_values(text="test"),
        relevant_paths=frozenset(relevant),
        required_paths=frozenset(required),
    )


def _index(paths: list[str]) -> RepositoryIndex:
    return RepositoryIndex(
        fingerprint="test-repo",
        files=tuple({"path": path, "size": 1, "symbols": [], "imports": []} for path in paths),
    )
