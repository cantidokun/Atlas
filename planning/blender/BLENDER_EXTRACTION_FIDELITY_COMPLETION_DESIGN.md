# Atlas Blender — Extraction Fidelity v1 Scoped Producer Completion Design Gate

**Status:** DESIGN ONLY — NO IMPLEMENTATION  
**Track:** Blender canonical extraction  
**Baseline:** Wave 12 merged to `main` at `2ec5a84c0b4d82898a0fb8169844ddd5d93668d2`  
**Scope statement:** This milestone completes producer fidelity only for the explicitly supported v1 fields below. **Normals and UV fidelity are intentionally deferred** to separate future design gates.

## 1. Purpose and bounded claim

Atlas already has a canonical `SceneModel` / `MeshModel`, extraction payload schema v1, and deterministic health kernel. The remaining producer-side problem is that the real Blender extractor currently substitutes or omits source facts that the canonical layer can represent.

This milestone is therefore **not** full extraction fidelity. It is a bounded producer completion milestone for:

- object membership and deterministic representative collection;
- object visibility source selection;
- transform extraction including quaternion rotation mode;
- mesh vertex/face extraction and existing numeric policy;
- material-slot-name extraction;
- explicit omission semantics for normals, UVs, and local-frame data;
- deterministic payload encoding and cross-process evidence;
- preservation of the existing digest boundary.

**Normals and UVs are NOT completed by this milestone.** The extractor must not begin emitting them merely because Blender exposes source-side values. Their semantics conflict with the current canonical contracts and require separate gates.

No correction capability is added or changed here.

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

The extractor must not mutate Blender, save or persist a file, invoke a correction executor, create authorization/receipt/workflow authority, retry, rollback, recover, dispatch actions, or infer repairs.

A future real-asset write-back binding remains a separate design decision.

## 3. Existing payload/model compatibility

Extraction payload schema remains **version 1** for this milestone.

No field meaning or cardinality changes:

- `vertices`: ordered vertex coordinates;
- `faces`: ordered polygon vertex indices;
- `materials`: ordered material-slot names only;
- `normals`: omitted by the v1 extractor;
- `uvs`: omitted by the v1 extractor;
- `local_frame_id`: omitted by the v1 extractor;
- `collection`: one deterministic representative child collection name or `None`;
- `visible`: deterministic global viewport visibility value defined below.

A schema bump is mandatory before any of the following is introduced:

- per-corner/per-loop UV data;
- per-face material assignments;
- ordered multi-collection membership;
- provenance/availability state markers;
- a new canonical field;
- a changed field meaning or cardinality.

The extractor must never overload an existing field to avoid a schema bump.

## 4. Representation-state rules

The producer uses one encoding per field and does not use `null` as a v1 producer placeholder.

### 4.1 Normals

Normals are **producer-deferred** in v1.

For every mesh, the v1 extractor omits the `normals` key regardless of whether Blender exposes `MeshPolygon.normal`.

Reason: Blender's polygon normal is derived data, while the canonical health kernel independently derives a comparison normal from the first three face corners with a 1° sign-agnostic test. Emitting Blender polygon normals without a dedicated semantic agreement gate can manufacture `MESH_NORMAL_INCONSISTENT` on ordinary warped polygons.

No parser or canonical-model tightening is authorized here. Existing `null`, `[]`, and omitted-input acceptance remains unchanged for existing closed capabilities and fixtures.

Future normal-fidelity work requires its own design gate covering source semantics, derivation algorithm, unit/orientation policy, warped polygons, undefined references, tolerance, and compatibility with the existing kernel contract.

### 4.2 UVs

UVs are **producer-deferred** in v1.

For every mesh, the v1 extractor omits the `uvs` key regardless of Blender loop/corner UV availability.

A face-level `(u,v)` cannot represent Blender loop-domain UVs without loss when a face has distinct corner values. No averaging, first-corner selection, representative UV, or other lossy collapse is permitted.

A future UV gate must introduce a versioned corner-domain representation and update every closed consumer that snapshots mesh UV state before emission is allowed.

There is no v1 caller-selectable UV-fidelity mode. `extract_scene()` remains a fixed-contract API.

### 4.3 Materials

`MeshModel.materials` means exactly:

> the ordered names of the target object's mesh datablock material slots, read from `obj.data.materials` in Blender slot order.

Object-level `obj.material_slots` semantics are out of scope for v1.

Rules:

- zero material slots → `materials: []`;
- one or more slots, all containing non-empty material names → emit those names in slot order;
- any slot is empty/unassigned → omit the `materials` key for that mesh rather than invent a token;
- per-face `material_index` assignments are explicitly **not represented**;
- material names are not lexically sorted; source slot order is canonical;
- pointer identity is never used for ordering.

The current canonical string validator requires non-empty strings, so empty-slot tokens cannot be invented without a schema change.

### 4.4 Local frame

`local_frame_id` is explicitly omitted in v1. It is not a populated producer field and is not part of the v1 fidelity completion claim.

A future local-frame contract must define the Blender source datum and representation before emission.

### 4.5 Omission semantics

For fields whose v1 producer contract is deliberately deferred (`normals`, `uvs`, `local_frame_id`), **key omission** is the sole producer encoding.

`null` is not emitted by the producer.

A legitimately empty field is distinct from omission only where the existing field semantics already define a genuine empty state (`materials: []` means zero material slots). The existing canonical parser's broader acceptance of `null`/absent/empty is preserved and is not changed by this milestone.

Representation state does not participate in `SceneReport.digest()` in v1. The digest boundary therefore remains intentionally based on the existing canonical fields. This is documented behavior, not an attempt to claim provenance equivalence between omitted and empty optional fields.

## 5. Object and scene membership contract

### 5.1 Scene domain

The v1 scene domain is the recursive object membership of `bpy.context.scene.collection` and all descendant collections.

Traversal rules:

- recurse through child collections deterministically;
- include each reachable Blender object exactly once by source-object identity;
- do not deduplicate objects by `object_id` during traversal;
- after traversal, canonical `object_id` remains the object's `name` string;
- objects are emitted in Unicode code-point lexical order of `object_id`/name.

This source-object identity deduplication prevents a multi-linked object from appearing twice while preserving the kernel's ability to report duplicate canonical IDs in hand-built payloads.

### 5.2 Collection representative

The canonical `collection` field is a **representative**, not complete membership.

For each object:

1. consider collections that are reachable from the scene root;
2. exclude the scene master collection itself;
3. among included child collections containing the object, choose the lexicographically smallest collection name using Unicode code-point order (`str` ordering);
4. if no included child collection contains the object, emit `collection: None`.

The v1 loss is explicit: multiple collection memberships are not represented in full.

A future complete membership contract requires a versioned ordered collection list and must not reuse the single `collection` string.

### 5.3 Object classes

The v1 extractor includes scene objects once even when `mesh=None`.

- `MESH`: mesh geometry is extracted.
- `EMPTY`: object record is extracted; `instance_collection` is not expanded.
- `CURVE`, `SURFACE`, `FONT`, `META`, and other non-MESH object classes: object record is extracted with `mesh=None`; their non-mesh geometry is explicitly out of scope in v1.
- collection instances are not expanded into duplicated contained geometry.
- linked/library objects are included when reachable through the scene collection graph; source datablock linkage is not represented in v1.
- hidden/excluded state does not remove an object from the scene domain; visibility is represented separately by §9.1.

Any object class that the extractor cannot inspect at the required source interfaces fails closed rather than producing a partial object record.

## 6. Mesh identity and ordering

For v1, `mesh_id` remains the existing producer convention: `str(obj.name)`.

This is **not** declared to be Blender datablock identity. Two objects sharing a mesh datablock may therefore have distinct canonical `mesh_id` values.

Vertex order follows `obj.data.vertices` source index order.

Face order follows `obj.data.polygons` source polygon index order.

No sorting or reindexing of vertices/faces is permitted.

## 7. Transform and visibility fidelity

### 7.1 Location and scale

Location and scale must be read from the authoritative `obj.location` and `obj.scale` components. Missing/malformed required transform attributes fail closed.

The extractor must not default individual missing components to `0.0` or `1.0`.

### 7.2 Rotation

Rotation extraction is closed by Blender `rotation_mode`.

- `XYZ`, `XZY`, `YXZ`, `YZX`, `ZXY`, `ZYX`: read `obj.rotation_euler` and use the existing `euler_xyz_degrees_to_quaternion` canonical conversion convention; the mode/order is part of the extraction precondition and a fixture must cover a non-XYZ Euler mode.
- `QUATERNION`: read `obj.rotation_quaternion` directly in Blender's `(w, x, y, z)` order and emit the same canonical tuple order.
- `AXIS_ANGLE`: fail closed in v1 because the existing canonical conversion contract does not define axis-angle semantics.

No rotation exception may be converted to an identity quaternion. Any failure to read or convert the selected source channel is extraction failure.

### 7.3 Visibility

The v1 canonical visibility source is the data property `obj.hide_viewport`.

Emit:

`visible = not bool(obj.hide_viewport)`

This is a global viewport visibility value. View-layer-dependent `hide_get()` / `visible_get()` and render visibility (`hide_render`) are not represented by `ObjectModel.visible` in v1.

If `hide_viewport` is unavailable or malformed, extraction fails closed rather than substituting `True`.

## 8. Numeric policy

Existing vertex extraction remains rounded to six decimal places because that is already part of the producer contract.

The v1 design pins that operation to **round-half-even to 6 decimal places**, matching Python's existing `round(value, 6)` semantics for the current producer.

Other emitted floats are not newly rounded in this milestone. They must be finite and representable by the canonical parser.

The C++ seam therefore claims **canonical value parity**, not byte-identical JSON parity, for v1. Exact cross-language byte serialization is deferred to a future serialization-specific gate.

This avoids asserting a byte-level contract without first introducing and testing a shared canonical numeric encoder.

## 9. Canonicalization and determinism

For semantic comparison, payload canonicalization is:

- UTF-8 JSON;
- dictionary keys sorted lexicographically;
- compact separators `(',', ':')`;
- `ensure_ascii=True`;
- non-finite numbers forbidden (`allow_nan=False` in any canonical serializer used by the gate);
- list ordering preserved exactly because source ordering is semantically significant.

This canonicalization is an evidence format, not a promise of a cross-language byte-identical production serializer.

Three deterministic runs are required:

1. identical disposable scene construction under one `PYTHONHASHSEED`;
2. identical scene under a different `PYTHONHASHSEED`;
3. same semantic scene with object/collection construction order changed while preserving source vertex, face, material-slot, and polygon ordering.

The collection-linking subcase must also reverse the order in which an object is linked to two child collections.

Expected result: identical canonical payload values and identical payload hashes for all semantically identical runs.

## 10. Fidelity / fail-closed rules

The extractor is a truth-preserving boundary.

For all in-scope fields:

```text
available + representable → emit exact canonical value
available + unsupported/unrepresentable → explicit v1 omission or explicit extraction failure per field rule
malformed required source → fail closed
extractor exception after partial traversal → fail closed; never return a successful partial payload
never → fabricate, approximate, average, infer, normalize, or repair
```

Required fail-closed conditions include:

- missing/malformed coordinates;
- missing/malformed transform channels;
- unsupported rotation mode;
- non-finite emitted numbers;
- malformed material slot names;
- ambiguous collection traversal;
- unsupported object class when a required interface is missing;
- duplicate payload schema keys or unsupported schema version;
- partial traversal exceptions.

The payload validator remains responsible for payload shape; the deterministic kernel remains responsible for health findings.

The extractor does **not** move every kernel finding into an extraction failure. In particular, duplicate canonical object IDs remain a kernel `OBJECT_ID_DUPLICATE` finding for hand-built or adapter payloads. Traversal deduplication is source-object-identity based, not name based.

## 11. Digest compatibility

The existing `scene_input_digest` covers object identity/name, collection, parent, location, scale, rotation, visibility, mesh_id, vertices, and faces.

This milestone does **not** change the digest algorithm.

Therefore:

- `normals`, `uvs`, `materials`, and `local_frame_id` do not participate in the current digest;
- a change to `collection`, `visible`, location, scale, rotation, vertices, faces, or other already-digested fields legitimately changes the digest;
- the new collection representative and visibility source may therefore make a previously extracted scene produce a different digest. That is an intentional producer correction, not a silent digest-algorithm change;
- correction artifacts built against an old source digest become stale when the source digest changes and must fail their existing stale-source checks;
- the frozen real asset must prove that its digest and pinned report expectations remain unchanged under the v1 representative/visibility rules.

Existing correction suites must remain green. No canonical parser tightening is permitted in this milestone because closed Wave 1–3 fixtures intentionally use both omitted and `None` optional mesh metadata.

### Wave-3 interaction disclosure

The existing Wave-3 merge executor includes mesh material/UV/normal/local-frame metadata in its MQ-5/MQ-6 identity snapshots. Under v1, material-bearing meshes may newly expose non-empty material tuples where they previously exposed `[]`, so a future live merge harness may now detect material-copy omissions that were previously invisible.

That is a legitimate newly observable postcondition, not an extraction defect. This milestone must disclose and test the interaction; it must not weaken MQ-5/MQ-6 or add material mutation authority.

## 12. Live evidence model

The live Blender boundary uses Blender **4.4.3** with the pinned build identity `802179c51ccc`.

The live gate may open a frozen `.blend` asset **read-only**. It must:

- SHA-256 the asset before the run;
- open it without save;
- run extraction;
- SHA-256 it after the run;
- prove the hash is unchanged;
- prove no `.blend` or `.blend1` was created or modified;
- prove no unrelated repository asset changed.

The disposable live fixtures remain the primary positive fidelity mechanism.

## 13. Required live fixtures

### Fixture A — scoped fidelity positive

A disposable scene containing:

- a mesh with multiple polygons;
- two or more non-empty material slots in known order;
- a quaternion-mode object with a non-identity quaternion;
- a non-XYZ Euler-mode object;
- nested child collections;
- an object linked to two child collections in reversed construction orders across runs;
- a master-only object;
- an unrelated object;
- an object hidden with `hide_viewport=True`;
- no UV fidelity expectation and no normal-fidelity expectation.

Expected v1 payload facts include material slot names, quaternion/euler transform parity, deterministic representative collection, master-only `None`, and visibility.

### Fixture B — explicitly unsupported domains

A mesh containing:

- a genuine Blender UV layer, including a seam/corner-varying face;
- an empty material slot.

Expected v1 behavior: `uvs` omitted; `materials` omitted. No averaging, no first-corner selection, no empty-slot token.

### Fixture C — membership and object identity

A nested collection tree containing:

- one object in two child collections;
- one master-only object;
- one object reachable only through a nested collection;
- one linked/library object if available;
- one `instance_collection` Empty;
- one CURVE object.

Expected behavior follows §5.3 and §5.2 without expanding instanced collection geometry.

### Fixture D — frozen asset regression

Open `tests/assets/blender/atlas_transform_validation.blend` read-only and preserve all existing pinned expectations:

- scene id;
- object count and ids;
- pitch topology;
- probe world transform;
- finding-code set;
- validation state;
- asset SHA-256.

Also assert the v1 producer semantics for omitted normals/UVs/local-frame and current material state.

## 14. Required deterministic tests

At minimum:

- quaternion-mode extraction;
- non-XYZ Euler extraction;
- unsupported AXIS_ANGLE refusal;
- missing/malformed transform attributes fail closed;
- `hide_viewport=True/False` mapping;
- no per-axis transform defaults;
- material-slot order from `obj.data.materials`;
- empty material slot causes `materials` omission;
- zero material slots produce `materials: []`;
- per-face `material_index` never appears in payload;
- normals key absent in v1;
- UV key absent in v1 even when UV layer exists;
- local_frame_id omitted;
- recursive collection traversal;
- representative lexical rule;
- master-only fallback;
- reversed multi-collection link order;
- source-object-identity deduplication;
- duplicate canonical IDs remain kernel-findable on hand-built payloads;
- CURVE/instance collection behavior;
- malformed/non-finite values fail closed;
- partial traversal exceptions never return a successful payload;
- canonical payload hash equality across the three determinism runs;
- frozen asset digest unchanged.

Run the deterministic suite under both Python 3.9 and Python 3.11.

## 15. Required adversarial tests

At minimum:

- hostile object exposing wrong rotation mode/channel types;
- quaternion with malformed/non-finite components;
- axis-angle object;
- absent `hide_viewport`;
- non-bool `hide_viewport`;
- object with location/scale missing one axis;
- material slot with empty/unassigned material;
- object in multiple collections with reversed insertion order;
- object only in the master collection;
- duplicate source references to one object;
- hand-built payload with duplicate object_id values;
- curve, surface, font, meta, and instance_collection objects;
- UV layer with multiple values on one face;
- exception after some objects are extracted;
- mutated/aliased source collections;
- different `PYTHONHASHSEED` values;
- fabricated pointer-derived ordering;
- non-finite numeric payload.

Every hostile case must either fail closed or produce the exact bounded payload state defined by this design. No hostile case may silently fabricate data.

## 16. C++ seam

The C++ interoperability requirement for v1 is **semantic payload parity**, not byte-for-byte JSON identity.

A future C++ producer must reproduce:

- the same source-to-canonical field meanings;
- the same source-domain ordering rules;
- the same omission/failure semantics;
- the same six-decimal half-even vertex rounding;
- the same Unicode code-point lexical collection ordering;
- the same canonical values after parsing.

A future byte-identical serialization guarantee requires a separate serialization gate with a shared language-independent numeric encoding algorithm.

## 17. Explicit non-goals

This milestone does not authorize:

- normal fidelity implementation;
- UV fidelity implementation;
- per-face material assignment;
- multi-collection canonical representation;
- mesh repair;
- correction planning changes;
- vertex merging;
- topology cleanup;
- normal reconstruction;
- UV reconstruction;
- material reassignment;
- transform normalization;
- write-back to Blender;
- persistence/save;
- receipts/workflow/action-runner authority;
- retry/rollback/recovery;
- correction dispatcher/orchestrator creation;
- caller-selectable extraction modes.

## 18. Exit criteria

Implementation may begin only after independent review confirms all of the following:

1. the v1 scoped claim explicitly excludes normals and UV fidelity;
2. rotation source selection is closed by `rotation_mode` and quaternion WXYZ order;
3. visibility source is exactly `obj.hide_viewport` with explicit polarity;
4. material accessor is exactly `obj.data.materials` and empty-slot behavior is closed;
5. collection traversal, deduplication, representative rule, and master fallback are closed;
6. non-MESH object and instance semantics are explicit;
7. omission semantics are pinned and producer `null` emission is forbidden;
8. digest participation and stale-artifact implications are documented;
9. Wave-3 MQ-5/MQ-6 interaction is disclosed without weakening the closed contract;
10. the deterministic evidence protocol is executable and named;
11. frozen-asset read-only regression is included;
12. deterministic and adversarial tests are specified for Python 3.9 and 3.11;
13. the C++ claim is limited to semantic parity until a separate byte-serialization gate exists;
14. no execution, persistence, workflow, recovery, or write-back authority exists in the milestone;
15. an independent reviewer re-gates the final design and does not self-clear it.

The milestone is complete only after deterministic, adversarial, and live Blender 4.4.3 validation pass and the extracted payload remains compatible with the existing canonical kernel and closed correction contracts.

## 19. Required independent red-team questions

The reviewer must specifically attempt to break:

- quaternion vs Euler extraction;
- visibility semantics and digest participation;
- material-slot accessor identity;
- master-excluded collection representative semantics;
- linked/multi-collection/source-object deduplication;
- instance/curve geometry omission boundaries;
- omitted-vs-empty optional field behavior;
- Wave-3 MQ-5/MQ-6 compatibility;
- digest changes caused by corrected collection/visibility values;
- three-run determinism across hash seeds and construction order;
- frozen asset regression;
- the boundary between this read-only producer milestone and any future production write-back adapter.

Desired review output: concrete blockers, ambiguities, test gaps, and contract corrections — never a score or ranking.
