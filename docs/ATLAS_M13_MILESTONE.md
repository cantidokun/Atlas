# Atlas M13 — Token-Efficient Development Context

## Current milestone

M13.1 through M13.3 are implemented on the `m13-repository-intelligence` development branch.

The architecture now has a deterministic path from a development task to bounded repository context:

`task -> repository index -> relevance ranking -> bounded context package -> frozen M11 router`

M11 remains unchanged and frozen. No provider or production execution authority has been added.

## Why this matters

The objective is not simply to send fewer tokens. The objective is to improve **reasoning quality per token** by removing irrelevant repository material while retaining structural information that matters to the task.

M13.1 provides deterministic repository facts. M13.2 turns those facts into explainable relevance scores. M13.3 turns the ranking into a bounded context package and records included/excluded material for later measurement.

## Safety properties

- deterministic inputs produce deterministic rankings and fingerprints;
- structural relevance outranks lexical similarity;
- every selected file has explicit reasons for inclusion;
- context is bounded by total and per-file limits;
- sensitive path classes are excluded from compilation;
- missing source is excluded rather than fabricated;
- stable instructions and dynamic runtime state remain separate;
- no model/provider call occurs during indexing, ranking, or compilation;
- no production authority, recovery, scheduler, receipt, Blender, or Unreal path is imported or invoked.

## Validation boundary

The new tests are ordinary deterministic Python tests and do not require the local action runner, Blender, Unreal, or provider credentials. Runtime execution of the suite has not been claimed where no execution environment is available.

## Next worthy milestone

M13.4 should connect the compiled context to the frozen M11 router in **advisory/shadow mode only**, followed by a context-quality benchmark. The benchmark should compare baseline repository context against compiled context on representative Atlas development tasks using token counts, first-pass success, test-fix rounds, escalations, architectural defects, and time-to-merge.
