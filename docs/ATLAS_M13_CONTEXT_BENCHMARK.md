# Atlas M13.5 — Repository Context Quality Benchmark

## Purpose

M13.5 evaluates whether Atlas repository intelligence selects a minimum-sufficient,
explainable development context from explicit ground truth. The benchmark is
structural and deterministic: it does not ask a model whether its own context was
good, and it does not modify production authority, execution, recovery, scheduling,
persistence, receipts, or evidence paths.

## Corpus

The initial corpus contains ten representative development task classes:

- documentation
- unit testing
- bug fixing
- refactoring
- API-boundary work
- recovery semantics
- concurrency / duplicate execution identity
- authority-sensitive changes
- M12 semantic soccer production work
- security-sensitive context handling

Every case explicitly declares:

- `relevant_paths`: useful repository context for the task
- `required_paths`: minimum files that must be present for the task to be considered adequately grounded
- structured query signals used by M13.2
- per-case context budgets

Ground truth is curated and version-controlled. It is not inferred from model output,
execution success, or the compiler itself.

## Objective metrics

For each case the evaluator records:

- recall over relevant paths
- precision over selected paths
- F1
- required-file missing count
- context-budget utilization
- truncated-file count
- deterministic package fingerprint comparison

The aggregate result reports the corresponding corpus-level means and totals.

## Acceptance gates

The structural benchmark must satisfy these properties before live-model comparison:

1. **No required path missing** for every curated case.
2. **Deterministic selection** for identical index, query, source, weights, and context inputs.
3. **Budget safety**: compiled context never exceeds the configured maximum.
4. **Sensitive-source exclusion**: credential, secret, environment, and key material paths are never selected by the compiler.
5. **Explainability**: every selected file has named relevance reasons and a deterministic score.
6. **Model independence**: structural benchmark execution makes no provider or model calls.

Recall, precision, and F1 are tracked as quality metrics rather than converted into
an arbitrary single pass/fail threshold at this stage. Thresholds should be set only
after the corpus has been observed across representative Atlas development work.

## Important interpretation rule

`ContextEvaluationResult.deterministic` currently compares the package fingerprint
to an optional baseline package. A different baseline represents a different package,
not necessarily nondeterministic behavior. A future refinement should add an explicit
repeatability helper that compiles identical inputs twice and compares selection
fingerprints independently from dynamic runtime state.

## Safety boundary

This benchmark is development tooling only. It must not become an authority path,
execution dispatcher, scheduler, retry controller, recovery owner, receipt issuer, or
evidence authority. M11 remains the frozen model-routing authority; M13 supplies
repository context to development-model calls without replacing M11 routing semantics.
