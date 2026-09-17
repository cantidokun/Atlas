# Atlas Blender — Extraction Fidelity Completion Design Gate

**Status:** DESIGN REVISION 2 — REVIEW REQUIRED / NO IMPLEMENTATION  
**Track:** Blender canonical extraction  
**Baseline:** Wave 12 merged to `main` at `2ec5a84c0b4d82898a0fb8169844ddd5d93668d2`  
**Design branch:** `feat/blender-extraction-fidelity-design`

## 1. Purpose and scope

This gate addresses a producer-side truthfulness gap in the Blender boundary. The canonical model and health kernel contain fields and checks for mesh-domain information, but the current real-Blender extractor does not faithfully populate all of those fields. Scene discovery is also narrower than a complete scene-graph traversal.

This revision closes the design decisions raised by independent red-team review. It intentionally **narrows the implementation scope where the existing canonical representation cannot make a truthful claim** rather than forcing new semantics into old fields.

The milestone is therefore a bounded **Extraction Fidelity v1** milestone:

### In scope

- truthful vertex/face extraction already representable by the canonical schema;
- deterministic object discovery within the defined scene-membership domain;
- material-slot name extraction only, under the exact existing `tuple[str, ...]` meaning defined below;
- explicit extraction-state semantics for supported fields;
- fail-closed handling of existing fabricated-default paths;
- deterministic payload canonicalization and cross-process validation;
- read-only real-Blender evidence.

### Explicitly deferred

- UV fidelity beyond the current schema's representational capacity;
- per-face or per-loop material assignment;
- a new multi-collection canonical field;
- changing the canonical normal-consistency algorithm;
- any production write-back adapter.

These deferred items are not hidden failures. They are explicit architectural boundaries recorded by this gate so that future work cannot accidentally reinterpret them as completed fidelity.

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

The extractor must not mutate Blender, save a file, invoke correction executors, create persistence authority, alter workflow/action-runner behavior, or infer repairs.

This milestone does **not** create a production write-back adapter. Any future engine-binding/write-back milestone requires its own design gate and explicit authority decision.

## 3. Truthfulness rule

Extraction is a truth-preserving boundary, not a cleanup or inference layer.

For every supported field:

```text
source observed + canonically representable
    -> emit the exact canonical value

source unavailable / out of declared scope
    -> emit the declared omission state

source observed but not representable without loss
    -> emit the declared omission state AND record the limitation in the extraction contract

malformed source / ambiguous mapping where the contract requires fidelity
    -> fail closed

never
    -> fabricate, approximate, average, infer, normalize, repair, or select a convenient representative
```

A successful extraction must never claim more fidelity than the declared canonical contract supports.

## 4. Canonical representation-state policy

The previous revision treated `None`, `[]`, and absent keys as abstractly distinct. The actual parser and digest layer do not preserve all such distinctions. This revision therefore defines a narrower state policy for schema version `1`.

### 4.1 Normals and UVs

For schema version `1`:

- **present/non-empty** means the field is explicitly populated and satisfies the field's exact cardinality rules;
- **present/empty** is valid only when `faces == ()` and the field is intentionally empty under the canonical mesh contract;
- **omitted/unavailable/unrepresentable** uses the canonical empty/omitted representation already accepted by the v1 payload parser; it is not presented as evidence that the source contained empty data;
- the extractor must not emit `null` for these fields in a successful v1 payload;
- a future schema may add an explicit provenance/availability marker if the distinction must participate in canonical identity.

The digest contract remains unchanged in this milestone. The design explicitly accepts that v1 extraction-state provenance is **not** part of `scene_input_digest` unless and until a versioned digest/schema change is separately approved.

### 4.2 Materials

`materials == ()` means no material-slot names are represented in the canonical v1 output. It does not claim that Blender had zero material slots unless that is established by the declared material contract.

## 5. Normals — closed v1 rule

### 5.1 Canonical source

The v1 extractor may read `bpy.types.MeshPolygon.normal`, but this value is a Blender-derived polygon normal, not immutable stored source data.

Therefore v1 makes the following explicit claim:

> `MeshModel.normals` is a **Blender-derived polygon-normal observation**, not a preserved source-normal channel.

The extractor must not label it as custom split/corner normal data and must not synthesize it from per-vertex or loop-domain normal data.

### 5.2 Kernel-agreement boundary

The existing kernel compares declared normals against its own first-three-corners reference using a sign-agnostic one-degree tolerance. That means emitting Blender polygon normals without reconciliation can manufacture `MESH_NORMAL_INCONSISTENT` findings on ordinary warped polygons.

**Therefore v1 does not authorize real-Blender normal emission yet.**

Until a separate normal-semantics gate establishes a compatible kernel/producer contract, the live extractor must continue to omit normals rather than create a false-positive fidelity signal.

The normal field remains fully supported by the canonical model, but its live producer completion is explicitly deferred. The future normal-semantics gate must establish:

- authoritative source semantics;
- derived-vs-stored status;
- unit/normalization semantics;
- orientation semantics;
- agreement algorithm and tolerance;
- behavior for warped polygons and undefined first-three-corner references;
- compatibility impact on existing findings/digests/tests.

### 5.3 Required evidence for the future normal gate

The future gate must include a warped quad/polygon matrix spanning values below, at, and above the existing one-degree kernel threshold, plus inverted and non-unit vectors, and must record the exact intended semantics rather than inferring them from current behavior.

## 6. UVs — closed v1 rule

The current canonical type stores exactly one `(u, v)` pair per face. Blender UVs are loop/corner-domain and a face may legitimately carry distinct UVs at different corners.

**V1 therefore declares UV data outside the lossless canonical representation domain.**

The v1 extractor must:

- not emit averaged, first-corner, representative, or otherwise collapsed UV values;
- not claim that `MeshModel.uvs` contains the Blender UV layout;
- omit UVs from successful v1 real-Blender extraction;
- fail closed only when the caller explicitly requests a UV-fidelity contract rather than ordinary v1 extraction.

A future UV capability requires a versioned canonical representation capable of preserving per-corner data, for example an explicit per-face ordered corner-UV structure. That future design must bump the payload schema and update the canonical model, parser, extraction digest semantics, Wave-11 empty-mesh rules, and any closed correction postcondition that snapshots `uvs`.

## 7. Materials — closed v1 rule

The existing canonical `MeshModel.materials` is a tuple of strings. V1 defines it precisely as:

> the deterministic ordered names of the target mesh object's material slots.

Rules:

- source order is Blender material-slot order;
- the extractor must not sort material slots by pointer, object identity, or arbitrary name order;
- an empty material slot cannot be represented by a string name in the existing contract, so **any empty material slot causes v1 material extraction to omit the field rather than invent a token**;
- per-face `material_index` assignments are explicitly **not represented** by v1 and must not be inferred from the slot-name tuple;
- no material reassignment, normalization, deduplication, or repair occurs.

A future per-face material-domain capability requires a versioned schema/model extension and a separate design gate.

## 8. Scene-membership contract — closed v1 rule

V1 defines extracted scene membership as:

> objects reachable from `scene.collection` through its collection-child hierarchy, recursively, excluding the scene's master collection object itself as a semantic collection record.

Rules:

- traverse collection children recursively;
- include each reachable Blender object exactly once;
- deduplicate by Blender object identity during traversal, not by display name;
- emit canonical objects sorted by canonical `object_id` (`obj.name` in v1);
- do not rely on collection pointer order;
- an object linked to multiple included collections is emitted once;
- the canonical `collection` field is the deterministic representative **lexicographically smallest included child-collection name attached to the object**;
- the scene master collection is excluded from representative selection;
- if an object is attached only to the master collection, `collection` is `None`;
- the single `collection` field is explicitly a **lossy representative**, not a claim of complete multi-collection membership;
- multi-collection completeness remains deferred to a future versioned collection-domain field.

### 8.1 Object classes

V1 includes all ordinary scene objects reachable through the declared collection hierarchy, including non-mesh objects, represented with `mesh=None`.

V1 does not expand an `instance_collection` Empty into the contents of the referenced collection. The Empty itself may be emitted; the instanced geometry is out of scope for v1 and this limitation must be recorded in the live evidence.

Library-linked objects are included if reachable through the declared hierarchy and expose the required read-only Blender interfaces. Name collisions are governed by Blender's canonical object-name rules; duplicate canonical `object_id` detection remains a fail-closed guard for hostile or malformed adapter inputs.

View-layer hiding, render hiding, and collection exclusion are **not scene-membership predicates** in v1. Visibility is handled separately by the object-state rule below.

## 9. Existing fabricated-default paths — brought into scope

The prior design did not address several fields that currently fabricate values when Blender interfaces are absent or raise exceptions. That is incompatible with a truth-preserving extraction boundary.

V1 therefore requires:

### 9.1 Visibility

The extractor must use one named, documented Blender visibility source. If the declared source cannot be read, extraction fails closed for the affected object rather than defaulting to `True`.

### 9.2 Location and scale

If `obj.location` or `obj.scale` is unavailable or malformed, extraction fails closed for the object. The extractor may not substitute `(0,0,0)` or `(1,1,1)` as a successful result.

### 9.3 Rotation

Rotation extraction may not swallow arbitrary exceptions and silently substitute an identity quaternion. A malformed/unreadable rotation source must fail closed.

The exact named Blender source and conversion convention must be pinned by implementation tests before the producer is changed.

## 10. Geometry-domain contract

The existing v1 geometry contract remains unchanged unless a separate design gate explicitly changes it:

- mesh vertex order follows Blender mesh vertex order;
- face order follows Blender polygon order;
- vertex coordinates are emitted using the existing six-decimal canonical rounding rule;
- no geometry evaluation, modifier application, triangulation, smoothing, welding, or topology repair occurs;
- original `obj.data` geometry is the v1 source domain.

Evaluated/depsgraph geometry is explicitly out of scope for v1 because it changes topology and identity attribution and would require a separate determinism/representation gate.

## 11. Determinism contract

Identical source state must produce byte-equivalent canonical payloads under a named canonical JSON encoding.

V1 uses the following deterministic procedure for evidence:

1. object order is canonical `object_id` order;
2. collection representative selection is lexical over included child collection names;
3. material slot order is source slot order;
4. face and vertex order remain source order;
5. payload JSON is serialized with UTF-8, sorted keys, compact separators, and `ensure_ascii=True`;
6. numeric encoding is the canonical Python JSON representation of the already-canonicalized numeric values;
7. C++ parity is defined as byte-equivalent output under this same encoding and number normalization rules.

The live gate must run:

- process A with `PYTHONHASHSEED=1`;
- process B with `PYTHONHASHSEED=2`;
- process C using the same scene values but a different object/collection construction order.

All three canonical payload hashes must match.

## 12. Fail-closed rules

Extraction must fail closed for:

- missing required Blender interfaces;
- malformed or non-finite coordinates;
- malformed/non-finite supported source values;
- ambiguous source-to-canonical mappings requiring loss;
- duplicate canonical object IDs at the canonical payload boundary;
- unsupported in-scope object/collection classes;
- rotation/location/scale/visibility fallback paths;
- payload schema mismatch;
- exceptions after partial extraction that would otherwise return a successful payload.

No partial payload may be treated as a successful `SceneModel`.

The deterministic payload validator remains the final schema-shape gate before kernel parsing.

## 13. Read-only validation fixtures

### Fixture A — supported fidelity

A disposable Blender 4.4.3 scene containing:

- multiple mesh faces with deterministic polygon ordering;
- nested collections;
- an object linked to multiple child collections;
- two or more material slots, all non-empty, whose slot names are known;
- a non-trivial transform;
- unrelated mesh and non-mesh objects;
- visibility states exercising the declared visibility source;
- no UV fidelity claim beyond the v1 omission rule.

### Fixture B — intentionally unrepresentable domains

A disposable mesh containing:

- a genuine UV layer with distinct loop/corner values on at least one face;
- at least one material-slot configuration that would require an empty-slot token if fidelity were claimed.

V1 must omit these unsupported domains without manufacturing representatives.

### Fixture C — membership and deduplication

- nested collection hierarchy;
- one object attached to two included child collections;
- one object attached only to the master collection;
- one instance-collection Empty;
- one library-linked or simulated hostile object when the runtime permits it.

### Fixture D — source-integrity/failure paths

Hostile Blender-like adapters must exercise unavailable visibility, location, scale, rotation, partial iteration, and post-partial-extraction exceptions. Each must fail closed rather than synthesize defaults.

### Frozen asset

The existing frozen `.blend` asset may be opened **read-only** for regression validation. The gate must hash the asset before and after, require byte-identical hashes, and prohibit saving or creation/modification of any `.blend`, `.blend1`, or temporary Blender asset.

The frozen asset is a regression anchor only; it does not prove positive UV/material fidelity because its known contents do not exercise those domains. New disposable fixtures provide the positive evidence for the closed v1 claims.

## 14. Validation layers

### Deterministic unit tests

Required coverage:

- payload normals/UV/material omission semantics;
- material-slot-name semantics including empty-slot refusal/omission;
- deterministic representative collection selection;
- duplicate identity handling;
- visibility/location/scale/rotation failure behavior;
- canonical JSON serialization and hashing;
- schema validation and schema mismatch;
- source-order preservation.

### Adversarial tests

At minimum:

- UV seam within a single face;
- malformed UV loop data;
- empty material slot;
- per-face material-index variation;
- collection traversal reordering;
- master-only object;
- multi-collection object;
- hostile duplicate object IDs;
- exceptions after partial traversal;
- non-finite source values;
- fabricated pointer ordering;
- missing visibility/location/scale/rotation interfaces;
- modifier-bearing object proving original `obj.data` scope;
- instance-collection Empty;
- linked-object adapter behavior.

### Live Blender 4.4.3 gate

The gate must independently prove:

- Blender 4.4.3 executable/build identity;
- frozen asset SHA unchanged before/after read-only open;
- no save and no `.blend/.blend1` file creation/modification;
- exact supported-domain payload content;
- explicit UV/material omission behavior;
- deterministic nested membership and representative collection semantics;
- visibility/location/scale/rotation source reads;
- three-process determinism with two distinct `PYTHONHASHSEED` values plus reordered construction;
- zero source mutation.

The live gate must print/record the payload canonicalization method, process hash seed, fixture construction order, and resulting payload SHA-256 for every process.

## 15. Schema/version and digest boundary

V1 retains `PAYLOAD_SCHEMA_VERSION = "1"` because it deliberately does **not** change the meaning/cardinality of the existing `uvs` or collection fields and does not add a provenance marker.

The following are explicit future version triggers:

- per-corner UV representation;
- complete multi-collection membership representation;
- explicit availability/representation-state field;
- per-face material assignment;
- changed normal semantics;
- any new canonical field.

No implementation may use an existing field to smuggle one of these richer representations into schema v1.

Because the existing scene input digest does not include normals/UV/materials/local-frame state, this milestone does not claim that representation-state changes alter `SceneReport.digest`. That behavior is documented rather than silently modified. Any future digest participation change requires its own compatibility analysis for correction plans, authorizations, and receipts.

## 16. C++ seam

A future C++ producer must be able to emit the same v1 extraction payload without Blender Python types.

The parity requirement is limited to the closed v1 fields and exact canonical serialization defined above. Richer UV/material/membership domains remain versioned future contracts and therefore do not constrain the current seam.

## 17. Explicit non-goals

This milestone does not authorize:

- normal-semantic kernel redesign;
- UV schema expansion;
- per-face material assignments;
- multi-collection schema expansion;
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
- correction dispatcher/orchestrator creation;
- evaluated/depsgraph geometry extraction.

## 18. Exit criteria for implementation

Production implementation may begin only after an independent re-gate confirms all of the following:

1. v1 normals remain explicitly deferred rather than falsely emitted;
2. v1 UV behavior is closed to omission, with no lossy representative;
3. v1 material semantics are closed to ordered non-empty slot names;
4. v1 collection semantics are closed to recursive membership plus a documented single representative;
5. fabricated visibility/location/scale/rotation defaults are either eliminated or explicitly excluded from the completion claim;
6. digest/provenance implications are explicitly recorded and no existing digest-bound contract is silently changed;
7. the frozen-asset read-only regression protocol is defined;
8. the three-run determinism protocol is defined and falsifiable;
9. all adversarial and live fixtures are mechanically capable of proving the claims;
10. the C++ serialization seam is byte-defined;
11. no mutation/persistence/workflow authority has entered the design;
12. an independent reviewer, not the implementer, clears the revised design.

The implementation milestone is complete only after deterministic, adversarial, Python 3.9/3.11 CI, and real Blender 4.4.3 boundary validation pass.

## 19. Independent re-red-team questions

The next reviewer must specifically attack:

- whether deferring normals while calling this "extraction fidelity completion" overstates the milestone;
- whether the UV omission policy is sufficiently explicit to prevent accidental face-domain fabrication;
- whether material-slot-name semantics are mechanically stable across Blender files;
- whether the representative collection is an acceptable declared loss rather than a hidden fidelity claim;
- whether master-only and instance-collection objects are correctly bounded;
- whether removal of fabricated defaults is complete;
- whether the frozen-asset read-only protocol is safe and reproducible;
- whether the three-process determinism protocol actually distinguishes ordering dependencies;
- whether keeping schema v1 is genuinely compatible with all existing consumers;
- whether the design has accidentally changed any existing digest-bound capability contract;
- whether the milestone is now narrow enough to implement without becoming a disguised production engine-binding project.

The desired review output remains concrete blockers, ambiguities, test gaps, and contract corrections — not a score or ranking.
