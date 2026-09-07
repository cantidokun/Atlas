# Atlas M12.1 — Unreal Semantic Task Contract + Normalization/Compile Boundary

**Status:** IMPLEMENTED (M12.1). Builds on the merged M12 design (PR #86).

## What M12.1 implements

A small, foundational semantic layer above the proven M4-M10 Unreal machinery:

- `planning/m12/task_classes.py` — the constrained, canonical Unreal
  soccer-production task taxonomy (scene-prepare, environment-configure,
  camera-configure, lighting-configure, sequence-configure, render-execute,
  artifact-validate). `effect-pass-prepare` is reserved but NOT selectable.
  Unsupported/reserved task classes fail closed.
- `planning/m12/target_state.py` — `UnrealTargetStateSpec`: a data-only,
  language-neutral descriptor of requested target state (description, invariant
  names, expects_render). This is NOT a second evidence system; it expresses
  invariants for a future independent verifier (M12.5).
- `planning/m12/semantic_task.py` —
  - `UnrealProductionTaskDefinition`: immutable, validated semantic task
    contract (canonical task id, task class, digital-twin id, task version,
    intent, target state, allowed mutations, dependencies, provenance).
  - `normalize_unreal_semantic_request`: deterministic normalization into
    canonical form, fail-closed on malformed/ambiguous/unsupported input and on
    ANY authority material in the inbound request.
  - `compile_unreal_semantic_task`: a narrow compiler onto the existing
    `AtlasTaskDefinition` runtime contract, carrying Unreal semantic provenance
    through metadata and preserving dependencies + target-state requirements.
    It is a compile boundary only — no second runtime, no execution authority.
- Deterministic tests: `tests/m12/test_m12_semantic_task.py` (contract,
  normalization, serialization, compile) and
  `tests/m12/test_m12_authority_isolation.py` (no authority leakage).

## What M12.1 deliberately does NOT implement

- No render-bearing task compilation: `compile_unreal_semantic_task` REJECTS
  `render-execute` / `artifact-validate` with `UnsupportedCompileMappingError`,
  because their safe mapping requires the existing render-submission machinery
  (deferred until the semantic contract is proven independently).
- No independent verification: the target-state evaluator used at compile time is
  a deterministic *structural placeholder*; real verification is deferred to M12.5
  and wired through the existing evidence machinery.
- No catalog / fragments / composition / adapter (M12.2-M12.4).
- No authority: the semantic layer never mints authorization IDs, receipts,
  recovery authority, protected flags, or scheduler/retry/persistence authority.

## How it compiles to the existing runtime

`compile_unreal_semantic_task` produces an existing
`planning.task_definition.AtlasTaskDefinition`:

- name = semantic `task_name` (or `task_class:canonical_task_id`);
- evidence / actions / allowed_action_tools carried through from the semantic task
  (validated for well-formedness and authorized-tool consistency);
- evaluator = caller-supplied or a deterministic structural placeholder
  (`TargetStateEvaluator` over the declared invariant names);
- metadata carries `unreal_semantic_task_id/class/version`, the canonical
  digital-twin id, dependencies, target-state spec, and the provenance dict.

## How authorization remains separate

- Creating / normalizing / compiling a semantic task produces NO authorization
  material and does NOT authorize execution (verified by tests).
- The M12 package does not import or expose any production-authority module
  (render submission, recovery coordinator, receipt, evidence contract, job
  store) — verified by an import-scan test.
- Inbound requests containing authorization/receipt/nonce/HMAC/credential or
  artifact/manifest material are REJECTED (`UnauthorizedSemanticFieldError`);
  model-provided authorization is never trusted.
- Execution authorization continues to flow exclusively through the existing
  Atlas mechanism (submission + recovery coordinator + evidence verifier +
  receipt).

## Deterministic validation

- `pytest tests/m12/` → 37 passed
- `pytest tests/test_unreal_render_submission.py tests/test_unreal_recovery_coordinator.py tests/m10/ tests/m11/ tests/m12/` → 384 passed
- `pytest -m "not integration"` → **1488 passed** (no regressions)

No live Unreal, no workflow/action-runner tests, no Blender, no M11 continuation.

## What M12.2 should implement next

- Unreal-specific catalog (`planning/m12/catalog.py`): versioned
  `UnrealSoccerProductionCatalog` resolving canonical task classes to concrete,
  parameterized semantic task definitions; proposal-resolution only.
- Fragment/composition layer (`planning/m12/fragments.py`): reusable composable
  fragments (scene/camera/lighting/sequence/render setup) with dependency
  ordering and idempotence expectations.
- Integration of the catalog + fragments so a semantic intent resolves to an
  ordered plan that compiles to the existing runtime.

Update the handoff and development log (this doc is the M12.1 implementation
record).