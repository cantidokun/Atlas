# Atlas M13 — Token-Efficient Development Context

## Current milestone

M13.1 through M13.7 are implemented on the `m13-repository-intelligence` development branch.

The architecture now has a deterministic path from a development task to bounded repository context:

`task -> repository index -> relevance ranking -> bounded context package -> frozen M11 router`

M11 remains unchanged and frozen. No provider or production execution authority has been added.

## M13.7 executable repository benchmark

M13.7 adds a reproducible, read-only benchmark harness in `planning/repository_intelligence/m13_benchmark.py`.

The harness:

- builds the structural repository index from an actual checkout;
- constructs an explicit UTF-8 source mapping while excluding sensitive paths and unreadable/binary files;
- executes the curated 10-case corpus through the existing deterministic benchmark;
- compiles every case twice with identical inputs to measure repeatability;
- reports required-path recall, precision/F1, budget utilization, truncation, required-path misses, selected paths, and aggregate metrics;
- emits machine-readable JSON without embedding source contents in the report;
- remains development-only and does not invoke models, providers, production authority, Blender, Unreal, schedulers, retries, persistence, or workflow/action runners.

The pure context compiler remains filesystem-free. Filesystem access is deliberately confined to the benchmark harness, which converts the checkout into an explicit source mapping before calling the compiler.

## M13.6 context-quality hardening

M13.6 strengthens the structural evaluation boundary before any model-performance comparison:

- benchmark execution validates that all curated ground-truth paths exist in the supplied repository index and required source mapping;
- benchmark ground truth rejects sensitive paths rather than allowing secret-bearing fixtures into the evaluation corpus;
- corpus coverage validation remains separate from per-run input validation;
- context truncation prefers complete line boundaries when the budget permits;
- `selection_fingerprint` identifies repository/context selection decisions independently of dynamic runtime state;
- full package fingerprints continue to include stable instructions, dynamic state, and selected content;
- repeatability remains objective and is measured by compiling identical inputs twice;
- no model/provider call occurs during structural benchmarking.

## Why this matters

The objective is not simply to send fewer tokens. The objective is to improve **reasoning quality per token** by removing irrelevant repository material while retaining structural information that matters to the task.

M13.1 provides deterministic repository facts. M13.2 turns those facts into explainable relevance scores. M13.3 turns the ranking into a bounded context package. M13.4 connects that package to frozen M11 routing in advisory mode. M13.5 establishes objective context-selection metrics and a curated 10-case benchmark. M13.6 hardens the benchmark and separates selection identity from runtime package identity. M13.7 makes the benchmark executable against a real repository checkout and produces a reproducible machine-readable report.

## Safety properties

- deterministic inputs produce deterministic rankings and fingerprints;
- structural relevance outranks lexical similarity;
- every selected file has explicit reasons for inclusion;
- context is bounded by total and per-file limits;
- sensitive path classes are excluded from compilation and benchmark ground truth;
- missing source is excluded rather than fabricated;
- stable instructions and dynamic runtime state remain separate;
- selection identity does not change merely because dynamic runtime state changes;
- no model/provider call occurs during indexing, ranking, compilation, or structural benchmarking;
- no production authority, recovery, scheduler, receipt, Blender, or Unreal path is imported or invoked.

## Validation boundary

The M13 tests are ordinary deterministic Python tests and do not require the local action runner, Blender, Unreal, or provider credentials. The GitHub branch currently has no workflow runs attached to the latest development commit, so no test-pass claim is being made from CI.

The focused M13 benchmark test now covers the executable harness's secret-safe source loading and report isolation. The actual 10-case repository-snapshot benchmark is still awaiting execution from an environment with a usable Atlas checkout; no benchmark metrics are being fabricated while the current development environment cannot resolve GitHub for cloning.

When local repository execution is available, the intended validation is the focused M13 context/index/relevance/benchmark test set first, followed by the broader non-integration suite. Workflow/action-runner and Unreal runtime tests remain outside the M13 change boundary unless explicitly needed for a later integration milestone.

## Next worthy milestone

Once M13.7 has produced real snapshot metrics, investigate any ranking failures using the explicit explanations and only then consider changing relevance weights. Only after the structural benchmark is stable should M11's frozen benchmark infrastructure be used for controlled model-quality comparisons.
