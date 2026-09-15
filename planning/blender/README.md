# Atlas Blender Development

This directory contains the deterministic Blender health kernel, canonical scene/mesh contracts, bounded correction capabilities, and Blender boundary validation work.

## Current completed baseline

Waves 1–11 are the completed Blender correction/analysis baseline as of September 15, 2026. Wave 11 merged to `main` at `fda85a994ec0669d8ee9d1ff1ab6d52e9bfec0d3`.

The development pattern is deliberately staged:

```text
bounded design
    ↓
implementation
    ↓
deterministic validation
    ↓
adversarial validation
    ↓
live Blender boundary validation
    ↓
focused regression + CI
    ↓
independent red-team review
    ↓
merge
```

Execution authority remains separate from the canonical analysis/model layer. Blender-facing adapters are boundary components; canonical executors do not gain persistence, receipt, recovery, workflow, or action-runner authority.

## Wave 12 — `REPAIR_PARENT_CYCLE`

Branch: `feat/blender-wave12-reference-integrity`

Status: **DESIGN / NOT IMPLEMENTED**

Design gate: `BLENDER_WAVE12_PARENT_CYCLE_REPAIR_DESIGN.md`

Wave 12 extends the existing Wave 4 hierarchy-correction boundary to one additional malformed-reference class: a parent cycle. The canonical health kernel already reports hierarchy cycles through `OBJECT_HIERARCHY_INVALID`; Wave 12 makes cycle repair explicit without broadening Wave 4's dangling-parent correction.

The correction is intentionally bounded to one selected parent edge: the explicitly authorized target object's `parent_object_id` is detached to `None`. No new parent is inferred, no other hierarchy edge is changed, and no geometry, transform, naming, collection, persistence, recovery, receipt, workflow, or action-runner authority is introduced.

## Validation / merge rule

Wave 12 is not complete until its deterministic cycle/reference tests, adversarial fail-closed checks, live Blender boundary gate, focused Wave 1–Wave 12 regression, final-head CI, and independent red-team review all pass.

Workflow/action-runner tests remain excluded unless explicitly authorized.

Do not broaden a cycle repair into general hierarchy normalization. A multi-edge mutation, stale authorization acceptance, hidden re-parenting, or ambiguous target selection blocks merge.
