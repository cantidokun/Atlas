# Atlas Blender — Extraction Fidelity v1 (Scoped Producer Completion) Design Gate

**Status:** DESIGN REVISION 3 — REVIEW REQUIRED / NO IMPLEMENTATION
**Track:** Blender canonical extraction
**Baseline (authoritative):** `origin/main` = `2ec5a84c0b4d82898a0fb8169844ddd5d93668d2` (Wave 12 merged)
**Design branch:** `feat/blender-extraction-fidelity-design`
**Revision chain:** `fd26da0` → `d973c9a` → `3257f2d` → `66c1c77` → this revision (§0.1)
**Scope statement (read this before the title):** this milestone completes producer fidelity **only** for the explicitly supported v1 fields below. **Normals, UVs, and local-frame fidelity are intentionally NOT delivered**, and a cross-language byte-identical serializer is **NOT** delivered. Those are separate gates.

> The file name retains `COMPLETION` for continuity with the revisions a reviewer cites by path.
> The file name is not a claim; §1.1 is the claim boundary.

## 0. Revision control, authoritative baseline, and repository state

Nothing in this section is a contract; it exists so a reviewer can determine **which revision is authoritative** without guessing.

### 0.1 Revision chain and what this revision covers

| Commit | Subject | Content |
| --- | --- | --- |
| `fd26da0` | Add extraction fidelity completion design gate | initial gate (superseded) |
| `d973c9a` | Tighten extraction fidelity representation-state gate | representation-state tightening |
| `3257f2d` | Revise extraction fidelity design after independent red-team | round-1 remediation |
| `66c1c77` | Tighten extraction fidelity v1 contract after red-team round 2 | round-2 remediation |
| *(this revision)* | Close round-2 blockers/ambiguities — design only | §21 closure map |

The closing task named `3257f2d` as "the current design commit"; the branch head at that moment was
`66c1c77`, a child of `3257f2d` that tightened the same single document (+361 / −290). This revision is
built **on top of `66c1c77`** so that no earlier remediation is discarded; nothing in `66c1c77` is
reverted. `3257f2d` is therefore historical, and this revision is the design as it stands.

The branch diff against `main` is **documentation-only**: one file
(`planning/blender/BLENDER_EXTRACTION_FIDELITY_COMPLETION_DESIGN.md`), zero production files. No
implementation drift can be present on this branch.

### 0.2 Authoritative baseline for every source claim; local-ref hazard

Every `path:line` citation in this document was verified against commit
`2ec5a84c0b4d82898a0fb8169844ddd5d93668d2` (= `origin/main`) checked out in a dedicated worktree.
Line numbers refer to that revision.

**Citation provenance convention.** A citation marked *(untracked working file)* refers to a file that
exists in the primary working tree but is **not tracked in the repository** (`git ls-files` does not
list it, and it is absent from the branch tree). Such citations are supporting context only: they may
not be treated as repository authority, and any contract claim that depends on them must be **proven by
the live gate** instead (see §11.3). Two files in this document fall in that class:
`tests/assets/blender/generate_asset.py` and `tests/merge_vertex_live_script.py`.

**Hazard — the local `main` ref is not the project baseline.** In the primary working tree,
`main` = `fb7e5e87755a45cae6d10a4e07e8a2c9ac231cf0` ("Merge PR #67: Unreal cross-process recovery
M4", 2026-09-05): 412 commits **behind** `origin/main`, and it does **not** contain `2ec5a84`. A
reviewer or script that runs `git diff main...<branch>` from that ref will produce a meaningless
diff. Use the SHA above, never the ref name.

### 0.3 D4 — `slots=True` working-tree drift (previously reported; NOT repaired here)

The drift is a **working-tree modification, not a commit**. It removes `slots=True` from frozen
dataclass declarations and edits one matching docstring line:

| File | HEAD blob sha256 | Primary-worktree sha256 | Delta (content) |
| --- | --- | --- | --- |
| `planning/blender/correction_authorization.py` | `1934f0de1eec8fd7…` | `faa218b9794f4f82…` | 4 declarations |
| `planning/blender/correction_contract.py` | `04692bfda3d69be6…` | `e477313106eb28fe…` | 3 declarations + 1 docstring line |
| `planning/blender/correction_planner.py` | `7400834fb3b6f4a6…` | `ba6acfe3ea803c70…` | 1 declaration |

`git diff --ignore-cr-at-eol` (which removes the CRLF checkout artifact) reports 8 insertions / 8
deletions — i.e. the drift is a real content delta of eight `slots=True` removals.

* **Where it lives:** the **primary** working tree (`Desktop/Atlas`), on branch
  `feat/blender-wave10-collection-normalization`, HEAD `2ec5a84` — 3 modified files, 31 untracked
  files, uncommitted and unstaged.
* **Status in the working tree used for this revision:** the design worktree is a clean checkout of
  `66c1c77`; `git status --porcelain` is empty there and the three files above carry **no** content
  delta. **D4 is absent from this revision and present only in the primary tree.**
* **Why it is recorded and not fixed:** those three files are gate-cleared correction artifacts whose
  pinned revisions are part of closed Wave-1/2/3 evidence; repairing, staging or reverting them is a
  change to that evidence and requires its own authorization. This milestone is a documentation-only
  change and does not touch them.
* **Consequence a reviewer must carry forward:** any local test run performed in the **primary** tree
  exercises a different revision of those three files than `HEAD`. D4 does not affect this design.
* **Explicit non-action list:** not repaired, not staged, not committed, not reverted, not re-pinned.

### 0.4 What this revision may touch

This revision touches **only this document**. No production Python, no correction executor or planner,
no canonical model (`SceneModel`/`MeshModel`/parser/validator), no schema v2, no write-back, and no
Unreal / optimization / workflow / persistence / recovery / autonomous-runtime surface.

## 1. Purpose and bounded claim

Atlas already has a canonical `SceneModel` / `MeshModel`, extraction payload schema v1, and a
deterministic health kernel. The remaining producer-side problem is that the real Blender extractor
substitutes or omits source facts that the canonical layer can represent.

This milestone is **not** full extraction fidelity. It is a bounded producer completion milestone for:

* object membership and the deterministic representative collection;
* object visibility source selection;
* transform extraction including quaternion rotation mode;
* mesh vertex/face extraction and the existing numeric policy;
* material-slot-name extraction;
* explicit omission semantics for normals, UVs, and local-frame data;
* deterministic payload encoding and cross-process evidence;
* preservation of the existing digest boundary.

No correction capability is added or changed here.

### 1.1 What this milestone does NOT deliver (non-claim boundary)

| Domain | v1 status | Where the boundary is defined |
| --- | --- | --- |
| normal fidelity | **not delivered** — the producer omits normals | §4.1 |
| UV fidelity | **not delivered** — the producer omits UVs | §4.2 |
| local-frame fidelity | **not delivered** — the producer omits `local_frame_id` | §4.4 |
| per-face material assignment | **not delivered** | §4.3 |
| complete multi-collection membership | **not delivered** — one lossy representative | §5.4 |
| evaluated/modifier geometry | **not delivered** — original `obj.data` only | §6 |
| non-mesh object geometry (CURVE/SURFACE/FONT/META/…) | **not delivered** — declared limitation | §5.5 |
| instanced collection contents | **not delivered** — declared limitation | §5.5 |
| cross-language byte-identical serializer | **not delivered** — semantic parity only | §8.3, §17 |
| representation-state provenance in the digest | **not delivered** — documented, unchanged | §11, §12 |

A later reader must not interpret this milestone as "all extraction fidelity solved". If a downstream
document needs a single statement, it is: *"Extraction fidelity v1 completes membership, visibility,
transform-source, material-slot, omission-state and determinism fidelity, and defers normals, UVs,
local-frame, richer material/membership domains and byte-parity serialization to their own gates."*

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

The extractor must not mutate Blender, save or persist a file, invoke a correction executor, create
authorization/receipt/workflow authority, retry, rollback, recover, dispatch actions, or infer
repairs.

A future real-asset write-back binding remains a separate design decision with its own authority
grant. This milestone grants nothing beyond read-only extraction.

## 3. Payload/model compatibility and the per-field producer encoding

Extraction payload schema remains **version 1** for this milestone. No field meaning or cardinality
changes.

The producer has **exactly one encoding per field and state**. Any state not listed below is not
producible by the v1 extractor:

| Payload field | v1 producer encoding | Resulting canonical value | Notes |
| --- | --- | --- | --- |
| `schema_version` | `"1"` | n/a | payload-only key |
| `scene_id`, `unit_system` | string | `SceneModel` fields | existing mapping |
| `object_id`, `name` | string (equal in v1) | `ObjectModel` fields | `object_id` = source object name |
| `collection` | string **or** JSON `null` | `Optional[str]` | `null` is a real value: "no representative child collection" (§5.4), **not** an omission placeholder |
| `parent_object_id` | string or `null` | `Optional[str]` | existing semantics |
| `location`, `scale` | 3-element float arrays | tuples | §7.1, §8.1 |
| `rotation` | 4-element float array `(w,x,y,z)` | tuple, normalized on parse | §7.2 |
| `visible` | JSON bool | bool | §7.3 |
| `mesh_id` | string (source object name) | `str` | §6 |
| `vertices` | array of 3-element float arrays | tuples | source order, §8.1 |
| `faces` | array of integer arrays | tuples of ints | source order |
| `materials` | **non-empty** array of non-empty strings, **or** `[]`, **or** key omitted | `tuple[str, ...]` | exactly three encodings, §4.3 |
| `normals` | **key omitted** (always) | `()`/`None` per §4.5 | never emitted in v1 |
| `uvs` | **key omitted** (always) | `()`/`None` per §4.5 | never emitted in v1 |
| `local_frame_id` | **key omitted** (always) | `None` | never emitted in v1 |

Consequences pinned by this table:

* the producer **never** emits `null` for `normals`, `uvs`, or `local_frame_id`;
* the producer emits **no** `normals`/`uvs`/`local_frame_id` keys at all, so the emitted mesh key set
  is exactly `{mesh_id, vertices, faces}` plus `materials` when §4.3 permits it. This is directly
  assertable (§15) and is the mechanical form of the omission rule;
* `collection: null` is deliberate and is not an omission placeholder: omission and value-null are
  different concepts and must not be conflated by a reader or a test.

A schema bump is mandatory before any of the following is introduced:

* per-corner/per-loop UV data;
* per-face material assignments;
* ordered multi-collection membership;
* provenance/availability state markers;
* a new canonical field;
* a changed field meaning or cardinality.

The extractor must never overload an existing field to avoid a schema bump.

## 4. Representation-state rules

The producer uses one encoding per field and does not use `null` as a v1 producer placeholder for the
deferred optional sequence fields.

### 4.1 Normals — producer-deferred (key omitted)

For every mesh, the v1 extractor omits the `normals` key regardless of whether Blender exposes
`MeshPolygon.normal`.

Reason: `MeshPolygon.normal` is **derived** data (Blender computes it from the polygon's own
vertices), while the canonical health kernel independently derives a comparison normal from the
**first three face corners** with a sign-agnostic 1° test (`planning/blender/mesh_health.py:353-372`).
Emitting Blender polygon normals without a dedicated semantic agreement gate can manufacture
`MESH_NORMAL_INCONSISTENT` on ordinary warped polygons: measured against the current kernel, a quad
warped by 0.1 in Z diverges by 4.035° (1.0 → 30.0°) and already exceeds the 1° threshold.

No parser or canonical-model tightening is authorized here. Existing `null`, `[]`, and omitted-input
acceptance remains unchanged for existing closed capabilities and fixtures (§4.5, §12).

Future normal-fidelity work requires its own design gate covering source semantics, derivation
algorithm, unit/orientation policy, warped polygons, undefined references, tolerance, and
compatibility with the existing kernel contract.

### 4.2 UVs — producer-deferred (key omitted)

For every mesh, the v1 extractor omits the `uvs` key regardless of Blender loop/corner UV
availability.

A face-level `(u,v)` cannot represent Blender loop-domain UVs without loss when a face has distinct
corner values; the canonical parser accepts only a 2-element pair per face
(`planning/blender/scene_model.py:98-102`). No averaging, first-corner selection, representative UV,
or other lossy collapse is permitted.

There is **no** caller-selectable UV-fidelity mode. `extract_scene()` remains a fixed-contract API;
omission is unconditional and is not an error.

A future UV gate must introduce a versioned corner-domain representation and update every closed
consumer that snapshots mesh UV state before emission is allowed.

### 4.3 Materials — closed rule

`MeshModel.materials` means exactly:

> the ordered names of the target object's **mesh datablock** material slots, read from
> `obj.data.materials` in Blender slot order.

Object-level `obj.material_slots` semantics are **out of scope** for v1: `material_slots` is an
object-level view that can also carry object-linked slots, whereas the payload field is scoped to the
mesh. OBJECT-linked slots are therefore not represented, and this is a declared limitation.

Rules:

* **zero slots** → emit `materials: []` (a legitimate empty, §4.5);
* **one or more slots, every slot assigned a non-empty name** → emit those names in slot order;
* **any slot empty/unassigned** → **omit** the `materials` key for that mesh rather than invent a
  token; the omission is all-or-nothing for that mesh (one empty slot discards every slot name for
  that mesh, which is the deliberate price of not fabricating a placeholder);
* per-face `material_index` assignments are explicitly **not represented** and must never be inferred
  from the slot-name tuple;
* material names are not lexically sorted; source slot order is canonical;
* pointer identity is never used for ordering.

Blender enforces non-empty datablock names, and the canonical string validator requires non-empty
strings (`planning/blender/scene_model.py:12-19, 83`), so the rule is satisfiable by construction; a
malformed/empty name reaching the extractor is a fail-closed condition (§10), not a token to invent.

**Canonical-collapse disclosure.** `materials: []` and an omitted `materials` key both parse to
`()` (`planning/blender/scene_model.py:206`). The payload therefore distinguishes *zero slots* from
*omitted because of an empty slot*, but **no canonical consumer can tell them apart**: nothing in the
kernel, the digest, or any correction executor reads the distinction. v1 claims only that slot names
were represented or were not; it makes no canonical-level claim about which of the two omission
reasons applied. Completing that distinction requires a versioned state marker (§3 bump list).

### 4.4 Local frame — omitted

`local_frame_id` is explicitly omitted in v1. It is not a populated producer field and is not part of
the v1 fidelity claim.

A future local-frame contract must define the Blender source datum and representation before
emission.

### 4.5 Omission semantics and canonical acceptance (measured)

**Producer rule.** For `normals`, `uvs`, and `local_frame_id`, **key omission is the sole producer
encoding**; the producer never emits `null` for them. For `materials`, the three encodings in §4.3
apply.

**Canonical acceptance (unchanged, measured).** The measured mapping from payload state to canonical
attribute is:

| Payload state | `MeshModel.normals` / `.uvs` | `MeshModel.materials` |
| --- | --- | --- |
| key absent | `()` | `()` |
| `[]` | `()` | `()` |
| `null` | `None` (stored unnormalized; conditional validation) | **parse error** (`SceneReportInputError`) |

Two consequences must be stated plainly, because they are the reason this section exists:

* **The canonical parser must not be tightened.** `null` remains a legal input for existing
  consumers, and `[]` with a non-empty face set remains accepted and is treated by the kernel as "no
  normals" (`planning/blender/mesh_health.py:332`, `if not mesh.normals: return`). Closed Wave-1/2/3
  fixtures deliberately build payloads with `"normals": null` (for example
  `tests/test_correction_executor_wave3_merge_vertex.py:59,74`), and the Wave-3 executor's identity
  helper preserves `None` as a distinct state on purpose
  (`planning/blender/correction_executor.py:2357-2364`). Producer omission rules are **stricter than**
  canonical acceptance rules; that asymmetry is intentional and is the whole content of this section.
* **The contradictory state is not rejected, and that is deliberate.** A hand-built or hostile payload
  carrying `normals: []` with a non-empty face set is canonically indistinguishable from omission and
  makes no fidelity claim; it is accepted (no parser change), it cannot be produced by the v1
  extractor, and the producer-side guarantee is enforced by the exact key-set assertion in §15
  instead. Introducing a rejection would be a canonical-layer change, which §3 and §12 forbid in this
  milestone.

**Representation state does not participate in `SceneReport.digest()` in v1.** The digest boundary
therefore remains based on the existing canonical fields (§11). This is documented behaviour, not a
claim of provenance equivalence between omitted and empty optional fields.

## 5. Scene membership: domain, traversal, ordering, representative, classes

### 5.1 The membership DOMAIN is a source-side rule (separate from encoding)

The v1 scene domain is the **set of objects reachable from the scene's root collection through
child-collection links, recursively**:

```text
domain(scene) = { o : o is linked into some collection reachable from scene.collection
                      via collection.child links, including scene.collection itself }
```

This is a rule about the **source scene graph**, not about the payload. It is expressible without any
Blender Python type: a producer needs an equivalent source graph (objects, their collection
membership, per-object data) and does not need to reproduce Blender internals.

**Domain and byte parity are separate rules.** §9 pins how a *known* object set is encoded and hashed;
§5.1 pins which objects are in scope. A future non-Blender producer must be handed the equivalent
source graph to compute the same domain; it is not expected to reimplement Blender's collection
system.

### 5.2 Traversal and deduplication

* Include each reachable source object **exactly once**, keyed by **source-object identity** during
  traversal.
* **Do not** deduplicate by `object_id`/name during traversal.
* The traversal **mechanism** is free; the **set** is the contract. Any implementation that yields the
  §5.1 set is conforming.
* The source-object identity key is in-process only: it is never emitted, never ordered on, and never
  enters hashing or canonical output.
* The root collection itself is reachable and its objects are included; its **name** is not eligible
  as a representative (§5.4).
* Objects linked to no collection, or only to collections outside the scene graph, are excluded by
  definition. `bpy.data.objects` is never a membership source (it is file-wide, not scene-scoped).
* Unavailable/ungovernable membership interfaces fail closed (existing behaviour; §10).

This source-identity deduplication prevents a multi-linked object from appearing twice **while
preserving the kernel's ability to report true duplicate canonical IDs** on hand-built or adapter
payloads (§12, §16).

### 5.3 Object ordering

Canonical objects are emitted sorted by `object_id` (== the source object name in v1) using **Unicode
code-point order**, i.e. Python `str` ordering. A non-Blender producer comparing UTF-8 byte sequences
obtains the same order, because UTF-8 encoding preserves code-point order.

### 5.4 Representative collection

The canonical `collection` field is a **representative**, not complete membership.

For each object:

1. consider only collections reachable from the scene root;
2. exclude the scene master/root collection itself;
3. among included child collections containing the object, choose the **lexicographically smallest
   collection name** using Unicode code-point order (`str` ordering);
4. if no included child collection contains the object, emit `collection: null`.

The v1 loss is explicit: multiple collection memberships are not represented in full, and choosing one
representative is a declared projection. A future complete membership contract requires a versioned
ordered collection list and must not reuse the single `collection` string.

### 5.5 Object classes and declared limitations

The v1 extractor emits an object record for every object in §5.1, once each.

| Class | v1 treatment |
| --- | --- |
| `MESH` | mesh geometry extracted (§6) |
| `EMPTY` | record extracted; `instance_collection` **not** expanded |
| `CURVE`, `SURFACE`, `FONT`, `META`, `LATTICE`, and other non-`MESH` classes | record extracted with `mesh=None`; **their non-polygon geometry is explicitly out of scope** |
| collection instance (an object referencing an instanced collection) | record extracted; instanced contents **not** expanded and **not** represented |
| linked/library objects | included when reachable through the scene collection graph; datablock linkage is **not** represented |
| modifier/geometry-node results | **not** evaluated; §6 |
| hidden / view-layer-excluded objects | **still in the domain** — hiding is not a membership predicate; visibility is represented separately (§7.3) |

Every row above is a **declared limitation** recorded by this gate, not an accidental omission. The
live evidence must state them (§14). If a required source interface for an included class is missing,
extraction fails closed rather than emitting a partial record.

## 6. Mesh identity, geometry domain, and ordering

* `mesh_id` remains the existing producer convention: `str(obj.name)`.
* This is **not** declared to be Blender datablock identity. Two objects sharing one mesh datablock
  may therefore receive **distinct** canonical `mesh_id` values, and the kernel keys `mesh_metrics` by
  `mesh_id` (`planning/blender/kernel.py:60-63`), so a shared datablock appears as separate per-object
  entries. Treating `mesh_id` as datablock identity is a future contract, not a v1 claim.
* Geometry domain: the **original** `obj.data` datablock. Evaluated/depsgraph geometry, modifier
  application, triangulation, smoothing, welding and topology repair are out of scope.
* Vertex order follows `obj.data.vertices` index order; face order follows `obj.data.polygons` index
  order. No sorting or reindexing of vertices/faces is permitted.
* A mesh with zero faces is a legitimate truthful state (Wave 11); a mesh with zero vertices remains a
  source-extraction failure (Wave 11 §4 boundary, unchanged by this milestone).

## 7. Transform and visibility fidelity

### 7.1 Location and scale

Location and scale are read from the authoritative `obj.location` and `obj.scale` components.
Missing/malformed required transform attributes **fail closed**; the extractor must not default
individual missing components to `0.0` or `1.0`, and must not treat a partially readable transform as
a successful result.

### 7.2 Rotation — closed by `rotation_mode`

Rotation source selection **is part of canonical extraction semantics**: the same stored angle triple
denotes a *different* rotation under different Euler orders, so `rotation_mode` selects the
conversion, not merely the channel.

| `rotation_mode` | Source channel | Conversion | v1 |
| --- | --- | --- | --- |
| `XYZ` | `obj.rotation_euler` | `euler_xyz_degrees_to_quaternion` (`planning/blender/transforms.py:114-131`), documented as the active `R = Rz(ez)·Ry(ey)·Rx(ex)` composition; canonical `(w,x,y,z)` | **emit** |
| `QUATERNION` | `obj.rotation_quaternion` | direct map; Blender component order `(w, x, y, z)` → canonical `(w, x, y, z)`; the canonical model normalizes on parse and rejects a zero quaternion (`planning/blender/transforms.py:147-151`) | **emit** |
| `XZY`, `YXZ`, `YZX`, `ZXY`, `ZYX` | — | **no conversion is defined in-tree** | **fail closed** |
| `AXIS_ANGLE` | — | no conversion is defined in-tree | **fail closed** |
| any other / unreadable `rotation_mode` | — | — | **fail closed** |

Rationale (measured, not asserted): the repository contains exactly **one** Euler→quaternion
convention, and it implements a single composition. Routing a non-`XYZ` mode's stored angles through
it mis-rotates ordinary multi-axis input: for stored angles `(30°, 40°, 50°)` the resulting rotation
is wrong by **44.900°**, for `(10°, 20°, 30°)` by **11.974°**, and for single-axis input by exactly
**0.000°**. A fixture that asserted the helper's output for a non-`XYZ` mode would therefore enshrine
a wrong rotation as the contract. Consequently v1 **refuses** non-`XYZ` Euler modes and
`AXIS_ANGLE` instead of silently converting them; adding those conventions is a future capability with
its own fixtures, not a v1 decision.

Two hard requirements follow, and both are test requirements (§14, §15):

1. **Independent validation of the `XYZ` convention.** The only multi-axis live-validated rotation in
   this repository is single-axis — the frozen asset's probes rotate about Z only
   (`tests/assets/blender/generate_asset.py:115-120`, *untracked working file*; the branch tree carries
   the asset but not its generator) — so the `XYZ` mapping itself is currently **assumed**, not proven,
   for multi-axis input. The live gate must include a two-axis `XYZ`-mode object whose expected
   canonical rotation is derived **independently of**
   `euler_xyz_degrees_to_quaternion` — e.g. from Blender's own `obj.matrix_local` rotation part — so
   the fixture cannot validate the helper against itself.
2. **Quaternion-mode positive coverage.** A quaternion-mode object with a non-identity, non-unit and
   unit quaternion must be covered deterministically and live, asserting component order and the
   canonical normalization behaviour.

No rotation failure may be converted into an identity quaternion. Any failure to read or convert the
selected channel is an extraction failure.

### 7.3 Visibility

The v1 canonical visibility source is the **data property** `obj.hide_viewport`:

```text
visible = not bool(obj.hide_viewport)
```

* **Property:** `obj.hide_viewport` (stored on the object datablock; file-persisted).
* **Polarity:** `visible = not hide_viewport`.
* **Context independence:** yes — it is a stored data property and does not require a view layer, a
  dependency graph, or an evaluation context. It is therefore deterministic in `--background` runs.
* **Unavailable/malformed** (attribute missing, or not interpretable as a bool): **fail closed** for
  the affected object. Substituting `True` is forbidden.

Declared exclusions, all intentional: view-layer hiding (`hide_get()`/`hide_set()`), render hiding
(`hide_render`), and collection exclusion are **not** represented by `ObjectModel.visible` in v1 and
are not membership predicates (§5.5). `visible_get()` is explicitly rejected as a source because its
value depends on the view layer/depsgraph and would make the canonical value context-dependent.

**Value-change disclosure.** Today's extractor resolves visibility to a constant `True`
(`planning/blender/bpy_extraction.py:44`). This milestone therefore **changes** the canonical `visible`
value for any object with `hide_viewport` set. `visible` participates in `scene_input_digest`
(§11), so that is a digest-moving change; it is a producer correction, not a digest-algorithm change.

## 8. Numeric policy and canonical serialization

### 8.1 Vertex coordinates

Vertex coordinates keep the existing producer rule: **six decimal places**. The operation is pinned
as **correctly-rounded, round-half-even, applied to the exact value of the (float32 → double widened)
coordinate** — i.e. Python's `round(value, 6)` semantics, which is what the current extractor already
does (`planning/blender/bpy_extraction.py:22`).

Two implementation constraints, stated because they are the usual way this rule silently diverges:

* float32 → double widening must be **exact** (Blender stores float32; `0.1` widens to
  `0.10000000149011612` and rounds to `0.1`);
* the rule must not be substituted by a reciprocal-multiply shortcut such as
  `nearbyint(x * 1e6) / 1e6`: that rounds the *intermediate product* rather than the exact value and
  is not guaranteed to agree with correctly-rounded decimal shortening.

No other emitted float is newly rounded in this milestone; all emitted floats must be finite and
representable by the canonical parser.

### 8.2 Canonical evidence encoding (normative for every gate hash)

Payload hashing uses exactly:

```text
json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
sha256( <that string>.encode("utf-8") )
```

This matches the repository's existing canonicalization convention
(`planning/blender/scene_report.py:135-140`).

Pinned number/typing behaviour (measured against the current Python toolchain, and normative for the
gate's evidence):

| Case | Emitted form |
| --- | --- |
| integral float | keeps a float form: `2.0` → `2.0` (never `2`) |
| negative zero | sign preserved: `-0.0` → `-0.0` |
| short decimals | shortest round-trip decimal form: `0.1` → `0.1`; `1e-07` → `1e-07` |
| integer fields (face indices) | JSON integers, never floats: `[0,1,2]` |
| non-ASCII strings | escaped because `ensure_ascii=True`: `é` → `\u00e9` |
| non-finite numbers | **refused** by `allow_nan=False` (and independently refused by the canonical parser) |

List order is preserved exactly, because every list in the payload carries semantic meaning (objects
sorted by `object_id`; vertices/faces in source order; `materials` in slot order).

### 8.3 Cross-language byte-parity disposition (explicitly downgraded)

**v1 claims semantic payload parity, not byte-identical JSON parity.** A future C++ producer must
reproduce field meanings, source-domain ordering rules, omission/failure semantics, the §8.1 rounding
rule and the §5.3/§5.4 code-point lexical ordering, and must produce canonical values that parse equal
under §8.2.

Byte-identical cross-language serialization is **explicitly deferred** to a separate serialization
gate with a shared, language-independent numeric encoding algorithm. The reason is concrete: the only
canonical serialization that exists in-tree is Python's `json`
(`planning/blender/scene_report.py:135-140`), and the exact byte form of a float depends on Python's
shortest-round-trip `repr`; asserting byte parity without a shared encoder would be an unverifiable
claim. The §8.2 rules are therefore **normative for the gate's own hashing only**, not a cross-language
promise.

## 9. Determinism protocol

Three runs are required, and all three must produce **identical payload values and identical SHA-256**
under §8.2:

| Run | Construction | Environment |
| --- | --- | --- |
| A | the fixture's canonical construction | `PYTHONHASHSEED=1` |
| B | identical construction to A | `PYTHONHASHSEED=2` |
| C | same semantic scene, **object/collection construction order changed** | any seed |

Rules for run C, stated because a careless reordering would change source-ordered domains and produce
a false failure (or hide a real one):

* **reorder only** object construction order and collection construction/creation order — i.e. things
  whose canonical order is *derived* by rule (`object_id` sorting, lexical representative selection);
* **do not reorder** source-domains whose order is defined as *source order*: vertex order, polygon
  order, and material-slot append order must be identical to A and B;
* additionally, include the sub-case of **linking the same object into two child collections in
  reversed order** across runs, which is the exact input the representative rule consumes and
  therefore the exact input a pointer/insertion-order-dependent implementation would get wrong.

Each run must record, as evidence: the payload SHA-256, the canonicalization identifier (§8.2), the
hash seed, and the fixture construction order used.

## 10. Fidelity and fail-closed rules

The extractor is a truth-preserving boundary.

```text
available + representable          -> emit the exact canonical value
available + unsupported/unrepresentable -> explicit v1 omission or explicit failure per field rule
malformed required source          -> fail closed
exception after partial traversal  -> fail closed; never return a successful partial payload
never                              -> fabricate, approximate, average, infer, normalize, or repair
```

Required fail-closed conditions include: missing/malformed coordinates; missing/malformed transform
channels; **unsupported or unreadable `rotation_mode`** (§7.2); unavailable/malformed
`hide_viewport` (§7.3); non-finite emitted numbers; malformed material slot names; unreadable
membership interfaces; an included object class missing a required source interface; duplicate payload
schema keys or an unsupported schema version; partial-traversal exceptions.

The payload validator remains responsible for payload shape; the deterministic kernel remains
responsible for health findings. **The extractor does not move every kernel finding into an extraction
failure.** In particular, duplicate canonical object IDs remain a kernel `OBJECT_ID_DUPLICATE`
finding for hand-built or adapter payloads
(`planning/blender/scene_health.py:77-88`); the extractor's traversal deduplication is
source-object-identity based, never name based (§5.2).

No partial payload may ever be returned as a successful `SceneModel`. If any object cannot be
extracted under its field rules, the extraction fails as a whole and no payload is emitted.

## 11. Digest participation and compatibility

### 11.1 Field table

`scene_input_digest` (`planning/blender/kernel.py:93-121`) is computed over exactly the following
fields; `SceneReport.digest()` includes it
(`planning/blender/scene_report.py:114-133`, `planning/blender/kernel.py:74-79`).

| Level | Field | In current digest | Changed by this milestone? |
| --- | --- | --- | --- |
| scene | `scene_id` | yes | no |
| scene | `unit_system` | yes | no |
| scene | `coordinate_frame` | yes | no |
| object | `object_id` | yes | no |
| object | `name` | yes | no |
| object | `collection` | yes | **yes** — new representative rule (§5.4) |
| object | `parent_object_id` | yes | no |
| object | `location` | yes | no (values unchanged for well-formed input; failures now refuse) |
| object | `scale` | yes | no (same as location) |
| object | `rotation` | yes | **yes** for non-`XYZ`/quaternion-mode objects (§7.2); no for `XYZ` |
| object | `visible` | yes | **yes** — constant `True` replaced by `hide_viewport` (§7.3) |
| mesh | `mesh_id` | yes | no |
| mesh | `vertices` | yes | no |
| mesh | `faces` | yes | no |
| mesh | `normals` | **no** | no digest effect |
| mesh | `uvs` | **no** | no digest effect |
| mesh | `materials` | **no** | no digest effect |
| mesh | `local_frame_id` | **no** | no digest effect |
| scene | `world_bounds` | **no** (derived, not digested) | no |

The `mesh` sub-object appears in the digest only when `ObjectModel.mesh is not None`; a meshless object
contributes `null`.

### 11.2 Consequences

* This milestone does **not** change the digest algorithm or the field set.
* Where it corrects a producer value that participates in the digest — `collection`, `visible`, and
  `rotation` for rotated-mode objects — the digest for the same source scene **legitimately changes**.
  That is a producer correction, **not** an executor contract rewrite, and it must not be described as
  a digest change.
* Correction artifacts built against an older source digest become **stale** and must fail their
  existing stale-source checks; they must never be silently reused across a changed digest. No
  correction-layer relaxation is authorized here, and no correction planner/executor is modified.
* `normals`, `uvs`, `materials` and `local_frame_id` do not participate, so the material-slot
  completion has **no** digest effect.

### 11.3 Frozen asset: must be proven, not assumed

The frozen asset (`tests/assets/blender/atlas_transform_validation.blend`, sha256
`cf618bdc1123734bf49bf6f22677ded3f2e6c3fa2803b97f7a6cf7c7c66f11aa`) must be shown to keep its digest
and its pinned report expectations under the v1 rules — **proof, not inference**. The structural
description below is *context from an untracked working file*
(`tests/assets/blender/generate_asset.py:41-47, 115-120`, *untracked working file*): the branch tree
carries the asset but **not** its generator, so no claim in this section may rest on that file. The
live gate is the authority. Context: the asset's 11 objects are each linked to the master collection
**and** one child collection, so the §5.4 rule is expected to yield the same representative names as the
current implementation, and no object is described as hidden, so §7.3 is expected to yield the same
`visible` values. The gate must assert this rather than rely on it.

The asset is a **regression anchor only**. It cannot exercise the positive v1 claims (no material
slots, no UV layer, single-axis Euler only, nothing hidden) — those come from the disposable fixtures
(§14). Existing pinned expectations to preserve:
`tests/test_live_blender_real_asset_gate.py:83-113` and `:228-265`.

## 12. Cross-capability compatibility disclosures (mandatory, verbatim scope)

These are consequences of this milestone for **closed** capabilities. Each is disclosed; none
authorizes a change to a closed capability.

1. **`normals=None` vs `normals=()` remain accepted by existing canonical consumers.** Both states are
   legal inputs today: validation is conditional on truthiness
   (`planning/blender/scene_model.py:73-82`), and the Wave-3 executor's identity helper preserves
   `None` as a distinct, documented state that must not compare equal to an empty tuple
   (`planning/blender/correction_executor.py:2357-2364`).
2. **Producer omission changes the live model state from `None` to `()`.** With key omission (this
   milestone's producer rule), live extraction yields `MeshModel.normals == ()` where today it yields
   `None` (measured mapping in §4.5). Because pre- and post-extraction states inside a single
   correction run both come from the same extractor, closed postconditions remain internally
   consistent.
3. **This must NOT trigger a parser change.** No tightening of `scene_model`/`extraction_payload` is
   authorized; closed Wave-1/2/3 fixtures intentionally use `"normals": null`
   (`tests/test_correction_executor_wave3_merge_vertex.py:59,74` and the wave-1/2 payload builders).
4. **Wave-3 MQ-5/MQ-6 include `materials`/`uvs`/`normals`/`local_frame_id` in their identity
   snapshots.** `_merge_mesh_identity_key` and `_merge_mesh_state_key`
   (`planning/blender/correction_executor.py:2370-2396`) are compared by MQ-5
   (`:2579`) and MQ-6.
5. **Once real materials are extracted, a merge on a material-bearing live fixture may legitimately
   fail MQ-5 if the harness does not preserve material slots.** The operator-gated live merge driver
   rebuilds the target mesh datablock and assigns it (`tests/merge_vertex_live_script.py:109-112`,
   *untracked working file*) without copying slot data, and reads slots only as evidence (`:138`,
   *untracked working file*). Previously both sides of the comparison were empty, so the loss was
   invisible; after this milestone it becomes a genuine postcondition failure. That is a **newly
   observable, correct** detection. This disclosure rests on the **tracked** MQ-5 identity comparison
   (`planning/blender/correction_executor.py:2370-2396, 2579`), not on the untracked line numbers: the
   consequence follows whenever a mutator rebuilds a mesh datablock without carrying slot data.
6. **This is a disclosed compatibility consequence, not permission to modify Wave 3 during this
   milestone.** No correction executor/planner/mapping change is authorized, and MQ-5/MQ-6 must not be
   weakened or given material-mutation authority to make a harness pass.
7. **Documentation staleness must be recorded as follow-up, never silently altered.** Known instances:
   (a) the Wave-3 `_merge_opt_seq` docstring's statement that `None` means "the extraction carried
   none" (`planning/blender/correction_executor.py:2360-2363`), which v1 live extraction will no longer
   produce; (b) any Wave-3/Wave-12 live record that describes live extraction as emitting
   `normals: null`; (c) this document's own §4.5 as the single source of truth for the producer
   encoding. Each becomes a separately authorized documentation task; none may be edited inside this
   milestone.

## 13. Live evidence model

The live boundary is Blender **4.4.3** with the pinned build identity `802179c51ccc`, and the existing
environment contract for live scripts (`ATLAS_BLENDER_EXECUTABLE`; `ATLAS_REPO_ROOT` where the harness
requires it).

The live gate may open the frozen `.blend` asset **read-only**. It must:

* SHA-256 the asset before the run;
* open it read-only and run extraction (no save, no `save_as_mainfile`, no `bpy.ops.wm.save*`);
* SHA-256 it after the run and prove the hash is unchanged;
* prove no `.blend` or `.blend1` was created or modified anywhere in the repository, and assert no new
  file appears in the asset directory;
* run with `--factory-startup` (or otherwise prove user preferences/auto-save cannot write outside the
  run), so that "no temp file" claims are mechanically checkable;
* prove no unrelated repository asset changed (the existing read-only pattern: content hash before and
  after the run, `tests/test_live_blender_real_asset_gate.py:58-64`, `:199-225`, with the read-only
  scene-state snapshot field at `:187`).

The disposable fixtures (§14) remain the primary positive fidelity mechanism.

## 14. Required live fixtures

### Fixture A — scoped fidelity positive (disposable scene)

Must contain:

* a mesh with multiple polygons in deterministic source order;
* **two or more non-empty material slots in a known order**;
* a **quaternion-mode** object with a non-identity quaternion, plus a second quaternion-mode object
  with a non-unit (un-normalized) source quaternion;
* a **two-axis `XYZ`-mode** Euler object, whose expected canonical rotation is derived **independently
  of `euler_xyz_degrees_to_quaternion`** (e.g. from `obj.matrix_local`'s rotation part) — this is the
  fixture that validates the `XYZ` convention rather than assuming it (§7.2);
* nested child collections;
* an object linked into two child collections, with the two link orders reversed across runs (§9);
* a master-only object (expected `collection: null`);
* an unrelated object and an unrelated non-mesh object;
* an object with `hide_viewport = True` and one with `hide_viewport = False`;
* **no** UV or normal fidelity expectation.

Expected v1 payload facts: exact material slot-name order; quaternion and Euler transform values
matching independently derived expectations; deterministic representative collection; master-only
`null`; visibility mapping; omitted `normals`/`uvs`/`local_frame_id` keys.

### Fixture B — explicitly unsupported domains (disposable scene)

* a mesh with a genuine Blender UV layer, including a face whose corners carry **distinct** UV values;
* a mesh with an **empty material slot**.

Expected v1 behaviour: `uvs` key absent; `materials` key absent (empty slot → all-or-nothing omission,
§4.3); no averaging, no first-corner selection, no empty-slot token, no error.

### Fixture C — membership, identity and object classes (disposable scene)

* a nested collection tree;
* one object in two child collections;
* one master-only object;
* one object reachable **only** through a nested collection;
* one object linked only to a collection **outside** the scene graph (must be excluded);
* one linked/library object if the runtime permits;
* one `instance_collection` Empty;
* one `CURVE` object.

Expected behaviour follows §5.2-§5.5, without expanding instanced or non-polygon geometry.

### Fixture D — frozen asset regression (read-only)

Open the frozen asset read-only and preserve **all** existing pinned expectations: scene id; object
count and sorted ids; `pitch` topology; probe world transforms; finding-code set; validation state;
asset SHA-256. Additionally assert the v1 producer semantics: `normals`/`uvs`/`local_frame_id` keys
absent, current material state, and the digest/pinned-expectation proof of §11.3.

### Fixture E — rotation-mode refusal (disposable scene)

* one object in a non-`XYZ` Euler mode (`XZY`/`YXZ`/`YZX`/`ZXY`/`ZYX`);
* one object in `AXIS_ANGLE` mode.

Expected behaviour: extraction **fails closed** with a named error for the affected object; no payload
is produced; no scene mutation occurs. These are refusal fixtures, deliberately **not** positive
conversion cases (§7.2).

## 15. Required deterministic tests

At minimum, the deterministic suite must cover:

* exact producer **key-set assertion** per mesh: `{mesh_id, vertices, faces}` plus `materials` only when
  §4.3 permits — in particular no `normals`, `uvs`, or `local_frame_id` key, and no `null` anywhere in
  the emitted payload;
* rotation matrix: `XYZ` (single-axis and **two-axis**, expected value derived independently),
  `QUATERNION` (component order, unit and non-unit source, canonical normalization),
  non-`XYZ` Euler **refusal**, `AXIS_ANGLE` **refusal**, unreadable `rotation_mode` **refusal**;
* missing/malformed transform attributes fail closed; no per-axis `0.0`/`1.0` defaults;
* `hide_viewport` mapping for `True`/`False`; absent/non-bool → fail closed;
* material-slot order from `obj.data.materials`; zero slots → `[]`; empty slot → key omitted;
  per-face `material_index` variation never appears in the payload;
* recursive collection traversal; representative lexical rule (including a case where the lexical
  minimum is the master collection name and must be skipped); master-only fallback;
  reversed multi-collection link order; source-object-identity deduplication; distinct same-named
  objects are not silently merged by traversal;
* duplicate canonical IDs remain **kernel-findable** on hand-built payloads (§10/§12);
* `CURVE`/`SURFACE`/`FONT`/`META`/`instance_collection` behaviour per §5.5;
* malformed/non-finite values fail closed; partial traversal exceptions never return a successful
  payload;
* canonical encoding vectors under §8.2 (integral floats, `-0.0`, `1e-07`, integer typing,
  non-ASCII escaping, non-finite refusal) and payload hash equality across the three §9 runs;
* digest assertions from the §11.1 table: changes to `materials`/`uvs`/`normals`/`local_frame_id` do
  **not** move `scene_input_digest`; changes to `collection`/`visible`/`rotation` **do**;
* frozen-asset digest and pinned expectations unchanged (§11.3).

Run the deterministic suite under **both Python 3.9 and Python 3.11**.

## 16. Required adversarial tests

At minimum: hostile object exposing a wrong rotation mode or channel types; quaternion with
malformed/non-finite components; axis-angle object; absent and non-bool `hide_viewport`; object with
one transform axis missing; material slot with an empty/unassigned material; malformed material name;
object in multiple collections with reversed insertion order; object only in the master collection;
duplicate source references to one object; hand-built payload with duplicate `object_id` values;
curve/surface/font/meta/instance-collection objects; UV layer with multiple values on one face;
exception after some objects were extracted; mutated/aliased source sequences; differing
`PYTHONHASHSEED` values; fabricated pointer-derived ordering; non-finite numeric payload.

Every hostile case must either fail closed or produce exactly the bounded payload state defined by this
design. No hostile case may silently fabricate data, and no partial payload may be treated as success.

## 17. C++ seam

The v1 C++ interoperability requirement is **semantic parity** (§8.3), not byte identity:

* the same source-to-canonical field meanings;
* the same source-domain ordering rules;
* the same omission/failure semantics (§3, §4.5);
* the same six-decimal, correctly-rounded half-even vertex rounding (§8.1);
* the same Unicode code-point lexical ordering for object order and representative selection (§5.3,
  §5.4);
* the same canonical values after parsing.

A future C++ producer must be **given** the equivalent source graph (§5.1) to compute the membership
domain; it is not required to reproduce Blender internals. A byte-identical serialization guarantee
requires a separate serialization gate with a shared language-independent numeric encoder.

## 18. Explicit non-goals

This milestone does not authorize: normal fidelity implementation; UV fidelity implementation;
local-frame fidelity; per-face material assignment; multi-collection canonical representation; schema
v2 or any new canonical field; parser/validator/model tightening; mesh repair; correction planning
changes; vertex merging; topology cleanup; normal reconstruction; UV reconstruction; material
reassignment; transform normalization; evaluated/depsgraph geometry extraction; write-back to Blender;
persistence/save; receipts/workflow/action-runner authority; retry/rollback/recovery; correction
dispatcher/orchestrator creation; caller-selectable extraction modes; any change to a closed
capability's contract.

## 19. Exit criteria

Implementation may begin only after an independent review confirms all of the following:

1. the v1 scoped claim explicitly excludes normal, UV and local-frame fidelity (§1.1);
2. rotation source selection is closed by `rotation_mode`, with `XYZ` + `QUATERNION` emitted and every
   other mode refused, plus independent validation of the `XYZ` convention (§7.2);
3. visibility source is exactly `obj.hide_viewport` with stated polarity, context independence and
   fail-closed behaviour (§7.3);
4. the material accessor is exactly `obj.data.materials`, the three encodings are closed, and the
   canonical-collapse disclosure is present (§4.3);
5. the membership domain, traversal deduplication, ordering, representative rule and master fallback
   are closed, and the domain is declared a source-side rule separate from encoding (§5);
6. non-mesh and instanced geometry limitations are declared, not implied (§5.5);
7. producer omission semantics are pinned per field, including the explicit statement that canonical
   acceptance is unchanged and must not be tightened (§4.5);
8. digest participation is tabulated field-by-field with the changed-field column, and stale-artifact
   consequences are recorded (§11);
9. the Wave-3 MQ-5/MQ-6 interaction and the remaining cross-capability disclosures are recorded
   without weakening any closed contract (§12);
10. the determinism protocol is executable, named, and includes the reversed collection-linking
    sub-case with source-ordered domains preserved (§9);
11. the frozen-asset read-only regression protocol is defined and its expectations named (§13, §14);
12. deterministic, adversarial and refusal fixtures are specified for Python 3.9 and 3.11 (§14-§16);
13. the C++ claim is limited to semantic parity until a separate byte-serialization gate exists (§8.3,
    §17);
14. no execution, persistence, workflow, recovery, or write-back authority exists in the milestone;
15. an independent reviewer re-gates this revision and does not self-clear it.

The milestone is complete only after deterministic, adversarial, Python 3.9/3.11 and live Blender
4.4.3 validation pass, and the extracted payload remains compatible with the existing canonical kernel
and closed correction contracts.

## 20. Required independent red-team questions

The reviewer must specifically attempt to break:

* the rotation-mode closure — in particular whether refusing non-`XYZ` modes is preferable to
  converting them, and whether the `XYZ` convention is validated independently of the helper;
* quaternion component order and canonical normalization;
* visibility semantics, its context independence, and its digest participation;
* material-slot accessor identity, the all-or-nothing empty-slot rule, and the canonical collapse of
  `[]` vs omitted;
* master-excluded representative semantics and the code-point lexical rule;
* linked/multi-collection/source-object deduplication and the preservation of kernel duplicate-ID
  findings;
* instance/curve geometry omission boundaries;
* omitted-vs-empty optional field behaviour and the asymmetry between producer rules and canonical
  acceptance;
* the per-field encoding table — whether any producible state is missing or ambiguous;
* Wave-3 MQ-5/MQ-6 compatibility and the material-slot preservation consequence;
* digest changes caused by corrected `collection`/`visible`/`rotation` values, and stale-artifact
  behaviour;
* the three-run determinism protocol, including whether run C's reordering scope is correct;
* frozen-asset regression, including whether the §11.3 coincidence is proven rather than assumed;
* the boundary between this read-only producer milestone and any future production write-back adapter.

Desired review output: concrete blockers, ambiguities, test gaps, and contract corrections — never a
score or ranking.

## 21. Closure map for this revision

| Item (round-2 finding) | Closed in | How |
| --- | --- | --- |
| BL-1 rotation source | §7.2 (+§14 Fixture A/E, §15) | mode table; `XYZ`+`QUATERNION` emit; non-`XYZ`/`AXIS_ANGLE` refuse; `(w,x,y,z)` pinned; measured 44.900°/11.974°/0.000° rationale; independent two-axis validation requirement |
| BL-2 milestone claim | header + §1.1 | non-claim table; explicit "does not deliver" list; file-name note; one-sentence downstream statement |
| BL-3 visibility | §7.3 | `obj.hide_viewport`, polarity, context independence, fail-closed, declared exclusions, value-change disclosure |
| BL-4 byte parity / serialization | §8.1-§8.3 (+§17) | rounding rule pinned; §8.2 encoding + number/typing behaviour pinned and measured; cross-language byte identity **explicitly downgraded** (permitted alternative), semantic parity normatively defined |
| BL-5 material accessor | §4.3 | `obj.data.materials`; slot order; slot names only; empty-slot omission; OBJECT-linked slots out of scope; per-face excluded; canonical-collapse disclosure |
| BL-6 digest participation | §11.1-§11.3 | explicit field table with a "changed by this milestone" column; consequences; frozen-asset proof requirement |
| AM-1 omission encoding | §3, §4.5 | one encoding per field/state; key omission for deferred fields; producer never emits `null`; `[]` only where legally empty; `collection: null` distinguished from omission |
| AM-2 no parser tightening | §4.5, §12.3 | explicit prohibition; closed-suite evidence cited |
| AM-3 present-empty semantics | §3, §4.3, §4.5, §15 | when `[]` is legal (zero slots); deferred fields never emitted; contradictory state documented as unreachable-and-unrejected, with the producer key-set assertion as the mechanical guarantee |
| AM-4 duplicate object IDs | §5.2, §10, §12.4 | traversal dedup by source identity; **not** by `object_id`; kernel `OBJECT_ID_DUPLICATE` preserved for hand-built/adapter payloads; no boundary rejection added |
| AM-5 unsupported classes | §5.5 (+§14 Fixture C) | CURVE/SURFACE/FONT/META/LATTICE → `mesh=None` and geometry out of scope; instance_collection not expanded; declared limitations table |
| AM-6 mesh identity / local frame | §6, §4.4 | `mesh_id = str(obj.name)`, explicitly not datablock identity, shared datablocks get distinct ids; `local_frame_id` omitted |
| AM-7 no caller UV mode | §4.2, §18 | no caller-selectable mode; unconditional omission; API fixed |
| AM-8 determinism run C | §9, §14 | reorder derived-order construction only; source-ordered domains preserved; reversed collection-linking sub-case required |
| AM-9 lexical ordering | §5.3, §5.4, §8.2 | Unicode code-point order pinned, with the UTF-8 byte-order equivalence stated |
| AM-10 domain vs encoding | §5.1, §17 | membership domain declared a source-side graph rule; parity is an encoding rule; C++ producer receives an equivalent graph |
| Disclosure 1-7 | §12 items 1-7 | each recorded with file:line evidence; item 5 (MQ-5 material-slot detection) disclosed; item 7 lists documentation-staleness follow-ups |
| Baseline / D4 | §0.1-§0.3 | authoritative revision chain; local-`main` hazard; D4 drift recorded with hashes, location and non-action list |
