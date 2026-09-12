"""Curated deterministic benchmark corpus for Atlas repository context selection.

This module is development tooling only. Ground truth is explicitly authored by
humans rather than inferred from models, execution results, or repository writes.
The benchmark compiles context from an explicit source mapping and evaluates it
with the objective M13.5 metrics; it does not invoke model providers or any
production authority path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from planning.repository_intelligence.context import ContextPackage, compile_context
from planning.repository_intelligence.evaluation import (
    ContextEvaluationCase,
    ContextEvaluationResult,
    aggregate_evaluations,
    evaluate_context,
    repeat_context,
)
from planning.repository_intelligence.index import RepositoryIndex
from planning.repository_intelligence.relevance import RelevanceQuery, RelevanceWeights


@dataclass(frozen=True)
class ContextBenchmarkCase:
    """One curated Atlas development task with explicit context ground truth."""

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
        return ContextEvaluationCase(
            case_id=self.case_id,
            relevant_paths=self.relevant_paths,
            required_paths=self.required_paths,
        )


@dataclass(frozen=True)
class ContextBenchmarkResult:
    """Objective result bundle for one benchmark corpus run."""

    cases: tuple[ContextEvaluationResult, ...]
    aggregate: dict


def compile_benchmark_context(
    index: RepositoryIndex,
    case: ContextBenchmarkCase,
    source_by_path: Mapping[str, str],
    *,
    stable_instructions: str = "",
    dynamic_state: Mapping[str, object] | None = None,
    weights: RelevanceWeights = RelevanceWeights(),
) -> ContextPackage:
    """Compile one benchmark case with its declared limits and query."""
    return compile_context(
        index,
        case.query,
        source_by_path,
        stable_instructions=stable_instructions,
        dynamic_state=dynamic_state,
        max_context_chars=case.max_context_chars,
        max_file_chars=case.max_file_chars,
        weights=weights,
    )


def run_context_benchmark(
    index: RepositoryIndex,
    cases: Sequence[ContextBenchmarkCase],
    source_by_path: Mapping[str, str],
    *,
    stable_instructions: str = "",
    dynamic_state: Mapping[str, object] | None = None,
    weights: RelevanceWeights = RelevanceWeights(),
) -> ContextBenchmarkResult:
    """Compile and evaluate every curated case without model or runtime calls."""
    validate_benchmark_corpus(cases)
    results: list[ContextEvaluationResult] = []
    for case in cases:
        context = compile_benchmark_context(
            index,
            case,
            source_by_path,
            stable_instructions=stable_instructions,
            dynamic_state=dynamic_state,
            weights=weights,
        )
        repeat = compile_benchmark_context(
            index,
            case,
            source_by_path,
            stable_instructions=stable_instructions,
            dynamic_state=dynamic_state,
            weights=weights,
        )
        results.append(evaluate_context(case.evaluation_case(), context, deterministic=repeat_context(context, repeat)))
    return ContextBenchmarkResult(tuple(results), aggregate_evaluations(results))


def validate_benchmark_inputs(
    index: RepositoryIndex,
    cases: Sequence[ContextBenchmarkCase],
    source_by_path: Mapping[str, str],
) -> None:
    """Reject ground-truth paths absent from the indexed repository."""
    validate_benchmark_corpus(cases)
    indexed = {item["path"] for item in index.files}
    for case in cases:
        missing = (case.relevant_paths | case.required_paths) - indexed
        if missing:
            raise ValueError(f"benchmark case {case.case_id} references missing indexed paths: {sorted(missing)}")
        absent_source = case.required_paths - set(source_by_path)
        if absent_source:
            raise ValueError(f"benchmark case {case.case_id} is missing required source: {sorted(absent_source)}")


def validate_benchmark_corpus(cases: Sequence[ContextBenchmarkCase]) -> None:
    """Validate corpus-level uniqueness and useful task-class coverage."""
    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("benchmark case IDs must be unique")
    if not cases:
        raise ValueError("benchmark corpus must not be empty")
    classes = {case.task_class for case in cases}
    required_classes = {
        "docs",
        "test",
        "bug_fix",
        "refactor",
        "api_boundary",
        "recovery",
        "concurrency",
        "authority_sensitive",
        "m12_semantic",
        "security",
    }
    missing = required_classes - classes
    if missing:
        raise ValueError(f"benchmark corpus missing task classes: {sorted(missing)}")


def curated_context_benchmark_cases() -> tuple[ContextBenchmarkCase, ...]:
    """Return the initial curated Atlas context-quality corpus.

    Ground truth deliberately emphasizes the minimum files a competent engineer
    should need for the task, while ``relevant_paths`` may include supporting
    documentation/tests that improve reasoning quality without being mandatory.
    """
    cases = (
        ContextBenchmarkCase(
            case_id="docs-runtime-boundary",
            task_class="docs",
            description="Update documentation describing the autonomous Unreal execution boundary.",
            query=RelevanceQuery.from_values(
                text="document Unreal autonomous executor execution boundary",
                paths=["planning/unreal_autonomous_executor.py", "planning/unreal_execution_boundary.py"],
                task_classes=["docs"],
            ),
            relevant_paths=frozenset({"planning/unreal_autonomous_executor.py", "planning/unreal_execution_boundary.py", "README.md", "UNREAL_AGENT_HANDOFF_CURRENT.md"}),
            required_paths=frozenset({"planning/unreal_autonomous_executor.py", "planning/unreal_execution_boundary.py"}),
        ),
        ContextBenchmarkCase(
            case_id="test-relevance-engine",
            task_class="test",
            description="Add unit coverage for deterministic repository relevance scoring.",
            query=RelevanceQuery.from_values(
                text="test deterministic repository relevance scoring",
                paths=["planning/repository_intelligence/relevance.py"],
                symbols=["rank_repository_files"],
                task_classes=["test"],
                test_paths=["tests/test_repository_relevance.py"],
            ),
            relevant_paths=frozenset({"planning/repository_intelligence/relevance.py", "planning/repository_intelligence/index.py", "tests/test_repository_relevance.py"}),
            required_paths=frozenset({"planning/repository_intelligence/relevance.py", "tests/test_repository_relevance.py"}),
        ),
        ContextBenchmarkCase(
            case_id="bug-fix-context-budget",
            task_class="bug_fix",
            description="Fix context budget accounting so evaluation uses the package budget rather than a constant.",
            query=RelevanceQuery.from_values(
                text="fix context budget evaluation package max_context_chars",
                paths=["planning/repository_intelligence/context.py", "planning/repository_intelligence/evaluation.py"],
                symbols=["evaluate_context", "ContextPackage"],
                task_classes=["bug_fix"],
            ),
            relevant_paths=frozenset({"planning/repository_intelligence/context.py", "planning/repository_intelligence/evaluation.py", "tests/test_repository_context.py", "tests/test_repository_context_evaluation.py"}),
            required_paths=frozenset({"planning/repository_intelligence/context.py", "planning/repository_intelligence/evaluation.py"}),
        ),
        ContextBenchmarkCase(
            case_id="refactor-router-bridge",
            task_class="refactor",
            description="Refactor the M13 advisory context bridge while preserving frozen M11 routing authority.",
            query=RelevanceQuery.from_values(
                text="refactor advisory context routing frozen M11 ModelRouter",
                paths=["planning/repository_intelligence/m13_router.py"],
                task_classes=["refactor"],
            ),
            relevant_paths=frozenset({"planning/repository_intelligence/m13_router.py", "planning/repository_intelligence/context.py", "planning/m11_router/router.py", "docs/ATLAS_M11_ADAPTIVE_MODEL_ROUTING_DESIGN.md"}),
            required_paths=frozenset({"planning/repository_intelligence/m13_router.py", "planning/m11_router/router.py"}),
        ),
        ContextBenchmarkCase(
            case_id="api-boundary-semantic-adapter",
            task_class="api_boundary",
            description="Change the M12 semantic-to-runtime adapter without creating a new authority.",
            query=RelevanceQuery.from_values(
                text="M12 semantic task adapter runtime boundary no new authority",
                paths=["planning/m12/runtime_adapter.py"],
                symbols=["UnrealSemanticTaskAdapter"],
                task_classes=["api_boundary"],
                contract_paths=["docs/UNREAL_M12_4_RUNTIME_ADAPTER.md"],
            ),
            relevant_paths=frozenset({"planning/m12/runtime_adapter.py", "planning/m12/semantic_task.py", "planning/unreal_task_planner.py", "planning/unreal_autonomous_executor.py", "docs/UNREAL_M12_4_RUNTIME_ADAPTER.md"}),
            required_paths=frozenset({"planning/m12/runtime_adapter.py", "planning/m12/semantic_task.py", "docs/UNREAL_M12_4_RUNTIME_ADAPTER.md"}),
        ),
        ContextBenchmarkCase(
            case_id="recovery-failure-semantics",
            task_class="recovery",
            description="Review recovery behavior for failed Unreal execution and prevent synthetic success or retry authority.",
            query=RelevanceQuery.from_values(
                text="Unreal recovery failed execution no retry synthetic success evidence",
                paths=["planning/unreal_recovery_coordinator.py"],
                task_classes=["recovery"],
                recent_paths=["planning/unreal_recovery_coordinator.py"],
            ),
            relevant_paths=frozenset({"planning/unreal_recovery_coordinator.py", "planning/unreal_execution_boundary.py", "docs/UNREAL_M12_4_RUNTIME_ADAPTER.md", "UNREAL_AGENT_HANDOFF_CURRENT.md"}),
            required_paths=frozenset({"planning/unreal_recovery_coordinator.py", "planning/unreal_execution_boundary.py"}),
        ),
        ContextBenchmarkCase(
            case_id="concurrency-retry-isolation",
            task_class="concurrency",
            description="Investigate concurrent execution identity handling without automatic retry or identity adoption.",
            query=RelevanceQuery.from_values(
                text="concurrency stale duplicate execution identities conflict recovery retry",
                paths=["planning/unreal_execution_boundary.py"],
                task_classes=["concurrency"],
            ),
            relevant_paths=frozenset({"planning/unreal_execution_boundary.py", "planning/unreal_recovery_coordinator.py", "UNREAL_AGENT_HANDOFF_CURRENT.md"}),
            required_paths=frozenset({"planning/unreal_execution_boundary.py", "planning/unreal_recovery_coordinator.py"}),
        ),
        ContextBenchmarkCase(
            case_id="authority-sensitive-model-input",
            task_class="authority_sensitive",
            description="Review code paths to ensure model-provided authorization data never becomes Atlas authority.",
            query=RelevanceQuery.from_values(
                text="model authorization authority isolation protected production intent router",
                paths=["controller/agent_controller_host.py"],
                task_classes=["authority_sensitive"],
                contract_paths=["docs/ATLAS_ARCHITECTURE_CONTRACT.md"],
            ),
            relevant_paths=frozenset({"controller/agent_controller_host.py", "planning/task_planner.py", "docs/ATLAS_ARCHITECTURE_CONTRACT.md", "planning/m11_router/router.py"}),
            required_paths=frozenset({"controller/agent_controller_host.py", "planning/task_planner.py", "docs/ATLAS_ARCHITECTURE_CONTRACT.md"}),
        ),
        ContextBenchmarkCase(
            case_id="m12-semantic-production",
            task_class="m12_semantic",
            description="Extend semantic soccer production tasks while preserving the existing planner/runtime boundary.",
            query=RelevanceQuery.from_values(
                text="M12 semantic soccer production task catalog composition runtime adapter",
                paths=["planning/m12/semantic_task.py", "planning/m12/catalog.py", "planning/m12/composition.py", "planning/m12/runtime_adapter.py"],
                task_classes=["m12_semantic"],
                contract_paths=["docs/UNREAL_M12_SEMANTIC_SOCCER_DESIGN.md"],
            ),
            relevant_paths=frozenset({"planning/m12/semantic_task.py", "planning/m12/catalog.py", "planning/m12/composition.py", "planning/m12/runtime_adapter.py", "docs/UNREAL_M12_SEMANTIC_SOCCER_DESIGN.md", "docs/UNREAL_M12_3_EXECUTION_PLAN.md"}),
            required_paths=frozenset({"planning/m12/semantic_task.py", "planning/m12/catalog.py", "planning/m12/composition.py", "planning/m12/runtime_adapter.py"}),
        ),
        ContextBenchmarkCase(
            case_id="security-sensitive-config",
            task_class="security",
            description="Review development context handling to ensure credential and secret files are excluded.",
            query=RelevanceQuery.from_values(
                text="security credentials secrets environment context compiler exclusion",
                paths=["planning/repository_intelligence/context.py"],
                task_classes=["security"],
            ),
            relevant_paths=frozenset({"planning/repository_intelligence/context.py", "planning/repository_intelligence/index.py", "tests/test_repository_context.py"}),
            required_paths=frozenset({"planning/repository_intelligence/context.py", "tests/test_repository_context.py"}),
        ),
    )
    validate_benchmark_corpus(cases)
    return cases
