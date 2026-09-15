# Atlas Blender Wave 8 — Unit Metadata Normalization Design Gate

**Status:** DESIGN / NOT IMPLEMENTED  
**Branch:** `feat/blender-wave8-unit-metadata-normalization`  
**Baseline:** Wave 7 duplicate-vertex removal merged to `main` at `623087b8b06838f9a47563ac83c926198c8ccf23`

## 1. Objective

Wave 8 adds one narrowly bounded metadata correction: canonicalize a scene unit token only when the current token is an explicit alias of the same physical unit.

The correction MUST NOT perform physical unit conversion. In particular, `INCHES -> METERS` is not a metadata normalization and must remain review-only. The operation changes only `SceneModel.unit_system`.

## 2. Canonical target

The canonical Atlas token for the supported profile is `METERS`.

Accepted aliases for this Wave are exact built-in strings whose case-insensitive value is one of:

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

The executor is canonical-model only. It must not call Blender, save files, persist state, recover state, create receipts, invoke workflow/action-runner authority, or modify object/mesh/transform state.

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

The executor MUST NOT accept `INCHES`, `FEET`, `CENTIMETERS`, or other physically distinct tokens as alias-equivalent.

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
- a fresh digest is not forged or substituted;
- no persistence/recovery/receipt/workflow action occurs.

If any postcondition fails, return structured failure.

## 8. Planner safety correction

The existing planner currently derives `target_unit == "METERS"` whenever that token appears in `allowed_units`. Wave 8 must tighten this path so that an automatic proposal is emitted only when the measured current token is one of the explicit meter aliases above.

For a physically different token such as `INCHES`, the planner must emit no executable normalization proposal and must surface the finding for review instead.

This is a safety requirement, not an implementation detail: metadata relabeling across physical unit systems would silently reinterpret geometry.

## 9. Adversarial coverage

At minimum:

- `METERS -> METERS` is not proposed as a correction;
- `meters -> METERS` normalizes;
- `m -> METERS` normalizes;
- mixed case aliases normalize only when the canonical alias rule is satisfied;
- `INCHES -> METERS` is refused;
- arbitrary target unit is refused;
- extra parameters are refused;
- stale source digest is refused;
- tampered plan id/correction id is refused;
- authorization without explicit approval is refused;
- unrelated object/mesh/transform mutation is refused;
- repeated execution is deterministic;
- source immutability holds.

Every hostile case must prove failure with no mutation.

## 10. Live Blender validation

A live gate should create a disposable scene whose Blender unit metadata is represented by the supported extraction boundary and verify:

- alias normalization changes only the canonical unit metadata;
- mesh geometry, transforms, object identity, and bounds are unchanged;
- no file open/save occurs.

A second fixture should use a physically different unit token and prove the live boundary refuses normalization rather than relabeling geometry.

## 11. C++ seam

The alias set, target token, plan identity, authorization contract, and output canonical representation must be reproducible without Blender-specific types.

## 12. Explicit non-goals

Wave 8 does NOT:

- convert coordinates between physical unit systems;
- rescale meshes or transforms;
- modify object hierarchy, collections, names, or origins;
- repair geometry/topology;
- infer an intended physical unit from geometry;
- add rollback, recovery, persistence, receipt, scheduler, or workflow authority.

## 13. Exit criteria

Wave 8 is complete only when:

1. this design gate is reviewed and frozen;
2. planner safety tightening is implemented;
3. deterministic canonical executor exists without `bpy`;
4. focused deterministic tests pass;
5. adversarial tests prove zero unauthorized mutation;
6. live Blender validation passes;
7. focused Wave 1–Wave 8 regression passes with workflow/action-runner tests excluded;
8. independent red-team review finds no blocker.