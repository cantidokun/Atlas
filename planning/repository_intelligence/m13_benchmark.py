"""Executable M13.7 repository context benchmark harness.

Development tooling only. This module creates a read-only repository snapshot,
builds an explicit source mapping, runs the curated context benchmark, and emits
machine-readable metrics. It never invokes model providers, production authority,
Blender/Unreal, schedulers, retries, persistence, or workflow/action runners.

The pure compiler remains intentionally filesystem-free; filesystem access is
confined to this top-level benchmark harness so the benchmark is reproducible
against an actual checkout without changing compiler trust boundaries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Mapping

from planning.repository_intelligence.benchmark import ContextBenchmarkResult, curated_context_benchmark_cases, run_context_benchmark
from planning.repository_intelligence.context import is_sensitive_context_path
from planning.repository_intelligence.index import RepositoryIndex, build_repository_index
from planning.repository_intelligence.m13_benchmark_diagnostics import diagnose_results


def load_repository_sources(root: str | Path, index: RepositoryIndex) -> dict[str, str]:
    """Load UTF-8 repository text into an explicit, secret-safe source mapping."""
    root_path = Path(root).resolve()
    sources: dict[str, str] = {}
    for record in index.files:
        path = str(record["path"])
        if is_sensitive_context_path(path):
            continue
        candidate = root_path / Path(path)
        try:
            raw = candidate.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        sources[path] = text
    return sources


def validate_source_snapshot(index: RepositoryIndex, root: str | Path, sources: Mapping[str, str]) -> None:
    """Ensure source text matches the indexed checkout before reporting metrics."""
    root_path = Path(root).resolve()
    records = {str(item["path"]): item for item in index.files}
    for path, source in sources.items():
        record = records.get(path)
        if record is None:
            raise ValueError(f"source path is absent from repository index: {path}")
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if digest != record["sha256"]:
            raise ValueError(f"source changed after indexing: {path}")
        if not (root_path / Path(path)).is_file():
            raise ValueError(f"source disappeared after indexing: {path}")


def benchmark_report(result: ContextBenchmarkResult, *, index: RepositoryIndex) -> dict:
    """Build a machine-readable report without embedding source contents."""
    diagnostics = diagnose_results(result.cases)
    cases = []
    for item in result.cases:
        cases.append({
            "case_id": item.case_id,
            "selected_paths": list(item.selected_paths),
            "relevant_paths": list(item.relevant_paths),
            "required_paths": list(item.required_paths),
            "true_positive": item.true_positive,
            "false_positive": item.false_positive,
            "false_negative": item.false_negative,
            "required_missing": item.required_missing,
            "recall": item.recall,
            "precision": item.precision,
            "f1": item.f1,
            "budget_utilization": item.budget_utilization,
            "truncated_files": item.truncated_files,
            "deterministic": item.deterministic,
            "diagnostic": next(item_diag.status for item_diag in diagnostics if item_diag.case_id == item.case_id),
        })
    return {
        "report_schema_version": 1,
        "benchmark": "M13.7",
        "development_only": True,
        "production_execution_invoked": False,
        "model_provider_invoked": False,
        "index_fingerprint": index.fingerprint,
        "case_count": len(cases),
        "aggregate": result.aggregate,
        "diagnostics": [
            {
                "case_id": item.case_id,
                "status": item.status,
                "missing_required": list(item.missing_required),
                "missing_relevant": list(item.missing_relevant),
                "extra_selected": list(item.extra_selected),
                "truncated_files": list(item.truncated_files),
                "deterministic": item.deterministic,
            }
            for item in diagnostics
        ],
        "cases": cases,
    }


def run_repository_benchmark(root: str | Path) -> dict:
    """Run the curated ten-case benchmark against an actual repository checkout."""
    index = build_repository_index(root, include_git_history=True)
    sources = load_repository_sources(root, index)
    validate_source_snapshot(index, root, sources)
    result = run_context_benchmark(index, curated_context_benchmark_cases(), sources)
    return benchmark_report(result, index=index)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Atlas M13.7 repository context benchmark")
    parser.add_argument("root", nargs="?", default=".", help="Atlas repository checkout (default: current directory)")
    parser.add_argument("--output", type=Path, help="Write JSON report to this path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = run_repository_benchmark(args.root)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
