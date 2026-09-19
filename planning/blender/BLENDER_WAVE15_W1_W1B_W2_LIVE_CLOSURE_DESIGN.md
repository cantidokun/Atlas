# Atlas Blender Wave 15 — W1/W1b/W2 Live Boundary Closure Design

**Status:** DESIGN — implementation NOT started (this document is the pre-implementation package)
**Base HEAD:** `a3b6d6c2cb877e55835712001f0b41721ee509b2` (`main`)
**Scope class:** live-boundary evidence closure + documentation — **zero production semantic changes**
**Predecessors:** Wave 13 `REPAIR_MERGE_VERTEX` (merged), Wave 14 representation fidelity (merged,
`BLENDER_WAVE14_CORRECTION_REPRESENTATION_FIDELITY_DESIGN.md`)
**Design review status:** independent design review **CLEAR WITH MINOR FINDINGS**. F-1 (engine
representability) was resolved in the design round (§M.1–M.6, disposition **CASE A / LIVE-POSITIVE**);
the final GLM 5.3 pre-implementation red-team raised **F-1 (W1 duplicate/winding evidence)**,
**F-2 (W1b stale-degeneracy live negative)**, **F-3 (W2 authorization receipt honesty)** and
**F-4 (raw fidelity assertions remain test-only)**, all four closed in this revision
(§C.1, §D.D, §E.1, §F.1) with the evidence recorded in §M.7–§M.9.

---

## 0. Authority and provenance

* **The executable code and the deterministic tests on `main` are the SOLE contract authority.** For
  these three capabilities that means: `planning/blender/correction_mapping.py` (classification rows),
  `planning/blender/correction_planner.py` (proposal derivation, winding aggregation),
  `planning/blender/correction_executor.py` (`_execute_face_removal`,
  `execute_remove_duplicate_face`, `execute_remove_degenerate_face`,
  `execute_repair_face_winding`), `planning/blender/correction_authorization.py`, and the tests that
  pin behaviour (`tests/test_correction_executor_wave1.py` 32, `..._wave1b_degenerate.py` 31,
  `..._wave2_winding.py` 53, `tests/test_correction_authorization.py` 77, `tests/test_correction_planner.py` 53,
  `tests/test_correction_planner_winding_aggregation.py` 28).
* **Dangling historical citation — explicitly non-authoritative.** The executor's Wave-2 comment cites
  `planning/blender/BLENDER_WAVE2_AUTHORIZATION_AND_WINDING_DESIGN.md` (§1.2/§1.4/§4.4). **That file
  is not present in `main`**; only an untracked working-tree copy exists elsewhere. The citation is
  therefore a *dangling* reference: it is historical context, it is **not** an authority this milestone
  may rely on, and no requirement below rests on it. The same applies to the other absent Wave 1/1b/2
  narratives (`BLENDER_WAVE1*`, `BLENDER_WAVE2_CANDIDATE_REVIEW.md`,
  `BLENDER_WAVE2_LIVE_WINDING_VALIDATION.md`). Where a narrative statement would contradict the code
  and tests in `main`, the code and tests win. **This document does not reconstruct them.**
* **Scope.** This document defines only the live-boundary closure milestone: what a real-Blender 4.4.3
  gate must prove for three already-implemented, already-tested correction contracts, and what it must
  not claim. It adds no capability, no authority, no canonical field, no extraction field and no new
  finding code.
* **Zero frozen production-file changes for this closure task.** Writing/committing this document
  changes no production file: `bpy_extraction.py`, `extraction_payload.py`, `scene_model.py`,
  `kernel.py`, `scene_report.py`, `correction_executor.py`, `correction_planner.py`,
  `correction_mapping.py`, `correction_authorization.py`, the receipt schemas and the frozen asset are
  all unchanged (§K, §M.10).

---

## A. Problem statement

Three correction contracts are implemented, determined and tested **only against in-memory
`SceneModel` mutation**:

| Capability | Correction type | Executor entry point | Tests in `main` | Committed live gate |
| --- | --- | --- | --- | --- |
| W1 | `REMOVE_DUPLICATE_FACE` | `execute_remove_duplicate_face` | 32 | none |
| W1b | `REMOVE_DEGENERATE_FACE` | `execute_remove_degenerate_face` | 31 | none |
| W2 | `REPAIR_FACE_WINDING` | `execute_repair_face_winding` | 53 | none |

`grep -rln "REMOVE_DUPLICATE_FACE\|REMOVE_DEGENERATE_FACE\|REPAIR_FACE_WINDING" tests/*live*` returns
nothing. Consequences:

1. the **mutation primitive** for each capability has never been exercised against real Blender data —
   the in-memory tests inject a canonical mutator, so they prove the *decision logic*, never the
   *engine contact*;
2. the Wave 14 representation-fidelity obligations (material slots, raw slot tables, datablock
   inventory) have never been asserted for these three capabilities;
3. the W1b degeneracy sub-cases had never been shown to be engine-representable at all (F-1 design
   round — now resolved, §D.B);
4. the deterministic suites cannot detect engine-specific hazards (datablock replacement, material-slot
   loss, orphaned datablocks, loop-order surprises, save attempts);
5. the co-emission, survivorship and renumbering behaviour of the W1 duplicate repair had never been
   pinned (red-team F-1, §C.1);
6. execution-time **revalidation** (rather than a prebuilt happy path) had never been demonstrated
   (red-team F-2, §D.D);
7. the W2 receipt's honesty on negative authorization paths had never been required (red-team F-3,
   §E.1);
8. the containment of raw Blender assertions as test-only evidence had never been stated (red-team
   F-4, §F.1).

Wave 15 closes exactly that evidence gap under the discipline Waves 3/13/14 used for
`REPAIR_MERGE_VERTEX`. **It implements no new behaviour.**

---

## B. Authority classification

### B.1 W1 / W1b — DETERMINISTIC / auto-executable / NO authorization artifact

* `correction_mapping.py`: both rows are `DETERMINISTIC`, `FIDELITY_SAFE`, `REVERSIBLE`,
  `auto_propose=True`.
* The real planner emits executable proposals directly from the report. **There is no authorization
  artifact in this path**: `_execute_face_removal` refuses a correction whose `requires_human_review`
  is set or whose `determinism` is not `DETERMINISTIC` (`REVIEW_REQUIRED_NOT_AUTO`); for W1/W1b the
  planner produces the opposite, so execution proceeds with no artifact (probe-verified: both W1 and
  W1b COMPLETED with `authorization=None`).
* **The W1/W1b receipt contains no `authorization_verified` field at all** (probe-verified, §M.7/§M.8).
  A live gate must not assert authorization-verification fields on these paths, must not present an
  artifact, and must not invent authorization negatives (see §J.1/§J.2 not-applicable rows).
* **Plan-state nuance:** when a report contains BOTH a duplicate/degenerate finding and a winding
  finding, `plan.state` is `REVIEW_REQUIRED` (a *plan-level* summary driven by the heuristic winding
  proposal) even though the W1/W1b correction itself is auto-executable and executes without an
  artifact. The live gate must therefore assert the *correction's* posture, never infer an
  authorization requirement from `plan.state` (probe-verified, §M.7).

### B.2 W2 — HEURISTIC / human-authorized / D1–D2 designation model / D3 planner refusal

* `correction_mapping.py`: `HEURISTIC`, `FIDELITY_GEOMETRY`, `PARTIALLY_REVERSIBLE`,
  `auto_propose=True` with `requires_human_review` set → the executor requires an authorization
  artifact (mandatory by construction: keyword-only, no default; `None` → `AUTHORIZATION_REQUIRED`).
* Gate order: plan integrity → exactly-one winding correction + allowlist → parameter allowlist →
  **authorization gate (contract only, before any engine contact)** → source binding → preconditions
  `WC-P6..P17` → exactly one bounded mutation → fresh extraction + `WC-Q1..Q13` → receipt.
* Sub-case model (`_aggregate_winding_corrections`):
  * **D1** — several findings on one mesh sharing a single common candidate face ⇒ ONE proposal
    covering every recorded edge, designated by the **evidence** (`designated_face_index` supplied by
    the planner, `candidate_faces` null). Supplying a designation in the artifact is refused:
    `AUTHORIZATION_SCOPE_MISMATCH` / `DESIGNATION_SUPPLIED_FOR_D1` (probe-verified, §M.9).
  * **D2** — exactly one finding ⇒ ONE proposal that requires the operator to designate which member
    of the candidate pair is reversed (`designated_face_index` null in the plan; `counterpart_faces`
    names the member that must NOT be designated). Missing designation →
    `AUTHORIZATION_REQUIRED` / `DESIGNATION_REQUIRED`; out-of-pair designation →
    `AUTHORIZATION_SCOPE_MISMATCH` / `DESIGNATION_NOT_IN_CANDIDATE_PAIR`; designating the recorded
    **counterpart** → `PRECONDITION_FAILED` (counterpart rule) with `authorization_verified == False`
    (all probe-verified, §M.9).
  * **D3** — empty candidate-face intersection ⇒ **no proposal is produced**; the findings remain
    review-only. **D3 is planner non-emission only and must never be implemented as an executable
    case.**
* Artifact fields: nine required (`authorization_version`, `authorization_policy_version`, `decision`,
  `correction_type`, `correction_id`, `plan_id`, `source_report_digest`, `authorized_by`,
  `authorized_at_utc`) plus optional `designated_face_index`, `expected_face_tuple`, `scope_note`.
  Canonical-JSON text is accepted; unknown fields are refused (`UNKNOWN_FIELD`).

---

## C. W1 contract (as implemented in `main`)

Required mutation: **delete exactly ONE face** whose content equals the recorded duplicate — from the
target mesh, changing nothing else. The executor resolves the target from the fresh `SceneModel`,
re-derives the duplicate condition at execution time (`_recorded_duplicate_tuple` + `_duplicate_key`
count ≥ 2), and hands the injected mutator `{object_id, mesh_id, face_ids, dup_tuple}` where
`face_ids` is the recorded duplicate **pair** and `dup_tuple` the recorded content.

**Mutator rule (probe-verified):** the mutator deletes exactly one face — the gate pins the choice as
the **second recorded member** (`face_ids[-1]`). Deleting both members is refused by the postcondition:
`POSTCONDITION_FAILED` "face multiset changed by more than exactly one recorded face (or the wrong
face)" (§M.7).

Postconditions enforced by `_verify_postconditions`:
1. `scene_id`, `unit_system` unchanged;
2. object order and identity set unchanged;
3. target resolvable (fail-closed if the target or `mesh_id` is gone);
4. target **vertex table** bit-identical (ordered);
5. target `mesh_id` unchanged;
6. **exact one-face multiset delta**: `Counter(post) == Counter(pre) − Counter([removed_face_tuple])`
   — remaining faces keep their exact tuples and order; a face-count-only success is impossible;
7. every unrelated object's object-state key and mesh-state key unchanged (`_mesh_state_key` =
   `(mesh_id, vertices, faces)`);
8. target object state (name/collection/parent/pose/visibility) unchanged;
9. **no new `MESH_INVALID_INDEX`**.

### C.1 Live-gate evidence requirements (red-team F-1 closure)

The W1 live gate **must** produce and assert:

1. **Exact per-mesh pre/post finding-class histograms.** For the target mesh, the gate records
   `{code: {count, measured[]}}` for the pre-state and the post-state and asserts **exact equality**
   against the expected values — never "the duplicate finding disappeared".
2. **Exact expected clearing of the co-emitted `MESH_WINDING_INCONSISTENT` findings caused by the
   removed duplicate.** True duplicate faces traverse every shared edge in the same direction, so the
   duplicate pair necessarily carries winding findings. With a fixture whose duplicate pair is
   `[2, 3]` over vertices `(4, 5, 6)`, the pre-state winding set is
   `[{edge:[4,5],faces:[2,3]}, {edge:[5,6],faces:[2,3]}, {edge:[4,6],faces:[2,3]}]` and all three must
   be **exactly cleared** by the removal (probe-verified, §M.7). This clearing is a **consequence** of
   deleting the duplicate — it is **NOT** a winding repair, **NOT** a `REPAIR_FACE_WINDING` execution,
   and the W1 gate must make no winding-correctness claim.
3. **Survivor preservation.** The fixture must also carry an **unrelated** same-direction winding pair
   on other faces (probe fixture: faces `0` and `1` over edge `(0,1)`), whose measured payload
   `{edge:[0,1],faces:[0,1]}` must be **bit-identical after the mutation**. Assert:
   `post_winding_measured == [the survivor's exact pre-state payload]` **and**
   `pre_winding_count − cleared_pair_findings == post_winding_count`. An unrelated winding finding
   disappearing silently is a gate failure.
4. **Fixture policy preventing face-index renumbering ambiguity.** Removing face index *i* shifts
   every later face down by one, which rewrites the face indices inside winding payloads. The fixture
   must remove the **final face index** (policy: *the removed duplicate is the last face*), so the
   renumbering map is the identity. The gate must assert the renumbering map explicitly — for the
   probe fixture `[[0,0],[1,1],[2,2]]`, identity (probe-verified, §M.7). If a future fixture cannot
   satisfy the final-index policy, the gate must specify **and assert the exact renumbering map** for
   every surviving face.
5. **`mutator_invocations == 1`** asserted from the driver's own counter, plus the raw post face table
   asserted to be the exact pre-state subsequence (`post == pre minus the removed face`, in order).
6. **No second mutation may be inferred from finding changes.** The gate must never conclude "the
   winding findings vanished, therefore a winding repair also ran". The only admissible evidence of
   engine contact is the counted mutator invocation(s) and the raw pre/post state; finding deltas are
   *predicted consequences*, not mutation evidence. The receipt's `executed_correction_ids` must name
   exactly the one W1 correction, and `postcondition_results` must be the expected set.
7. **W1b is not involved:** the gate must assert the W1 receipt reports `field_count` consistent with
   the W1 receipt schema and that no `authorization_verified` field is present (§B.1).

---

## D. W1b contract (as implemented in `main`)

Required mutation: **delete exactly ONE face** — the exact face recorded at `parameters['face_id']` —
after re-verifying at execution time that the face at that index is still degenerate under the kernel
predicate. No substitution of "another degenerate face". Mutator receives
`{object_id, mesh_id, face_id, face_tuple}`. Postconditions are the Wave-1 shared set (§C), i.e. the
exact one-face multiset delta plus unchanged vertices/identity/unrelated state/no-new-invalid-index.
The mesh is **not** required to become degeneracy-free.

The kernel predicate (`mesh_health.py:244-262`, `_collect_degenerate_faces`; mirrored exactly by
`_is_degenerate_face`) has two branches: `len(face) < 3`, or `abs(signed_area) <= _EDGE_TOLERANCE`.

### D.A zero-area / collinear face — LIVE-POSITIVE

Fixture: three distinct collinear vertices, e.g. `[(0,0,0), (1,0,0), (2,0,0)]` with face `(0,1,2)`.
Probe (§M.5): 3 vertices / 3 edges / 1 polygon; parses; kernel emits
`MESH_DEGENERATE_FACE {'face': 0, 'signed_area': 0.0}`.

### D.B 2-vertex face — LIVE-POSITIVE (F-1 design round, CASE A)

Exact live fixture:

```
vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
faces    = [(0, 1)]                    # built as
mesh.from_pydata(vertices, [], [(0, 1)]); mesh.update()
# plus >= 2 assigned DATA-linked material slots on the same object (Wave 14 evidence)
```

`from_pydata(vertices, [], [(a,b)])` creates a **polygon** (1 polygon, 2 loops, area 0.0), whereas the
edge-only forms (`from_pydata(vertices, [(a,b)], [])`, a bmesh edge) create **no polygon** (§M.1).
Pre-state: raw 2 vertices / 1 edge / 1 polygon `[0, 1]`; payload `{"faces": [[0, 1]], "vertices": …}`;
canonical `MeshModel(vertices=(2), faces=((0,1),))`; kernel
`MESH_DEGENERATE_FACE {'face': 0, 'vertex_count': 2}` (§M.2).
Post-state (real planner → real executor → Pattern B): `COMPLETED`, exactly one mutation,
0 polygons / 0 edges / 2 vertices retained, same datablock, canonical `faces == ()`, findings cleared
(§M.3).

### D.C repeated-index face — parser/extraction limitation, **NOT live-positive coverage**

A Blender mesh holding `[(0,0,1)]` can be built, but the frozen parser refuses it before the kernel:
`extract_scene` succeeds and emits `faces: [[0,0,1]]`, then
`payload_to_scene_model → MeshModel.__post_init__ → _canon_face` raises
`SceneReportInputError: mesh face must not repeat a vertex index` (`scene_model.py:95`, reached via
`scene_model.py:71`). Binding scope: sub-case C is **never** a live-positive case, is out of scope
beyond an optional documented refusal observation, and `bpy_extraction.py` /
`extraction_payload.py` / `scene_model.py` / `MeshModel` must not be modified to make it coverable; no
substitute positive case may be invented for it.

### D.D Stale-degeneracy live negative (red-team F-2 closure)

The gate **must** include a live negative proving execution-time revalidation rather than a prebuilt
happy path. Exact design (probe-verified, §M.8):

* **Fixture** (one scene, two plans): vertices `[(0,0,0), (1,0,0), (2,0,0), (5,5,0)]`, faces
  `[(0,1,2), (0,1,3)]` — face 0 is collinear (degenerate), face 1 is non-degenerate.
* **Case (i) — recorded `face_id` IS degenerate:** real planner → `face_id = 0` → `COMPLETED`,
  `mutator_invocations == 1`, mutator kwargs `{face_id: 0, face_tuple: [0,1,2]}`, raw faces after
  `[[0,1,3]]`.
* **Case (ii) — recorded `face_id` still EXISTS but is NO LONGER degenerate:** the same scene, the
  same source digest, and a contract-valid plan (ids and dependency edges remapped, `plan_id`
  recomputed by the contract) whose `face_id` names the non-degenerate face → the executor must refuse
  with **`PRECONDITION_FAILED`** and the typed reason
  `"recorded face 1 is no longer degenerate under the kernel predicate; the exact planned target is
  absent/changed (never substitute another degenerate face)"`, with **`mutator_invocations == 0`** and
  the raw scene bit-identical before/after. This is the discriminator pair: identical scene, identical
  digest, only the recorded index differs, and the executor re-derives degeneracy from **fresh**
  evidence.
* **Case (iii) — engine mutated AFTER planning:** make the degenerate face non-degenerate by moving a
  vertex, then execute → the executor refuses with **`SOURCE_MISMATCH` / `SOURCE_DIGEST_MISMATCH`** and
  0 mutations, because **source binding precedes preconditions**. The gate must expect this code (not
  `PRECONDITION_FAILED`) and must document the gate order.
* **Reachability note (binding):** a case where the *same* engine state was degenerate at planning
  time and is no longer degenerate at execution time while the digest still matches is **unreachable**
  through the frozen contract — degeneracy is a function of the exact vertex/face data the digest
  covers. The gate must state that, and must not present case (ii) as if the engine had changed.
* W1b receipts carry **no `authorization_verified` field**; the negative asserts the absence of the
  field, `persisted is False` and `rollback_performed is False`.

---

## E. W2 contract (as implemented in `main`)

Required mutation: read the authoritative vertex table, build the face table with **only** the
designated index's tuple replaced by `reverse(pre_tuple)` — every other tuple unchanged, in order —
and rebuild the tables **in place on the same datablock** (`mesh.clear_geometry();
mesh.from_pydata(vertices, [], faces); mesh.update()`). Nothing else may change. Mutator receives
`(object_id, mesh_id, face_index, face_tuple)`.

Postconditions (`WC-Q1..Q13`): `WC-Q2` face count unchanged · `WC-Q1` exactly the designated tuple
reversed, others identical · `WC-Q4` every non-target face bit-identical · `WC-Q3` vertex table
unchanged (ordered, exact) · `WC-Q5` every recorded edge now opposite-traversed by the recorded pair ·
`WC-Q6`/`WC-Q13` the mesh's winding findings cleared · `WC-Q7`/`WC-Q8` no new duplicate/degenerate
finding and the target's degeneracy classification unchanged · `WC-Q9` no new `MESH_INVALID_INDEX`.

Preconditions (`WC-P6..P17`): target resolvable; designated index a non-negative exact int in range;
canonical recorded edge/counterpart contract; **`WC-P14`** the designated face is neither degenerate
nor duplicate; **`WC-P17`** independent re-derivation with bidirectional agreement between the plan's
recorded edge set and the fresh report's findings (plus the counterpart rule that refuses the recorded
counterpart). Authorization precedes all engine contact.

### E.1 Authorization receipt honesty (red-team F-3 closure)

**Requirement:** on EVERY negative authorization path the live gate asserts
`receipt["authorization_verified"] is False` **together with** the exact typed `failure_code`, the
exact `result` token and `mutator_invocations == 0`.

**Semantics (code, `correction_executor.py`):** `authorization_verified` is initialised `False` on
every path and set `True` **only after the authorization gate AND the fresh-evidence preconditions
(`WC-P6..P17`) have passed** — i.e. immediately before the single bounded mutation. `True` therefore
means "authorized and preconditions verified on fresh evidence"; it does **not** mean the correction
succeeded (probe: an accepted authorization with a no-op mutator yields `POSTCONDITION_FAILED` /
`WC-Q1` with `authorization_verified == True`, §M.9).

**Complete deterministic negative family** (each row probe-verified against the real executor, with the
exact typed codes; §M.9):

| Case | `result` | `failure_code` | `authorization_verified` | mutations |
| --- | --- | --- | --- | --- |
| no artifact presented | `AUTHORIZATION_REQUIRED` | `AUTHORIZATION_REQUIRED` | False | 0 |
| artifact is malformed JSON text | `AUTHORIZATION_INVALID` | `MALFORMED_JSON` | False | 0 |
| artifact JSON is not an object | `AUTHORIZATION_INVALID` | `NOT_A_MAPPING` | False | 0 |
| required field missing | `AUTHORIZATION_INVALID` | `MISSING_FIELD` | False | 0 |
| decision not approved | `AUTHORIZATION_INVALID` | `DECISION_NOT_APPROVED` | False | 0 |
| unsupported policy version | `AUTHORIZATION_INVALID` | `UNSUPPORTED_POLICY_VERSION` | False | 0 |
| unsupported authorization version | `AUTHORIZATION_INVALID` | `UNSUPPORTED_AUTHORIZATION_VERSION` | False | 0 |
| wrong `correction_id` | `AUTHORIZATION_SCOPE_MISMATCH` | `CORRECTION_ID_MISMATCH` | False | 0 |
| wrong `plan_id` | `AUTHORIZATION_SCOPE_MISMATCH` | `PLAN_ID_MISMATCH` | False | 0 |
| wrong `source_report_digest` | `AUTHORIZATION_SCOPE_MISMATCH` | `SOURCE_DIGEST_MISMATCH` | False | 0 |
| wrong `correction_type` | `AUTHORIZATION_INVALID` | `CORRECTION_TYPE_NOT_AUTHORIZABLE` | False | 0 |
| unknown/extra artifact field | `AUTHORIZATION_INVALID` | `UNKNOWN_FIELD` | False | 0 |
| **D2** without a designation | `AUTHORIZATION_REQUIRED` | `DESIGNATION_REQUIRED` | False | 0 |
| **D2** designation outside the candidate pair | `AUTHORIZATION_SCOPE_MISMATCH` | `DESIGNATION_NOT_IN_CANDIDATE_PAIR` | False | 0 |
| **D2** designating the recorded counterpart | `PRECONDITION_FAILED` | `PRECONDITION_FAILED` (counterpart rule) | False | 0 |
| **D1** artifact supplying a designation | `AUTHORIZATION_SCOPE_MISMATCH` | `DESIGNATION_SUPPLIED_FOR_D1` | False | 0 |
| **D1** no artifact | `AUTHORIZATION_REQUIRED` | `AUTHORIZATION_REQUIRED` | False | 0 |

D1 and D2 positives (authorization accepted) are covered separately: D2 with a valid designation and
D1 with the evidence-supplied designation both reach the mutation stage
(`authorization_verified == True`, exactly one mutator invocation). **D3 remains planner
non-emission only** — the gate asserts the planner produces no winding correction for a D3 report
and never constructs an executable D3 case.

---

## F. Wave 14 fidelity transfer (per property)

Scope fact: the W1/W1b/W2 executors have **no material clause**. The Wave-1 snapshot records only the
target's `mesh_id`, vertex table and face tuples, and unrelated meshes compare as
`(mesh_id, vertices, faces)` — no `materials`, `normals`, `uvs`, `local_frame_id`. Wave 14's
*obligations* transfer; Wave 14's *executor-side enforcement* does not.

| Property | Classification | Proven by |
| --- | --- | --- |
| target vertices/faces, exact remaining face order, exact one-face delta (W1/W1b) | CANONICALLY PROVABLE | executor postconditions §C/§D |
| exactly-one-reversed-tuple, other faces and vertex table unchanged, winding class cleared (W2) | CANONICALLY PROVABLE | `WC-Q1..Q6/Q13` §E |
| target canonical `materials` tuple + producer `materials` key presence | CANONICALLY PROVABLE **as gate-side evidence only** | gate compares pre/post payload + canonical tuple |
| assigned DATA-linked slots (names, count, order), all-assigned configuration | CANONICALLY PROVABLE as gate-side evidence; otherwise raw | gate-side canonical tuple + raw table |
| unassigned material slots | RAW-BLENDER-BOUNDARY-ONLY | raw `[link, material name]` table (producer omits the key → canonical `()` both sides) |
| OBJECT-linked material slots | RAW-BLENDER-BOUNDARY-ONLY | raw link+name table; the canonical omission must be asserted, not assumed |
| mesh datablock identity / inventory / replacement / orphan creation | RAW-BLENDER-BOUNDARY-ONLY | raw inventory equality; **no canonical clause exists** for these three ops |
| unrelated-object material state | RAW-BLENDER-BOUNDARY-ONLY | `_mesh_state_key` excludes materials; the gate asserts the unrelated raw slot table itself |
| polygon `material_index` | NOT CURRENTLY PROVABLE / out of contract | §G (provably destroyed by Pattern B) |
| same-name / different-datablock material substitution | NOT CURRENTLY PROVABLE | the canonical representation carries names only |
| normals, UVs, local-frame, material node/property metadata | NOT CURRENTLY PROVABLE | frozen extraction omissions — no claim, no expansion |

### F.1 Raw fidelity assertions remain test-only (red-team F-4 closure)

Binding, and to be repeated in every gate's module documentation:

1. **All raw Blender fidelity assertions live only in test/gate code** (the live driver scripts and
   the gate modules under `tests/`). They are evidence about a specific engine run, not contract.
2. **No production code imports, requires or depends on them.** No production module may reference the
   raw slot-table reader, the datablock-inventory reader, the raw snapshot or any assertion helper
   introduced by this milestone.
3. **They are not promoted into a shared production assertion/validator library.** No new production
   module, no new executor call-site, no new verifier, no new branch is introduced by Wave 15. Any
   future promotion requires its own design gate.
4. **They do not create a hidden canonical Atlas contract.** Where canonical extraction cannot express
   a property, the canonical contract says nothing about it; raw assertions may neither extend the
   canonical model nor be cited as if they did.

**Known limitation preserved (not upgraded to a guarantee):** the W1/W1b/W2 executors do not compare
material state at all. For W1 in particular, an unrelated object's material slots can only be protected
by the gate's **raw** assertions — the canonical postcondition compares unrelated meshes as
`(mesh_id, vertices, faces)` only. This is a **documented limitation**, not a newly claimed canonical
guarantee, and the design must not describe it as one.

---

## G. REQUIRED MATERIAL-INDEX NON-CLAIM (binding wording)

> **Pattern B rebuild resets `polygon.material_index`.**
> `mesh.clear_geometry()` followed by `mesh.from_pydata(...)` reconstructs every polygon with
> `material_index == 0`; per-face material assignment does **not** survive a geometry rebuild.
> Polygon material assignment is **outside the frozen Atlas representation contract** — the canonical
> model has no per-face material field and the frozen producer does not emit one.
> **Wave 15 makes NO claim that per-face material assignment survives**, and no live gate may assert
> `material_index` preservation.
> Measured evidence (Blender 4.4.3 / `802179c51ccc`): a two-slot mesh whose first polygon carried
> `material_index == 1` read back as `[0, 0]` after a Pattern B rebuild, while the object's material
> **slots** and the canonical `materials` tuple were unchanged.

**Same-datablock identity is observed live behaviour, not a canonical invariant.** Wave 14 demoted
datablock replacement from the normative reference primitive; MQ-5 records only that a datablock *may*
be replaced while represented identity may not change. For W1/W1b/W2 there is no canonical datablock
clause at all: same-datablock continuity is what the live gate **observes** through raw datablock
inventory equality, and it must be documented as observed engine behaviour rather than as a contract
guarantee.

---

## H. Live gate architecture

Two gate families; all new code is test/harness code (no production abstraction, §F.1).

### H.1 Gate family 1 — W1 + W1b shared face-removal harness

* One live driver script + one gate module covering **two case groups** (W1 duplicate-face, W1b
  degenerate-face): both share `_execute_face_removal`, the same postcondition function, the same
  DETERMINISTIC/no-artifact posture and the same mutation shape (delete exactly one recorded face).
* W1 case group: the §C.1 fixture (duplicate pair = final index + unrelated winding pair survivor),
  duplicate-only minimal fixture (optional), exact histograms, clearing expectations, survivor
  preservation, identity renumbering map, `mutator_invocations == 1`, and the both-members-deleted
  refusal.
* W1b case group: zero-area (D.A), 2-vertex (D.B), zero-face post-state (Wave 11 touch-point) and the
  §D.D stale-degeneracy discriminator pair plus the digest-first case.
* Both groups use the **real planner** and the **real executor**; no authorization artifact is built,
  presented or asserted (§B.1).

### H.2 Gate family 2 — W2 authorization-aware gate

Separate driver script + gate module (different executor entry point, authorization before engine
contact, closed parameter set, `WC-P*/WC-Q*`, reversal mutation, D1/D2 designations, D3 refusal).
Cases: D2 positive (operator designation), D1 positive (evidence designation, no designation field),
the full §E.1 authorization negative family with `authorization_verified is False`, and the
mutation-shape/precondition negatives of §J.3.

### H.3 Shared requirements (both families)

Wave 14 fidelity evidence (raw link-aware slot table, canonical `materials` evidence, datablock
inventory), **anti-vacuity assertions** (a material-bearing positive must fail if its pre-state
canonical material tuple becomes empty), identity-based target selection **plus content-verified
pre-flight finding binding** (§I), frozen-asset SHA-256 before/after, `.blend`/`.blend1` file-set
snapshot equality, `bpy.data.filepath == ""`, exact mutator-invocation counts, in-memory disposable
fixtures only, Blender version pin (4.4.3 / `802179c51ccc` / build date 2025-04-29), the F-4
containment statement (§F.1) and the material-index non-claim (§G).

---

## I. Target selection (mandatory)

* Live drivers resolve the fixture target by **identity**: an explicit `TARGET_OBJECT_ID` /
  `TARGET_MESH_ID` pair (e.g. `"pitch"` / `"pitch"`) with a **fail-loud** error if the named object or
  mesh is absent from the extracted scene.
* Selection by ordering, by "the first mesh object returned by extraction", by name-sort position or
  any positional fallback is **forbidden** (historical hazard: the producer emits objects in
  name-sorted order, which already caused a Wave 13 live-gate retarget defect).
* Every fixture includes at least one unrelated object whose name sorts **before** the target, so a
  positional selector fails loudly.
* **Content-verified pre-flight finding binding (mandatory):** before executing, the gate must bind
  the plan to the fixture **by content** — assert that the pre-state report contains the expected
  finding for the target (`code`, `object_id`/`mesh_id`, and the exact `measured` payload), that the
  plan's `object_id`/`mesh_id` and (for W2) `designation`/recorded edge set agree with that finding,
  and that the proposal count for the capability is exactly one. Identity equality alone is not
  sufficient evidence that the plan targets the intended defect.

---

## J. Adversarial matrices (minimum live negatives)

Legend: **✔ deterministic-only today** (the live gate re-proves it against fresh engine evidence),
**▲ boundary-only**, **— NOT APPLICABLE / must not be invented**.

### J.1 W1 (`REMOVE_DUPLICATE_FACE`)

| Case | Status | Expected |
| --- | --- | --- |
| wrong/missing target object, wrong `mesh_id` | ✔ ▲ | `PRECONDITION_FAILED` / source mismatch; 0 mutations |
| malformed parameters (unexpected key, bad `face_ids` shape, non-int) | ✔ | `PLAN_INVALID` / `UNEXPECTED_PARAMETER:*` |
| plan_id mismatch; forged/stale source digest | ✔ ▲ | `PLAN_INVALID` / `SOURCE_DIGEST_MISMATCH`; 0 mutations |
| duplicate condition no longer holds at execution time | ✔ ▲ | `PRECONDITION_FAILED`; 0 mutations |
| mutator removes the WRONG face | ✔ ▲ | `POSTCONDITION_FAILED` (multiset delta) |
| **mutator removes BOTH duplicate members** | ✔ ▲ | `POSTCONDITION_FAILED` "changed by more than exactly one recorded face" (probe-verified §M.7) |
| mutator also moves a vertex | ✔ ▲ | `POSTCONDITION_FAILED` (vertex table) |
| mutator touches an unrelated object / its mesh | ✔ ▲ | `POSTCONDITION_FAILED` (unrelated state) |
| no-op mutator | ✔ ▲ | `POSTCONDITION_FAILED` |
| liar mutator (claims success, mutates nothing) | ✔ ▲ | `POSTCONDITION_FAILED`; receipt not authority |
| **unrelated winding survivor disappears** | ▲ | gate failure (survivor-preservation assertion, §C.1.3) |
| **finding-class histogram mismatch (pre or post)** | ▲ | gate failure (§C.1.1) |
| **renumbering map not the identity (final-index policy violated)** | ▲ | gate failure (§C.1.4) |
| unexpected datablock replacement (Pattern A diagnostic) | ▲ | raw inventory + raw slot table detect it; **no canonical clause exists** — no executor-detection claim |
| material-slot destruction on the target | ▲ | raw slot table + anti-vacuity canonical comparison |
| orphaned datablock / inventory gain | ▲ | inventory equality |
| persistence / save attempt | ▲ | `filepath == ""`, frozen-asset hash, `.blend` snapshot |
| authorization artifact missing / mismatched | **—** | not applicable: no authorization path exists (§B.1) |
| `authorization_verified` assertions | **—** | the field does not exist on W1 receipts (§B.1) |
| rollback / recovery behaviour | **—** | no rollback exists; receipt must show `rollback_performed is False` |

### J.2 W1b (`REMOVE_DEGENERATE_FACE`)

J.1 minus the duplicate-specific rows, plus:

| Case | Status | Expected |
| --- | --- | --- |
| **recorded `face_id` exists but is no longer degenerate** | ▲ | **`PRECONDITION_FAILED`** with the typed reason, 0 mutations, raw state bit-identical (§D.D case ii) |
| **engine mutated after planning (degenerate face changed)** | ▲ | `SOURCE_MISMATCH` / `SOURCE_DIGEST_MISMATCH`, 0 mutations (§D.D case iii) |
| an untargeted degenerate face remains elsewhere | ✔ | legal: no global degeneracy-clear requirement |
| zero-face post-state (the only face removed) | ▲ | COMPLETED; post extraction yields `MeshModel(vertices=(…), faces=())`; Wave 11 permits it |
| repeated-index fixture as a W1b positive | **—** | not representable: the parser fails closed (§D.C) |
| authorization negatives / `authorization_verified` | **—** | no authorization path and no such receipt field (§B.1) |

### J.3 W2 (`REPAIR_FACE_WINDING`)

| Case | Status | Expected |
| --- | --- | --- |
| the complete §E.1 authorization negative family (17 rows) | ✔ ▲ | exact `result` + typed `failure_code` + **`authorization_verified is False`** + 0 mutations |
| recorded edge set no longer agrees with fresh evidence (`WC-P17`) | ✔ ▲ | `PRECONDITION_FAILED`; 0 mutations |
| designated face became degenerate/duplicate (`WC-P14`) | ✔ ▲ | `PRECONDITION_FAILED`; 0 mutations |
| designation is the recorded counterpart | ✔ ▲ | `PRECONDITION_FAILED` (counterpart rule), `authorization_verified is False` (probe-verified §M.9) |
| mutator reverses the WRONG face | ✔ ▲ | `POSTCONDITION_FAILED` (`WC-Q1`) |
| mutator reverses TWO faces | ✔ ▲ | `POSTCONDITION_FAILED` (`WC-Q1`/`WC-Q2`/`WC-Q4`) |
| mutator changes the vertex table | ✔ ▲ | `POSTCONDITION_FAILED` (`WC-Q3`) |
| mutator touches an unrelated object | ✔ ▲ | `POSTCONDITION_FAILED` (shared snapshot) |
| recorded edge not opposite-traversed post-mutation | ✔ ▲ | `POSTCONDITION_FAILED` (`WC-Q5`) |
| new duplicate/degenerate/invalid-index appears | ✔ ▲ | `POSTCONDITION_FAILED` (`WC-Q7/Q8/Q9`) |
| no-op mutator after an ACCEPTED authorization | ✔ ▲ | `POSTCONDITION_FAILED` / `WC-Q1` with `authorization_verified == True` (probe-verified §M.9) — proves `True` is a pre-mutation claim, not a success claim |
| liar mutator (claims success without mutating) | ✔ ▲ | `POSTCONDITION_FAILED`; receipt not authority |
| unexpected datablock replacement; slot destruction; orphan | ▲ | raw evidence only (as §J.1); no canonical clause exists |
| D3 (empty candidate-face intersection) | **—** | planner non-emission only: assert no winding proposal is produced; never an executable case |
| rollback / recovery behaviour | **—** | no rollback exists; receipt must show none was performed |

---

## K. Frozen boundaries — implementation must require ZERO production semantic changes to:

extraction (`bpy_extraction.py`) · payload (`extraction_payload.py`) · `scene_model.py` · `kernel.py` ·
`scene_report.py` · planner semantics (`correction_planner.py`) · authorization semantics
(`correction_authorization.py`) · executor semantics (`correction_executor.py`) · mapping
(`correction_mapping.py`) · the receipt schemas and the `WC-P*/WC-Q*` vocabulary · Temporal · Unreal ·
persistence/recovery · workflow/action-runner · the frozen asset
(`tests/assets/blender/atlas_transform_validation.blend`, sha256 `cf618bdc…`).

Wave 15 implementation may touch **only**: new live driver/gate test files and documentation. The
acceptable production diff is **empty**; any production semantic diff is a scope failure. **This
closure task itself changes zero frozen production files** (§M.10).

---

## L. Promotion gate (all must hold before an implementation task is issued)

1. This design document is complete and independently reviewed.
2. **F-1 (design round) resolved** — done, §D.B / §M.1–§M.6 (2-vertex face = LIVE-POSITIVE).
3. **Red-team F-1 closed** — W1 live gate carries the §C.1 evidence requirements (histograms, exact
   co-emitted winding clearing, survivor preservation, final-index renumbering policy, single
   mutation, no inferred second mutation).
4. **Red-team F-2 closed** — the §D.D stale-degeneracy live negative exists, with the digest-first
   ordering case and the unreachability note.
5. **Red-team F-3 closed** — the §E.1 requirement (`authorization_verified is False` on every negative
   authorization path) plus the complete deterministic negative family; D3 remains non-emission.
6. **Red-team F-4 closed** — the §F.1 test-only containment statement, with the W1 unrelated-material
   limitation preserved as a limitation.
7. W1/W1b shared gate (§H.1) and the separate W2 gate (§H.2) are accepted with their case groups.
8. **Anti-vacuity assertion mandatory** in every material-bearing positive case.
9. **Identity-based target selection and content-verified pre-flight finding binding mandatory** (§I).
10. **The `polygon.material_index` non-claim (§G) is mandatory** in this design and in every gate's
    documentation; same-datablock identity is documented as observed live behaviour, not an invariant.
11. **Zero production-file semantic diff** on the implementation head (`git diff --stat` touches tests
    + docs only).
12. The **Wave 14 Pattern-B wording** is referenced as the normative reference primitive (same-datablock
    rebuild; Pattern A remains superseded and diagnostic-only).
13. The adversarial matrices (§J) are reviewed, including the explicitly not-applicable authorization
    and rollback rows, so no implementation invents authority that does not exist.
14. Live evidence at the real boundary (Blender 4.4.3 / `802179c51ccc`) with exact mutation counts,
    receipt evidence, frozen-asset hash and no-save proof; CI green on the exact head SHA (the live
    gates remain operator-gated and are not CI-wired).
15. Independent post-implementation red-team review at the exact head SHA before merge.

---

## M. Probe records (evidence)

All probes ran on Blender **4.4.3**, build hash **802179c51ccc**, build date **2025-04-29**, against
in-memory disposable scenes with `bpy.data.filepath == ""` before and after and nothing saved; the
frozen asset was never opened. Scripts were kept outside the repository
(`%LOCALAPPDATA%\Temp\w15_*`), importing the frozen modules read-only from a detached worktree at
`a3b6d6c`.

**M.1 Construction matrix (F-1 design round)**

| Construction | vertices | edges | polygons | polygon sizes | loops |
| --- | --- | --- | --- | --- | --- |
| `from_pydata(v2, [], [(0,1)])` | 2 | 1 | **1** | `[2]` | 2 |
| `from_pydata(v2, [(0,1)], [])` | 2 | 1 | 0 | `[]` | 0 |
| bmesh edge primitive | 2 | 1 | 0 | `[]` | 0 |

**M.2 Frozen path on the 2-vertex polygon** — payload
`{"faces": [[0,1]], "vertices": [[0,0,0],[1,0,0]], "materials": ["turf","line_markings"],
"mesh_id": "pitch"}`; canonical `MeshModel(vertices=(2), faces=((0,1),))`; kernel
`MESH_DEGENERATE_FACE {'face': 0, 'vertex_count': 2}`.

**M.3 W1b repairability (real planner → real executor, no artifact)** — `state ==
AUTO_PROPOSALS_AVAILABLE`, one proposal `{'mesh_id': 'pitch', 'face_id': 0, 'reason':
'degenerate_face'}`; one invocation `{face_id: 0, face_tuple: [0,1]}`; `COMPLETED`,
`failure_code is None`, `persisted False`, `rollback_performed False`, receipt field count 17 (no
authorization field); post raw 0 polygons / 0 edges / 2 vertices, same datablock, no orphan; post
extraction yields `faces == ()` with no findings.

**M.4 Sub-case C failure site** — `SceneReportInputError: mesh face must not repeat a vertex index` at
`scene_model.py:95` (`_canon_face`) via `scene_model.py:71`.

**M.5 Sub-case A control** — collinear triangle → `MESH_DEGENERATE_FACE {'face': 0,
'signed_area': 0.0}`.

**M.6 Wave 14 control** — two assigned DATA-linked slots survived both the W1b repair path and a
Pattern B rebuild (raw table and canonical `materials` unchanged, single datablock, no orphan); a mesh
with `material_index == 1` read back `[0, 0]` after the rebuild (§G).

**M.7 Red-team F-1 — W1 duplicate/winding fixture (probe A)**

Fixture: target `pitch` with `faces = [[0,1,2], [0,1,3], [4,5,6], [4,5,6]]` over vertices
`[(0,0,0),(1,0,0),(0,1,0),(0,-1,0),(10,0,0),(11,0,0),(10,1,0)]`; unrelated object `goal` present
(its name sorts before the target and is linked into a child collection).
Planner: `state == REVIEW_REQUIRED` (plan-level, because of the co-emitted winding proposal), one
`REMOVE_DUPLICATE_FACE` proposal with `parameters == {'duplicate_relationship': 'exact_duplicate',
'face_ids': [2, 3], 'mesh_id': 'pitch'}`.
Execution (Pattern B, deleting exactly the second recorded member = final face index):
`COMPLETED`, `executed_correction_ids == ['MESH_DUPLICATE_FACE-pitch-65287896']`, receipt field count
17, `persisted False`, `rollback_performed False`, one mutator invocation with
`{dup_tuple: [4,5,6], face_ids: [2,3], mesh_id: 'pitch', object_id: 'pitch'}`.
Raw faces after: `[[0,1,2],[0,1,3],[4,5,6]]` — the exact pre-state subsequence; renumbering map
`[[0,0],[1,1],[2,2]]` (**identity**).
Pre-histogram: `MESH_DUPLICATE_FACE ×1 {face_a: 2, face_b: 3, vertices: [4,5,6]}`,
`MESH_WINDING_INCONSISTENT ×4 [{edge:[0,1],faces:[0,1]}, {edge:[4,5],faces:[2,3]},
{edge:[5,6],faces:[2,3]}, {edge:[4,6],faces:[2,3]}]`.
Post-histogram: `MESH_WINDING_INCONSISTENT ×1 [{edge:[0,1],faces:[0,1]}]`.
→ duplicate cleared; the three duplicate-pair winding findings cleared exactly; the **unrelated
winding survivor preserved with a bit-identical measured payload**; identical scene, one mutation.
Counter-case (deleting BOTH members): `POSTCONDITION_FAILED` — "face multiset changed by more than
exactly one recorded face (or the wrong face)".

**M.8 Red-team F-2 — W1b execution-time revalidation (probe A)**

Fixture: faces `[[0,1,2],[0,1,3]]`, vertices `[(0,0,0),(1,0,0),(2,0,0),(5,5,0)]`; pre-histogram
`MESH_DEGENERATE_FACE ×1 {face: 0, signed_area: 0.0}` and `MESH_WINDING_INCONSISTENT ×1
{edge:[0,1],faces:[0,1]}`.
(i) recorded `face_id = 0` (degenerate) → `COMPLETED`, one invocation
`{face_id: 0, face_tuple: [0,1,2]}`, raw faces after `[[0,1,3]]`.
(ii) recorded `face_id = 1` (exists, non-degenerate), same scene, same digest, contract-valid plan →
`PRECONDITION_FAILED`, reason "recorded face 1 is no longer degenerate under the kernel predicate; the
exact planned target is absent/changed (never substitute another degenerate face)",
**0 mutator invocations**, raw faces unchanged; `authorization_verified` field **absent**.
(iii) engine mutated after planning → `SOURCE_MISMATCH` / `SOURCE_DIGEST_MISMATCH`, 0 invocations
(source binding precedes preconditions).

**M.9 Red-team F-3 — W2 authorization negative family (probe B, deterministic, no bpy)**

D2 fixture: faces `[(0,1,2),(0,1,3)]`, one winding finding `{edge:[0,1],faces:[0,1]}`; planner
parameters `{'candidate_faces': [0,1], 'counterpart_faces': [1], 'designated_face_index': null,
'recorded_edges': [[0,1]], 'orientation': …}`. D1 fixture: faces `[(0,1,2),(0,1,3),(2,0,4)]`, two
findings (`edge [0,1]` and `edge [0,2]`), planner supplies `designated_face_index: 0`,
`candidate_faces: null`, `counterpart_faces: [1,2]`, `recorded_edges: [[0,1],[0,2]]`.
All 17 negative rows of §E.1 reproduce their exact `result`, `failure_code`,
`authorization_verified == False` and `mutator_invocations == 0` against the real executor. Positives:
D2 with valid designation and D1 with the evidence designation both reach the mutation stage
(`authorization_verified == True`, 1 invocation) and then fail `WC-Q1` because the probe's mutator was
a deliberate no-op — which is itself the §J.3 "no-op after accepted authorization" row.

**M.10 Frozen-boundary audit for this closure task** — `git status` in the design worktree at
`a3b6d6c` shows exactly one new untracked file (this document), zero modified files, empty
`git diff --stat` / `git diff --cached --stat`; `bpy_extraction.py`, `extraction_payload.py`,
`scene_model.py`, `kernel.py`, `scene_report.py`, `correction_executor.py`, `correction_planner.py`,
`correction_authorization.py`, `correction_mapping.py` unchanged; `tests/` unchanged; frozen asset
sha256 `cf618bdc1123734bf49bf6f22677ded3f2e6c3fa2803b97f7a6cf7c7c66f11aa` matches the pinned constant;
no `.blend`/`.blend1` created or modified; every probe reported `bpy.data.filepath == ""` and saved
nothing.

---

## N. Explicit non-claims

No claim is made about: per-face `material_index` or any material assignment; material datablock
identity; same-name/different-datablock substitution; normals, UVs, local-frame data, material node or
property metadata; the repeated-index degeneracy sub-case as live-positive coverage; datablock
replacement detection by canonical means (for these three capabilities no canonical clause exists);
orphan cleanup authority; rollback, recovery or persistence; multi-correction sequencing; a second
mutation inferred from finding deltas; winding *correctness* as a consequence of the W1 duplicate
removal; and any change to extraction, the canonical model, authority, receipts, Temporal or Unreal.
**Raw Blender assertions are test-only boundary evidence (§F.1) and do not extend the canonical
contract.**
