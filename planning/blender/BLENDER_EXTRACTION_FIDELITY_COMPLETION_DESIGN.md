# Atlas Blender — Extraction Fidelity Completion Design Gate

**Status:** DESIGN ONLY — NO IMPLEMENTATION  
**Track:** Blender canonical extraction  
**Baseline:** Wave 12 merged to `main` at `2ec5a84c0b4d82898a0fb8169844ddd5d93668d2`

## 1. Purpose

This gate addresses a producer-side truthfulness gap in the Blender boundary: the canonical model and health kernel already accept mesh-domain data such as per-face normals, UVs, and materials, but the current real-Blender extractor does not populate those fields, and scene membership is intentionally limited to `scene.collection.objects`.

The objective is **read-only extraction fidelity**, not a new correction capability and not a write-back path.

The milestone is complete only when a real Blender scene can be converted into the existing canonical payload without silently replacing available source data with empty placeholders or silently omitting in-scope scene members.

## 2. Authority boundary

```text
real Blender scene
      ↓
read-only bounded extractor
      ↓
versioned extraction payload
      ↓
canonical SceneModel
      ↓
deterministic health kernel
```

The extractor must not mutate Blender, save a file, invoke a correction executor, create persistence authority, alter workflow/action-runner behavior, or infer repairs.

This milestone does **not** create a production write-back adapter. A future engine-binding milestone requires its own design gate and explicit authority decision.

## 3. Current known producer gap

The current extractor emits:

- `normals = None`;
- `uvs = None`;
- `materials = []`;

for real mesh extraction. The canonical `MeshModel` already supports these domains, and the extraction payload schema already reserves the fields. The intended change is therefore completion of an existing contract, not creation of a new correction model.

The current scene discovery also enumerates only `scene.collection.objects`. The fidelity milestone must either:

1. extend discovery to the complete intended scene-membership domain; or
2. explicitly freeze a narrower membership boundary in the canonical contract and prove that the omitted domains are out of scope.

The design must choose one. Silent partial discovery is not acceptable.

## 4. Normative mesh-domain contract

### 4.1 Normals

If source polygon normals are available from Blender, emit **one canonical 3-vector per polygon, in canonical face order**.

Requirements:

- source order must map deterministically to extracted face order;
- finite numeric values only;
- no relabelling of per-vertex normals as per-face normals;
- no synthesized normals when the source does not provide a trustworthy polygon-normal value;
- unavailable or structurally unsupported normals must be represented as an explicit omission state, not fabricated data;
- output length must equal face count whenever normals are present;
- parser/kernel validation remains authoritative for canonical shape and finiteness.

### 4.2 UVs

The design must define exactly what one `MeshModel.uvs` entry means before implementation.

The current canonical model represents UVs as one `(u, v)` pair per face. Blender UV data may be loop/corner-domain rather than face-domain, so the extractor must **not silently collapse multiple loop UVs into one face value**.

Therefore implementation must first establish one of these closed outcomes:

- a deterministic, lossless mapping from the Blender source representation to the existing one-value-per-face contract, with a proof that no face carries multiple materially distinct UV values; or
- an explicit fidelity limitation/omission rule that leaves `uvs` absent whenever the source cannot be represented without loss.

A lossy averaging, first-corner selection, or arbitrary representative UV is prohibited.

### 4.3 Materials

The design must define whether `MeshModel.materials` represents:

- the ordered material-slot names attached to the mesh object; or
- per-face material assignments.

The existing canonical type is a tuple of strings, so a richer per-face material-domain representation cannot be invented inside this milestone. The implementation must therefore preserve the existing meaning exactly and reject/omit data that cannot be represented without semantic loss.

Material-slot order must be deterministic. Blender runtime pointer identity must never be used as canonical ordering.

## 5. Scene membership contract

The extractor must define the complete set of objects considered part of the extracted scene.

Preferred design:

- discover objects through the scene's collection hierarchy recursively;
- preserve each actual scene object exactly once, even when linked into multiple collections;
- use stable object identity (`object_id`) for deduplication;
- emit objects in deterministic order independent of Blender collection/pointer traversal order;
- retain the existing canonical `collection` field using a documented deterministic representative when an object belongs to multiple collections.

The representative-collection rule must be explicit. The extractor must not depend on runtime collection pointer order.

If recursive discovery exposes linked/library/hidden or otherwise unsupported Blender object classes, the contract must state whether they are included, excluded, or cause fail-closed extraction. No silent omission is allowed for a class declared in scope.

## 6. Fidelity principle

The extractor is a truth-preserving boundary, not a cleanup layer.

For every field:

```text
available + representable → emit exact canonical value
available + not representable → explicit omission/failure
unavailable → explicit omission
never → fabricate, approximate, average, infer, normalize, or repair
```

A successful extraction must never imply stronger fidelity than the source actually supports.

## 7. Determinism requirements

For identical Blender source state, repeated extraction must produce byte-equivalent canonical payload content after JSON canonicalization.

At minimum:

- object ordering is deterministic;
- face ordering follows source mesh polygon order;
- vertex ordering follows source mesh vertex order;
- normals follow canonical face ordering;
- material ordering follows the chosen closed contract;
- collection/object deduplication is deterministic;
- no memory addresses, pointers, hash-randomized ordering, or process-local identifiers enter the payload.

A two-process determinism gate is required because same-process repetition alone does not prove pointer/order independence.

## 8. Fail-closed rules

Extraction must fail closed for:

- missing required Blender data interfaces;
- malformed coordinate values;
- non-finite normals or UVs where the source claims them to be present;
- ambiguous source-to-canonical mappings that would require data loss;
- duplicate canonical object identities that cannot be disambiguated;
- unsupported collection/object classes that are declared in scope;
- payload schema mismatch;
- any extractor exception that would otherwise produce a partial payload.

A partially populated payload must not be returned as a successful full-fidelity extraction.

## 9. Preservation requirements

On a disposable real Blender scene, the gate must demonstrate preservation of source facts across extraction:

- vertex coordinates;
- face topology and polygon order;
- polygon normals when represented;
- UV data when representable under the closed contract;
- material information under the closed contract;
- object identity/name;
- parent relationship;
- local transform values;
- collection membership represented by the contract;
- unrelated objects.

The gate is read-only: no source mesh/object/collection may change as a side effect.

## 10. Required live fixtures

The real Blender 4.4.3 boundary must include at least:

### Fixture A — fidelity-positive mesh

A disposable mesh containing:

- multiple faces with deterministic polygon order;
- non-trivial polygon normals;
- UV data whose representability under the selected contract is unambiguous;
- multiple material slots and known face/material relationship;
- a non-trivial object transform;
- at least one unrelated object;
- membership through nested collections.

### Fixture B — non-representable/ambiguous source

A disposable mesh deliberately containing a source condition that cannot be represented losslessly by the current canonical UV/material contract. The extractor must either produce an explicitly documented omission or fail closed according to the chosen rule. It must never silently select or average a value.

### Fixture C — membership/deduplication

An object linked to multiple collections and a nested collection tree. The gate must prove exact-once object extraction and deterministic representative collection semantics.

## 11. Required validation layers

### Deterministic unit tests

Test payload construction and canonical conversion without Blender-specific objects, including:

- exact normals cardinality/order;
- UV representability and refusal rules;
- material-slot semantics;
- deterministic collection representative selection;
- duplicate object identity handling;
- malformed/non-finite data;
- source omission vs failure semantics;
- canonical JSON determinism.

### Adversarial tests

At minimum:

- normals length mismatch;
- non-finite normals;
- malformed UV loop data;
- multiple distinct UV values on one face;
- ambiguous material mapping;
- duplicate object IDs;
- object linked to multiple nested collections;
- collection traversal reordered between runs;
- hostile Blender-like adapters that raise after partial iteration;
- mutable/aliased source sequences;
- fabricated pointer-derived ordering;
- exception after some objects were extracted.

Every hostile case must either produce an explicitly partial/invalid result token or fail without returning a successful full payload. No partially trusted payload may reach the kernel as valid.

### Live Blender 4.4.3 gate

The live gate must independently verify:

- Blender version and executable identity;
- no `.blend` opened;
- no `.blend` or `.blend1` created/modified;
- two-process deterministic payload equality;
- exact expected normals/UV/material content for Fixture A;
- explicit behavior for Fixture B;
- exact-once nested collection membership for Fixture C;
- zero Blender mutation during extraction.

## 12. Canonical payload/schema rule

The preferred implementation reuses extraction payload schema version `1` if the existing fields can express the completed fidelity contract without changing their meaning.

A schema-version bump is required if the milestone needs a new canonical field, changes the meaning/cardinality of an existing field, or introduces a new representational domain.

The extractor must never stuff richer data into an existing field merely to avoid a schema change.

## 13. C++ seam

The fidelity contract must be expressible independently of `bpy` types:

- source-to-canonical field definitions;
- ordering rules;
- omission/failure semantics;
- exact JSON-native output;
- deterministic canonical serialization.

A future C++ producer must be able to emit the same extraction payload without depending on Blender Python runtime types.

## 14. Explicit non-goals

This milestone does not authorize:

- mesh repair;
- correction planning changes;
- vertex merging;
- topology cleanup;
- normal reconstruction;
- UV reconstruction;
- material reassignment;
- transform normalization;
- write-back to Blender;
- saving/persistence;
- receipts/workflow/action-runner authority;
- retry/rollback/recovery;
- correction dispatcher/orchestrator creation.

## 15. Exit criteria

Implementation may begin only after an independent review establishes:

1. the normals contract is exact and source-faithful;
2. the UV representation is either proven lossless for the supported source domain or explicitly bounded by omission/failure;
3. material semantics are closed and consistent with the existing canonical type;
4. scene membership is complete within a documented scope and deterministic;
5. no payload field silently understates or overstates source fidelity;
6. no mutation/persistence authority has entered the design;
7. the proposed live fixtures can prove the claims independently.

The milestone is complete only after deterministic, adversarial, and live Blender 4.4.3 validation pass and the extracted payload remains compatible with the canonical kernel contract.

## 16. Red-team questions

An independent reviewer must specifically attempt to break:

- the claim that one UV value per face can represent the source without loss;
- the material-slot vs per-face-material interpretation;
- recursive scene membership and multi-collection deduplication;
- deterministic ordering across processes;
- omission vs successful extraction semantics;
- partial extraction after a hostile adapter exception;
- compatibility with the existing schema version;
- the boundary between extraction fidelity and a future production write-back adapter.

The desired review output is concrete blockers, ambiguities, and contract corrections — not a score or ranking.
