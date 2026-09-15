# Atlas Blender Wave 8 — Unit Metadata Normalization Design Gate

**Status:** IMPLEMENTED / VALIDATION COMPLETE  
**Branch:** `feat/blender-wave8-unit-metadata-normalization`  
**Baseline:** Wave 7 duplicate-vertex removal merged to `main` at `623087b8b06838f9a47563ac83c926198c8ccf23`

## 1. Objective

Wave 8 adds one narrowly bounded metadata correction: canonicalize a scene unit token only when the current token is an explicit alias of the same physical unit.

The correction MUST NOT perform physical unit conversion. In particular, `INCHES -> METERS` is not a metadata normalization and must remain review-only. The operation changes only `SceneModel.unit_system`.

## 2. Canonical target

The canonical Atlas token for the supported profile is `METERS`.

Accepted aliases for this Wave are exact built-in strings whose value is one of:

- `METERS`
- `meters`
- `m`

Only these aliases may be normalized to `METERS`. Unknown tokens and physically different units fail closed.

## 3. Authority boundary

```text
SceneReport finding SCENE_UNIT_INVALID
        |
        v
alias-only target derivation
        |
        v
explicit authorization
        |
        v
Wave 8 deterministic executor
        |
        v
new canonical SceneModel
```

The executor is canonical-model only. It does not call Blender, save files, persist state, recover state, create receipts, invoke workflow/action-runner authority, or modify object/mesh/transform state.

## 4. Exact correction contract

Correction type:

`NORMALIZE_UNIT_METADATA`

Closed parameter set:

- `current_unit`
- `target_unit`

The authorized target MUST be exactly `METERS`. The authorized current token MUST be an alias-equivalent member of the same canonical unit family. No arbitrary target token is accepted.

## 5. Preconditions

Fail closed unless all are true:

1. correction type is exactly `NORMALIZE_UNIT_METADATA`;
2. authorization binds to correction id, plan id, and source digest;
3. plan parameters contain exactly `current_unit` and `target_unit`;
4. `current_unit` equals the fresh source `SceneModel.unit_system` exactly;
5. `current_unit` is one of the approved meter aliases;
6. `target_unit == "METERS"`;
7. source digest is unchanged;
8. no unrelated scene state changed before mutation.

The executor does not accept `INCHES`, `FEET`, `CENTIMETERS`, or other physically distinct tokens as alias-equivalent.

## 6. Mutation semantics

Create a new immutable `SceneModel` that differs from the source only in `unit_system`.

Preserve exactly:

- `scene_id`
- object count/order/identity and every `ObjectModel` field
- every mesh, vertex, face, normal, UV, material, and local frame
- coordinate frame
- world bounds

No coordinate scaling, transform baking, geometry remapping, topology change, or object reordering is permitted.

## 7. Postconditions

After execution:

- `unit_system == "METERS"`;
- every non-unit scene field is byte-equivalent under canonical serialization;
- the source `SceneModel` remains immutable;
- a fresh output digest is computed from the returned canonical scene;
- no persistence/recovery/receipt/workflow action occurs.

If any postcondition fails, return structured failure.

## 8. Planner safety correction

The existing planner keeps `SCENE_UNIT_INVALID` review-only instead of fabricating an executable normalization target. Wave 8 therefore preserves that safety boundary while providing the separate explicitly-authorized alias-only executor.

For a physically different token such as `INCHES`, no executable normalization proposal is emitted by the planner and the finding remains review-required.

The dedicated executor accepts only the explicit aliases listed in §2 and is intentionally stricter than the broader Blender-side `is_meters_like` helper, which recognizes additional meters-family spellings for validation/mapping purposes. Wave 8 does not inherit those broader aliases because metadata normalization must be an explicit contract, not a generalized string canonicalizer.

## 9. Adversarial coverage

The implementation covers:

- alias normalization from `meters` and `m` to `METERS`;
- canonical `METERS` no-op rejection;
- `INCHES -> METERS` refusal;
- arbitrary target refusal;
- extra parameter refusal;
- stale source digest refusal;
- tampered authorization refusal;
- repeated deterministic execution;
- source immutability;
- preservation of objects, transforms, meshes, coordinate frame, and world bounds.

Every hostile case is required to fail without source mutation.

## 10. Live Blender validation

The disposable Blender live gate verifies:

- canonical meters metadata is visible at the Blender boundary;
- mesh geometry is preserved;
- object location, scale, and rotation are preserved;
- filepath remains unchanged;
- no save is attempted;
- a genuine `IMPERIAL + INCHES` boundary remains physically distinct.

The live probe does not perform a physical unit conversion or silently relabel geometry.

## 11. C++ seam

The alias set, target token, plan identity, authorization contract, and output canonical representation are reproducible without Blender-specific types.

## 12. Explicit non-goals

Wave 8 does NOT:

- convert coordinates between physical unit systems;
- rescale meshes or transforms;
- modify object hierarchy, collections, names, or origins;
- repair geometry/topology;
- infer an intended physical unit from geometry;
- add rollback, recovery, persistence, receipt, scheduler, or workflow authority.

## 13. Validation record

Focused Wave 8 deterministic/adversarial + live Blender validation: **10 passed** on the supported Blender installation.

The live Blender boundary initially exposed a gate-aggregation defect in the probe itself; the probe was corrected so the negative `save_attempted=False` assertion is checked independently of the positive aggregate. A second hardening step requires the physical-unit distinction fixture to set both Blender's coarse system and precise length token (`IMPERIAL` + `INCHES`).

CI had already passed on a prior Wave 8 head; the corrected probe and frozen documentation are the final local validation inputs for the final CI run.

## 14. Exit criteria

Wave 8 is complete only when:

1. this design gate is reviewed and frozen;
2. planner safety boundary remains fail-closed;
3. deterministic canonical executor exists without `bpy`;
4. focused deterministic tests pass;
5. adversarial tests prove zero unauthorized mutation;
6. live Blender validation passes;
7. focused Wave 1–Wave 8 regression passes with workflow/action-runner tests excluded;
8. independent red-team review finds no blocker.