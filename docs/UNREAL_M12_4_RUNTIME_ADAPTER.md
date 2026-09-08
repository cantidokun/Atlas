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
  plan to its exact source task, VERIFIES the plan's immutable
  M12.3 `source_content_digest` against the digest recomputed from the supplied
  source (the caller-supplied `expected_source_task_digest`, if present, is a
  redundant assertion only and NEVER establishes authority), reconciles every
  step against the canonical fragment (including render steps), validates closed
  typed provenance and source-metadata against the ONE canonical
  `__post_init__` path, reuses the existing M12.1 compiler to build the existing
  `AtlasTaskDefinition` runtime representation, and fails closed for render and
  on source substitution (PLAN_A + SOURCE_B rejected).

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

**Source-content binding (R5-1/R5-2).** M12.3 embeds an immutable
`source_content_digest` on the plan, computed from the authoritative resolved
source content. `map_unreal_execution_plan` recomputes that digest from the
supplied source and REQUIRES it to equal the plan's commitment; a
same-identity/different-content substitution is rejected EVEN when the caller
supplies a digest matching the substituted source (PLAN_A + SOURCE_B +
DIGEST(SOURCE_B) fails). The caller-supplied `expected_source_task_digest`, if
present, is a redundant assertion only — it never establishes authority.

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

- `pytest tests/m12/` → **279 passed** (incl. Round-1/2/3 blocker tests and Round-4 hardening)
- `pytest tests/m12/ tests/test_unreal_render_submission.py tests/test_unreal_recovery_coordinator.py tests/test_unreal_task_planner.py tests/test_unreal_autonomous_executor.py tests/test_task_definition.py tests/test_authorized_task_runtime.py tests/m10/ tests/m11/` → **614 passed**
- `pytest -m "not integration"` → **1730 passed** (no regressions)
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

### 2. Runtime write-authority mismatch — FIXED (R4-4: REJECT, don't rewrite)
An all-inspect-only semantic plan must never emit a write-capable runtime task.
**Fix:** the adapter independently reconciles the compiled `AtlasTaskDefinition`
against the inspect-only contract (tools/actions/evidence must be `unreal_inspect`
only). Under R4-4 the adapter **REJECTS** a write-capable source rather than
silently zeroing `allow_writes`: a source declaring `allowed_mutations` under an
inspect-only mapping, or a compiled task with `allow_writes=True`, raises
`UnrealRuntimeAdapterError`. The previous `dataclasses.replace(..., allow_writes=False)`
rewrite was removed — caller/source write intent is never downgraded.

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
**Fix (R4-3):** the adapter reconciles `plan.render_plan` against the
authoritative union of source class, canonical fragment render semantics, and
`target_state.expects_render`, failing closed on **any** mismatch (both over- and
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
- `pytest tests/m12/ tests/test_unreal_render_submission.py tests/test_unreal_recovery_coordinator.py tests/test_unreal_task_planner.py tests/test_unreal_autonomous_executor.py tests/test_task_definition.py tests/test_authorized_task_runtime.py tests/m10/ tests/m11/` → **614 passed**
- `pytest -m "not integration"` → **1697 passed** (no regressions)
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

## Round-3 remediation (independent red-team gate #2 — 9 blockers)

An independent adversarial gate (Astra + Claude 5) returned BLOCK with 9 concrete
blockers. All are remediated in this M12.4 line. The changes are architectural
(invariants made true), not documentation-only; every fix is covered by new
deterministic adversarial regression tests (`test_b1_*` … `test_b9_*`).

### B1. Runtime action authority — FIXED
The compiled `AtlasTaskDefinition` is independently reconciled against the
inspect-only contract: `allowed_action_tools` must be exactly `{unreal_inspect}`,
every action and evidence tool must be `unreal_inspect`, and `allow_writes` must
be False. Any render/write/unknown tool or action FAILS CLOSED (never merely
cleared). Tests: `test_b1_render_tool_in_inspect_task_rejected`,
`test_b1_extra_render_tool_rejected`, `test_b1_unknown_tool_in_actions_rejected`.

### B2. Render classification from ALL axes — FIXED
Render-bearing status derives from the UNION of authoritative axes: the source
task class AND canonical fragment render semantics (render-configured /
non-``expandable`` fragments like ``render_setup``). The dangerous direction — a
render-constrained fragment routed through a non-render class — FAILS CLOSED so
it cannot escape the render boundary. A render CLASS with no render fragment (e.g.
``artifact-validate``) still routes to the render boundary. Tests:
`test_b2_render_setup_via_non_render_class_rejected`,
`test_b2_render_class_still_fails_toward_boundary`,
`test_b2_artifact_validate_still_routes_to_boundary`.

### B3. Closed-allowlist provenance + source-metadata smuggling — FIXED
Caller-supplied plan/step provenance is now gated by a CLOSED ALLOWLIST of keys
with explicit meaning (`proposal_source`, `note`, `source_task_version`,
fragment identity/contribution). Unknown keys (``signature``, ``grant``,
``approved``, ``capability``-shaped, etc.) are REJECTED. The resolved source
metadata that reaches the runtime snapshot is likewise allowlisted and
recursively scanned for high-confidence authority material (e.g. a catalog JSON
``camera_slots`` parameter smuggling ``authorization_id``). Tests:
`test_b3_unknown_provenance_key_rejected`, `test_b3_source_metadata_smuggling_rejected`,
`test_b3_legitimate_provenance_preserved`.

### B4. Snapshot is the SOLE runtime-task representation — FIXED
No hidden mutable backing ``AtlasTaskDefinition`` is retained. ``materialize_runtime_task()``
rebuilds from the immutable snapshot only and asserts the rebuilt snapshot's
digest equals ``runtime_task_digest`` before returning an isolated copy. Mutating
a materialized object cannot affect the snapshot, digest, or canonical JSON.
Tests: `test_b4_no_hidden_backing_task`, `test_b4_materialize_rebuild_matches_digest`.

### B5. Unresolved requirements fail closed — FIXED
Every canonical fragment requirement must be resolved by an EARLIER producer
step. An orphan step / missing producer FAILS CLOSED (never an empty-dependency /
supported representation). Test: `test_b5_orphan_step_fails_closed`.

### B6. Catalog version single source of truth — FIXED
`catalog_version` is now the plan's authoritative value; a caller override that
disagrees (or a mismatch with the resolved source metadata) FAILS CLOSED. No
shadow versions. Tests: `test_b6_catalog_version_conflict_rejected`,
`test_b6_catalog_version_agrees_accepted`.

### B7. declared / validated semantics machine-visible — FIXED
``declared`` is now True ONLY when non-canonical caller content is carried
verbatim in a step; clean steps report ``declared=False, reconciled=True``.
Tests: `test_b7_declared_false_for_clean_mapping`,
`test_b7_step_with_caller_provenance_is_declared`.

### B8. Strict JSON / canonical representation — FIXED
``canonical_json``, ``compute_source_task_digest`` and ``_digest_of_jsonable`` all
use ``allow_nan=False``; the strict-JSON + authority validation is applied to the
assembled snapshot (metadata included) before freezing/digesting. NaN/Infinity/
Fraction-like values fail closed. Tests: `test_b8_nan_via_source_parameter_rejected`,
`test_b8_canonical_json_is_strict_and_stable`.

### B9. Self-validating construction — FIXED
``UnrealRuntimeMapping`` / ``UnrealRuntimeStepMapping`` run the SAME single
canonical validation path in ``__post_init__`` as the factory (provenance
allowlist, source digest shape, render-consistency, runtime authority
consistency, digest binding). A directly-constructed invalid mapping FAILS CLOSED.
Tests: `test_b9_direct_invalid_render_contradiction_rejected`,
`test_b9_direct_invalid_snapshot_tools_rejected`.


## Round-4 structural hardening (R4-1..R4-12)

A fourth adversarial gate returned groups of surviving findings. Rather than
expanding vocabulary filters further, R4 made the trust boundary **structural**
— invalid states are now unrepresentable / fail closed — and each change is
covered by deterministic `test_r4_*` adversarial regression tests
(`pytest tests/m12/` → **279 passed**).

### R4-1. Source binding (SUPERSEDED by R5-1/R5-2)
R4-1 made `expected_source_task_digest` a REQUIRED keyword (no silent omission)
so the adapter could not attach to an unbound source. The fourth gate then showed
this was still caller-cooperative: a caller could supply BOTH an alternate
same-identity source AND that source's matching digest. **Round-5 supersedes
R4-1** (see R5-1/R5-2 below): the M12.3 plan now carries the authoritative source
commitment, the caller digest is optional/redundant, and PLAN_A + SOURCE_B +
DIGEST(SOURCE_B) is rejected independently of any caller assertion. The R4-1
tests were replaced by the R5 source-binding tests.

### R4-2 / R4-11. SINGLE canonical validation path
`UnrealRuntimeMapping.__post_init__` runs the SAME canonical validation as the
factory: provenance (typed schema + authority scan), source-digest shape,
render/requirements consistency, runtime-action authority, snapshot<->digest
binding, and (new) a recursive strict-JSON + reserved-key scan of the snapshot
metadata. A directly-constructed invalid mapping FAILS CLOSED identically to a
malformed factory input. Tests: `test_r4_direct_snapshot_metadata_authority_scan`,
`test_b9_direct_invalid_render_contradiction_rejected`,
`test_b9_direct_invalid_snapshot_tools_rejected`.

### R4-3. Render classification — COMPLETE authoritative axes
Render-bearing status now derives from the union of EVERY authoritative M12
axis: source task class (`render_task`), canonical fragment render semantics
(render-execution-constrained / non-`expandable` fragments such as
`render_setup`), AND `target_state.expects_render`. Any authoritative render
requirement routes to the render boundary; conflicting render vs non-render
signals FAIL CLOSED (no silent collapse to non-render). The benign
render-class-without-render-fragment direction (e.g. `artifact-validate`) is
preserved. Tests: `test_r4_target_state_render_axis_recognized`,
`test_r4_render_class_with_target_state_axis_authoritative`,
`test_b2_render_setup_via_non_render_class_rejected`.

### R4-4. Runtime action authority — REJECT, DON'T REWRITE
The adapter no longer silently zeroes write authority. A source task that
declares write mutations (`allowed_mutations` non-empty) under an inspect-only
mapping is **REJECTED** with `UnrealRuntimeAdapterError`, and a compiled runtime
task whose `allow_writes` is True is likewise rejected by
`_reconcile_runtime_authority` (the previous `dataclasses.replace(..., allow_writes=False)`
rewrite is removed). Caller/source write intent is never downgraded. The same
inspect-only gate still requires `allowed_action_tools == {unreal_inspect}` and
every action/evidence tool inspect-only. Tests: `test_r4_write_capable_source_rejected_not_rewritten`,
`test_r4_compiled_allow_writes_rejected_not_rewritten`,
`test_r4_allow_writes_tool_violation_rejected`, `test_b1_*`.

### R4-5. Provenance — CLOSED TYPED SCHEMA (structural, not keyword-guessing)
Caller provenance is validated against an explicit typed schema
(`proposal_source:str`, `source_task_version:int`, `note:str`,
`fragment_id:str`, `fragment_version:int`,
`target_state_contribution:list[str]`). Unknown keys, nested undeclared
structures, free-form caller metadata, and authority-shaped values are REJECTED
structurally — the boundary no longer depends on an ever-growing suspicious-word
vocabulary. The canonical fragment identity/version/contribution fields are
reconciled ADAPTER TRUTH (a caller-forged value is overwritten, never trusted).
A scalar `note` is the only accepted free-form shape and is never promoted into
trusted runtime authority/verification state. Tests:
`test_r2_nested_freeform_provenance_rejected_structural`,
`test_r2_freeform_provenance_rejected_in_step_and_nested_list`,
`test_r4_authority_value_structurally_rejected`, `test_r3_*`.

### R4-6. Snapshot is the SOLE runtime source
`materialize_runtime_task()` rebuilds the existing runtime object from the
immutable canonical snapshot only and asserts the rebuilt snapshot's digest
equals `runtime_task_digest`; no live `AtlasTaskDefinition` is retained as hidden
state. Tests: `test_b4_no_hidden_backing_task`, `test_b4_materialize_rebuild_matches_digest`.

### R4-7. Unresolved requirements fail closed
Every canonical fragment requirement must be resolved by an earlier producer;
orphan/missing-producer steps fail closed. Test: `test_b5_orphan_step_fails_closed`.

### R4-8. Catalog version — exact-int identity
`catalog_version` has ONE authoritative exact-int source. Caller overrides and
resolved source metadata must be EXACT `int` and equal to the plan's value;
lossy `int()` coercion and bool/float/str values FAIL CLOSED (no
`"1"`/`1.9`/`True` collapsing). Tests: `test_r4_catalog_version_type_coercion_rejected`,
`test_r4_source_metadata_catalog_version_exact_int`,
`test_b6_catalog_version_conflict_rejected`.

### R4-9. Declared vs reconciled, truthful and machine-visible
`declared` is True exactly when caller-supplied non-canonical content is carried
verbatim; reconciled fields are re-derived from the canonical fragment. Caller
provenance that survives is explicitly declared, never labeled validated. Tests:
`test_b7_declared_false_for_clean_mapping`, `test_b7_step_with_caller_provenance_is_declared`.

### R4-10. Strict JSON / canonicalization — reject unsupported numeric types
Canonical JSON stays `allow_nan=False`, string-keyed, finite-only; additionally
unsupported numeric types (`Fraction`, `Decimal`, numpy scalars, other
`numbers.Real`/`Integral` subclasses) are REJECTED STRUCTURALLY before
serialization with the declared canonical-contract error type (no leaked
`TypeError`/`ValueError`). Tests: `test_r4_fraction_rejected_structurally`,
`test_r4_decimal_rejected_structurally`, `test_b8_*`.

### R4-12. M12.5 future boundary
Independent evidence verification remains unimplemented. The snapshot carries
explicit disclosure (`m12.4.evaluator_kind`, `m12.4.independently_verified`,
`m12.4.declared`) so no future layer mistakes a structural placeholder for
verified evidence. No verification authority is granted at M12.4.

## Validation (after Round-4 hardening)

- `pytest tests/m12/` → **279 passed** (incl. Round-1/2/3 and new `test_r4_*`)
- `pytest -m "not integration"` → **1730 passed**
- `tests/m12/test_m12_authority_isolation.py` → **5 passed** (adapter imports
  only M12 + `AtlasTaskDefinition`; no production-authority module).
- No live Unreal, no workflow/action-runner tests, no Blender, no M11, no M4-M10
  change.


## Round-5 — Source-commitment + single canonical validation path (R5-1..R5-7)

Fourth-gate synthesis (independent Astra BLOCK + Claude PASS-with-concerns) both
flagged the caller-cooperative source binding and the direct-construction
validation-path divergence. Round-5 restructures rather than adding keyword
filters.

### R5-1 — M12.3 plan carries the authoritative source commitment
`generate_execution_plan` computes an immutable `source_content_digest`
(STRICT-JSON SHA-256 of the resolved source content) and embeds it in the plan's
canonical representation and plan id. Same-identity/different-content tasks yield
different plans. A caller cannot inject a digest assertion as authoritative;
missing/invalid commitment fails closed at plan construction.

### R5-2 — M12.4 verifies the plan commitment (binding no longer caller-cooperative)
`map_unreal_execution_plan` recomputes the digest from the supplied source and
REQUIRES it to equal the plan's `source_content_digest`. The
`expected_source_task_digest` argument is now OPTIONAL and is a redundant
assertion only. The exact exploit PLAN_A + SOURCE_B + DIGEST(SOURCE_B) FAILS
because PLAN_A's commitment is DIGEST(SOURCE_A).
Tests: `test_r5_plan_a_source_b_digest_b_rejected`,
`test_r5_expected_digest_is_redundant_assertion`,
`test_r5_source_binding_uses_plan_commitment_not_caller_digest`,
`test_r5_same_identity_different_content_plan_identity`.

### R5-3 / R5-5 — ONE canonical validation path (incl. source-metadata)
`UnrealRuntimeMapping.__post_init__` is the single validation entry for BOTH the
factory and direct construction. In addition to the R4-inherited checks it now
enforces, in the SAME path:
- per-step consistency (a supported step must target `unreal_inspect` with
  `inspect-only` capability and a canonical fragment identity; an unsupported
  step must carry the explicit render-boundary reason) — R5-3;
- source-derived runtime metadata must conform to the closed
  `_ALLOWED_SOURCE_METADATA_KEYS` schema (direct construction can no longer
  inject `scheduler`/`retry`/`scope`-shaped keys into the trusted snapshot) —
  R5-5.
Tests: `test_r5_direct_step_supported_non_inspect_rejected`,
`test_r5_direct_step_write_capability_rejected`,
`test_r5_direct_unsupported_step_without_reason_rejected`,
`test_r5_factory_and_direct_use_same_validator`.

### R5-4 — Adapter-owned provenance must match authoritative fields
`_validate_mapping_provenance` now CROSS-VALIDATES adapter-owned provenance keys
against the mapping's authoritative dataclass fields (`recognized_render_plan ==
render_plan`, `semantic_fidelity`, `source_task_digest`, `runtime_task_digest`,
`mapped_runtime_task_type`), and pins `independently_verified is False` and
`runtime_evaluator_kind == structural-placeholder`. A caller-supplied
`source_task_version` in provenance must equal the plan's authoritative version
(no shadow identity). A directly-constructed mapping carrying
`independently_verified=True` / a contradictory render/digest/fidelity claim
FAILS CLOSED.
Tests: `test_r5_direct_independently_verified_true_rejected`,
`test_r5_direct_invalid_evaluator_kind_rejected`,
`test_r5_direct_forged_source_digest_rejected`,
`test_r5_direct_forged_runtime_digest_rejected`,
`test_r5_direct_render_flag_contradiction_rejected`,
`test_r5_source_task_version_provenance_reconciled_not_shadow`.

### R5-6 — Declared / reconciled is truthful
`declared` is now set from actual caller-carried content: True exactly when
`proposal_source`/`note` survive, and an explicit `declared_caller_fields` list
is emitted. A mapping no longer claims `declared=False` while carrying caller
strings (`test_b7_*` was corrected, having previously encoded the defect).
`reconciled=True` is scoped to the adapter's authoritative/security-relevant
fields, which are re-derived and validated.
Tests: `test_b7_declared_true_when_caller_provenance_carried`,
`test_b7_declared_false_only_when_no_caller_verbatim_content`.

### R5-7 — Direct-construction adversarial tests
`test_r5_direct_*` constructs `UnrealRuntimeMapping` directly with forged
provenance (`independently_verified`, `runtime_evaluator_kind`, source/runtime
digests, render/fidelity/type contradictions), forgeable steps (non-inspect
target, write capability, unsupported-without-reason), and out-of-schema snapshot
metadata — every one fails closed through the SAME `__post_init__` path the
factory uses. A faithful reconstruction succeeds.

## Round-5 validation

- `pytest tests/m12/` → **279 passed** (was 263; +16 R5 tests)
- `pytest -m "not integration"` → **1730 passed** (no regressions)
- `tests/m12/test_m12_authority_isolation.py` → **5 passed**
- M12.1 (`semantic_task.py`) is UNTOUCHED; the source-commitment implementation
  lives in M12.3 (`execution_plan.py`).
- No live Unreal, no workflow/action-runner tests, no Blender, no M4-M10 change.


## Round-6 — Canonical identity + reconstruction hardening (R6-1..R6-6)

Fifth-gate synthesis (independent Astra BLOCK, 5 blockers; Claude BLOCK, 3
blockers) converged on the surviving structural gaps: caller-controlled plan
identity, a shape-only (not canonical) `__post_init__`, un-scoped provenance that
could create competing truths, coercion in source hashing, and non-structural
source-metadata filtering. Round-6 makes the five central claims TRUE by
construction.

### R6-1 — plan_id is DERIVED, never caller-authoritative
`UnrealExecutionPlan.__post_init__` recomputes `plan_id` from the canonical
identity inputs (source task id/version, ordered canonical fragment operations,
source commitment) and rejects any mismatch; `_build_plan_id` has NO digest-less
fallback. `map_unreal_execution_plan` independently recomputes the expected
plan_id and rejects a plan whose `plan_id` disagrees with its own canonical inputs.
Tests: `test_r6_plan_id_cannot_be_forged`,
`test_r6_plan_a_identity_source_b_commitment_rejected`,
`test_r6_no_digestless_plan_identity`.

### R6-2 — one shared strict canonicalization for hashing + serialization
`compute_source_content_digest`, plan `canonical_json()`, and identity digests all
go through the single `_validate_strict_json` / `_canonical_sha256` in M12.3. They
reject non-string keys, NaN/Infinity, non-JSON-native numeric types, preserve
bool/int/float distinction, and order mappings deterministically — so json.dumps
implicit coercion can no longer collapse distinct typed source content into one
commitment. Tests: `test_r6_non_string_key_rejected_in_digest`,
`test_r6_typed_distinctions_preserved_in_digest`.

### R6-3 — direct construction is CANONICAL (not shape checking)
`UnrealRuntimeMapping.__post_init__` now invokes `_reconstruct_canonical_targets`,
which resolves every step's `canonical_fragment`, requires `fragment_id`/`version`
to equal canonical, runs `_reconcile_step_fidelity` against a producer map derived
from the mapping's own step order, enforces render/support consistency (a
render-configured fragment can never be a supported inspect step; an unsupported
step must carry the render-boundary reason and only on a render-plan), and
cross-checks the runtime snapshot's embedded identity/catalog fields against the
mapping's authoritative identity. A direct mapping that cannot be canonically
reconstructed fails closed — identical to the factory's validation of the same
state. Tests: `test_r6_render_setup_as_supported_inspect_rejected`,
`test_r6_forged_fragment_id_rejected`, `test_r6_forged_fragment_version_rejected`,
`test_r6_forged_idempotence_rejected`, `test_r6_forged_verification_requirements_rejected`,
`test_r6_snapshot_identity_cross_consistency`.

### R6-4 — explicit provenance scope; no competing truths
Provenance is validated with an explicit scope. Step/fragment-authoritative fields
(`fragment_id`, `fragment_version`, `target_state_contribution`) are only valid at
STEP scope (where the adapter reconciles them to canonical truth); at PLAN/mapping
scope they are REJECTED, so the same semantic value cannot exist as both caller
provenance and adapter canonical state. Tests:
`test_r6_plan_level_step_scoped_provenance_rejected`.

### R6-5 — structural source-metadata gate
`_validate_source_metadata_parameters` bounds the snapshot's source-derived
`parameters` against the catalog entry's declared `parameter_kinds` (explicit
schema/type/meaning) — a STRUCTURAL gate, not a suspicious-vocabulary scan.
Undeclared parameter keys (whatever their spelling) and unsupported `json` shapes
are rejected, so nested authority/security-shaped values inside a catalog parameter
cannot enter the trusted snapshot. Test: `test_r6_undefined_catalog_parameter_rejected`.

### R6-6 — declared/reconciled derived from actual content, cross-validated
`declared` / `declared_caller_fields` / `reconciled_caller_fields` are DERIVED from
the mapping's actual surviving plan-level caller content (informational
`proposal_source`/`note` mark declared; reconciled `source_task_version` does not)
and cross-validated in `_validate_mapping_provenance`: a direct construction
asserting `declared=False` while carrying caller content is rejected. Tests:
`test_r6_declared_matches_surviving_caller_content`,
`test_r6_declared_reconciled_not_hardcoded`,
`test_r6_direct_false_declaration_with_caller_content_rejected`.

## Round-6 validation

- `pytest tests/m12/` → **296 passed** (was 279; +17 R6 tests)
- `pytest -m "not integration"` → **1747 passed** (no regressions)
- `tests/m12/test_m12_authority_isolation.py` → **5 passed**
- Scope: M12.3 (`execution_plan.py`) + M12.4 (`runtime_adapter.py`) + tests. M12.1,
  M4-M10, M12.5 untouched.
- can_execute remains False on plan, mapping, and steps; no
  execute/authorize/submit/recover/verify authority added.


## Round-7 — Targeted regression + identity hardening (R7-1..R7-5)

The sixth gate independently confirmed a critical regression and three coupled
identity/truthfulness blockers. Round-7 is a TARGETED incremental repair on top of
Round-6's canonical reconstruction — it does not roll back or broaden anything.

### R7-1 — Restore direct-construction inspect-only step authority (regression fix)
Round-6's `_reconstruct_canonical_targets` dropped the R5-3 checks that a SUPPORTED
step must target `unreal_inspect` with `inspect-only` capability. Round-7 restores
them in the SAME canonical path used by factory and direct construction:
- supported ⇒ `target_runtime_operation == "unreal_inspect"`, `capability_requirement ==
  "inspect-only"`, `unsupported_reason is None`, `fragment_id` present;
- unsupported ⇒ `target_runtime_operation == "<none>"` (and the explicit
  render-boundary reason).
A directly-constructed supported step with `unreal_render`/`write` now FAILS CLOSED.
Tests: `test_r7_supported_step_*`, `test_r5_direct_step_supported_non_inspect_rejected`,
`test_r5_direct_step_write_capability_rejected`.

### R7-2 — False-green tests repaired (mandatory)
The R5/R6 direct-step authority tests previously passed because `dataclasses.replace(m,
steps=(s,))` without valid provenance tripped an unrelated frozen-provenance
`TypeError`, not the authority guard. All such tests now construct valid
`provenance=dict(m.provenance)` first and, where applicable, assert the specific
`"inspect-only authority"` message — proving the rejection is caused by the intended
contract validation, not a setup error.

### R7-3 — Mapping-level identity is MANDATORY and DERIVED
`_reconstruct_canonical_targets` now requires:
- `mapping.plan_id == _build_plan_id(source_task_id, version, ordered step
  operations, source_task_digest)` (derived, never caller-supplied; no "identity A +
  commitment B", no arbitrary plan_id);
- for non-render mappings, the snapshot metadata identity/catalog fields
  (`unreal_semantic_task_id`, `unreal_semantic_task_version`, `catalog_version`) must
  be PRESENT and equal — fail closed on omission (no "skip validation because absent");
- render-bound mappings (no snapshot) preserve the non-executable boundary.
Tests: `test_r7_forged_mapping_plan_id_rejected`, `test_r7_correct_mapping_plan_id_accepted`,
`test_r7_snapshot_identity_omission_fails_closed`, `test_r7_source_commitment_mismatch_rejected`.

### R7-4 — Step provenance reconciles; step `declared` is derived
Within a step, the canonical fragment id/version and target-state contributions are
authoritative: any step-provenance copy that carries one of these fields must equal
canonical truth (fail closed), and `step.declared` must equal
`bool(surviving caller-controlled fields)` — never hard-coded and never a false
"no caller content" claim.
Tests: `test_r7_step_provenance_forged_*`, `test_r7_step_false_declared_rejected`,
`test_r7_step_declared_true_when_caller_content_present`.

### R7-5 — mapping source_task_version is reconciled
`mapping.source_task_version` is authoritative; if caller provenance also carries
`source_task_version` it must equal it exactly, otherwise reject. The field is only
labelled reconciled after that comparison.
Tests: `test_r7_source_task_version_mismatch_rejected`,
`test_r7_source_task_version_match_accepted`.

## Round-7 validation

- `pytest tests/m12/` → **314 passed** (was 296; +18 R7 tests; the R5 direct-step
  authority tests now genuinely exercise the restored guards)
- `pytest -m "not integration"` → **1765 passed** (no regressions)
- `tests/m12/test_m12_authority_isolation.py` → **5 passed**
- Scope: M12.4 (`runtime_adapter.py`) + tests only this round. M12.3, M12.1, M4-M10,
  M12.5 untouched.
- can_execute remains False (plan, mapping, steps); no
  execute/authorize/submit/recover/verify authority; no M4-M10 authority imports.


## Round-8 — Targeted canonical snapshot reconstruction (R8-1..R8-4)

The seventh gate (independent Astra BLOCK + Claude BLOCK) confirmed two concrete
blockers: a broken unsupported-step guard raising `NameError`, and the direct
construction path not canonically reconstructing snapshot *semantic* content.
Round-8 is a targeted correction that preserves all confirmed-working R6/R7
controls.

### R8-1 — Repaired unsupported-step guard (`NameError` fix)
The R7-1 unsupported-step target-operation message literal
`"target the "<none>" operation"` was a broken string that Python parsed as a
chained comparison against the undefined name `none`, raising `NameError` instead
of `UnrealRuntimeAdapterError` when that branch was reached. It is fixed to a valid
literal (`must target the '<none>' operation`). Added a guard-reaching test that
mutates ONLY `target_runtime_operation` on a valid render mapping's `render_setup`
step (preserving provenance, declared state, derived plan_id, fragment identity),
and asserts the exact `UnrealRuntimeAdapterError` message — so it FAILS if the
guard is removed. Empirically verified: the branch now raises
`UnrealRuntimeAdapterError`, not `NameError`.

### R8-2 — Canonical snapshot semantic reconstruction (shared path)
`_reconstruct_canonical_targets` (used by BOTH factory and direct construction)
now derives authoritative expected snapshot semantics from the mapping's own
canonical source/steps and rejects any supplied snapshot that disagrees (fail
closed on omission, never skip-on-absence):
- (A) `unreal_target_state.invariant_names` must equal the canonical union of the
  step target-state contributions;
- (B) `unreal_target_state.expects_render` must equal `render_plan`;
- (C) `unreal_semantic_task_class` render semantics must be consistent with
  `render_plan` (a render-bearing class cannot appear in an inspect-only snapshot);
- (D) `unreal_semantic_dependencies` must equal the deterministic ordered semantic
  step operations;
- (E) snapshot `parameters` must pass the SAME structural catalog-parameter schema
  gate the factory applies (`_validate_source_metadata_parameters`, now shared).

All five checks hold for every factory-produced mapping and close the
factory/direct divergence the gate confirmed (a directly-constructed mapping could
previously inject forged invariants / render axis / class / dependencies /
nested parameters and have them reach `materialize_runtime_task()`).

### R8-3 — direct-route authority guard coverage
Direct-construction tests now build from a valid factory mapping, mutate exactly
one security/semantic field, preserve valid provenance/digest/plan_id/declared
state, and assert the intended canonical guard message.

### R8-4 — false-green test audit
The previously suspect tests are corrected so they cannot pass via accidental
setup exceptions (valid provenance first, recomputed digest/plan_id, `match=` on
the unique guard message).

## Round-8 validation

- `pytest tests/m12/` → **324 passed** (was 314; +10 R8 tests; R8-1 guard-reaching
  test, 6 snapshot semantic-forgery tests, omission + positive controls)
- `pytest -m "not integration"` → **1775 passed** (no regressions)
- `tests/m12/test_m12_authority_isolation.py` → **5 passed**
- semantic/runtime deterministic subset → **80 passed**
- Scope: M12.4 (`runtime_adapter.py`) + tests only. M12.3, M12.1, M4-M10, M12.5
  untouched.
- can_execute remains False; no execute/authorize/submit/recover/verify authority;
  no M4-M10 authority imports.

