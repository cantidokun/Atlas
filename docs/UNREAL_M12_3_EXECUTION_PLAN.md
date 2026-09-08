# Atlas M12.3 — Unreal Semantic Execution Plan Boundary

**Status:** IMPLEMENTED (M12.3). Builds on merged M12.2 (PR #88) and M12.1.

## What M12.3 implements

A small, immutable, language-neutral **semantic execution-plan** boundary between
the M12 catalog/composition layer and the future M12.4 Unreal execution adapter.
M12.3 is a PLAN, not an executor.

### Execution-plan contract — `planning/m12/execution_plan.py`
- `UnrealExecutionPlanStep` — immutable step (step_id, semantic_operation,
  required_inputs, preconditions, dependencies, target_state_contributions,
  idempotence, verification_requirements, execution_capability_requirement,
  provenance).
- `UnrealExecutionPlan` — immutable plan (plan_id, source_task_id/version,
  catalog_version, digital_twin_id, **source_content_digest**, ordered steps,
  provenance) with stable canonical JSON.
- `compute_source_content_digest(task)` — the SINGLE authoritative
  source-content commitment (STRICT-JSON SHA-256 of the resolved source content).
- `generate_execution_plan(task, *, catalog_version)` — deterministic plan
  generation from a resolved `UnrealProductionTaskDefinition` and its ordered
  fragment dependencies; computes and embeds the immutable
  `source_content_digest`.

### Source-content commitment (R5-1) + derived plan identity (R6-1)
`generate_execution_plan` computes an immutable `source_content_digest` — a
STRICT-JSON SHA-256 (`allow_nan=False`, sorted keys, string-only keys) of the
AUTHORITATIVE resolved source content (identity, version, twin, target state,
dependencies, evidence, actions, allowed tools/mutations, catalog metadata). It is:
- computed from the resolved source task content itself (never from a caller
  assertion — a caller cannot inject a digest as authoritative);
- embedded in the plan's canonical representation and participates in plan
  identity (same task identity with different resolved content yields a
  different plan_id);
- immutable and validated at construction (missing/invalid commitment fails
  closed);
- deterministic and stable for semantically equivalent source content.

**R6-1: plan_id is DERIVED, not caller-controlled.** `UnrealExecutionPlan.__post_init__`
recomputes the authoritative `plan_id` from the canonical identity inputs (source
task identity, version, ordered canonical fragment operations, source commitment)
via `_build_plan_id` and rejects any supplied value that differs. There is no
digest-less identity fallback. This makes impossible:
- "plan A identity + source commitment B" (the digest is part of the identity);
- "source commitment A + arbitrary plan ID" (plan_id is a pure function of the
  canonical inputs).

A caller cannot SUPPLY the plan's commitment; M12.4 recomputes it from the
supplied source and verifies it equals the plan's commitment (closing the
PLAN_A + SOURCE_B + DIGEST(SOURCE_B) substitution), and independently recomputes
the expected plan_id and rejects mismatches.

**R6-2: one shared strict canonicalizer.** `_validate_strict_json` /
`_canonical_bytes` / `_canonical_sha256` are the SINGLE strict canonicalization used
for source hashing, plan `canonical_json()`, and identity digests. It rejects
non-string mapping keys (so `{1:"x"}` is not coerced), NaN/Infinity, non-JSON-native
numeric types (Fraction/Decimal/numpy), preserves bool/int/float distinctions, and
orders mappings deterministically. Hashing and serialization therefore can never
diverge, and a caller cannot collapse distinct typed source content into one digest
via json coercion.

### What it describes (no execution)
- canonical plan ID + source semantic task ID/version + catalog version +
  digital-twin identity;
- ordered plan steps + step identity + semantic operation (the fragment id) +
  required inputs + expected preconditions + target-state contributions +
  dependency relationships (resolved to producing steps) + provenance +
  idempotence + execution-capability requirement.

## Plan vs execution / authorization / verification

- **Plan vs execution:** a plan describes steps; `can_execute` is always `False`.
  No step maps to an Atlas authorization or Unreal transport payload.
- **Plan vs verification:** steps carry `verification_requirements` as
  *descriptions* only; creating a plan marks NOTHING verified (no
  verified/result field exists).
- **Plan vs authorization:** plan creation produces no authorization material and
  no side effects.

## Preconditions

Each step's `preconditions` are descriptive planning constraints (e.g. `scene_ready`
must exist before `camera_setup`). They are NOT runtime checks — a future
executor/verifier (M12.4+) may consume them.

## Dependency semantics

Steps carry explicit `dependencies` = the step ids that produce the required
requirements (e.g. `camera_setup` depends on the `scene_setup` step). This makes
the semantic-dependency relationship explicit without any scheduling authority.

## Render handling

Render-bearing tasks (render-execute, artifact-validate) generate a **render
plan** (`render_plan=True`, `has_render_step()`) describing render intent, but:
- `can_execute` is always False;
- mapping to the trusted runtime remains blocked — `compile_unreal_semantic_task`
  still raises `UnsupportedCompileMappingError` for render-bearing tasks (M12.1
  rule preserved);
- render steps are `non-idempotent`, `inspect-only`.

## Verification requirements

Each step declares `verification_requirements` (its target-state contributions).
These are descriptions for a future independent verifier; M12.3 creates no
evidence and grants no verification authority (no second evidence system).

## Provenance

Preserved: digital-twin id, source semantic task id/version, catalog version,
fragment ids (via steps), proposal provenance. NOT created: receipts, production
artifacts, recovery records, authorization IDs.

## Idempotence & repeatability

Fragment idempotence is carried into each step: `idempotent` (scene/camera/
lighting/sequence/environment), `non-idempotent` (render), `unknown` (fail-closed
default for unknown fragments).

## Failure model (all fail closed)

- unresolved/missing dependency → plan cannot be generated (error);
- contradictory composition → rejected in M12.2 composition before reaching this
  layer;
- invalid step input / non-task → TypeError / UnrealExecutionPlanError;
- unsupported mapping → remains blocked at compile (M12.1);
- ambiguous semantics → deterministic rejection;
- invalid provenance → plan construction error;
- unsupported execution capability → not present (all `inspect-only`).

## C++ interoperability

`canonical_json()` is language-neutral, sorted-key, compact. No C++ in M12.3.

## Blender relationship

Conceptually comparable to `AtlasTaskDefinition` step decomposition but expressed
as a semantic description. Generic structures (immutable frozen dataclasses,
deterministic serialization, fail-closed validation) are reused; Unreal-specific
semantics stay behind M12. Blender untouched.

## M12.4 relationship

M12.4 (future) will consume `UnrealExecutionPlan` and map approved semantic
operations onto the existing trusted Atlas runtime (task planner / submission /
recovery / evidence). M12.3 defines the interface (the plan contract) but does
NOT implement that adapter.

## Validation

- `pytest tests/m12/` → **296 passed** (incl. M12.3 + R5/R6 source-commitment & identity tests)
- `pytest -m "not integration"` → **1747 passed** (no regressions)

No live Unreal, no workflow/action-runner tests, no Blender, no M11, no M4-M10
change.

## What remains intentionally blocked

Render-bearing execution, live Unreal invocation, independent evidence
verification, and M12.4 runtime mapping.