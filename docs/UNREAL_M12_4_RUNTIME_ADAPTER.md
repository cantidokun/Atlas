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
  fragment_id, fragment_version, preconditions, verification_requirements,
  unsupported_reason, declared, provenance). Every reconciled field is re-derived
  from the canonical fragment; a crafted plan cannot distort it.
- `UnrealRuntimeMapping` — immutable result (plan_id, source_task_id/version,
  catalog_version, digital_twin_id, source_task_digest, ordered step mappings,
  render_plan, requires_existing_render_submission_path,
  runtime_task_snapshot, runtime_task_digest, semantic_fidelity, provenance)
  with stable canonical JSON.
- `compute_source_task_digest(source_task)` — deterministic SHA-256 binding of
  the resolved canonical source content (substitution detector).
- `map_unreal_execution_plan(plan, *, source_task, catalog_version=None,
  expected_source_task_digest=None)` — deterministic mapping. Identity-locks the
  plan to its exact source task, reconciles every step against the canonical
  fragment (including render steps), recursively rejects authority/security
  material in provenance, reuses the existing M12.1 compiler to build the
  existing `AtlasTaskDefinition` runtime representation, and fails closed for
  render and on source-content substitution.

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
  from the AUTHORITATIVE source-task classification and produce **no** runtime
  representation (`runtime_task_snapshot=None`). M12.4 does not fabricate render
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
- sets `runtime_task_snapshot=None` (no runtime representation is fabricated);
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
catalog version, execution-plan id, source-content digest, fragment ids/versions
(via steps), preconditions, verification requirements, and legitimate proposal
provenance. The mapping never collapses canonical digital-twin identity, semantic
task identity, execution-plan identity, or runtime job identity.

**Authority/security material is REJECTED, never forwarded.** `map_unreal_execution_plan`
recursively validates every key in plan and step provenance (nested dicts and
lists at any depth), normalizing casing/separators, and rejects any
authorization/receipt/nonce/HMAC/credential/secret/session/jwt/bearer/recovery/
scheduler/artifact/manifest-like key, including aliases (`apiKey`/`apikey`) and
casing tricks (`IS_AUTHORIZED`). Non-string mapping keys and non-JSON values are
rejected. Adapter-owned provenance fields are authoritative and cannot be
shadowed by a caller.

**Source-content binding.** `compute_source_task_digest` hashes the resolved
canonical source content; every mapping carries and serializes it. Two
same-identity tasks with different resolved content yield different digests, and
a caller may pass `expected_source_task_digest` to fail closed on substitution.

## Immutability of the embedded runtime task

The mapping does **not** expose a mutable `AtlasTaskDefinition` handle. It stores
`runtime_task_snapshot` (a deeply immutable, JSON-serializable snapshot covering
name, evidence, actions, `allowed_action_tools`, `allow_writes`,
`verify_after_action`, and metadata) plus `runtime_task_digest`. Callers that need
the existing runtime object call `mapping.materialize_runtime_task()` to obtain a
**fresh, isolated deep copy** — mutating that copy (e.g. adding `unreal_render` to
`allowed_action_tools`, editing metadata) can never change the mapping's
snapshot, digest, or canonical JSON.

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

- `pytest tests/m12/` → **226 passed** (88 prior + 138 M12.4, incl. Round-2 blocker tests)
- `pytest tests/m12/ tests/test_unreal_render_submission.py tests/test_unreal_recovery_coordinator.py tests/test_unreal_task_planner.py tests/test_unreal_autonomous_executor.py tests/test_task_definition.py tests/test_authorized_task_runtime.py tests/m10/ tests/m11/` → **594 passed**
- `pytest -m "not integration"` → **1677 passed** (was 1594, +83)
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
## Red-team remediation (independent adversarial review)

An adversarial review of `planning/m12/runtime_adapter.py` found reproducible
issues; all were remediated in the same M12.4 line (no new milestone). Each fix
is covered by a deterministic adversarial regression test.

### 1. Authority/secret smuggling — FIXED
A crafted plan could place forbidden authority/security material (e.g.
`authorization_id`, `hmac_key`, `attempt_nonce`, `receipt`, `credential`,
protected/recovery/artifact authority, scheduler/retry directives) in
`plan.provenance`, which the adapter previously forwarded verbatim.
**Fix:** the adapter now independently validates plan-level and step-level
provenance (`is_forbidden_authority_key`, mirroring M12.1's exact+substring
matcher) and **rejects** any forbidden key with `UnrealRuntimeAdapterError`
rather than silently dropping or forwarding it. Legitimate provenance fields
(proposal source, notes) are preserved.

### 2. Runtime write-authority mismatch — FIXED
An all-inspect-only semantic plan compiled to an `AtlasTaskDefinition` with
`allow_writes=True` (inherited from source-task `allowed_mutations`), which could
be mistaken for write authority.
**Fix:** the adapter reconciles the existing `allow_writes` field against the
plan's capability. For an all-inspect-only plan the emitted runtime task is
produced with `allow_writes=False` (via `dataclasses.replace` on the existing
`AtlasTaskDefinition`). No new authority field is invented; the semantic
restriction is honored by the existing runtime field.

### 3. Dependency / target-state / input fidelity — FIXED
A crafted plan could alter `dependencies`, `required_inputs`,
`target_state_contributions`, or `idempotence` after generation and still map,
because the adapter copied plan values verbatim.
**Fix:** the adapter re-derives each supported step's required inputs,
target-state contributions, idempotence, and dependencies from the **canonical
fragment** (`canonical_fragment`) and from a reconstruction of M12.3's
producer→step map, and rejects any inconsistency with
`UnrealRuntimeAdapterError`. The mapping is now independent of mutable/adversarial
plan contents on these critical fields.

### 4. Per-step fragment provenance — FIXED
`UnrealRuntimeStepMapping` previously had no provenance field, so fragment
identity/version was lost.
**Fix:** each step mapping now carries `fragment_id` and `fragment_version`
(driven from the canonical fragment) plus a deep-frozen step provenance dict,
included in `to_json_compatible()` and the canonical JSON.

### 5. Render-plan classification trust — FIXED
`render_plan` was trusted from the plan flag rather than the authoritative source
task.
**Fix:** the adapter reconciles `plan.render_plan` against the authoritative
`source_task.render_task` and fails closed on **any** mismatch (both over- and
under-flag). A caller cannot understate render-bearing status to reach a runtime
task, nor overstate it to route a non-render plan. Render-safe behavior is
preserved: render-bearing → `requires_existing_render_submission_path=True`,
`runtime_task=None`, `can_execute=False`.

### 6. Deep immutability — FIXED
Nested `provenance` was mutable despite the mapping being frozen.
**Fix:** provenance (mapping-level and step-level) is deep-frozen to
`MappingProxyType`/tuple at construction via `_deep_freeze`. Mutation after
construction fails (TypeError on `MappingProxyType`), and canonical JSON is stable
against attempted mutation.

### 7. Semantic fidelity decision — EXPLICIT
**Conclusion (not just documentation):** The existing Atlas runtime represents an
M12 semantic task as a **single aggregate** `AtlasTaskDefinition` (one
`unreal_inspect` action built by the M12.1 compiler); it has **no per-fragment
runtime operations**. Therefore M12.4 does not claim per-fragment executable
fidelity. The mapping's `semantic_fidelity` field is set to `"aggregate"` for
non-render plans (task-level aggregate representation + per-step declared
semantics) and `"unavailable"` for render-bearing plans. A step whose semantic
operation is not a known canonical fragment fails closed. M12.4 does **not**
redesign M4–M10 and does **not** introduce a second runtime; per-fragment
distinctions remain declared semantics that M12.5's independent verifier consumes
from the plan, not distinct runtime operations this adapter pretends to execute.

### 8. Placeholder verifier — DEFERRED TO M12.5 (documented)
The emitted `AtlasTaskDefinition` carries M12.1's structural placeholder
evaluator (presence/truthiness of declared invariant names in evidence). M12.4
itself performs no verification and never claims verified status. This document
distinguishes:
- **target-state declaration** — the semantic invariants the plan/compiled task
  declares (no verification authority);
- **runtime evaluator representation** — the placeholder `TargetStateEvaluator`
  attached by M12.1's compiler (structural only, must NOT be treated as
  independent verification);
- **actual independent verification** — M12.5's job, using the existing evidence
  machinery; must not trust self-reported evidence.

## Validation (after red-team remediation)

- `pytest tests/m12/` → **226 passed** (incl. Round-2 blocker regression tests)
- `pytest tests/m12/ tests/test_unreal_render_submission.py tests/test_unreal_recovery_coordinator.py tests/test_unreal_task_planner.py tests/test_unreal_autonomous_executor.py tests/test_task_definition.py tests/test_authorized_task_runtime.py tests/m10/ tests/m11/` → **594 passed**
- `pytest -m "not integration"` → **1677 passed** (no regressions)
- Authority-isolation import scan clean. No M4–M10 / Blender / authority change.

## Round-2 remediation (independent red-team BLOCKERS)

An independent adversarial gate returned BLOCK with a specific blocker list.
All are remediated in this M12.4 line (still no new milestone, still adapter-only).

### B1. Nested / casing / alias provenance smuggling — FIXED
`is_forbidden_authority_key` now normalizes casing/separators and checks a broad
authority/credential vocabulary (authorization, receipt, nonce, HMAC, credential,
password/secret, session, jwt, bearer, recovery, scheduler/retry, protected,
artifact/manifest, token, api-key, ...). `_validate_provenance` recurses through
mappings and sequences at any depth, rejects non-string keys and non-JSON values,
rejects adapter-reserved shadow keys, and never strips-and-continues.
Tests: `test_r2_forbidden_authority_nested_casing_alias_rejected`,
`test_r2_nested_step_provenance_rejected`, `test_r2_is_forbidden_alias_vocabulary`.

### B2. Embedded runtime_task mutability — FIXED
The mapping no longer exposes a mutable `AtlasTaskDefinition`. It stores an
immutable `runtime_task_snapshot` + `runtime_task_digest`; callers use
`materialize_runtime_task()` for a fresh isolated deep copy. `canonical_json`
serializes the full snapshot, so `runtime_task_snapshot.allowed_action_tools` can never gain
`unreal_render` in the canonical view and metadata cannot be changed to alter
semantics undetected.
Tests: `test_r2_runtime_task_no_mutable_handle_exposed`,
`test_r2_canonical_binds_runtime_permissions`.

### B3. Asymmetric render-path fidelity — FIXED
The same `_reconcile_step_fidelity` (inputs, target-state contributions,
idempotence, prefix-only dependencies, preconditions, verification requirements)
is applied to EVERY step, including render-bearing steps. A forged
render-path target-state or preconditions now fails closed.
Tests: `test_r2_render_path_step_fidelity_reconciled`,
`test_r2_render_path_precondition_tamper_rejected`,
`test_r2_preconditions_and_verification_preserved`.

### B4. Source binding — FIXED
`compute_source_task_digest` deterministically binds the resolved canonical
source content. The mapping carries and serializes `source_task_digest`; a caller
may pass `expected_source_task_digest` to fail closed on same-identity /
different-content substitution. Plan target-state is also reconciled against the
source task's target-state invariants.
Tests: `test_r2_source_digest_binds_resolved_content`,
`test_r2_expected_source_digest_rejects_substitution`,
`test_r2_deterministic_source_binding`.

### B5. Adapter-owned provenance shadowing — FIXED
Adapter-owned keys (`recognized_render_plan`, `semantic_fidelity`,
`mapped_runtime_task_type`, `source_task_digest`, `runtime_task_digest`,
`declared`) are reserved: a caller supplying them is rejected. Fragment identity
in step provenance (M12.3-declared) is overwritten with canonical truth rather
than surviving as a shadow.
Tests: `test_r2_adapter_owned_provenance_not_shadowable`.

### B6. Immutability / serialization — FIXED
Provenance and runtime-task snapshot are deeply frozen and recursively thawed
inside the canonical serializer, so nested structures are both immutable and
JSON-serializable (no MappingProxyType serialization error).
Tests: `test_r2_nested_provenance_canonical_json_serializes`,
`test_r2_nested_provenance_immutable_after_construction`.

## Contract alignment (authoritative / validated / declared / deferred)

- **Authoritative**: source-task render classification, source-content digest,
  adapter-owned provenance field values, allowed-action-tools snapshot.
- **Validated**: every `_RECONCILED_FIELDS` step field (required inputs,
  dependencies, target-state contributions, idempotence, fragment id/version,
  preconditions, verification requirements) is re-derived from the canonical
  fragment and reconciled; divergence fails closed.
- **Immutable**: `UnrealRuntimeMapping` / `UnrealRuntimeStepMapping` are frozen;
  provenance and runtime-task snapshot are deeply frozen and canonically bound.
- **Merely declared (not validated truth)**: nothing in a step mapping is
  presented as validated runtime truth unless it is both reconciled against the
  canonical fragment AND materialized through the existing runtime; M12.4 never
  claims per-fragment executable fidelity.
- **Intentionally deferred to M12.5**: independent evidence verification and the
  authoritative render-submission entry point. M12.4 performs no verification and
  never marks anything verified.

