# Atlas Blender Wave 11 — Empty-Mesh Canonical Contract Design Gate

**Status:** VALIDATION COMPLETE / READY TO MERGE  
**Branch:** `feat/blender-wave11-empty-mesh-contract`  
**Baseline:** Wave 10 collection normalization merged to `main` at `d1c2a5a804ad801c67cc05d439bc6dc921ac8f4e`

## 1. Objective

Wave 11 is a canonical-model contract hardening wave, not a new scene-repair capability.

It resolves the deferred representation gap exposed by Wave 6: the canonical `MeshModel` contract could not faithfully represent the result of removing every isolated vertex from an all-isolated mesh. Wave 6 explicitly requires that case in its deterministic test plan.

Wave 11 establishes one truthful closed-topology representation boundary:

- vertices present, faces present — ordinary mesh;
- vertices present, faces empty — a real vertex-only/zero-polygon mesh;
- vertices empty, faces empty — the exact canonical result of removing every vertex from an all-isolated mesh;
- vertices empty, faces present — invalid and rejected.

## 2. Exact semantic rules

1. `MeshModel.vertices` and `MeshModel.faces` remain immutable tuples.
2. `faces == ()` is valid.
3. `vertices == ()` is valid only when `faces == ()`.
4. A non-empty face set still requires valid integer indices into the vertex tuple.
5. No placeholder face is synthesized.
6. No vertex is fabricated or silently reintroduced merely because the face set is empty.
7. `MeshModel(vertices=(), faces=())` is distinct from `ObjectModel.mesh is None`.
8. Per-face normals and UVs remain cardinality-bound to the face set; they therefore must be empty when `faces == ()`.
9. Materials and `local_frame_id` remain metadata and are not silently discarded solely because topology is empty.
10. Serialization, parsing, equality, and scene-input digests must preserve the two zero-face states exactly.

## 3. Wave 6 relationship

Wave 6 continues to require a non-empty authorized isolated-vertex set. For an all-isolated source with `N > 0` vertices and zero faces, the authorized set is exactly `[0..N-1]`; execution removes those vertices and deterministically produces `MeshModel(vertices=(), faces=())`.

An empty authorization set remains rejected so Wave 6 cannot become a no-op deletion primitive.

## 4. Adapter boundary

The live Blender extractor must truthfully emit a mesh with vertices and zero polygons as `faces == []` / canonical `faces == ()`.

The live extraction boundary continues to fail closed for a Blender mesh with zero vertices. That is a source-extraction boundary, not a canonical-result restriction: the zero-vertex canonical state is produced only by a bounded canonical mutation such as Wave 6.

No Blender mutation, persistence, save, receipt, recovery, workflow, or action-runner authority is introduced by Wave 11.

## 5. Health-kernel semantics

Zero-face meshes must not cause fabricated topology findings. Existing face-based checks simply have no faces to inspect. A profile may independently choose to treat a zero-face scene as unsuitable for a production role, but the canonical constructor must not encode that policy as a representation failure.

## 6. Non-goals

Wave 11 does not:

- remove isolated vertices;
- remove duplicate vertices;
- repair non-manifold edges;
- fill holes;
- create or infer faces;
- alter transforms, origins, collections, names, or hierarchy;
- add execution authorization or persistence authority;
- modify M5, M12.5, or frozen M11.

## 7. Validation gate

Validation completed on the final branch head:

- Wave 11 live Blender disposable-scene gate: **1 passed**;
- focused Wave 6 + Wave 11 + scene-report regression: **43 passed**;
- deterministic Wave 1–Wave 11 regression with workflow/action-runner tests excluded: **3570 passed, 27 skipped, 6 deselected**;
- current-head CI run **1855: success**;
- independent red-team review: **CLEAR / NO BLOCKER**.

The full local suite with `ATLAS_RUN_LIVE_BLENDER=1` also exposed three pre-existing/legacy live gates that could not locate Blender because neither `blender` nor `ATLAS_BLENDER_EXECUTABLE` was available in the shell environment. Those failures were environmental and unrelated to the Wave 11 dedicated gate. The deterministic regression was therefore rerun with live Blender disabled and completed successfully as recorded above.

A representation failure blocks merge. No test was weakened to accommodate an incorrect topology state.

## 8. C++ seam

The resulting empty/zero-face states remain language-neutral canonical values. A future C++ implementation must be able to construct, serialize, hash, compare, and reproduce the same representations without Blender-specific types.
