"""Curated deterministic benchmark corpus for Atlas repository context selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from planning.repository_intelligence.context import ContextPackage, compile_context, is_sensitive_context_path
from planning.repository_intelligence.evaluation import ContextEvaluationCase, ContextEvaluationResult, aggregate_evaluations, evaluate_context, repeat_context
from planning.repository_intelligence.index import RepositoryIndex
from planning.repository_intelligence.relevance import RelevanceQuery, RelevanceWeights


@dataclass(frozen=True)
class ContextBenchmarkCase:
    case_id: str
    task_class: str
    description: str
    query: RelevanceQuery
    relevant_paths: frozenset[str]
    required_paths: frozenset[str]
    max_context_chars: int = 48_000
    max_file_chars: int = 16_000

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id must be non-empty")
        if not self.task_class.strip():
            raise ValueError("task_class must be non-empty")
        if not self.description.strip():
            raise ValueError("description must be non-empty")
        if not self.required_paths.issubset(self.relevant_paths):
            raise ValueError("required_paths must be a subset of relevant_paths")
        if self.max_context_chars <= 0 or self.max_file_chars <= 0:
            raise ValueError("context limits must be positive")

    def evaluation_case(self) -> ContextEvaluationCase:
        return ContextEvaluationCase(self.case_id, self.relevant_paths, self.required_paths)


@dataclass(frozen=True)
class ContextBenchmarkResult:
    cases: tuple[ContextEvaluationResult, ...]
    aggregate: dict


def compile_benchmark_context(index: RepositoryIndex, case: ContextBenchmarkCase, source_by_path: Mapping[str, str], *, stable_instructions: str = "", dynamic_state: Mapping[str, object] | None = None, weights: RelevanceWeights = RelevanceWeights()) -> ContextPackage:
    return compile_context(index, case.query, source_by_path, stable_instructions=stable_instructions, dynamic_state=dynamic_state, max_context_chars=case.max_context_chars, max_file_chars=case.max_file_chars, weights=weights)


def run_context_benchmark(index: RepositoryIndex, cases: Sequence[ContextBenchmarkCase], source_by_path: Mapping[str, str], *, stable_instructions: str = "", dynamic_state: Mapping[str, object] | None = None, weights: RelevanceWeights = RelevanceWeights()) -> ContextBenchmarkResult:
    """Compile and evaluate every curated case without model or runtime calls."""
    # Input safety/ground-truth validation comes first so malformed isolated
    # cases fail for their concrete defect before corpus-wide coverage checks.
    validate_benchmark_inputs(index, cases, source_by_path)
    validate_benchmark_corpus(cases)
    results: list[ContextEvaluationResult] = []
    for case in cases:
        context = compile_benchmark_context(index, case, source_by_path, stable_instructions=stable_instructions, dynamic_state=dynamic_state, weights=weights)
        repeat = compile_benchmark_context(index, case, source_by_path, stable_instructions=stable_instructions, dynamic_state=dynamic_state, weights=weights)
        results.append(evaluate_context(case.evaluation_case(), context, deterministic=repeat_context(context, repeat)))
    return ContextBenchmarkResult(tuple(results), aggregate_evaluations(results))


def validate_benchmark_inputs(index: RepositoryIndex, cases: Sequence[ContextBenchmarkCase], source_by_path: Mapping[str, str]) -> None:
    indexed = {item["path"] for item in index.files}
    for case in cases:
        ground_truth = case.relevant_paths | case.required_paths
        sensitive = sorted(path for path in ground_truth if is_sensitive_context_path(path))
        if sensitive:
            raise ValueError(f"benchmark case {case.case_id} contains sensitive ground-truth paths: {sensitive}")
        missing = ground_truth - indexed
        if missing:
            raise ValueError(f"benchmark case {case.case_id} references missing indexed paths: {sorted(missing)}")
        absent_source = case.required_paths - set(source_by_path)
        if absent_source:
            raise ValueError(f"benchmark case {case.case_id} is missing required source: {sorted(absent_source)}")


def validate_benchmark_corpus(cases: Sequence[ContextBenchmarkCase]) -> None:
    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("benchmark case IDs must be unique")
    if not cases:
        raise ValueError("benchmark corpus must not be empty")
    classes = {case.task_class for case in cases}
    required_classes = {"docs", "test", "bug_fix", "refactor", "api_boundary", "recovery", "concurrency", "authority_sensitive", "m12_semantic", "security"}
    missing = required_classes - classes
    if missing:
        raise ValueError(f"benchmark corpus missing task classes: {sorted(missing)}")


def curated_context_benchmark_cases() -> tuple[ContextBenchmarkCase, ...]:
    cases = (
        ContextBenchmarkCase("docs-runtime-boundary", "docs", "Update documentation describing the autonomous Unreal execution boundary.", RelevanceQuery.from_values(text="document Unreal autonomous executor execution boundary", paths=["planning/unreal_autonomous_executor.py", "planning/unreal_execution_boundary.py"], task_classes=["docs"]), frozenset({"planning/unreal_autonomous_executor.py", "planning/unreal_execution_boundary.py", "README.md", "UNREAL_AGENT_HANDOFF_CURRENT.md"}), frozenset({"planning/unreal_autonomous_executor.py", "planning/unreal_execution_boundary.py"})),
        ContextBenchmarkCase("test-relevance-engine", "test", "Add unit coverage for deterministic repository relevance scoring.", RelevanceQuery.from_values(text="test deterministic repository relevance scoring", paths=["planning/repository_intelligence/relevance.py"], symbols=["rank_repository_files"], task_classes=["test"], test_paths=["tests/test_repository_relevance.py"]), frozenset({"planning/repository_intelligence/relevance.py", "planning/repository_intelligence/index.py", "tests/test_repository_relevance.py"}), frozenset({"planning/repository_intelligence/relevance.py", "tests/test_repository_relevance.py"})),
        ContextBenchmarkCase("bug-fix-context-budget", "bug_fix", "Fix context budget accounting so evaluation uses the package budget rather than a constant.", RelevanceQuery.from_values(text="fix context budget evaluation package max_context_chars", paths=["planning/repository_intelligence/context.py", "planning/repository_intelligence/evaluation.py"], symbols=["evaluate_context", "ContextPackage"], task_classes=["bug_fix"]), frozenset({"planning/repository_intelligence/context.py", "planning/repository_intelligence/evaluation.py", "tests/test_repository_context.py", "tests/test_repository_context_evaluation.py"}), frozenset({"planning/repository_intelligence/context.py", "planning/repository_intelligence/evaluation.py"})),
        ContextBenchmarkCase("refactor-router-bridge", "refactor", "Refactor the M13 advisory context bridge while preserving frozen M11 routing authority.", RelevanceQuery.from_values(text="refactor advisory context routing frozen M11 ModelRouter", paths=["planning/repository_intelligence/m13_router.py"], task_classes=["refactor"]), frozenset({"planning/repository_intelligence/m13_router.py", "planning/repository_intelligence/context.py", "planning/m11_router/router.py", "docs/ATLAS_M11_ADAPTIVE_MODEL_ROUTING_DESIGN.md"}), frozenset({"planning/repository_intelligence/m13_router.py", "planning/m11_router/router.py"})),
        ContextBenchmarkCase("api-boundary-semantic-adapter", "api_boundary", "Change the M12 semantic-to-runtime adapter without creating a new authority.", RelevanceQuery.from_values(text="M12 semantic task adapter runtime boundary no new authority", paths=["planning/m12/runtime_adapter.py"], symbols=["UnrealSemanticTaskAdapter"], task_classes=["api_boundary"], contract_paths=["docs/UNREAL_M12_4_RUNTIME_ADAPTER.md"]), frozenset({"planning/m12/runtime_adapter.py", "planning/m12/semantic_task.py", "planning/unreal_task_planner.py", "planning/unreal_autonomous_executor.py", "docs/UNREAL_M12_4_RUNTIME_ADAPTER.md"}), frozenset({"planning/m12/runtime_adapter.py", "planning/m12/semantic_task.py", "docs/UNREAL_M12_4_RUNTIME_ADAPTER.md"})),
        ContextBenchmarkCase("recovery-failure-semantics", "recovery", "Review recovery behavior for failed Unreal execution and prevent synthetic success or retry authority.", RelevanceQuery.from_values(text="Unreal recovery failed execution no retry synthetic success evidence", paths=["planning/unreal_recovery_coordinator.py"], task_classes=["recovery"], recent_paths=["planning/unreal_recovery_coordinator.py"]), frozenset({"planning/unreal_recovery_coordinator.py", "planning/unreal_execution_boundary.py", "docs/UNREAL_M12_4_RUNTIME_ADAPTER.md", "UNREAL_AGENT_HANDOFF_CURRENT.md"}), frozenset({"planning/unreal_recovery_coordinator.py", "planning/unreal_execution_boundary.py"})),
        ContextBenchmarkCase("concurrency-retry-isolation", "concurrency", "Investigate concurrent execution identity handling without automatic retry or identity adoption.", RelevanceQuery.from_values(text="concurrency stale duplicate execution identities conflict recovery retry", paths=["planning/unreal_execution_boundary.py"], task_classes=["concurrency"]), frozenset({"planning/unreal_execution_boundary.py", "planning/unreal_recovery_coordinator.py", "UNREAL_AGENT_HANDOFF_CURRENT.md"}), frozenset({"planning/unreal_execution_boundary.py", "planning/unreal_recovery_coordinator.py"})),
        ContextBenchmarkCase("authority-sensitive-model-input", "authority_sensitive", "Review code paths to ensure model-provided authorization data never becomes Atlas authority.", RelevanceQuery.from_values(text="model authorization authority isolation protected production intent router", paths=["controller/agent_controller_host.py"], task_classes=["authority_sensitive"], contract_paths=["docs/ATLAS_ARCHITECTURE_CONTRACT.md"]), frozenset({"controller/agent_controller_host.py", "planning/task_planner.py", "docs/ATLAS_ARCHITECTURE_CONTRACT.md", "planning/m11_router/router.py"}), frozenset({"controller/agent_controller_host.py", "planning/task_planner.py", "docs/ATLAS_ARCHITECTURE_CONTRACT.md"})),
        ContextBenchmarkCase("m12-semantic-production", "m12_semantic", "Extend semantic soccer production tasks while preserving the existing planner/runtime boundary.", RelevanceQuery.from_values(text="M12 semantic soccer production task catalog composition runtime adapter", paths=["planning/m12/semantic_task.py", "planning/m12/catalog.py", "planning/m12/composition.py", "planning/m12/runtime_adapter.py"], task_classes=["m12_semantic"], contract_paths=["docs/UNREAL_M12_SEMANTIC_SOCCER_DESIGN.md"]), frozenset({"planning/m12/semantic_task.py", "planning/m12/catalog.py", "planning/m12/composition.py", "planning/m12/runtime_adapter.py", "docs/UNREAL_M12_SEMANTIC_SOCCER_DESIGN.md", "docs/UNREAL_M12_3_EXECUTION_PLAN.md"}), frozenset({"planning/m12/semantic_task.py", "planning/m12/catalog.py", "planning/m12/composition.py", "planning/m12/runtime_adapter.py"})),
        ContextBenchmarkCase("security-sensitive-config", "security", "Review development context handling to ensure credential and secret files are excluded.", RelevanceQuery.from_values(text="security credentials secrets environment context compiler exclusion", paths=["planning/repository_intelligence/context.py"], task_classes=["security"]), frozenset({"planning/repository_intelligence/context.py", "planning/repository_intelligence/index.py", "tests/test_repository_context.py"}), frozenset({"planning/repository_intelligence/context.py", "tests/test_repository_context.py"})),
    )
    validate_benchmark_corpus(cases)
    return cases
