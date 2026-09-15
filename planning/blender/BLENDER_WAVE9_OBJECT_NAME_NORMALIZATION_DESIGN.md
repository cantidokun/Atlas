# Atlas Blender Wave 9 — Object Name Normalization Design Gate

**Status:** DESIGN / NOT IMPLEMENTED  
**Branch:** `feat/blender-wave9-object-name-normalization`  
**Baseline:** Wave 8 unit metadata normalization merged to `main` at `f54c79cb5b95d7acf8a27f11c1a55ba0d0cecd9e`

## 1. Capability

Wave 9 introduces one narrow canonical-model correction:

`NORMALIZE_OBJECT_NAME`

It changes exactly one `ObjectModel.name` to an explicitly authorized target name. It does **not** infer a name, rename based on object role, rewrite identifiers, change hierarchy, alter collections, or mutate geometry/transforms.

## 2. Why this is the next bounded scope

The current validation profile can emit `OBJECT_NAME_INVALID` when an object name violates the profile naming regex. The current correction mapping classifies this as a heuristic correction and identifies `RENAME_OBJECT` as its correction type. Wave 9 deliberately does **not** inherit an inferred rename policy: the executable target name must be supplied explicitly by the caller and bound into the correction plan and authorization artifact.

The default soccer-field profile accepts lowercase alphanumeric names beginning with an alphanumeric character and continuing with `[a-z0-9._-]`.

## 3. Allowed mutation

For exactly one target object:

- preserve `object_id` unchanged;
- replace only `name` with the explicitly supplied `target_name`;
- preserve collection, parent, location, scale, rotation, visibility, mesh, scene metadata, and all other objects byte-for-byte at the canonical payload level.

No physical, topological, transform, hierarchy, or collection normalization is permitted.

## 4. Exact target contract

The plan parameters are exactly:

```text
expected_object_id
current_name
target_name
name_pattern
```

`target_name` is explicit input, never inferred.

The executor must reject:

- empty/non-string names;
- a target identical to the current name (`ALREADY_CANONICAL`);
- a target that does not satisfy the supplied exact naming pattern;
- a current-name mismatch;
- an object-id mismatch;
- a target name already used by another object in the scene;
- any extra/unknown parameter;
- stale or forged source-report digest;
- mismatched correction/plan/authorization bindings.

The pattern is data, not executable code. Regex compilation/execution is outside the canonical executor contract; the plan records the exact expected pattern string and the executor uses only the supported closed pattern grammar required by the Wave 9 tests.

## 5. Collision rule

Names must be unique within the canonical scene for this correction. A target name matching another object's current name is a hard refusal. The target object itself may retain its current name only for the already-canonical refusal path; there is no no-op success path.

## 6. Authorization boundary

The operation remains human-authorized and content-bound:

- `correction_id` binds the exact correction type, target object, current name, target name, and source report digest;
- `plan_id` binds the complete plan body;
- authorization must be `APPROVED`;
- authorization `correction_id`, `plan_id`, and `source_report_digest` must exactly match the plan.

Wave 9 does not extend the existing generic authorization artifact allowlist unless a dedicated Wave 9 authorization contract is separately designed and tested. The bounded executor therefore uses its own exact authorization shape, following the proven Wave 8 pattern.

## 7. Source freshness

Execution must call a supplied extractor and require the freshly extracted report digest to equal the plan's source digest. The executor must then verify that the expected object exists exactly once and still has the recorded `current_name`.

## 8. Postconditions

The executor must prove:

1. exactly one object's name changed;
2. that object's `object_id` is unchanged;
3. the target name matches exactly;
4. no other object changed;
5. no mesh, transform, parent, collection, visibility, scene unit, coordinate frame, or bounds changed;
6. the target name is unique in the resulting scene;
7. a deterministic output scene digest is returned.

The source scene remains immutable.

## 9. Explicit non-goals

Wave 9 does not:

- generate names from semantic roles;
- rename multiple objects in one operation;
- modify `object_id`;
- alter parent references;
- move objects between collections;
- normalize collection names;
- update Blender data directly;
- save/persist `.blend` files;
- create receipts or recovery logs;
- invoke workflows/action runners;
- weaken or modify M5, M12.5, or M11.

## 10. Validation gate

Before merge:

- deterministic unit tests for planning/execution and failure modes;
- adversarial tests for collision, stale digest, forged plan/authorization, duplicate object IDs, unusual regex strings, and non-target immutability;
- live Blender boundary probe using a disposable scene;
- full Wave 1–Wave 9 regression with workflow/action-runner tests excluded;
- final-head CI;
- independent red-team review.

## 11. Merge rule

Wave 9 may merge only when all gates above are green. A failed red-team finding blocks merge until addressed or explicitly scoped out in the design with evidence.
