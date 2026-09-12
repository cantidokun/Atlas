"""Tests for the curated M13.5 repository-context benchmark corpus."""

from planning.repository_intelligence.benchmark import curated_context_benchmark_cases, validate_benchmark_corpus


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
