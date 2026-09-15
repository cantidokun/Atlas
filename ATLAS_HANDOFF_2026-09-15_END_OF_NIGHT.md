# Atlas End-of-Night Handoff — September 15, 2026

## Repository baseline

- `main` includes Wave 10 merge commit `d1c2a5a804ad801c67cc05d439bc6dc921ac8f4e`.
- Wave 10 PR #100 is merged and closed.
- M5, M12.5, and the frozen M11 development-model work remain untouched.
- Do not run workflow/action-runner tests unless explicitly authorized.

## Blender correction waves

Waves 1–10 are treated as the current completed Blender correction/analysis baseline.

Wave 10 (`NORMALIZE_OBJECT_COLLECTION`) is complete. Its contract changes exactly one `ObjectModel.collection` to an explicitly authorized target; it does not infer destinations, mutate geometry/transforms/hierarchy, persist `.blend` files, or add workflow/receipt/recovery authority.

The Wave 10 validation gate was satisfied before merge: deterministic/adversarial validation, live Blender boundary validation, focused Wave 1–Wave 10 regression with workflow/action-runner tests excluded, CI, and independent red-team review.

## Wave 11 — next resume point

Active branch:

`feat/blender-wave11-empty-mesh-contract`

Status:

**DESIGN / NOT IMPLEMENTED**

Design:

`planning/blender/BLENDER_WAVE11_EMPTY_MESH_CONTRACT_DESIGN.md`

Wave 11 is a canonical-model contract hardening wave, not a new scene-repair capability.

The deferred seam is that `MeshModel` currently requires non-empty `faces`, while Wave 6 explicitly requires the all-isolated/zero-face case. The current live Blender extraction layer also rejects meshes with no polygon faces. Wave 11 must make a zero-face mesh with vertices representable and extractable without fabricating topology or silently dropping vertices.

Required semantic boundary:

- `vertices` remains non-empty;
- `faces == ()` becomes valid;
- no placeholder face is synthesized;
- existing face/index validation remains intact;
- zero-face mesh remains distinct from `ObjectModel.mesh is None`;
- normals/UVs remain absent unless truthfully representable under the existing contract;
- materials remain metadata;
- serialization, equality, hashing, and digests preserve the distinction exactly;
- no correction/execution/persistence/recovery/receipt/workflow authority is introduced.

## Wave 11 validation gate

Do not merge until all of the following are green:

1. deterministic canonical-model tests for zero-face construction, parsing, serialization, equality, digest stability, and round-trip;
2. regression proving ordinary non-empty meshes remain canonical-equivalent;
3. Wave 6 all-isolated/zero-face coverage is re-enabled without weakening safety conditions;
4. live Blender disposable-scene extraction proves vertices with zero polygons round-trip as `faces == ()`;
5. focused Wave 1–Wave 11 regression with workflow/action-runner tests excluded;
6. final-head CI on supported Python versions;
7. independent red-team review for hidden topology fabrication or semantic broadening.

A representation failure blocks merge. Do not coerce the mesh into a different topology just to satisfy tests.

## Known contract facts to preserve

The canonical model and extraction boundary are intentionally language-agnostic. Blender-specific limitations belong in the adapter, not the canonical representation. The C++ seam remains the canonical JSON/value contract.

Historical handoff files remain archival. This file is the current September 15 session resume note for the Blender work.
