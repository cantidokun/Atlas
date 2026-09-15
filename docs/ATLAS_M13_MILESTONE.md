# Atlas M13 — Token-Efficient Development Context

## Current milestone

M13.1 through M13.7 are implemented on the `m13-repository-intelligence` development branch.

M13.8 is the diagnostic gate before any relevance-weight change. It adds deterministic visibility into the score, rank, and explicit reasons for benchmark-relevant paths. It does not change ranking policy.

The architecture now has a deterministic path from a development task to bounded repository context:

`task -> repository index -> relevance ranking -> bounded context package -> frozen M11 router`

M11 remains unchanged and frozen. No provider or production execution authority has been added.

## M13.8 ranking-failure diagnostics

M13.8 adds `planning/repository_intelligence/m13_rank_diagnostics.py` and an opt-in `--ranking-diagnostics` flag to the M13.7 executable benchmark.

The diagnostic layer:

- recomputes the existing deterministic relevance ranking for each curated case;
- records rank, score, and explicit relevance reasons for every benchmark-relevant path;
- marks whether each path was selected, relevant, and/or required;
- distinguishes a path that ranked weakly from a path that ranked strongly but was excluded by bounded packing;
- emits no source contents, model output, provider state, or runtime state;
- does not modify relevance weights or context-selection behavior.

The default benchmark output remains unchanged unless `--ranking-diagnostics` is supplied.

The purpose is to satisfy the M13.7 next gate: investigate observed required-context misses using evidence from the deterministic ranking layer before changing relevance weights.

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

M13.1 provides deterministic repository facts. M13.2 turns those facts into explainable relevance scores. M13.3 turns the ranking into a bounded context package. M13.4 connects that package to frozen M11 routing in advisory mode. M13.5 establishes objective context-selection metrics and a curated 10-case benchmark. M13.6 hardens the benchmark and separates selection identity from runtime package identity. M13.7 makes the benchmark executable against a real repository checkout and produces a reproducible machine-readable report. M13.8 exposes deterministic ranking evidence for diagnosing benchmark misses before calibration.

## Safety properties

- deterministic inputs produce deterministic rankings and fingerprints;
- structural relevance outranks lexical similarity;
- every selected file has explicit reasons for inclusion;
- context is bounded by total and per-file limits;
- sensitive path classes are excluded from compilation and benchmark ground truth;
- missing source is excluded rather than fabricated;
- stable instructions and dynamic runtime state remain separate;
- selection identity does not change merely because dynamic runtime state changes;
- ranking diagnostics do not mutate ranking policy;
- no model/provider call occurs during indexing, ranking, compilation, or structural benchmarking;
- no production authority, recovery, scheduler, receipt, Blender, or Unreal path is imported or invoked.

## Validation boundary

M13.8 is ordinary deterministic Python development tooling. It does not require the local action runner, Blender, Unreal, or provider credentials. No workflow/action-runner validation is required or included in this change.

The branch has not been represented as CI-validated from this environment. Local validation must cover the new focused tests plus the existing M13 deterministic suite. The executable benchmark should then be run from the user's actual Atlas checkout with `--ranking-diagnostics` so the next calibration decision is based on the current repository snapshot rather than stale metrics.

No relevance-weight change is authorized by this milestone alone. The next gate is evidence review of the ranking diagnostics. Only if the failures are demonstrably ranking-policy failures should a separate calibration change be designed and red-teamed.

## Next worthy milestone

Run the executable M13.7 benchmark with `--ranking-diagnostics`, inspect every required-context miss, classify each as ranking failure versus packing/budget failure, and only then design the smallest evidence-backed relevance-policy change. After structural context selection is stable, use M11's frozen benchmark infrastructure for controlled model-quality comparisons.
