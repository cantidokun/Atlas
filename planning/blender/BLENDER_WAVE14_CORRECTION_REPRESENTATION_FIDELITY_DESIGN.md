# Atlas Blender Wave 14 — Correction-Boundary Representation Fidelity (Material Slots)

**Status:** IMPLEMENTATION / VALIDATION IN PROGRESS
**Branch:** `feat/blender-wave14-representation-fidelity`
**Baseline:** Wave 13 merged to `main` at `bfcf147317122d5da5427698ee0a60c1c9ab790f`
**Scope class:** evidence / documentation only — no production semantic change

---

## 1. Problem statement

The correction contract already requires material-slot identity to survive a geometry-rebuilding
correction, and the live evidence for it was vacuous:

* `execute_merge_vertex` compares a target-mesh identity key that includes `tuple(mesh.materials)`
  in **MQ-5** (`planning/blender/correction_executor.py`, `_merge_mesh_identity_key` / MQ-5), and
  every unrelated mesh's full state including materials in **MQ-6**. Both postconditions therefore
  already claim material-slot preservation.
* Every live fixture that undergoes a geometry rebuild was **material-free**, so MQ-5 only ever
  compared `() == ()` — the material clause could not fail.
* The Wave 13 live harness *recorded* a data-slot list but no gate ever asserted it.
* The Wave 13 live mutation primitive (`bpy.data.meshes.new(...)` + `from_pydata(...)` +
  `obj.data = new_mesh`) replaces the mesh datablock. A disposable Blender 4.4.3 probe
  (build `802179c51ccc`) demonstrated that this pattern drops every material slot of the target
  object, orphans the superseded datablock, and — for the unassigned / OBJECT-linked configurations —
  changes the payload's representation state while remaining invisible to the canonical model.

Wave 14 closes the evidence gap: the material-bearing real-Blender case now exercises MQ-5
non-vacuously, the same-datablock rebuild becomes the normative reference primitive, the lossy
replacement pattern is retained **only** as a diagnostic RED case, and the classes the canonical
model cannot express are asserted at the raw Blender boundary and documented as limitations.

## 2. Contract basis (unchanged by this wave)

| Element | Source | Wave 14 effect |
| --- | --- | --- |
| MQ-5 target object/mesh identity (incl. `materials`) | `correction_executor.py` (merge postconditions) | unchanged |
| MQ-6 unrelated object/mesh full state (incl. `materials`) | same | unchanged |
| `materials` decision tree (§4.3) | `bpy_extraction.py` | unchanged |
| Producer omission semantics for OBJECT-linked / unassigned slots | `bpy_extraction.py` §4.3 branch 2 | unchanged (asserted, not altered) |
| Representation-state fact (`materials:omitted`) | `extraction_payload.py` (`payload_representation_state`) | unchanged; used as live evidence |
| Receipt schema and `field_count` | merge executor receipt | unchanged (no new field) |

## 3. Fidelity classification matrix

| Property | Classification |
| --- | --- |
| Slot count | CANONICALLY PROVABLE |
| Slot order | CANONICALLY PROVABLE for assigned/data-linked, all-assigned cases |
| Material names | CANONICALLY PROVABLE |
| Material datablock identity | NOT CURRENTLY PROVABLE |
| Unassigned slots | RAW-BLENDER-BOUNDARY-ONLY |
| OBJECT-linked slots | RAW-BLENDER-BOUNDARY-ONLY |
| `[]` vs key-omitted distinction | NOT CURRENTLY PROVABLE |
| Polygon `material_index` | NOT CURRENTLY PROVABLE / out of contract |
| Other material metadata | NOT CURRENTLY PROVABLE / out of contract |
| Datablock replacement / orphan creation | RAW-BLENDER-BOUNDARY-ONLY |

"CANONICALLY PROVABLE" means the frozen canonical model represents the property and the existing
MQ-5/MQ-6 comparison can detect a change. "NOT CURRENTLY PROVABLE" means the frozen model does not
represent the property at all, so no canonical comparison can detect a change in it.
"RAW-BLENDER-BOUNDARY-ONLY" means the property exists in Blender and is asserted by the live gate
against raw Blender state, but the canonical model cannot see it.

### 3.1 Why the boundary-only classes are boundary-only

`bpy_extraction.py` §4.3 decides the `materials` key per mesh:

1. a slot whose material carries a malformed/empty name → fail closed;
2. any OBJECT-linked slot (`slot.link == 'OBJECT'`) or unassigned slot (`slot.material is None`) →
   **omit the `materials` key entirely**, and this branch dominates;
3. zero data slots (and no branch-2 slot) → emit `[]`;
4. otherwise the data-slot names in exact source order.

Consequences (probe-verified, Blender 4.4.3 / `802179c51ccc`):

* configuration **C1** (all slots DATA-linked, all assigned): canonical `materials` is the ordered
  name tuple → MQ-5 is a real detector; a datablock replacement fires it.
* configuration **C2** (one OBJECT-linked slot) and **C3** (one unassigned data slot): the key is
  omitted, so canonical `materials` is `()` **before and after** — MQ-5 cannot see a total slot loss
  (probe: raw slot table 2 entries → 0, MQ-5 silent). Only raw Blender evidence detects it.
* in C2/C3 a datablock replacement also flips the payload from key-omitted to `[]`, i.e. it changes
  the payload-level representation state while the canonical tuple stays `()`.

## 4. Explicit non-claims

Wave 14 does **not** claim, and must not be read as claiming:

* that raw Blender assertions extend the canonical Atlas contract — they are boundary evidence for
  properties the canonical model does not represent;
* material datablock *identity* (only names are represented; Blender names are unique per datablock
  type, and nothing here claims pointer identity, per-object substitution detection, or
  same-name/different-datablock detection);
* any statement about normals, UVs, local-frame data, polygon `material_index`, material node
  metadata, material properties, or any other unextracted material state;
* that a same-datablock mutation is a canonical invariant — it is the **normative reference
  primitive**, not a contract rule (see §5);
* that orphan creation is now an Atlas authority rule or that automatic cleanup exists — no cleanup
  behaviour is introduced anywhere;
* that W1/W2 corrections satisfy this fidelity boundary today — they have no committed live gate, and
  this wave does not create one.

## 5. Reference primitive decision

**Pattern B — same-datablock table rebuild — is the normative reference implementation pattern for
geometry-rebuilding corrections when represented material slots must be preserved:**

```python
mesh.clear_geometry()
mesh.from_pydata(authorized_vertices, [], authorized_faces)
mesh.update()
```

It rebuilds the authorized tables on the existing datablock, so the object's slot table (including
unassigned and OBJECT-linked slots) is untouched, the datablock inventory is unchanged, and
MQ-5/MQ-6 keep their existing meaning. It is the pattern the already-merged Wave 7 live gate uses.

**Pattern A — `bpy.data.meshes.new(...)` + `from_pydata(...)` + `obj.data = new_mesh` — is
SUPERSEDED as the normative reference primitive**, because it can lose material slots: it truncates
the object's slot table to the new (empty) datablock's table, which destroys assigned, unassigned and
OBJECT-linked slots alike, and it leaves the superseded datablock orphaned. Pattern A is retained in
the Wave 14 live gate **only** as a deliberately lossy diagnostic RED case that proves the gate can
detect material-slot loss.

Datablock replacement remains **canonically legal** (`MQ-5` records that the datablock may be
replaced while identity may not change): replacement is legitimate whenever the resulting represented
state stays valid. Wave 14 demotes replacement from the normative reference primitive; it does not
forbid it, does not add validation for it, and does not add cleanup authority. A future operation
that genuinely needs a replacement must carry its own design gate covering slot-state transfer.

Wave 6's bmesh in-place deletion (`bmesh.ops.delete` + `bm.to_mesh(mesh)`) is an equally conformant
in-place alternative already live-validated by the Wave 6 gate; it also preserves the full slot table.

## 6. Coverage

* **REPAIR_MERGE_VERTEX (primary)** — primitive demoted (Pattern A → Pattern B), material-bearing
  fixtures, raw slot assertions, anti-vacuity assertion, diagnostic RED case.
* **REMOVE_DUPLICATE_VERTICES (Wave 7) and REMOVE_ISOLATED_VERTICES (Wave 6)** — assertion
  strengthening only. Their existing primitives (same-datablock rebuild; bmesh in-place) already
  preserve slots; no correction implementation, authority or receipt behaviour is changed.
* **W1/W2 corrections** — out of scope: no committed live gate exists for them, so requiring live
  representation fidelity there would be a different milestone (creating boundary evidence).
* The **canonical contract, extraction producer, planner, executor, authorization, receipt schema,
  Temporal and Unreal surfaces are untouched.**

## 7. Evidence obligations

1. Offline discriminators (no bpy, existing MQ-5 mechanism only): a faithful mutator on a
   material-bearing fixture completes with MQ-1…MQ-7 green; drop / add / reorder / substitute
   mutators are refused with `failure_code == "MQ-5"` after exactly one mutation, with no rollback.
2. Limitation tests documenting what canonical MQ-5 cannot detect: `[]` vs omitted-key collapse in
   the parser, unassigned-slot loss, OBJECT-link loss, and same-name substitution.
3. Live boundary: a material-bearing positive case (canonical tuple non-empty pre and post, raw slot
   table equal, slot count/order/names preserved, inventory unchanged), an unassigned-slot case and
   an OBJECT-linked case asserted from raw state with the canonical omission asserted rather than
   assumed, and a diagnostic Pattern-A case that must fail through raw evidence and MQ-5.
4. Discriminator proof: with the superseded Pattern A primitive in place, the material-bearing
   positive case must fail; with Pattern B it must pass.

## 8. Frozen boundaries

Wave 14 does not reopen: Extraction Fidelity v1, `bpy_extraction.py`, `extraction_payload.py`,
`scene_model.py`, `kernel.py`, `scene_report.py`, correction authorization/planner/contract/mapping
semantics, executor authority semantics, the MQ-1…MQ-7 vocabulary and receipt schema, normals, UVs,
local-frame data, standalone edges, non-manifold repair, invalid-index repair, bounds-overlap repair,
invalid-transform repair, duplicate-object-ID repair, persistence/recovery, workflow/action-runner
(incl. the autonomous boundary modules), Temporal, Unreal.

Remediation for this wave is confined to test/live-harness code plus documentation, plus one
comment-only supersession inside `correction_executor.py` (W2 primitive guidance) and the Wave 13
live-driver wording that previously called the replacement pattern normative.
