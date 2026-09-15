# Atlas Blender Wave 10 — Object Collection Normalization Design Gate

**Status:** IMPLEMENTATION / VALIDATION IN PROGRESS  
**Branch:** `feat/blender-wave10-collection-normalization`  
**Baseline:** Wave 9 object-name normalization merged to `main` at `4834a94ee72ece965682430f465ce1ff16233427`

## 1. Capability

Wave 10 introduces one narrow canonical-model correction:

`NORMALIZE_OBJECT_COLLECTION`

It changes exactly one `ObjectModel.collection` value to an explicitly authorized target collection. It does **not** infer a collection, create/delete collections, rename collections, alter hierarchy, change object IDs/names/transforms, mutate geometry, or modify any other object.

## 2. Why this is the next bounded scope

The current health profile can emit `OBJECT_COLLECTION_INVALID` when an object's collection is outside the profile's explicit `allowed_collections` set. The existing correction mapping correctly classifies this finding as `REQUIRES_REVIEW` because the intended destination is ambiguous.

Wave 10 removes that ambiguity only by requiring the destination collection to be supplied explicitly by the authorized caller. The executor must never choose the first, default, nearest, semantic, or otherwise inferred collection.

The canonical model already represents the object's collection as one optional string, so this wave can remain a field-local correction with no new collection graph semantics.

## 3. Allowed mutation

For exactly one target object:

- preserve `object_id` unchanged;
- preserve `name`, parent, location, scale, rotation, visibility, mesh, and all scene metadata unchanged;
- replace only `collection` with the explicitly supplied `target_collection` string.

The target collection must be an allowed collection in the supplied execution profile. No collection creation or deletion is permitted.

## 4. Exact target contract

The plan parameters are exactly:

```text
expected_object_id
current_collection
target_collection
allowed_collections
```

`target_collection` is explicit input, never inferred.

The executor must reject:

- missing/non-string current collection;
- empty/non-string target collections;
- a target identical to the current collection (`ALREADY_CANONICAL`);
- a target not present in the exact supplied `allowed_collections` set;
- a current-collection mismatch;
- an object-id mismatch;
- a target collection mismatch against the authorization artifact;
- duplicate/ambiguous object IDs in the source scene;
- any extra/unknown parameter;
- stale or forged source-report digest;
- mismatched correction/plan/authorization bindings.

`allowed_collections` is data, not executable code. The executor treats it as a canonical exact string set and does not consult external Blender collection state.

## 5. Collection policy

The target must be one of the exact `allowed_collections` recorded in the plan. The executor must not broaden, normalize, case-fold, trim, or otherwise reinterpret collection names.

A target that exists in Blender but is absent from the authorized profile remains invalid.

The target object may retain its current collection only through the explicit already-canonical refusal path; there is no no-op success path.

## 6. Authorization boundary

The operation remains human-authorized and content-bound:

- `correction_id` binds the exact correction type, target object, current collection, target collection, allowed-collection set, and source report digest;
- `plan_id` binds the complete plan body;
- authorization must be `APPROVED`;
- authorization `correction_id`, `plan_id`, and `source_report_digest` must exactly match the plan;
- the authorization object must use an exact closed schema with no ignored extra keys.

Wave 10 does not broaden the generic authorization contract implicitly. The bounded executor uses a dedicated exact authorization shape following the proven Wave 8/9 pattern.

## 7. Source freshness

Execution must call a supplied extractor and require the freshly extracted report digest to equal the plan's source digest.

The supplied extractor result is untrusted input: the canonical executor independently recomputes the digest from the extracted `SceneModel` rather than treating a caller-supplied digest field as authoritative.

## 8. Postconditions

The executor must prove:

1. exactly one object's collection field changed;
2. that object's `object_id` is unchanged;
3. the resulting collection equals `target_collection` exactly;
4. the target collection belongs to the authorized `allowed_collections` set;
5. no other object changed;
6. no name, parent, transform, visibility, mesh, unit metadata, coordinate frame, or bounds changed;
7. the source scene remains immutable;
8. a deterministic output scene digest is returned.

## 9. Explicit non-goals

Wave 10 does not:

- infer semantic collection assignment;
- create, rename, merge, or delete Blender collections;
- move multiple objects in one operation;
- modify `object_id` or object `name`;
- alter parent references;
- alter geometry, materials, UVs, normals, or transforms;
- update Blender data directly in the canonical executor;
- save/persist `.blend` files;
- create receipts or recovery logs;
- invoke workflows/action runners;
- automatically resolve `OBJECT_COLLECTION_INVALID` findings without an explicit authorized target;
- modify the meaning of M5, M12.5, or M11.

## 10. Validation gate

Before merge:

- deterministic unit tests for planning/execution and failure modes;
- adversarial tests for unauthorized target collections, already-canonical refusal, stale/forged digest, forged plan/authorization, duplicate object IDs, non-target immutability, extra authorization keys, and source/report mismatch;
- live Blender boundary probe using a disposable scene that proves the narrow collection mutation primitive without granting broader collection authority;
- full Wave 1–Wave 10 regression with workflow/action-runner tests excluded;
- final-head CI;
- independent red-team review.

## 11. Merge rule

Wave 10 may merge only when every gate above is green. A failed red-team finding blocks merge until addressed or explicitly scoped out in this design with evidence.
