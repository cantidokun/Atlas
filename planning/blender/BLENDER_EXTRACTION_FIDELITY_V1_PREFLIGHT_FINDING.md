# Atlas Blender — Extraction Fidelity v1 — Frozen-Asset Preflight Finding (facts and digests)

**Status:** EVIDENCE RECORD (design track) — no implementation, no code change.
**Track:** Blender canonical extraction — Extraction Fidelity v1 pre-implementation preflight.
**Baseline (authoritative):** `origin/main` = `2ec5a84c0b4d82898a0fb8169844ddd5d93668d2` (Wave 12 merged).
**Design branch:** `feat/blender-extraction-fidelity-design`.
**Related design sections:** §13 (pre-implementation rotation-mode enumeration), §11.3 (frozen-asset
anchor), §21.4 (preflight anchor revision).
**Content rule:** measured facts and digests only. No script, fixture, capture file or source code is
stored in this record; the inspection scripts were kept outside the repository
(`%LOCALAPPDATA%\Temp`, host-side scratch).

## 1. Engine and method

| Item | Value |
| --- | --- |
| Engine | Blender 4.4.3 (`bpy.app.version_string`) |
| Build hash | `802179c51ccc` (`bpy.app.build_hash`) |
| Build commit date | 2025-04-29 (`bpy.app.build_commit_date`) |
| Invocation | `--background --factory-startup` (no user preferences, no auto-save, no startup scene) |
| Access mode | read-only: `wm.open_mainfile` only; no `wm.save*` / `save_as_mainfile`, no datablock write, no state-mutating operator |
| Inspection scope | the single scene `atlas_validation`, every object, every collection datablock, and the full scene collection tree |
| Scripts | kept outside the repository by design; none is stored here |

Method for the *previous producer* column, both digests and both canonical payload hashes: the frozen
asset was opened read-only and the **unmodified** current producer
(`planning/blender/bpy_extraction.py`, worktree sha256 `ca5e6709a4019866ce8ad72b5f17167ceae7d09f832df96c845a93068688e8e3`)
was run through the real canonical path
(`extract_scene` → `payload_to_scene_model` → `run_scene_health`) and its report, `scene_input_digest`,
`input_digest` and canonical payload hash were recorded. The v1 values were then derived by applying the
cleared §5.1/§5.2/§5.4 membership and representative rules and the §3/§4.3/§4.4/§4.5 field-encoding
rules to the measured source graph, and re-running the same real canonical path on the resulting
payload. **No v1 producer exists yet and no producer file was modified in this work.**

## 2. Asset identity

| Item | Value |
| --- | --- |
| Path | `tests/assets/blender/atlas_transform_validation.blend` |
| Size | 461338 bytes |
| SHA-256 before inspection | `cf618bdc1123734bf49bf6f22677ded3f2e6c3fa2803b97f7a6cf7c7c66f11aa` |
| SHA-256 after inspection | `cf618bdc1123734bf49bf6f22677ded3f2e6c3fa2803b97f7a6cf7c7c66f11aa` |
| Change | none |
| mtime before / after | `2026-09-14 21:02:15` / `2026-09-14 21:02:15` — unchanged |

The asset is the pinned anchor named by design §11.3; its SHA-256 matches that section's pin exactly.

## 3. Object rotation-mode enumeration (the §13 pre-implementation check)

Distribution over the asset's 11 objects: **`{XYZ: 11}`**. Every object uses a supported mode, so §7.2's
refusal rule conflicts with nothing on this asset and the §13 pre-implementation condition is satisfied.
Class split: **9 `MESH`, 2 `EMPTY`** (`goal_left`, `goal_right`).

| # | Object | Type | `rotation_mode` | `hide_viewport` | `users_collection` (source order) | previous producer `collection` (`users_collection[0]`) | v1 `collection` (§5.4) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `goal_left` | EMPTY | XYZ | false | `["Goals", "Scene Collection"]` | `Goals` | `null` |
| 2 | `goal_right` | EMPTY | XYZ | false | `["Goals", "Scene Collection"]` | `Goals` | `null` |
| 3 | `leaf` | MESH | XYZ | false | `["Structure", "Scene Collection"]` | `Structure` | `null` |
| 4 | `mid` | MESH | XYZ | false | `["Structure", "Scene Collection"]` | `Structure` | `null` |
| 5 | `pitch` | MESH | XYZ | false | `["Field", "Scene Collection"]` | `Field` | `null` |
| 6 | `probe_combined` | MESH | XYZ | false | `["Structure", "Scene Collection"]` | `Structure` | `null` |
| 7 | `probe_identity` | MESH | XYZ | false | `["Structure", "Scene Collection"]` | `Structure` | `null` |
| 8 | `probe_nscale` | MESH | XYZ | false | `["Structure", "Scene Collection"]` | `Structure` | `null` |
| 9 | `probe_rot` | MESH | XYZ | false | `["Structure", "Scene Collection"]` | `Structure` | `null` |
| 10 | `probe_trans` | MESH | XYZ | false | `["Structure", "Scene Collection"]` | `Structure` | `null` |
| 11 | `root` | MESH | XYZ | false | `["Structure", "Scene Collection"]` | `Structure` | `null` |

Non-zero rotations: `probe_rot` and `probe_combined` carry a single-axis Z rotation
(`rotation_euler = (0, 0, 90°)`); every other object has a zero rotation triple. No object carries a
quaternion-mode rotation, a material slot, a UV layer, or a hidden state.

## 4. Scene-graph reachability finding

| Fact | Measured value |
| --- | --- |
| Collections reachable from `scene.collection` by recursive child links | `["Scene Collection"]` — the master collection only |
| `scene.collection.children` | `[]` |
| Nested child collections anywhere in that tree | none |
| View-layer layer-collection root children (`ViewLayer`) | `[]` |
| Scene count in the file | 1 (`atlas_validation`) |
| Master-collection object membership | all 11 objects |
| View-layer object set | the same 11 objects |

## 5. Orphan collection finding

| Collection | Exists in `bpy.data.collections` | Objects held | Linked into any scene's collection tree |
| --- | --- | --- | --- |
| `Field` | yes | 1 (`pitch`) | **no** |
| `Goals` | yes | 2 (`goal_left`, `goal_right`) | **no** |
| `Structure` | yes | 8 (`leaf`, `mid`, `probe_combined`, `probe_identity`, `probe_nscale`, `probe_rot`, `probe_trans`, `root`) | **no** |

`Field`, `Goals` and `Structure` are therefore **orphan collection datablocks**: they hold objects and
appear in `obj.users_collection`, but they are reachable from `scene.collection` by no chain of
child-collection links, so they are outside the §5.1 reachable domain and are not eligible as the §5.4
representative (step 1 restricts the candidate set to reachable collections). The objects themselves
remain in the domain because they are linked into the master collection.

## 6. Representative-collection delta (the re-derived §11.3 anchor)

| Measure | Previous producer (`users_collection[0]`) | v1 producer (§5.4, unchanged rule) |
| --- | --- | --- |
| `collection` values | `Goals` (2 objects), `Field` (1 object), `Structure` (8 objects) | `null` for all 11 objects |
| Objects whose `collection` moves | — | **11 / 11** |
| Distinct values before → after | `{Goals, Field, Structure}` → `{null}` | |

`collection: null` is the correct v1 encoding for "no included child collection contains the object"
(§5.4 step 4; §3 states `null` is a real canonical value, not an omission placeholder).

## 7. Values NOT changed by the v1 producer contract (measured)

| Field / expectation | Previous producer | v1 producer | Changed |
| --- | --- | --- | --- |
| `scene_id` | `atlas_validation` | `atlas_validation` | no |
| object count / mesh object count | 11 / 9 | 11 / 9 | no |
| object IDs and their order | the same 11 name-sorted IDs | the same 11 name-sorted IDs | no |
| `unit_system` | `METERS` | `METERS` | no |
| finding set | `set()` (empty) | `set()` (empty) | no |
| validation state | `production_ready` | `production_ready` | no |
| `pitch` face cardinalities | `[3, 4, 5]` | `[3, 4, 5]` | no |
| probe world points (all mesh objects) | derived world points | identical | no |
| `visible` (all objects) | `true` | `true` (`hide_viewport = false`) | no |
| `rotation` (all objects) | from `rotation_euler` (mode not inspected) | identical values (all objects `XYZ`, single-axis Z) | no |
| `materials` (all meshes) | `[]` | `[]` (zero data slots, no OBJECT-linked slot) | no |
| mesh key set | `{mesh_id, vertices, faces, normals, uvs, materials, local_frame_id}` | `{mesh_id, vertices, faces, materials}` | yes — deferred keys omitted by §4.1/§4.2/§4.4 (no digest effect, §11.1) |

## 8. Digest transitions

Canonical evidence encoding (§8.2): `json.dumps(payload, sort_keys=True, separators=(",", ":"),
ensure_ascii=True, allow_nan=False)`, then SHA-256 over the UTF-8 bytes.

| Quantity | Previous producer | v1 producer (§5.4 representative) |
| --- | --- | --- |
| `scene_input_digest` | `8d009d0d8cb7b3ed9604dfca753c998faceb839f1bcf17f7336e3676e54eb331` | `ee430d6fdc69928b9c91284deda96c14cf3e25d745aa14cfab6c51dabf3a3203` |
| `input_digest` | `13bbf29c69449a9c9f825e9fe4212acc3c4c62f519c1aa989d0f2aed1fecf92b` | `d90895bae02e30502cb9077b219b67cc4fbe104f3cbab664850c9346dc60ddfb` |
| canonical payload SHA-256 | `21f8584aa0199f395abdbd920e61d4368ce97dd12fa7afb825957d3ce5fbdd76` | `4985c62d7de9b0972ef4fe114aa4a32d73e541d6d0b01f61811c74ce74295d07` |

The single cause of both digest transitions is the `collection` field: `collection` participates in
`scene_input_digest` (design §11.1), the representative value moves for 11 / 11 objects, and every other
digested field keeps its value (§7 above). This is the producer correction disclosed by §11.2; it is not
a digest-algorithm or field-set change.

## 9. Read-only and scope statements

* **No `.blend` was created or modified.** The asset's SHA-256 and mtime are identical before and after
  the inspection (461338 bytes, `cf618bdc…`, `2026-09-14 21:02:15`). Every run used
  `--factory-startup`, opened the asset read-only and never called a save operator. A repository-wide
  sweep of `*.blend` / `*.blend1` found no file with an mtime inside the inspection window; the newest
  pre-existing `.blend*` file in the tree predates this work.
* **No production code was changed.** `planning/blender/bpy_extraction.py` retains its pre-existing
  content (`ca5e6709a4019866ce8ad72b5f17167ceae7d09f832df96c845a93068688e8e3`); no module, test, fixture,
  schema, parser, validator or canonical model file was edited for this finding.
* **The design change accompanying this record is documentation-only** (design §11.3/§21.4 revision):
  no rule changes, and §5.1/§5.4 are unchanged.

## 10. Conclusion

**The frozen asset exposes a stale §11.3 anchor premise; §5.4 remains unchanged.**

The premise — that the asset's objects are each linked to the master collection **and** one reachable
child collection, so the §5.4 representative would equal the current implementation's value — is
measured false: the three named collections are orphan datablocks outside the §5.1 reachable domain, and
the §5.4 representative is `null` for all 11 objects. The resulting digest transition is the legitimate,
already-disclosed producer correction of §11.1/§11.2; the §5.4 representative rule itself is not
contradicted and is not modified.

## 11. What this record does NOT claim

* It is **not** a live gate of the v1 producer — no v1 producer exists at this revision; the v1 column
  is the cleared rules applied to the measured source graph and re-run through the real canonical
  pipeline.
* It makes no claim about any other asset, fixture, capability or milestone.
* It does not assert that any implementation, test, fixture or gate is complete; it authorises nothing.
* The frozen asset remains a **regression anchor only** and is **not** a positive anchor for
  representative child-collection semantics, which stay with the disposable fixtures (design §14).
