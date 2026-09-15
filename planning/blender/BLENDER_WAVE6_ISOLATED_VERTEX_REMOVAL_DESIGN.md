# Atlas Blender Wave 6 — Isolated Vertex Removal Design Gate

**Status:** DESIGN / NOT IMPLEMENTED  
**Branch:** `feat/blender-wave6-correction-scope`  
**Baseline:** Wave 5 topology intelligence merged to `main` at `16065f43abdd6daf9d3758ac921559e52c07703f`

## 1. Objective

Wave 6 introduces the smallest topology-informed mesh mutation following Wave 5: deterministic removal of **isolated vertices** that are not referenced by any face.

The capability is deliberately narrower than general mesh cleanup. It must not weld vertices, alter faces semantically, repair topology, fill holes, modify normals/UVs/materials, or infer that any other unused or unusual geometry is defective.

The purpose is to establish a tightly bounded mutation pattern driven by an already-defined Wave 5 structural fact.

## 2. Authority boundary

```text
canonical MeshModel
       |
       v
Wave 5 topology analysis
       |
       v
isolated-vertex correction proposal
       |
       v
explicit authorization
       |
       v
Wave 6 deterministic executor
       |
       v
new canonical MeshModel
```

Wave 6 execution authority exists only in the dedicated correction executor and only for the exact correction contract defined here.

The analyzer remains analysis-only. Models remain advisory. A proposal is not authorization. The executor must not call Blender, save files, or perform persistence/recovery.

## 3. Exact correction contract

Correction type:

`REMOVE_ISOLATED_VERTICES`

Closed parameter set:

- `expected_isolated_vertex_indices`

The proposed indices must be sorted, unique, non-negative integers and must exactly describe the isolated vertices observed in the source report.

The correction is all-or-nothing. There is no partial removal, automatic selection, threshold, tolerance, or inferred subset.

## 4. Why this capability is next

Wave 5 already exposes `isolated_vertex_count` and deterministic component membership. It explicitly treats isolated vertices as structural facts rather than automatically blocking readiness.

Wave 6 converts only that narrowly defined fact into a mutation, with explicit authorization and postcondition verification.

This avoids prematurely introducing higher-risk topology reconstruction such as hole filling, edge stitching, non-manifold repair, remeshing, or triangulation.

## 5. Preconditions

The executor must fail closed unless all are true:

1. correction type is exactly `REMOVE_ISOLATED_VERTICES`;
2. authorization binds to the exact correction/plan/source digest;
3. source `MeshModel` identity and digest match the authorized plan;
4. every expected isolated index exists;
5. every expected isolated index is currently unreferenced by every face;
6. the complete set of currently isolated vertices equals the authorized set;
7. no face contains an invalid vertex index;
8. no unrelated mesh/object state is changed before mutation.

A stale plan must be rejected if topology has changed since planning.

## 6. Mutation semantics

Given vertices `V[0..n-1]` and faces referencing those indices:

- preserve every referenced vertex in its original relative order;
- remove only the authorized isolated vertices;
- deterministically remap surviving vertex indices downward;
- preserve every face's vertex sequence exactly after applying the deterministic index remap;
- preserve face order;
- preserve object identity and all non-mesh object fields;
- preserve mesh identity only if the canonical mutation contract can truthfully do so; otherwise the replacement identity must be explicitly represented and verified rather than hidden;
- preserve all vertex coordinate values bit-for-bit at the canonical representation level;
- do not modify normals, UVs, materials, transforms, hierarchy, collections, or unrelated objects.

No geometry optimization beyond removal of truly isolated vertices is permitted.

## 7. Postconditions

After execution and fresh re-extraction/revalidation:

- `isolated_vertex_count == 0`;
- no removed vertex remains;
- surviving vertices occur in original order;
- every original face remains present in the same order and has the same cardinality;
- every face's vertex sequence maps exactly through the authorized remap;
- referenced vertex coordinates are unchanged;
- object identity/count/order is unchanged;
- unrelated objects are unchanged;
- no new invalid, duplicate, degenerate, winding, or non-manifold condition is introduced by the index remap;
- source/plan/authorization binding remains satisfied;
- no save or persistence operation occurs.

If any postcondition fails, execution must report failure rather than silently repair further.

## 8. Safety boundary

Wave 6 must **not**:

- remove vertices referenced by a face;
- remove boundary/non-manifold topology;
- remove loose edges (not represented by the canonical model);
- weld coincident vertices;
- merge nearby vertices;
- reorder vertices for optimization;
- triangulate or retriangulate faces;
- change face winding;
- alter normals or UVs;
- modify materials;
- alter transforms, parents, collections, or hierarchy;
- invoke Blender operators;
- save or overwrite a `.blend` file;
- introduce rollback/recovery/receipt authority.

## 9. Canonical remap

For old vertex indices `0..n-1`, define:

```text
removed = authorized isolated indices
survivors = [i for i in range(n) if i not in removed]
new_index(i) = position of i in survivors
```

The remap must be deterministic and derived only from the ordered source vertex list and authorized removal set.

The executor must reject an authorization whose expected isolated set is not exactly the current isolated set. This prevents a caller from using the capability as an arbitrary vertex-deletion primitive.

## 10. Adversarial test plan

At minimum, hostile cases must cover:

- deleting a referenced vertex;
- deleting only part of the isolated set;
- adding an unauthorized isolated index;
- duplicate indices in authorization;
- unsorted authorization;
- negative indices;
- boolean indices;
- stale source digest;
- changed vertex coordinates;
- changed face ordering;
- changed face indices;
- changed mesh/object identity;
- malformed faces;
- duplicate/degenerate/winding/non-manifold regressions;
- attempts to smuggle extra parameters;
- mutable aliasing through plan/authorization structures;
- repeated execution;
- forged post-mutation state;
- unauthorized mutation before validation completes.

Every hostile case must prove failure with no mutation.

## 11. Live Blender validation

The live gate must use the actual supported Blender executable and a disposable in-memory scene containing:

- a mesh with at least one isolated vertex;
- at least one face using multiple surviving vertices;
- non-trivial coordinates/transforms sufficient to prove preservation;
- an independent unrelated object.

The gate must independently inspect Blender's source mesh before and after the correction and prove:

- isolated vertex removal only;
- exact surviving vertex/face semantics;
- object preservation;
- no unrelated-object mutation;
- no save attempt;
- no file-path mutation.

If the Blender adapter cannot faithfully represent an aspect of the mutation, that limitation must be documented rather than silently widening Wave 6.

## 12. Deterministic test plan

Required cases:

- one isolated vertex;
- multiple isolated vertices at beginning/middle/end;
- no isolated vertices;
- all vertices isolated with zero faces;
- mixed triangles/quads/n-gons;
- deterministic remap;
- empty removal rejection;
- invalid authorization rejection;
- canonical round-trip;
- source immutability;
- postcondition verification;
- repeated deterministic execution from identical input.

## 13. Complexity target

The correction must remain linear in canonical mesh size:

- isolated-set validation: `O(V + face-corners)`;
- remap construction: `O(V)`;
- face remap: `O(face-corners)`;
- memory: `O(V + face-corners)`.

No quadratic nearest-neighbor or geometric clustering operation is permitted.

## 14. C++ seam

The correction contract must remain language-neutral. The canonical input, authorization parameters, remap semantics, and resulting `MeshModel` must be reproducible by a future C++ implementation without Blender-specific types.

## 15. Exit criteria

Wave 6 is complete only when:

1. this contract is frozen;
2. deterministic implementation exists without `bpy` dependency;
3. deterministic tests pass;
4. adversarial tests pass with zero unauthorized mutation;
5. live Blender validation passes;
6. focused Wave 1–Wave 6 regression passes;
7. an independent red-team review finds no blocker;
8. documentation records any extraction/identity limitations;
9. the capability is merged only after the independent gate clears.

Wave 6 must not expand into general topology repair under the name of isolated-vertex removal.
