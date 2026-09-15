# Atlas Blender Wave 7 — Duplicate Vertex Removal Design Gate

**Status:** DESIGN / NOT IMPLEMENTED  
**Branch:** `feat/blender-wave7-duplicate-vertex-removal`  
**Baseline:** Wave 6 isolated-vertex removal merged to `main` at `c4fb8d3681e4ea02387ce6ca7b366d929c7bbd5c`

## 1. Objective

Wave 7 proposes the next narrowly bounded topology-informed mesh correction: deterministic removal of **exact duplicate vertices** whose canonical coordinates are identical.

This is intentionally narrower than generic vertex merging. Wave 7 must not use spatial tolerances, nearest-neighbor clustering, smoothing, welding heuristics, or semantic inference.

The correction may only collapse vertices that are exactly equal at the canonical representation level and whose collapse cannot create a face with duplicate vertex indices or a duplicate face image.

## 2. Authority boundary

```text
canonical MeshModel
       |
       v
Wave 5 topology / mesh-health facts
       |
       v
exact-duplicate vertex proposal
       |
       v
explicit authorization
       |
       v
Wave 7 deterministic executor
       |
       v
new canonical MeshModel
```

Wave 7 execution authority exists only in the dedicated correction executor for the exact contract defined here.

The analyzer remains analysis-only. A proposal is not authorization. The canonical executor must not call Blender, save files, persist state, recover state, create receipts, or invoke unrelated correction capabilities.

## 3. Exact correction contract

Correction type:

`REMOVE_DUPLICATE_VERTICES`

Closed parameter set:

- `expected_duplicate_vertex_groups`

Each group is a sorted sequence of at least two vertex indices. Groups are pairwise disjoint and sorted lexicographically. Within each group all coordinates must be exactly equal at the canonical representation level. The minimum original index is the sole survivor.

The authorized groups must equal the **complete current exact-duplicate partition** for the target mesh. Singleton coordinate classes are omitted; every class with cardinality >= 2 must appear exactly once.

## 4. Safety rule: topology-collision prohibition

Reject any duplicate group if a face references two or more members of that group. Collapsing such a face would alter face corner identity and manufacture a repeated vertex index.

Also reject any authorization if deterministic face remapping would cause two distinct source faces to become the same ordered vertex-index tuple. This is a **face-image collision**: the operation would manufacture a duplicate face even though no single face contains two members of the same duplicate group.

Wave 7 must fail closed rather than perform secondary topology repair for either collision class.

The planner should reject collision-producing duplicate groups before emitting an executable plan. The executor must re-check the collision predicates against fresh canonical state before constructing the output.

The postcondition layer must additionally verify that no new duplicate face, degenerate face, or non-manifold condition is introduced by the remap. A postcondition failure is structured failure, never an implicit secondary repair.

## 5. Preconditions

The executor must fail closed unless all are true:

1. correction type is exactly `REMOVE_DUPLICATE_VERTICES`;
2. authorization binds to the exact correction, plan, and source digest;
3. target object and mesh identity match the authorized plan;
4. every duplicate group is structurally valid: sorted, unique, disjoint, and contains at least two indices;
5. every index is an exact integer within the vertex range;
6. all vertices within a group have exactly equal canonical coordinates;
7. the complete current duplicate grouping equals the authorized grouping;
8. no face references multiple members of a proposed group;
9. deterministic face remapping produces no duplicate face image;
10. no face index is malformed or out of range;
11. source digest still matches;
12. no unrelated state changes before mutation.

The executor must reject a stale plan if vertex coordinates or face topology changed since planning.

## 6. Deterministic grouping

Grouping is based only on canonical vertex coordinates:

```text
key(v_i) = canonical coordinate tuple
```

Vertices with identical keys form one duplicate group. Groups of one are ignored.

Each group is sorted ascending. The group list is sorted lexicographically by its full index tuple. The minimum original index is the deterministic survivor.

No floating-point tolerance is permitted in Wave 7.

## 7. Mutation semantics

Given original vertex sequence `V[0..n-1]`:

- retain the minimum index from each duplicate group;
- remove every other member;
- retain all non-duplicate vertices;
- preserve survivor order according to original indices;
- deterministically remap every face through the survivor mapping;
- preserve face order and face cardinality;
- preserve survivor coordinate values exactly at the canonical representation level;
- preserve normals, UVs, materials, local frame, transforms, hierarchy, collections, and unrelated objects;
- preserve object identity/order/count;
- retain the target mesh's canonical `mesh_id` unless a future contract explicitly requires replacement identity semantics.

No other topology operation is allowed.

## 8. Postconditions

After execution:

- every authorized duplicate group has exactly one survivor;
- no exact duplicate coordinate groups remain;
- every original face remains in the same order and with the same number of corners;
- no face has repeated vertex indices;
- no two output faces share the same ordered vertex-index tuple;
- every face's vertex sequence equals the deterministic source remap;
- survivor coordinates are unchanged;
- target and unrelated object state are unchanged;
- no new duplicate, degenerate, winding, or non-manifold condition is introduced by the remap;
- the source canonical scene remains immutable;
- no save/persistence/recovery/receipt action occurs.

If any postcondition fails, return structured failure. Do not attempt secondary repair.

## 9. Adversarial test plan

At minimum cover:

- partial duplicate-group authorization;
- extra unauthorized group;
- duplicate indices inside a group;
- unsorted groups;
- overlapping groups;
- singleton groups;
- booleans, negative, and out-of-range indices;
- coordinates differing by one representable unit;
- malformed coordinates where canonical construction permits malformed input;
- stale source digest;
- changed coordinates after planning;
- changed face topology after planning;
- malformed face indices;
- face containing two vertices from the same duplicate group;
- two distinct source faces collapsing to the same output face;
- tampered correction id;
- tampered plan id;
- extra plan parameters;
- hostile authorization;
- mutable aliasing;
- repeated deterministic execution;
- source immutability;
- forged extractor digest;
- unauthorized mutation before validation completes.

Every hostile case must prove failure with no mutation.

## 10. Live Blender validation

The live gate must use the supported Blender executable and a disposable in-memory scene containing:

- at least one exact duplicate vertex pair;
- a face set that remains semantically unchanged after the collapse;
- a non-trivial object transform;
- at least one unrelated object;
- no file opened or saved.

The live probe must independently verify:

- exact duplicate detection;
- deterministic survivor coordinate preservation;
- exact face semantics after remap;
- target object identity preservation;
- transform preservation;
- unrelated object preservation;
- no file-path mutation or save attempt.

A second live fixture must exercise a collision-producing duplicate scenario and prove that the live validation boundary rejects the proposed collapse rather than silently repairing the resulting duplicate/degenerate face.

If Blender's direct mesh operation has identity or ordering behavior that cannot be guaranteed, the limitation must be documented rather than hidden.

## 11. Deterministic test plan

Required cases:

- one duplicate pair with low-index survivor;
- duplicate groups in the middle and at the end;
- multiple duplicate groups;
- no duplicates;
- groups separated by unrelated vertices;
- remap of faces referencing later survivors;
- collision-producing face rejection;
- distinct faces collapsing to the same output face rejection;
- deterministic plan identity;
- deterministic output identity;
- canonical serialization round-trip;
- source immutability;
- repeated execution.

## 12. Complexity target

The correction should remain `O(V + face-corners)` using canonical coordinate hashing, face collision scanning, deterministic remap, and no spatial/quadratic proximity search.

## 13. C++ seam

The grouping key, authorization parameters, survivor rule, collision rule, index remap, and canonical output must be reproducible without Blender-specific types.

## 14. Explicit non-goals

Wave 7 does **not**:

- merge merely nearby vertices;
- merge vertices with different coordinates;
- repair arbitrary duplicate/degenerate faces;
- change face topology except index renumbering caused by the exact duplicate collapse;
- change winding;
- remove isolated vertices (Wave 6 authority already covers that);
- repair non-manifold topology;
- normalize normals or UVs;
- invoke generic vertex merge tools;
- invoke Blender operators as canonical mutation authority;
- introduce rollback, recovery, scheduler, receipt, persistence, or workflow authority.

## 15. Exit criteria

Wave 7 is complete only when:

1. this design gate is reviewed and frozen;
2. deterministic implementation exists without `bpy` dependency;
3. focused deterministic tests pass;
4. adversarial tests prove zero unauthorized mutation;
5. live Blender validation passes;
6. focused Wave 1–Wave 7 Blender regression passes with workflow/action-runner tests excluded;
7. independent red-team review finds no blocker;
8. all extraction/identity limitations are documented;
9. only then is the capability merged into `main`.

Wave 7 must not expand into generic vertex welding under the name of duplicate-vertex removal.
