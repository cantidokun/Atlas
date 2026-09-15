# Atlas Blender Wave 11 — Empty-Mesh Canonical Contract Design Gate

**Status:** DESIGN / NOT IMPLEMENTED  
**Branch:** `feat/blender-wave11-empty-mesh-contract`  
**Baseline:** Wave 10 collection normalization merged to `main` at `d1c2a5a804ad801c67cc05d439bc6dc921ac8f4e`

## 1. Objective

Wave 11 is a canonical-model contract hardening wave, not a new scene-repair capability.

It resolves the deferred representation gap exposed by Wave 6: the current `MeshModel` contract requires non-empty `faces`, so a mesh containing only isolated vertices, including the all-isolated/zero-face case, cannot be represented faithfully even though Wave 6 explicitly requires that case to be tested.

Wave 11 must make the canonical representation truthful for:

- zero-face meshes with vertices;
- empty post-correction mesh topology when all faces have been removed by a future bounded capability;
- ordinary meshes with one or more faces;
- deterministic round-tripping without fabricating faces or silently dropping vertices.

## 2. Why this is the next bounded scope

Wave 6 explicitly names `all vertices isolated with zero faces` as a deterministic test case while also requiring the canonical result to remain language-neutral and truthful. The current `MeshModel` constructor rejects an empty `faces` tuple, creating a representation-level contradiction that should be resolved before introducing another topology mutation.

Wave 11 therefore repairs the contract seam rather than adding a higher-risk correction such as non-manifold repair, hole filling, origin movement, or transform reconstruction.

## 3. Allowed contract change

`MeshModel` may represent:

- non-empty `vertices` with zero faces;
- non-empty `vertices` with one or more faces;
- no fabricated placeholder face;
- no implicit deletion of vertices merely because the face set is empty.

The contract must remain immutable and canonical. Existing valid meshes must serialize identically before and after this change.

## 4. Exact semantic rules

1. `vertices` remains non-empty for a `MeshModel`.
2. `faces` becomes an allowed empty tuple.
3. Every existing face-index validation rule remains unchanged.
4. An empty face set means exactly “the mesh has no polygonal faces”; it does not imply missing geometry metadata or an invalid mesh by itself.
5. A zero-face mesh with vertices remains distinct from an absent mesh (`ObjectModel.mesh is None`).
6. No placeholder face may be synthesized.
7. Vertex order and values remain authoritative and deterministic.
8. Normals/UVs, when present under the existing representation rules, must remain consistent with the zero-face semantics; no per-face data may be fabricated.
9. Materials remain metadata and are not silently removed solely because the face set is empty.
10. Serialization, deserialization, hashing, and equality must preserve the distinction exactly.

## 5. Health-kernel implications

Wave 11 must separately establish the intended finding semantics for zero-face meshes.

It must not silently redefine existing health findings merely to make the new representation convenient. If zero-face meshes are structurally acceptable, the kernel must continue to emit no fabricated topology finding. If a profile needs to reject zero-face meshes, that must be an explicit profile policy rather than a constructor failure.

No new correction authority is introduced by this wave.

## 6. Adapter implications

The Blender adapter must be able to extract a zero-face mesh without manufacturing topology.

For a live Blender object with vertices and zero polygons:

- extracted vertices remain exact and ordered under the existing adapter contract;
- extracted `faces` is `()`;
- object identity/name/collection/transform remain unchanged;
- no save/persistence is performed by the boundary probe.

Any Blender-specific limitation must remain in the adapter and must not leak into the canonical model.

## 7. Non-goals

Wave 11 does not:

- remove isolated vertices;
- remove duplicate vertices;
- repair non-manifold edges;
- fill holes;
- create faces;
- infer topology;
- alter transforms or origins;
- modify collections, object names, or hierarchy;
- add persistence, recovery, receipts, workflow, or action-runner authority;
- modify M5, M12.5, or M11.

## 8. Validation gate

Before merge:

- deterministic canonical-model tests for zero-face construction, serialization, digest stability, equality, and round-trip;
- regression proving all existing non-empty-face meshes remain byte/canonical-equivalent;
- Wave 6 regression re-enabled for the all-isolated/zero-face case without weakening any safety condition;
- live Blender disposable-scene extraction of a zero-face mesh;
- full focused Wave 1–Wave 11 regression with workflow/action-runner tests excluded;
- final-head CI on supported Python versions;
- independent red-team review focused on accidental semantic broadening and hidden topology fabrication.

## 9. Merge rule

Wave 11 may merge only when every validation gate is green. A representation-level failure must block merge rather than being masked by changing tests or by silently coercing the mesh into a different topology.

## 10. C++ seam

The resulting zero-face `MeshModel` must remain language-neutral. A future C++ implementation must be able to construct, serialize, hash, compare, and reproduce the same canonical representation without Blender-specific types.
