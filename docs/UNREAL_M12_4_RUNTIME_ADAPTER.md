# Atlas M12.4 — Unreal Semantic → Runtime Adapter

**Status:** IMPLEMENTED (M12.4). Builds on merged M12.3 (PR #89), M12.2 (PR #88), M12.1 (PR #87), M12 design (PR #86).

## What M12.4 implements

A narrow, immutable **semantic → runtime adapter** that maps a validated M12.3
`UnrealExecutionPlan` (plus its validated M12.1 source task) onto the EXISTING
Atlas task/runtime representation. M12.4 is an **adapter, not a new authority**:
it never authorizes, schedules, retries, recovers, persists, mints receipts,
produces evidence, or executes anything.

### Adapter contract — `planning/m12/runtime_adapter.py`
- `UnrealRuntimeStepMapping` — immutable per-step mapping (step_id,
  semantic_operation, supported, target_runtime_operation, required_inputs,
  dependencies, target_state_contributions, idempotence, capability_requirement,
  unsupported_reason).
- `UnrealRuntimeMapping` — immutable result (plan_id, source_task_id/version,
  catalog_version, digital_twin_id, ordered step mappings, render_plan,
  requires_existing_render_submission_path, runtime_task, provenance) with stable
  canonical JSON.
- `map_unreal_execution_plan(plan, *, source_task, catalog_version=None)` —
  deterministic mapping. Identity-locks the plan to its exact source task,
  reuses the existing M12.1 compiler to build the existing
  `AtlasTaskDefinition` runtime representation, and fails closed for render.

## Architecture

```text
semantic intent
    ↓
M12.1 semantic task contract
    ↓
M12.2 catalog + fragments + composition
    ↓
M12.3 semantic execution plan
    ↓
M12.4 Unreal semantic → runtime adapter   (THIS MILESTONE)
    ↓
EXISTING Atlas runtime / authorization
    ↓
EXISTING Unreal execution / recovery
    ↓
EXISTING evidence verification / receipts / artifact lineage
```

## Critical boundary

M12.4 is an adapter, not an authority:

- **Model** — proposes only.
- **M12 semantic layer** — describes and plans.
- **Atlas** — validates, authorizes, executes, tracks, verifies, recovers.
- **Unreal** — executes as the controlled engine.
- **Independent verification** — establishes truth.

M12.4 introduces **none** of: a second authorization authority, a second
scheduler, a second retry controller, a second recovery authority, a second
persistence authority, a second receipt authority, a second evidence system, or
a second runtime. It does not replace `AtlasRenderJobRecord`, does not replace
the existing task/runtime execution mechanism, and does not bypass the existing
submission/recovery/evidence path.

## Supported mappings

For **non-render** semantic tasks (scene-prepare, environment-configure,
camera-configure, lighting-configure, sequence-configure), every plan step maps
to the existing runtime `unreal_inspect` operation, and the plan is compiled to
the existing `AtlasTaskDefinition` via the M12.1 compiler. The adapter records
per-step: semantic operation id, target runtime operation, required inputs,
preserved dependencies (resolved to producing steps), preserved target-state
contributions, idempotence, capability requirement, and provenance.

## Unsupported mappings (fail closed)

- **Render-bearing plans** (`render-execute`, `artifact-validate`) are recognized
  via `render_plan`/`requires_existing_render_submission_path=True` and produce
  **no** runtime task (`runtime_task=None`). M12.4 does not fabricate render
  authorization, does not submit MRQ, does not create receipts, and does not mark
  anything verified. It records a structured
  `requires-existing-render-submission-path` boundary on every step.
- **Unknown idempotence** on a supported step → `UnrealRuntimeAdapterError`.
- **Unsupported capability requirement** (anything other than `inspect-only`) →
  `UnrealRuntimeAdapterError`.
- **Identity mismatch** (plan not generated from the provided source task) →
  `UnrealRuntimeAdapterError`.
- **Step-operation mismatch** (plan steps do not match the source task's fragment
  dependencies) → `UnrealRuntimeAdapterError`.

## Render handling

M12.1 deliberately blocks render-bearing compilation. M12.3 can describe
render-bearing plans but cannot execute them. **M12.4 does not circumvent this.**
For a render-bearing plan the adapter:

- explicitly recognizes render intent (`render_plan=True`);
- produces a structured `requires_existing_render_submission_path=True` mapping;
- sets `runtime_task=None` (no runtime representation is fabricated);
- never calls `compile_unreal_semantic_task` for a render-bearing task (the
  existing M12.1 `UnsupportedCompileMappingError` rule is preserved and
  re-verified by tests);
- never constructs trusted render authorization, never submits MRQ, never
  bypasses `AtlasRenderJobRecord`, never creates receipts, never marks anything
  verified.

If a future milestone provides a safe, already-authorized entry point for
consuming a mapped render request, it will be documented and used ONLY through
that existing authority boundary. Today such an interface is not yet safe to
consume from M12, so M12.4 fails closed and documents the dependency for M12.5.

## Authorization separation

Proven through types and tests:

```text
semantic request  ≠  execution plan  ≠  authorization  ≠  runtime execution  ≠  verification
```

`map_unreal_execution_plan` accepts only a validated `UnrealExecutionPlan` and a
validated `UnrealProductionTaskDefinition`. It never accepts model-supplied
`authorization_id`, `receipt`, `attempt_nonce`, `HMAC` material, protected
production flags, recovery authority, or artifact manifests. The mapping result
contains no authority-shaped fields or methods (`execute`, `authorize`,
`submit`, `reconcile`, `schedule`, `persist`, `mint_receipt`, `recover`,
`verify` are all absent). The existing Atlas authorization mechanism remains
authoritative.

## Provenance

Preserved through the mapping: digital-twin id, semantic task id/version,
catalog version, execution-plan id, fragment ids/versions (via steps), and
proposal provenance. The mapping never collapses canonical digital-twin
identity, semantic task identity, execution-plan identity, or runtime job
identity.

## Target-state requirements

Semantic target-state requirements are carried through the adapter
(`target_state_contributions` per step). They are **not verified here** — the
adapter only describes what later independent verification must establish. No
second evidence mechanism is introduced.

## Dependencies / ordering

The deterministic order generated by M12.3 is preserved verbatim. The adapter is
not a scheduler: it translates dependency relationships into the existing runtime
step representation without autonomously scheduling, retrying, reordering, or
silently dropping dependencies. A dependency the runtime cannot represent safely
fails closed.

## Idempotence

M12.2/M12.3 idempotence is preserved per mapped step (`idempotent` /
`non-idempotent`). An `unknown` idempotence on a supported step fails closed; the
adapter never silently upgrades an unknown operation to idempotent.

## Execution capabilities

M12.3's `execution_capability_requirement` descriptions are mapped to the
existing runtime tool constraint (`unreal_inspect`). Any unsupported capability
requirement fails closed. No new capability authority is created.

## C++ interoperability

The adapter boundary is language-neutral. `UnrealRuntimeMapping.canonical_json()`
is sorted-key, compact, and deterministic. No C++ is added in M12.4; no concrete
existing Unreal boundary requires it yet.

## Blender relationship

Blender is untouched. M12.4 reuses the generic Atlas semantic→runtime
compilation approach already used on the Blender side (the M12.1
`compile_unreal_semantic_task` → `AtlasTaskDefinition` boundary). Unreal-specific
mappings stay inside `planning/m12/`.

## Validation

- `pytest tests/m12/` → **112 passed** (88 prior + 24 new M12.4)
- `pytest tests/m12/ tests/test_unreal_render_submission.py tests/test_unreal_recovery_coordinator.py tests/test_unreal_task_planner.py tests/test_unreal_autonomous_executor.py tests/test_task_definition.py tests/test_authorized_task_runtime.py tests/m10/ tests/m11/` → **480 passed**
- `pytest -m "not integration"` → **1563 passed** (was 1539, +24)
- Authority-isolation import scan clean (adapter imports only M12 + `AtlasTaskDefinition`, no production-authority module).
- No live Unreal, no workflow/action-runner tests, no Blender, no M11, no M4–M10 change.

## Known limitations

- Render-bearing plans are recognized but **not** mapped to a runtime task; they
  fail closed at the `requires-existing-render-submission-path` boundary.
- The adapter only supports the `unreal_inspect` runtime operation (the sole
  demonstrated existing runtime equivalent for M12 non-render semantic steps).

## M12.5 dependency

M12.5 (independent semantic evidence verification) should consume the mapped
runtime representation and the preserved target-state requirements to establish
what actually happened, using the existing evidence machinery. It must not trust
self-reported evidence and must not be wired through M12.4 (which performs no
verification). If a safe, already-authorized render-submission entry point is
established, M12.5+ may document and consume it through that existing authority
boundary only.