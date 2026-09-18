# Atlas — Temporal Observation + State Delta v1 (Design Gate)

**Status:** DESIGN REVISION 8 — REVIEW REQUIRED / NO IMPLEMENTATION
**Track:** Atlas temporal layer (engine-neutral, downstream of canonical world state)
**Architectural parent (authoritative):** `b95d5ab3b1f92a803098c16e9d2af29e3c42aae9`
(Blender Extraction Fidelity v1 implementation + verification commits, itself on the cleared design
revision `32eb4f76`), whose own baseline is `origin/main` = `2ec5a84c0b4d82898a0fb8169844ddd5d93668d2`.
**Design branch:** `feat/temporal-observation-state-delta-design`
**Scope statement (read before the title):** this milestone designs **observation and factual
difference** only — a versioned, engine-neutral `TemporalObservation` envelope, an ordered observation
stream with explicit admission rules, and a deterministic `StateDelta` between two comparable
observations. It does **not** design semantic events, event recognition, impact/collision/entrance/exit
abstractions, streaming infrastructure, retention policy, storage, or any runtime authority. §1.1 is
the claim boundary.

> The layer proposed here observes canonical world state. It never redefines it, never repairs it, and
> never infers it. Every rule below is written so that a C++ implementation receiving the same
> canonical snapshots and envelopes produces semantically identical deltas.

## 0. Revision control, authority, and repository state

### 0.1 Revision chain

| Commit | Subject | Content |
| --- | --- | --- |
| `2ec5a84` | Merge pull request #102 (Wave 12 reference integrity) | authoritative `origin/main` baseline |
| `32eb4f76` | Re-derive the frozen-asset anchor after the v1 preflight | cleared Blender Extraction Fidelity v1 **design** |
| `9a9e3e8` | Implement the Extraction Fidelity v1 producer contract | read-only producer implementation |
| `a0f0071` | Make the section-9 determinism evidence gate mechanically explicit | verification-only |
| `b95d5ab` | Close the section-8.2 canonicalization identifier in the section-9 gate | verification-only — **architectural parent of this document** |
| `75744da` | Temporal Observation + State Delta v1 design gate | the document at **revision 1** (held pending review) |
| `f26746d` | Correct eight contract defects in the temporal observation design | the document at **revision 2** (held pending review) |
| `f1ed30d` | Resolve five contract contradictions in the temporal observation design | the document at **revision 3** (held pending review) |
| `6394803` | Close the `NEW_EPOCH` boundary-path ambiguity in the temporal observation design | the document at **revision 4** (held pending review) |
| `cdf376d` | Define the missing-pair-input record schema in the temporal observation design | the document at **revision 5** (held pending review) |
| `fd48733` | Unify the StateDelta pure-function domain in the temporal observation design | the document at **revision 6** (held pending review) |
| `44d0a1c` | Complete the evaluation-input purity boundary with `FromIdentity` in every variant | the document at **revision 7** (held pending review) |
| *(this revision)* | Temporal Observation + StateDelta v1 — **design revision 8**: close the remaining domain, boundary-mutation, enumeration and multi-cause consistency defects | this document only — §22.7 |

**What design revision 8 changes.** Revision 7 was held pending five consistency defects found by the independent architectural review. This revision closes them without changing the temporal v1 claim boundary or introducing implementation:

1. §8.2 no longer uses stale `StateDelta(A,B)` purity wording; the single purity domain remains `EvaluationInput` and is named consistently everywhere.
2. §6.7/§8.1 now distinguish the caller-supplied **`PairInput` content-bearing subset** from the complete four-variant **`EvaluationInput` domain**; stage 3 consumes an evaluation input constructed from classification, supplied `A` when available, `B`, `FromIdentity`, and the contract version.
3. T-25 / attack #39 now state the correct `NEW_EPOCH` behavior: a boundary identity mismatch refuses comparison but does **not** undo the stage-2 admission; `B` is still admitted and the new epoch is established. On `SAME_EPOCH`, the same mismatch leaves admission unchanged.
4. All stale two-form `NEW_EPOCH` enumerations and exit criteria now name all three record forms, including `PAIR_INPUT_IDENTITY_MISMATCH`.
5. Simultaneous boundary-field changes are deterministic: reason codes are the complete set of applicable boundary-cause codes for the changed declaring fields, emitted together and sorted; no implementation may select an arbitrary single cause or depend on input/order construction.

Revision 8 remains documentation-only. No schema implementation, production code, tests, version bump, live gate, Event Abstraction, streaming/storage, or runtime authority is introduced.

**What design revision 2 changes.** Revision 1 was held pending a design revision. This revision
corrects eight contract defects found in it — sequence-gap semantics, duplicate-observation admission,
the stale-versus-reset ambiguity, digest identity versus semantic equivalence, the missing
state-digest fields, the comparison field universe, the undefined digest-invalid variant, and the
snapshot representation — and re-derives every dependent rule across §§4-14, the red-team register
(`R2-1..R2-8` in §22.1), the `T-1..T-14` requirements, the six required conclusions (§20) and the
closure map (§22). It changes **no** non-goal (§16) and **no** Event Abstraction boundary rule (§17).
**What design revision 3 changes.** Revision 2 was held pending a further design revision. This revision
resolves five contradictions left in it: (i) where the compared pair's earlier observation comes from,
given that the temporal layer keeps no snapshot store (§6.4, new §6.7); (ii) what a
`TEMPORAL_DISCONTINUITY` record *is*, given that its endpoints are non-comparable (§8.1, §8.2);
(iii) how an admission-level rejection differs from a pair-level refusal, so that stream processing is
single-valued end to end (new §6.8, §8.2, §10.5, §20, §21); (iv) whether the temporal state digest is
genuinely producer-order independent when `object_id`s are duplicated (§11.2 — it now is, by a
content-derived tie-break); and (v) the dependent re-audit and adversarial requirements (§19.1 #27-#31,
§19.2 `T-15..T-18`, §22.2 R3-1..R3-5). It changes no non-goal (§16), no Event Abstraction rule (§17),
**What design revision 4 changes.** Revision 3 was held pending one further correction: `NEW_EPOCH` with
a missing `PairInput.A` permitted two readings (`TEMPORAL_DISCONTINUITY` or `OBSERVATION_INVALID` /
`PAIR_INPUT_UNAVAILABLE`). This revision closes it with one deterministic rule — the **`NEW_EPOCH`
boundary path** of §6.8.1 — which is distinct from the `SAME_EPOCH` comparison path, is chosen by the
stage-2 classification alone, never invokes §9 or any cross-boundary comparison check, and lets pair-input
availability determine only the *record form*. `NEW_EPOCH` classification takes precedence over the
`SAME_EPOCH` stage-3 checks: pair-input availability never erases, downgrades or re-classifies an epoch
boundary. Every dependent section is reconciled (§5.5, §6.2, §6.6, §6.7, §6.8, §8.1, §8.2, §10.5, §12.4,
§14, §19.1, §19.2, §20, §21, §22) and §22.3 records the closure. No version number is bumped, no non-goal
(§16) and no Event Abstraction rule (§17) changes, and it remains documentation-only for the reason below.

**What design revision 5 changes.** Revision 4 was held pending one schema-level correction: it permitted
`OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` on both paths when `A` was not supplied, while §8.1 still
declared `from_observation_id` / `from_state_digest` as mandatory strings with no defined content for that
form — and the contract never said whether those fields are Atlas-owned identity metadata or evidence that
`A` was available. This revision fixes the model: **the `from_*` fields are identity metadata read from
Atlas-owned admission bookkeeping, and a new mandatory `pair_input` field states whether the earlier
endpoint's *content* was supplied** (new §6.7.1, revised §8.1). Nullable fields and a separate result type
were both rejected, with the reasons recorded in §8.1. No version number is bumped, no non-goal (§16) and no
Event Abstraction rule (§17) changes, and it remains documentation-only for the reason below.

**What design revision 7 changes.** Revision 6 was held pending one remaining formal gap: `ComparisonInput`
and `BoundaryInput` did not carry `FromIdentity`, yet the contract requires a supplied `A` to be validated
against the recorded earlier endpoint and requires a boundary cause to be derived from the previous epoch's
identity — both of which §12.1 forbids reading from mutable admission state. This revision makes
`FromIdentity` an explicit component of **all four** variants, defines it as an **immutable projection** of
Atlas-owned admission bookkeeping taken before the stage-4 mutation, and makes the identity agreement and
the boundary cause functions of the input alone. Admission stays Atlas-owned and is never read by the
evaluator; the projection is passed in as data, contains no snapshot content, and can never substitute for
`A`. No version number is bumped, no non-goal (§16) and no Event Abstraction rule (§17) changes, and it
remains documentation-only for the reason below.

**What design revision 6 changes.** Revision 5 was held pending one formal inconsistency: §8.1 called
`StateDelta` a pure function of `PairInput` `(A, B, COMPARISON_CONTRACT_VERSION)`, while §12.1 described the
missing-`A` evaluator as a *second* function of `(B, FromIdentity, COMPARISON_CONTRACT_VERSION)` — so the
refusal forms were produced outside the stated purity domain. This revision unifies it: one closed
tagged-union **evaluation-input domain** (§8.1) with four disjoint variants — `ComparisonInput`,
`BoundaryInput`, `RefusalInput`, `BoundaryRefusalInput` — and one function `StateDelta := F(EvaluationInput)`
defined in exactly one place, with §12.1 restating it and adding nothing. Revision 5's semantics are
preserved unchanged: the admission state stays content-free, `FromIdentity` is bookkeeping and never an
observation, `A` is never replaced by a digest or a handle, `NEW_EPOCH` precedence is untouched, a missing
`A` never yields `COMPUTED` or `NO_CHANGE`, `B` stays admitted, and no cross-epoch comparison or skip count
exists. No version number is bumped, no non-goal (§16) and no Event Abstraction rule (§17) changes, and it
remains documentation-only for the reason below.

This document is revision 8 on branch `feat/temporal-observation-state-delta-design`, extending the revision-7
design-only checkpoint `44d0a1c`. Nothing is implemented: no `TemporalState`, no `StateDelta`, no event
detection, no streaming, cache, mutable temporal store or background worker — and none of the frozen
boundaries in §0.2 is touched.
`b95d5ab`. Nothing is implemented: no `TemporalState`, no `StateDelta`, no event detection, no
streaming, cache, mutable temporal store or background worker — and none of the frozen boundaries in
§0.2 is touched.

### 0.2 Frozen boundaries this design must not move

| Boundary | Artifact | What is frozen |
| --- | --- | --- |
| canonical model | `planning/blender/scene_model.py` (`MeshModel` :44-102, `ObjectModel` :105-137, `SceneModel` :140-164, parsers :167-206) | field set, cardinality, validation and rejection rules |
| canonical state identity | `planning/blender/kernel.py` `_scene_input_digest` :93-121 (public wrapper :88-90) | the digested field set, exactly |
| report identity | `planning/blender/scene_report.py` :26-27 (`VALIDATOR_VERSION`, `REPORT_FORMAT_VERSION`), :127-132 (`canonical_json` / `digest`), :135-140 (`compute_input_digest`) | report schema, canonicalization, digest algorithm |
| extraction payload | `planning/blender/extraction_payload.py` :14 (`PAYLOAD_SCHEMA_VERSION = "1"`), :17-27 (closed key grammar), :73-86 (mesh validation) | schema v1 and its accepted states |
| producer | `planning/blender/bpy_extraction.py` (cleared at `9a9e3e84`) | the v1 read-only extraction contract |
| extraction design | `planning/blender/BLENDER_EXTRACTION_FIDELITY_COMPLETION_DESIGN.md` (revision 7, cleared at `32eb4f76`) | §3 encoding table, §4.1/§4.2/§4.4 omissions, §4.3 material tree, §5.1-§5.5 membership, §7 transforms/visibility, §11.1 digest participation |
| correction authority | `planning/blender/correction_*` (authorization / contract / planner / executor / mapping / values / dependencies / codes) | unchanged and out of scope |
| live/DT state surfaces | `planning/live_world_state.py`, `planning/digital_twin_*` (identity, revision, provenance, adapters) | not redefined; cited only as architectural precedent (§7, §11, §14) |
| recovery vocabulary | `docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md` (§4 root/attempt identity :85-122, §9 process identity :237-266, §16 evidence identity binding :502-527, §19-§20 reconciliation incl. Step 6 :669-697) | the restart/session/fail-closed precedent the temporal layer must connect to |

### 0.3 What this revision may touch

This revision adds **one new document** under a new directory (`planning/temporal/`). It touches no
production Python, no canonical model, no parser/validator, no schema version, no kernel, no
correction authority/executor/planner, no Unreal adapter/transport, no workflow/action-runner, no
token-optimization surface, and no test. D4 (the working-tree `slots=True` drift in the three
correction files) is present, untouched and not addressed here.

### 0.4 Citation provenance

Per-file line numbers are cited only where this revision verified them against `b95d5ab`. Where a
claim rests on a *symbol* rather than a verified line (for example
`planning/digital_twin_identity.py` → `IdentityMatchStatus`), the citation is file + symbol and is
authoritative at symbol granularity. No claim in this document rests on an untracked working-tree
file. There is currently **no** tracked file in the repository containing the word `temporal` (checked
with `git grep -il temporal` → zero hits): this layer is new ground and deliberately borrows its
vocabulary from the existing identity, revision, provenance and recovery surfaces rather than
inventing names.

## 1. Purpose and bounded claim

Atlas can already produce a canonical, deterministic description of a world state: a producer emits an
extraction payload (`PAYLOAD_SCHEMA_VERSION = "1"`), the canonical model parses it into a `SceneModel`,
and `scene_input_digest` binds that state to a provenance identity. What Atlas cannot do is say **what
changed between two canonical states** — and it cannot say it without either (a) misusing
`scene_input_digest` as a comparison, or (b) inventing continuity from resemblance.

This milestone designs exactly three things:

1. **`TemporalObservation`** — a versioned, engine-neutral envelope that binds *one canonical scene
   snapshot* to the temporal and provenance metadata needed to order it, scope it, and trust it.
2. **The ordered observation stream** — the admission rules that decide whether an arriving
   observation is accepted into a stream, rejected, or starts a new continuity epoch.
3. **`StateDelta`** — the deterministic, factual difference between two *comparable* observations,
   with an explicit coverage record that distinguishes "observed and unchanged" from "not observable".

The temporal layer is **read-only with respect to world state**: it observes canonical snapshots and
emits factual deltas. It holds no authority to mutate, repair, authorize, execute, persist, retry or
schedule anything.

### 1.1 What this milestone does NOT deliver (non-claim boundary)

| Domain | v1 status | Where the boundary is defined |
| --- | --- | --- |
| semantic events (impact, collision, entrance, exit, hit, reaction) | **not designed, not delivered** | §17 |
| event recognition / detection algorithms | **not designed** | §17, §16 |
| streaming, back-pressure, buffering, caches, mutable temporal store, background workers | **not designed** | §13, §16 |
| observation retention / eviction policy | **not designed** | §16, §18 |
| cross-engine geometric normalization (coordinate frame agreement) | **not delivered** — `coordinate_frame` is unobservable in v1 | §10, §18 |
| object rename vs replacement discrimination | **not delivered** — reported as remove+add | §7.4 |
| vertex/face correspondence, topological matching, index-invariant mesh comparison | **not delivered** — comparisons are positional | §9.7 |
| normals / UV / local-frame observation and comparison | **not delivered** — producer-deferred | §10 |
| numeric tolerance as *semantic* equality | **not delivered** — semantic equality is exact; only diagnostic magnitudes exist | §9.4 |
| multi-stream merging, cross-stream ordering | **not delivered** | §6, §16 |
| persistence of observations or deltas | **not designed** | §16 |
| byte-identical cross-language serialization | **not claimed** — semantic parity only | §15 |
| any runtime authority (mutation, repair, authorization, execution) | **absent by construction** | §2 |

One-sentence statement for a downstream reader: *"Temporal v1 defines what an observation is, when two
observations may be compared at all, and what a factual state delta between them is — and it explicitly
refuses to turn any of that into interpretation."*

## 2. Authority boundary

```text
Blender / Unreal / replay / future producer
        |  (produces, engine-side)
        v
canonical SceneModel snapshot              <-- FROZEN canonical layer (§0.2)
        |  (wrapped, never re-derived)
        v
Temporal Observation envelope              <-- THIS milestone defines the shape
        |
        v
observation stream admission               <-- THIS milestone defines the rules
        |
        v
deterministic State Delta                  <-- THIS milestone defines the semantics
        |
        v
(future) Event Abstraction                 <-- NOT this milestone (§17)
```

Rules of the boundary:

* **B1 — observe, never redefine.** The temporal layer consumes canonical snapshots exactly as the
  canonical layer produced them. It may not re-normalize, re-round, re-sort, repair, complete or
  re-derive any canonical value. If a snapshot is not canonical, the observation is invalid (§10).
* **B2 — no write authority.** The temporal layer emits observations/deltas. It does not mutate the
  scene, the canonical model, the payload, artifacts on disk, or any engine. It is a read-only
  boundary in the same sense as the extraction boundary (extraction design §2).
* **B3 — no authorization, execution, retry, recovery, scheduling.** Those belong to the existing
  authorities (correction authorization/executor; the recovery coordinator contract §2). The temporal
  layer may *describe* that a discontinuity happened; it may not act on it.
* **B4 — engine neutrality.** No rule in this document may require a Blender or Unreal API. Everything
  is expressed over canonical dictionaries and typed scalars, so a C++ producer/consumer can compute
  the same deltas (§15).
* **B5 — no self-identity.** The temporal layer never invents identity the producer did not supply:
  it does not invent entity keys (§7), continuity (§6), or time (§5). Where the producer's declaration
  is missing, the outcome is fail-closed, never a default.

## 3. Conceptual model

```text
TemporalObservation        one canonical snapshot + temporal scope + provenance + capability record
        |
ObservationStream          an ordered, admitted sequence of observations sharing a stream identity
        |                  (one stream = one producer-side subject: one scene / twin / capture)
        v
comparison admission        "are these two observations comparable at all?"      (§6, §10)
        |
        v
StateDelta                 the factual difference, plus the coverage record       (§8, §9, §10)
```

Vocabulary (all names are v1 contract names; none is implemented in this milestone):

| Concept | Meaning | Section |
| --- | --- | --- |
| `stream_id` | stable identity of the observed subject across restarts; survives producer and Atlas restarts | §4.2 |
| `continuity_id` | identity of one continuous temporal history *within* a stream; changes on restart, seek, reset | §6 |
| `sequence` | deterministic admission-order counter inside one continuity epoch | §5.4 |
| `source_time` | engine/media timeline position the snapshot represents (typed, integer-exact) | §5.1 |
| `capture_time` | when Atlas observed it (host monotonic, diagnostic only) | §5.2 |
| `state_digest` | **raw content identity** of the canonical state (temporal-level, §11.2): no semantic equivalence is applied to it | §11 |
| `envelope_digest` | identity of the observation record as received, including metadata | §11.3 |
| `observation_id` | derived, stable handle for one observation inside its stream | §4.3 |
| `pair input` | the previously accepted observation `A`, **supplied** to a comparison by the caller and never stored or reconstructed by the layer | §6.7 |
| `AdmissionOutcome` | stream admission result: `ACCEPTED` / `DUPLICATE_ACKNOWLEDGED` / `REJECTED_STALE` / `NEW_EPOCH` / `REJECTED_INVALID` — the last is admission-level only and is never the pair-level `OBSERVATION_INVALID` | §6.6, §6.8 |
| `DeltaOutcome` | delta-level outcome: `COMPUTED` / `TEMPORAL_DISCONTINUITY` / `OBSERVATION_INVALID` | §8.2 |
| `EntityDeltaKind` | entity-level fact: `OBJECT_ADDED` / `OBJECT_REMOVED` / `OBJECT_CHANGED` / `NO_CHANGE` / `IDENTITY_AMBIGUOUS` | §8.3 |
| `FieldObservationState` | per-field coverage: observed-changed / observed-unchanged / unavailable / unsupported / invalid | §10.2 |

## 4. Temporal Observation contract

### 4.1 Schema shape

`TEMPORAL_OBSERVATION_SCHEMA_VERSION = "1"` (temporal-level; **independent** of
`PAYLOAD_SCHEMA_VERSION` and of `REPORT_FORMAT_VERSION` — a temporal schema bump never implies a
canonical or payload bump, and vice versa).

```text
TemporalObservation := {
  observation_schema_version : "1"
  stream_id                  : non-empty string
  continuity_id              : non-empty string
  sequence                   : integer >= 0          # strictly increasing per epoch; MAY gap (§5.4)
  source_time                : SourceTime            # §5.1
  capture_time               : CaptureTime           # §5.2, diagnostic only
  producer                   : ProducerProvenance    # §4.4
  capability                 : CapabilityContract    # §4.5 / §10
  snapshot                   : CanonicalSnapshot     # §4.6 — ONE normative representation
  state_digest               : 64-lowercase-hex      # §11.2 — ALWAYS required
}
```

`state_digest` is **always required** and is **always recomputed by Atlas** from `snapshot` under
§11.2. There is no producer-declared "invalid" variant of it (revision 1 left one undefined), and no
producer declaration is ever trusted as an authority: a declared value that disagrees with the
recomputation makes the **arrival** `REJECTED_INVALID` (`STATE_DIGEST_MISMATCH`) at stage 1 — the arrival
is not admitted as an observation and no record is emitted (§6.8, §10.5).

### 4.2 Identity fields that are NOT interchangeable

| Field | Scope | Survives producer restart | Survives Atlas restart | Identity-bearing for world state |
| --- | --- | --- | --- | --- |
| `stream_id` | one observed subject (scene/twin/capture) | yes (declared) | yes (durable, Atlas-owned) | no — scope only |
| `continuity_id` | one continuous temporal history | **no** (must change on producer restart) | yes | no — comparability gate only |
| `sequence` | one continuity epoch | **no** (reset on epoch change) | yes | no — order only |
| `state_digest` | one canonical state | yes | yes | **yes** (§11.2) |
| `observation_id` | one observation record | derived | derived | no |

`stream_id` and `continuity_id` are **producer-declared but Atlas-validated** (§6.3): a producer
that keeps `continuity_id` constant and resets `sequence` without declaring a boundary is **not**
granted a new epoch — its observations are rejected as stale (§6.3, §6.6), so an undeclared reset can
never buy a fresh comparability window.

### 4.3 `observation_id`

```text
observation_id := "obs:" + first_16_hex(sha256(canonical_tuple))
canonical_tuple := ("v1", stream_id, continuity_id, sequence)
```

`observation_id` is a *handle*, not evidence of state: two different states never share an
`observation_id` inside a stream (the triple is unique by admission, §6.4), while an identical
duplicate re-delivery carries the **same** `observation_id` and is acknowledged idempotently instead
of producing a delta (§5.5, §6.6). Nothing may compare states via `observation_id`.

### 4.4 `producer` provenance

Reuses the repository's provenance vocabulary (`planning/digital_twin_provenance.py` →
`ProvenanceSource`, `ProvenanceRecord`) instead of inventing a parallel one:

```text
ProducerProvenance := {
  producer_source    : "BLENDER" | "UNREAL" | "PHOTOGRAMMETRY" | "REPLAY" | "OTHER"   # ProvenanceSource-aligned
  producer_contract  : non-empty string        # e.g. "extraction_fidelity_v1"
  engine_version     : string                  # e.g. "4.4.3"
  engine_build       : string                  # e.g. "802179c51ccc"
  producer_session_id: non-empty string        # one producer PROCESS INCARNATION (recovery contract §9)
  producer_instance_ordinal : integer >= 0     # restart counter within a stream (Atlas-observed)
}
```

* `producer_session_id` follows recovery contract §9 in spirit: it must be freshly generated for every
  process start and must not be a reusable application-level session name; PID alone is not identity.
* `engine_build` is quoted rather than assumed: the Blender track pins build `802179c51ccc`
  (asset-level evidence recorded in `planning/blender/BLENDER_EXTRACTION_FIDELITY_V1_PREFLIGHT_FINDING.md`).
* The provenance record is **diagnostic**: no provenance field participates in `state_digest` (§11.4).

### 4.5 `capability` — the availability declaration (feeds §10)

```text
CapabilityContract := {
  contract_id               : non-empty string   # producer contract that produced the snapshot
  observable_fields         : sorted list of field names from the TEMPORAL COMPARISON FIELD UNIVERSE
                              (§10.1 set A) that the producer CLAIMS to observe
  unobservable_fields       : sorted list of field names from the DECLARED-UNOBSERVABLE SET
                              (§10.1 set B) that the producer DECLARES it does not observe
  representation_state      : sorted list of payload encoding facts, e.g.
                              "materials:omitted", "materials:empty", "normals:key-absent",
                              "uvs:key-absent", "local_frame_id:key-absent"
}
```

`observable_fields ∪ unobservable_fields` must equal the **temporal field universe** of §10.1
(set A ∪ set B) **exactly**, and the two lists must be disjoint — otherwise the capability declaration
is invalid and the observation fails closed (§10.5). Derived fields (`world_bounds`, §10.1 set C) are
in **neither** list: they are outside the temporal contract entirely and are never declared, compared
or reported. This is the mechanism that prevents the layer's central failure mode: reading *omitted*
as *unchanged*.

### 4.6 `snapshot` — the canonical snapshot (ONE normative representation)

Revision 1 allowed two alternative shapes ("payload-shaped **or** canonical-model-shaped"). That was
a defect: two admissible shapes make cross-language parity and digest agreement unverifiable. v1 now
defines **exactly one** representation.

**CanonicalSceneSnapshot (normative).** `snapshot` is a JSON-native value with the **canonical parser's
input shape**: exactly the scene/object/mesh dictionaries that `parse_scene_report_input` accepts,
using only exact built-in `str` / `bool` / `int` / `float` / `None` / `list` / `dict` values and the
closed key grammars the frozen canonical layer enforces (`_SCENE_ALLOWED`, `_OBJECT_ALLOWED`,
`_MESH_ALLOWED`, `planning/blender/scene_model.py` :167-206):

```text
CanonicalSceneSnapshot := {
  "scene_id": str, "unit_system": str,
  "objects": [ { "object_id": str, "name": str,
                  "collection": str|null, "parent_object_id": str|null,
                  "location": [f,f,f], "scale": [f,f,f], "rotation": [f,f,f,f],
                  "visible": bool,
                  "mesh": {"mesh_id": str,
                           "vertices": [[f,f,f], ...], "faces": [[int, ...], ...],
                           "materials": [str, ...] } | null }, ... ],
  "coordinate_frame": str|null, "world_bounds": [[f,f,f],[f,f,f]]|null
}
```

Requirements:

1. **One shape, no alternatives.** Producers holding an extraction payload convert it through the
   **frozen** canonical boundary first (`payload_to_scene_model` / `parse_scene_report_input`) and the
   observation carries only the resulting canonical input shape. A payload-shaped snapshot (for example
   one still carrying `schema_version`) is **not** admissible, and neither is "the canonical model's
   own dictionary form" as a second option.
2. `snapshot` MUST parse under `parse_scene_report_input` with no modification. A snapshot that fails
   canonical parsing makes the arrival `REJECTED_INVALID` at stage 1 (§6.8), with the parser's own error
   reported verbatim.
3. The temporal layer MUST NOT add, remove, default, reorder or repair any field, and MUST NOT inject
   omitted canonical fields (`normals`, `uvs`, `local_frame_id`) to "complete" the snapshot. Object
   order is preserved as received (comparison and the §11.2 digest do not depend on it).
4. `state_digest` is always required, is computed from `snapshot` under §11.2, and is **recomputed**
   before use; a mismatch makes the arrival `REJECTED_INVALID` (`STATE_DIGEST_MISMATCH`) at stage 1, so
   no record is emitted (§6.8). A producer-supplied digest is metadata, never authority.
5. The snapshot is **not** re-serialized into `scene_input_digest`'s input space: `scene_input_digest`
   remains a kernel-computed property of the canonical scene (§11.1) and is never recomputed,
   redefined or extended here.

## 5. Time-domain model

### 5.1 `source_time` — engine/media timeline position (typed, integer-exact)

```text
SourceTime := {
  domain : "MEDIA_TICKS" | "FRAME_INDEX" | "SOURCE_SECONDS_EXACT"
  value  : integer                 # ticks / frame number / exact-microsecond count
  rate   : {num: integer > 0, den: integer > 0}   # ticks or frames per second (exact rational)
  ordering_epoch : integer >= 0     # producer-declared timeline epoch; MUST change on seek/reset
}
```

Design decisions, with rationale:

* **Integers and rationals, not floats.** Ordering and equality on `source_time` are integer
  operations, so they are exactly reproducible in C++ and immune to float drift. `SOURCE_SECONDS_EXACT`
  is expressed in exact microseconds precisely so no decimal approximation enters ordering.
* **`ordering_epoch` is part of the time value.** A timeline seek/scrub is not a large backwards step
  in `value`; it is a **new epoch**. This makes "time went backwards" a legal, nameable event instead
  of an ordering error.
* **No cross-domain arithmetic, ever.** A `MEDIA_TICKS` value and a `FRAME_INDEX` value are never
  subtracted, compared for staleness, or converted for ordering. Domain mismatch between two
  observations is a comparability failure (§6.3), not a conversion problem. (This mirrors the
  established clock-domain rule: only same-domain subtraction is meaningful.)
* **`source_time` is not world-state identity.** Two observations may share `source_time` and differ in
  state (§5.3); they may differ in `source_time` and share state (§5.6). Nothing in §11 digests
  `source_time`.

### 5.2 `capture_time` — when Atlas observed it (diagnostic only)

```text
CaptureTime := {
  domain : "MONOTONIC_HOST"
  value  : integer   # nanoseconds from the host monotonic clock (perf_counter_ns-class)
  received_wallclock_utc : OPTIONAL string, ISO-8601 display form
}
```

* `capture_time` is **never** used for ordering, identity, staleness decisions against source time, or
  digests. It exists for diagnostics and latency measurement only.
* **No wall-clock value is canonical world-state identity.** `received_wallclock_utc` is an optional
  display field; it is not identity-bearing, may be absent, and must never enter any digest in §11.
  Two observations whose *only* difference is capture metadata are **semantically identical** (§11.5).
* Host monotonic time is meaningful **within** one Atlas process incarnation only. It is not compared
  across an Atlas restart.

### 5.3 The four time concepts, kept apart

| Concept | Answers | Authoritative field | Never used for |
| --- | --- | --- | --- |
| **source time** | "which point of the engine/media timeline is this?" | `source_time` | identity, digest, ordering across epochs |
| **capture time** | "when did Atlas see this?" | `capture_time` | ordering, identity, comparability |
| **sequence** | "what is the deterministic order of admission inside this continuity?" | `sequence` | identity, time arithmetic |
| **continuity** | "are these two observations part of one continuous history?" | `continuity_id` + `producer_session_id` | anything about content |

### 5.4 Ordering rule (single-valued)

Within one continuity epoch, admission order is **`sequence`**. `sequence` is **strictly increasing
for accepted observations but MAY gap**: an accepted observation must satisfy
`sequence > last_accepted_sequence`, and the difference is *not* required to be 1. Revision 1 said
"strictly increasing by 1" here while §5.5 accepted gaps; this subsection is now the single rule.

```text
sequence_gap(A, B)    := B.sequence - A.sequence           # >= 1 for two accepted observations in one epoch
observations_skipped  := max(0, sequence_gap(A, B) - 1)    # 0 when the two sequences are adjacent
```

A gap is an **admission-count fact**: it means Atlas did not admit an observation carrying those
intervening sequence values. It says nothing about the source timeline, and **a sequence gap must
never be conflated with a source-time jump** (or with its absence): the gap is reported as
`observations_skipped`, a source-time step is reported by the `source_time` fields themselves (§5.6),
and neither is ever derived from the other.

Ordering by `source_time.value` is *not* the admission rule (it is an independent, declared-ordering
property that must be non-decreasing, §5.6). A chain of observations for delta computation is built
from ascending `sequence` inside one epoch; **no chain ever crosses an epoch boundary**.

### 5.5 Required behaviours (single-valued outcomes)

Every arriving observation has exactly one `AdmissionOutcome` (§6.6), and only an `ACCEPTED` arrival
proceeds to pair evaluation (§6.8): `DUPLICATE_ACKNOWLEDGED`, `REJECTED_STALE` and `REJECTED_INVALID`
produce **no record at all**.

| Situation | Required `AdmissionOutcome` | Delta consequence |
| --- | --- | --- |
| normal forward progression | `ACCEPTED`; `sequence` strictly increases (adjacent or gapped); `source_time` non-decreasing | compare with the previous accepted observation |
| identical `source_time` on consecutive observations, **same state** | `ACCEPTED` | `COMPUTED`; all entities `NO_CHANGE` |
| identical `source_time` on consecutive observations, **different state** | `ACCEPTED`, with `source_time_hold = true` on the delta | `COMPUTED` with real field changes; the delta must **not** claim time advanced |
| sequence gap (same epoch, `sequence` > last accepted + 1) | `ACCEPTED`, with `observations_skipped = max(0, gap - 1)` | direct pair comparison only; **no intermediate state may be synthesized** |
| identical duplicate (same `sequence` **and** same `state_digest`) | `DUPLICATE_ACKNOWLEDGED` — idempotent acknowledgement of an observation already admitted | **no `StateDelta` is created** (§8.1); admission state unchanged |
| same `sequence` with a **different** `state_digest` (contradictory duplicate) | `REJECTED_INVALID` (`CONTRADICTORY_SEQUENCE`) | no record; admission state unchanged |
| stale observation (`sequence` < last accepted, **all declared continuity metadata unchanged**) | `REJECTED_STALE` (`STALE_SEQUENCE_REJECTED`) | no delta; admission state unchanged; **no epoch change** (§6.3) |
| source timeline seek/scrub (`ordering_epoch` changes) | `NEW_EPOCH` | boundary path (§6.8.1): one boundary record — `TEMPORAL_DISCONTINUITY` when `A` is supplied and agrees with the recorded identity, `OBSERVATION_INVALID` / `PAIR_INPUT_IDENTITY_MISMATCH` when it is supplied but contradicts it, `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` when it is not supplied; empty entity list in every case |
| engine restart (`producer_session_id` changes) | `NEW_EPOCH` | boundary path (§6.8.1); empty entity list |
| Atlas restart | Atlas-owned admission state restored or re-established; comparable **iff** the next observation declares the same `continuity_id`, `producer_session_id` and `ordering_epoch` | `ACCEPTED` (comparison path) when every declared boundary field is restored unchanged; `NEW_EPOCH` ⇒ boundary path (§6.8.1) when a declared boundary field differs; `REJECTED_INVALID` (`ADMISSION_STATE_UNAVAILABLE`) when the admission state cannot be established at all — nothing is guessed. In each record-producing case a missing `A` yields `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` **in place of** `COMPUTED` or of the boundary record, a supplied `A` that contradicts the recorded identity yields `OBSERVATION_INVALID` / `PAIR_INPUT_IDENTITY_MISMATCH` (§8.1), and the classification is unchanged (§6.8.1) |
| discontinuity/reset **declared** by the producer (`continuity_id` and/or `producer_session_id` and/or `ordering_epoch` changes) | `NEW_EPOCH` | boundary path (§6.8.1); empty entity list |
| missing/invalid time or identity metadata | `REJECTED_INVALID` (`MISSING_SOURCE_TIME` / `MALFORMED_TIME` / `MALFORMED_IDENTITY`) | no record; never default to zero |

All four `NEW_EPOCH` rows share exactly one path — the **boundary path** of §6.8.1. It is chosen by the
classification alone and is not one of the comparison outcomes: it emits exactly one `TEMPORAL_DISCONTINUITY`
record when `A` is supplied and agrees with the recorded identity, exactly one `OBSERVATION_INVALID` /
`PAIR_INPUT_IDENTITY_MISMATCH` record when it is supplied but contradicts it, and exactly one
`OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` record when it is not supplied. The epoch boundary is
established in all three cases, the admission-state mutation is identical, and none of them may synthesize
a transition, a `NO_CHANGE` entry, or a cross-epoch `observations_skipped` count (§6.8.1).

Three rules make this table single-valued, and all are normative:

* **R-T1 (no inferred continuity).** Continuity is derived **only** from the declared continuity
  boundary: `stream_id`, `continuity_id`, `producer_session_id` and `source_time.ordering_epoch`
  (§6.2). **Similar or identical snapshots must never be treated as evidence of continuity**, and an
  identical `state_digest` across two epochs does not merge them.
* **R-T2 (no fabricated transitions).** A comparison across an epoch boundary produces
  `TEMPORAL_DISCONTINUITY` with an **empty entity list**. A discontinuity must not be reported as a
  burst of `OBJECT_ADDED`/`OBJECT_REMOVED`/`OBJECT_CHANGED` — that would manufacture a state transition
  Atlas did not observe.
* **R-T3 (a reset must be declared).** A `sequence` regression with unchanged declared continuity
  metadata is **not** a new epoch. Because a stale re-delivery and an undeclared producer reset are
  indistinguishable from the evidence alone, v1 admits neither: the observation is `REJECTED_STALE`,
  with no epoch change and no delta (§6.3, §6.6). A producer that resets its counter **MUST** declare the
  boundary through `continuity_id`, `producer_session_id` or `source_time.ordering_epoch`.

### 5.6 `source_time` monotonicity: declared-ordering property

Within one epoch, `source_time.value` (with `domain` and `rate` fixed) MUST be non-decreasing across
accepted observations. A decrease without an `ordering_epoch` change is a producer self-contradiction:
**fail closed** (`OBSERVATION_INVALID`, `SOURCE_TIME_NON_MONOTONIC`). Equal values are legal (§5.5).

## 6. Continuity model

### 6.1 `continuity_id` construction (producer-declared)

```text
continuity_id := non-empty string, freshly chosen when ANY of:
  - the producer process starts or restarts        (producer_session_id changes)
  - the source timeline is seeked / re-opened      (ordering_epoch changes)
  - the producer resets its stream or capture      (explicit reset)
  - the scope changes (different scene/twin under the same stream_id is forbidden, §6.5)
```

`continuity_id` is opaque to Atlas: Atlas does not parse it, derive it, or compare it to anything but
itself (§6.3).

### 6.2 Continuity states

| `ContinuityState` | Condition | Comparison allowed |
| --- | --- | --- |
| `SAME_EPOCH` | `stream_id` equal, `continuity_id` equal, `producer_session_id` equal, `ordering_epoch` equal, and `sequence` **strictly greater** than the last accepted sequence (adjacent or gapped, §5.4) | yes |
| `NEW_EPOCH` | `stream_id` equal and **at least one declared boundary field differs**: `continuity_id`, `producer_session_id` or `source_time.ordering_epoch`. **Nothing else creates an epoch** (§6.3) | no comparison — the boundary path (§6.8.1) emits one `TEMPORAL_DISCONTINUITY` record, one `OBSERVATION_INVALID` / `PAIR_INPUT_IDENTITY_MISMATCH` record when `A` is supplied but contradicts the recorded identity, or one `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` record when `A` is not supplied |
| `UNKNOWN` | metadata missing/malformed, or `domain`/`rate` mismatch between the pair, or capability mismatch | no — emit a record with outcome `OBSERVATION_INVALID` and the reason (§8.1). Two already-admitted observations are refused as a **pair**; this is never the admission-level `REJECTED_INVALID` (§6.8) |
| `DIFFERENT_STREAM` | `stream_id` differs | no comparison at all; not an error, but never a delta |

### 6.3 Validation duties (Atlas-side, fail closed)

* `stream_id`, `continuity_id`, `producer_session_id` MUST be non-empty exact strings; whitespace-only
  is invalid.
* A **`sequence` regression with otherwise-identical continuity metadata** is **never** an epoch
  change: it is `REJECTED_STALE` (§6.6). Atlas has no evidence that distinguishes a stale re-delivery
  from an undeclared producer reset, so it admits neither and mutates no admission state. A producer
  that resets its counter **MUST** declare the boundary through `continuity_id`, `producer_session_id`
  or `source_time.ordering_epoch`; an undeclared reset is never promoted to an epoch (R-T3).
* The temporal layer MUST NOT derive continuity from snapshot content, from `source_time` proximity,
  from `capture_time` proximity, or from producer-instance ordinals it observed itself.

### 6.4 Stream admission state (Atlas-owned, minimal)

```text
StreamAdmissionState := {
  stream_id, continuity_id, producer_session_id, ordering_epoch : as above
  last_accepted_sequence : integer | null
  last_accepted_state_digest : 64-hex | null
  last_accepted_observation_id : string | null
  accepted_count, duplicate_acknowledged_count, rejected_stale_count,
  invalid_count, epoch_count : integer
}
```

This is the **minimum** state needed to admit or reject the next observation. It contains no snapshot
content, no field history, no cache and no derived temporal model — a deliberate v1 restriction (§13.4).

**Mutation rule (single-valued).** Only an `ACCEPTED` observation updates
`last_accepted_sequence`/`last_accepted_state_digest`/`last_accepted_observation_id`. A
`DUPLICATE_ACKNOWLEDGED`, `REJECTED_STALE` or `REJECTED_INVALID` outcome leaves every one of those fields
**unchanged** (only its own counter increments), so a rejected or repeated delivery can never move the
stream's comparability window. `NEW_EPOCH` replaces the boundary fields and resets the counters for the
new epoch.

**This state holds no observation, and cannot produce one.** `last_accepted_state_digest` is a hash, not
content: it exists only so that an identical duplicate is recognisable (§5.5) and so that a restart can
tell whether it is still inside the same epoch. It is not invertible, and the layer must never attempt to
recover a snapshot from it (§6.7, R-R2/R-R6). Producing a `StateDelta` therefore requires the previously
accepted observation to be **supplied** — the layer neither retains it nor reconstructs it, and the
absence of a snapshot store is a deliberate non-goal, not a gap (§13.4, §16).

**What this state does supply is identity.** `last_accepted_observation_id` and
`last_accepted_state_digest` are Atlas-owned metadata *about* the earlier endpoint; they say which
observation it was and what its content identity is. That is a different fact from having its content, and
the two are never conflated (§6.7.1): a record may therefore be emitted that names the expected earlier
endpoint without holding its snapshot, provided it says so (§8.1 `pair_input`).

**This state is never read by the evaluator.** The admission layer constructs an **immutable projection**
of this bookkeeping — `FromIdentity` (§8.1) — *before* the stage-4 mutation, and passes it into evaluation
as data. Evaluation therefore reads nothing mutable: the projection it receives cannot change while it
runs, and mutating the admission state afterwards cannot alter the record (§12.1).


### 6.5 Scope rule

`stream_id` denotes exactly one observed subject. `snapshot.scene_id` changing within one
`SAME_EPOCH` pair is a scope violation: `OBSERVATION_INVALID` (`SCENE_SCOPE_CHANGED`). A different
subject is a different stream, not a delta.

### 6.6 `AdmissionOutcome` (closed vocabulary, exactly one per arriving observation)

| `AdmissionOutcome` | Condition | Admission-state effect | Record emitted? |
| --- | --- | --- | --- |
| `ACCEPTED` | `SAME_EPOCH` and `sequence` strictly greater than the last accepted sequence | updates the accepted triple | yes — stage 3 evaluates the pair (§6.7, §6.8) |
| `DUPLICATE_ACKNOWLEDGED` | same `sequence` **and** same `state_digest` as the last accepted observation | counter only | **no** — an idempotent acknowledgement, not a new fact about the world |
| `REJECTED_STALE` | `sequence` < last accepted sequence, with **all** declared continuity metadata unchanged (§6.3, R-T3) | counter only | no |
| `NEW_EPOCH` | a declared boundary field differs (§6.2) | boundary replaced, counters reset, **identically in every boundary record form** | yes — the boundary path (§6.8.1): one record, empty entity list — `TEMPORAL_DISCONTINUITY` when `A` is supplied and agrees with the recorded identity, `OBSERVATION_INVALID` / `PAIR_INPUT_IDENTITY_MISMATCH` when it contradicts it, `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` when it is not supplied |
| `REJECTED_INVALID` | the arrival is not a valid observation (malformed metadata, `CONTRADICTORY_SEQUENCE`, capability-declaration/§10.1 violation, `STATE_DIGEST_MISMATCH`, unparseable snapshot) **or** the admission state needed to classify it cannot be established (`ADMISSION_STATE_UNAVAILABLE`) | counter only | **no** |

`DUPLICATE_ACKNOWLEDGED`, `REJECTED_STALE` and `REJECTED_INVALID` are **not** errors in the sense of a
retryable fault: they are the admission layer's refusal to invent a fact, and none of them produces a
record. `REJECTED_INVALID` says *this stream did not admit this arrival*; its reason code says why
(`STATE_DIGEST_MISMATCH` — the arrival is malformed — versus `ADMISSION_STATE_UNAVAILABLE` — the stream
could not be classified at all). It is **never** the same fact as the pair-level `OBSERVATION_INVALID` of
§8.2, which appears on a record for a pair of observations that were *both* admitted. Keeping the two
apart is what keeps the stream-processing path of §6.8 single-valued.

### 6.7 Pair input — where the previously accepted observation comes from

A `StateDelta` is a statement about **two** observations, so a comparison needs the canonical snapshot of
both endpoints. The temporal layer stores neither of them (§6.4, R-R4): its durable state is identity,
counters and one content digest. The pair's earlier endpoint is therefore an **input**, not something the
layer retrieves:

```text
PairInput := (A, B, COMPARISON_CONTRACT_VERSION)
  A : the previously accepted observation, SUPPLIED by the caller — held by it for the duration of one
      admission step, or supplied by a consumer that retained it itself
  B : the observation just admitted
```

All five rules are normative:

* **P1 — supply, never reconstruct.** The layer must never attempt to rebuild `A` from
  `last_accepted_state_digest`, from a durable record, from the payload/report store, or from any cache.
  A hash is not an observation, and re-deriving one would be "recovery as re-observation" (R-R2, R-R6).
* **P2 — the layer keeps no snapshot.** Nothing in this contract permits the temporal layer to retain,
  cache, serialize or allocate storage for a snapshot, a field history or a prior delta (§13.4, §16).
  `StreamAdmissionState` (§6.4) holds no content.
* **P3 — a missing pair input is a pair-level failure, not an admission failure, and it never changes the
  classification.** If the caller cannot supply `A`, the arrival is still admitted exactly on its own facts
  (stage 2), and the step emits exactly one record whose outcome is `OBSERVATION_INVALID` with reason
  `PAIR_INPUT_UNAVAILABLE` and an empty entity list. Which record it replaces depends on the stage-2
  classification, and on nothing else: on `SAME_EPOCH` it replaces the `COMPUTED` comparison, on
  `NEW_EPOCH` it replaces the `TEMPORAL_DISCONTINUITY` boundary record while the epoch boundary is still
  established (§6.8.1). It must **never** emit `NO_CHANGE`, an empty `COMPUTED` delta, a delta against a
  freshly captured "current" state, or a silent epoch merge.
* **P4 — who retains `A` is out of scope.** Retention, buffering and windowing of observations belong to
  the caller or to a future store layer and need their own design gate (§13.4, §16). This subsection
  states only that the temporal layer is not that store.
* **P5 — what may persist is exactly the §6.4 triple plus counters.** Duplicate recognition (§5.5) needs
  only `last_accepted_state_digest`; every compared field needs the snapshots — which is precisely why
  they must be supplied rather than stored.
* **P6 — the projection is passed in, never read.** Admission state is Atlas-owned and mutable across
  steps; what an evaluation receives is `FromIdentity`, an **immutable projection** of it taken before the
  stage-4 mutation (§6.4, §8.1). The evaluator never reads the state itself, and no evaluation result may
  depend on when the state was sampled (§12.1).

`PairInput` names only the caller-supplied **content-bearing pair subset**: when `A` is in hand, the caller
supplies `PairInput.A` and the classification selects `ComparisonInput` or `BoundaryInput`. It is **not**
the complete evaluation domain. The complete domain is the closed four-variant `EvaluationInput` union in
§8.1: `ComparisonInput`, `BoundaryInput`, `RefusalInput` and `BoundaryRefusalInput`. The latter two carry no
`A`; their `FromIdentity` is admission bookkeeping passed as immutable data, never a substitute for a pair
(§6.7.1).

#### 6.7.1 Identity known versus content available (two independent facts)

A step can stand in two different epistemic positions with respect to the pair's earlier endpoint, and the
contract keeps them strictly apart:

| Fact | Source | What it means | What it never means |
| --- | --- | --- | --- |
| **identity known** | Atlas-owned admission bookkeeping (§6.4): `last_accepted_observation_id`, `last_accepted_state_digest` | Atlas knows *which* observation it expected to compare against, and that observation's content digest, because it recorded both when it admitted it | it does not mean the observation's content is present, retrievable or re-derivable. A handle names a state and a digest summarises it irreversibly; neither can produce it |
| **content available** | the caller's `PairInput.A` (§6.7) | the canonical snapshot of the earlier endpoint is in hand **for this step** | it does not mean the step will be compared — the classification decides that, not availability (§6.8, §6.8.1) |

```text
PairInputAvailability := "AVAILABLE" | "UNAVAILABLE"
```

* **Every emitted record states which position it is in**, through the mandatory field `pair_input`
  (§8.1). No consumer may infer availability from the presence of a digest, from a non-null
  `from_observation_id`, from an empty `entity_deltas`, or from a reason code.
* **Identity is known whenever a record exists at all.** A record is emitted only for a step whose
  stage-2 classification succeeded, and classification requires the admission state; when that state
  cannot be established the arrival is `REJECTED_INVALID` / `ADMISSION_STATE_UNAVAILABLE` and **no**
  record is produced (§6.8). A stream's very first observation likewise produces none, having no
  predecessor (§8.1). So `from_observation_id` and `from_state_digest` are always defined on a record, and
  they are read from the admission state **as it stood before the stage-4 mutation** — never reconstructed
  from `A`, never read from a payload/report store, never inferred from a cache (§6.7 P1, R-R2/R-R6).
* **Content availability never changes a classification.** It selects the record form only (§6.8.1
  clause 6).
* **A digest is identity, never content.** `from_state_digest` is a content *identity*: it was computed by
  Atlas from canonical content when the earlier endpoint was admitted, and it summarises that content
  irreversibly. No field of a record may be described, documented or implemented as reconstructing,
  standing in for, or substituting for `A`'s snapshot. The only value that ever carries observation
  content is a supplied `PairInput.A` — which is an input to the step and is not part of the record
  (§4.6, §8.1).
* **Availability is not monotone in time and carries no history.** `UNAVAILABLE` describes this step only;
  it is not a claim about the earlier endpoint's existence, validity or persistence, and it must never be
  recorded as state (§6.4, §13.4).
* **`FromIdentity` is bookkeeping passed in as data — a component of every variant, never an observation.**
  It is the immutable projection of Atlas-owned metadata (§6.4, §8.1) that **all four** evaluation-input
  variants carry: the expected endpoint's handle and content digest, plus the previous epoch's declaring
  fields — so that both the identity agreement and a boundary cause are functions of the input alone. It
  contains no snapshot content, it may never be substituted for `A` in any comparison, and it is never
  evidence that `A`'s content was available.

### 6.8 The stream-processing path (single-valued, four stages)

For every arriving observation exactly one path is taken, in this order:

| Stage | Input | Question | Result |
| --- | --- | --- | --- |
| 1 arrival validation | the envelope alone | is this a valid observation of this stream? | pass, or `REJECTED_INVALID` (§10.5 items 1-5) |
| 2 admission | the arrival + `StreamAdmissionState` | does it enter the stream, and how? | exactly one `AdmissionOutcome` (§6.6) |
| 3 pair evaluation | `EvaluationInput` (§8.1), constructed from the classification, supplied `A` when available, `B`, `FromIdentity` and the contract version | what is the factual difference? | one record (§8.1) — via the **comparison path** for an `ACCEPTED` arrival, or the **boundary path** (§6.8.1) for a `NEW_EPOCH` one |
| 4 state update | the outcome | what does the admission state become? | the §6.4 mutation rule |

* Stages 1 and 2 share **one** outcome name, `REJECTED_INVALID`, distinguished by reason code
  (arrival-level: `STATE_DIGEST_MISMATCH`, `UNKNOWN_SCHEMA_VERSION`, `MALFORMED_TIME`; admission-level:
  `CONTRADICTORY_SEQUENCE`, `ADMISSION_STATE_UNAVAILABLE`). Neither emits a record.
* Stage 3 runs only for an `ACCEPTED` or `NEW_EPOCH` outcome, and it has **two mutually exclusive paths**,
  chosen by the stage-2 classification and by nothing else:

  | Classification | Path | Only question asked | Result |
  | --- | --- | --- | --- |
  | `ACCEPTED` (`SAME_EPOCH`) | comparison path | pair input available, then the four comparison checks below | `COMPUTED`, or one `OBSERVATION_INVALID` record with the failing reason |
  | `NEW_EPOCH` | boundary path (§6.8.1) | pair input available, and then — only when it is — whether the supplied `A` agrees with the projection | one boundary record: `TEMPORAL_DISCONTINUITY` when `A` is supplied and agrees, `OBSERVATION_INVALID` / `PAIR_INPUT_IDENTITY_MISMATCH` when it contradicts it, `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` when it is not supplied |

* On the **comparison path** the checks are evaluated in a fixed order and the **first** failure wins:
  1. pair input available (§6.7) → `PAIR_INPUT_UNAVAILABLE`;
  2. identity agreement: `A.observation_id` and `A.state_digest` must equal
     `FromIdentity.last_accepted_observation_id` and `FromIdentity.last_accepted_state_digest` (§8.1) →
     `PAIR_INPUT_IDENTITY_MISMATCH`;
  3. capability equality (§10.4) → `CAPABILITY_MISMATCH`;
  4. `source_time` `domain`/`rate` agreement and monotonicity (§5.6) → `SOURCE_TIME_NON_MONOTONIC`;
  5. scene scope (§8.5) → `SCENE_SCOPE_CHANGED`;
  6. unit system (§8.5) → `UNIT_SYSTEM_CHANGED`.
  Checks 2-6 read only the evaluation input (`A`, `B`, `FromIdentity`); none of them reads admission
  state, and check 2 is decided before any comparison is attempted.
* The comparison path is **never** entered for a `NEW_EPOCH` arrival and the boundary path is never entered
  for a `SAME_EPOCH` one. No check from one path may run inside the other.
* Every record either path emits carries `pair_input` (§6.7.1), and its `from_observation_id` /
  `from_state_digest` are read from the admission state **as it stood before the stage-4 mutation** — never
  from a reconstruction of `A` and never from a store. When `A`'s content was not supplied the record must
  say so and must be worded so that it cannot be read as evidence that it was (§8.1).
* Every record is the result of exactly **one variant** of the closed evaluation-input domain (§8.1):
  `ComparisonInput` or `BoundaryInput` when `A` is supplied, `RefusalInput` or `BoundaryRefusalInput` when
  it is not. The variant is fixed by the classification and by availability, and by nothing else. **All
  four variants carry the immutable `FromIdentity` projection**, and evaluation reads nothing outside its
  argument (§8.1, §12.1).
* A stage-3 refusal **never retracts** a stage-2 acceptance: `B` remains the latest accepted observation
  (and, on the boundary path, the latest accepted observation *of the new epoch*) and the next arrival
  pairs with it. Admission and comparison are independent facts.
* The two names are not interchangeable anywhere in this document, and no outcome may be reported for a
  stage that did not run.

#### 6.8.1 The `NEW_EPOCH` boundary path (distinct from the comparison path)

Stage 2 detects `NEW_EPOCH` from the **declared** boundary fields alone — `continuity_id`,
`producer_session_id` or `source_time.ordering_epoch` differing from the last accepted observation's
(§6.2). That classification is made before any pair-level check runs, and it is not revised afterwards.

With `B` the arriving observation:

1. **`B` is admitted as the first accepted observation of the new epoch.** The admission-state mutation is
   identical to every other `NEW_EPOCH` outcome: the boundary fields are replaced, the epoch counters reset,
   and `last_accepted_sequence`/`last_accepted_state_digest`/`last_accepted_observation_id` become `B`'s. `B`
   is the latest accepted observation afterwards (§6.4).
2. **§9 field comparison is never invoked.** No field of the pair is compared, so no field change and no
   `NO_CHANGE` may be reported for any field or entity, and `entity_deltas` is empty (§8.1).
3. **No `SAME_EPOCH` comparison check is evaluated across the boundary** — not capability equality (§10.4),
   not `source_time` `domain`/`rate` agreement or monotonicity (§5.6), not scene scope (§8.5), not unit
   system (§8.5). Their inputs belong to two different temporal histories, so a reading taken across a
   boundary would be meaningless. Only the declared boundary fields (`continuity_id`, `producer_session_id`,
   `ordering_epoch`) can contribute boundary-cause codes. Other differences never become a comparison, a
   field change, or a substitute boundary cause.
   `reason_codes`, but it never becomes a comparison, a field change or a refusal.
4. **`observations_skipped` is never computed across the boundary** — `sequence` counters restart per epoch.
   It is `0` on whichever record the path emits, and no intermediate observation may be synthesized. The
   boundary reason is represented by the complete sorted set of applicable boundary-cause codes, not by an
   arbitrary primary cause.
5. **The only pair-level question the path asks is whether `A` was supplied**, and it determines the record
   form alone:
   * `A` **supplied and agreeing** with the projection (§8.1: `observation_id` and `state_digest` equal
     `FromIdentity`'s) ⇒ the input is `BoundaryInput` ⇒ emit exactly **one** boundary record with outcome
     `TEMPORAL_DISCONTINUITY`, whose cause is derived from `B`'s declaring fields against `FromIdentity`'s
     (§8.1);
   * `A` **supplied and disagreeing** with the projection ⇒ the input is still `BoundaryInput` ⇒ emit
     exactly **one** record with outcome `OBSERVATION_INVALID`, reason `PAIR_INPUT_IDENTITY_MISMATCH` and
     `pair_input = "AVAILABLE"`: no boundary record may be emitted from an endpoint that is not the
     recorded one, and the epoch boundary is nevertheless established;
   * `A` **not supplied** ⇒ the input is `BoundaryRefusalInput` (§8.1) ⇒ emit exactly **one** record with
     outcome `OBSERVATION_INVALID` and reason `PAIR_INPUT_UNAVAILABLE`.

Nothing else differs between the three cases: the epoch boundary is established in every one of them, the
admission-state mutation is identical, `B` remains the latest accepted observation of the new epoch, and
none of them may synthesize a state transition, a `NO_CHANGE` entry, or a cross-epoch skip count. All
three carry the *same* `from_*` identity metadata, taken from the projection (§6.7.1, §8.1). The supplied-
`A` agreement case is the only one that yields `TEMPORAL_DISCONTINUITY`; a contradictory supplied `A`
yields `PAIR_INPUT_IDENTITY_MISMATCH`, and a missing `A` yields `PAIR_INPUT_UNAVAILABLE`. Boundary-cause
codes, when applicable to the declared boundary fields, are included in the refusal forms as well.
6. **Precedence.** `NEW_EPOCH` classification takes precedence over the `SAME_EPOCH` stage-3 comparison
   checks. Pair-input availability determines only *which record the boundary path emits*; it must never
   erase, downgrade or re-classify the detected boundary, and it must never route the step into the
   comparison path. A step that declares a boundary is a boundary step, whether or not its earlier endpoint
   was supplied: the variant is fixed by the classification and by availability alone, and availability
   selects `BoundaryInput` versus `BoundaryRefusalInput`, never a different classification (§8.1). Whether
   the supplied endpoint agrees with the projection decides the *record form* on that path — boundary
   record, identity refusal, or pair-input refusal — and never the classification. A boundary identity refusal
   still preserves the stage-2 admission mutation; it does not roll back `B`.

## 7. Temporal identity model

### 7.1 The problem, stated exactly

The canonical model's object identity is `object_id`, which the validator and the parser require to be
a **non-empty exact string** but do **not** require to be unique
(`planning/blender/scene_model.py` :118-121 for `ObjectModel`; duplicate ids remain a kernel finding
rather than a parse failure — the kernel reports `OBJECT_ID_DUPLICATE`). The extraction design says so
explicitly: extraction §5.2 deduplicates by *source-object identity during traversal*, never by name,
"while preserving the kernel's ability to report true duplicate canonical IDs on hand-built or adapter
payloads", and §12 item 4 keeps `OBJECT_ID_DUPLICATE` a kernel finding. Mesh identity is weaker still:
`mesh_id = str(obj.name)`, as the extraction design §6 states plainly, is **not** declared to be
datablock identity — two objects sharing one mesh datablock receive *distinct* `mesh_id` values.

Consequence for this layer: **`object_id` is not a globally unique temporal identity**, and the design
must not pretend otherwise.

### 7.2 Decision: `object_id` is the v1 temporal key, with an explicit uniqueness precondition

v1 matches entities across two observations **by `object_id`**, under a precondition that is checked,
not assumed:

```text
For a pair (A, B) and each distinct object_id value v:
  countA(v) = number of objects in A with object_id == v
  countB(v) = number of objects in B with object_id == v

  if countA(v) == 1 and countB(v) == 1   -> v is PAIRABLE
  else                                   -> v is AMBIGUOUS   (§7.3)
```

* Every `PAIRABLE` id is compared field-by-field and yields `OBJECT_CHANGED` or `NO_CHANGE`.
* Every `AMBIGUOUS` id yields an entity entry of kind `IDENTITY_AMBIGUOUS` and is **excluded from
  pairing**. No best-effort matching, no positional matching, no "pick the first".
* The delta carries `identity_ambiguous_ids` (sorted) and the guarantee "no pairing was attempted for
  these ids".

### 7.3 Why not introduce a new stable temporal entity key in v1

Considered and rejected for v1, on architectural grounds rather than convenience:

1. **No such key exists in the frozen contract.** The canonical model has exactly the fields of
   `ObjectModel` (:105-137); extraction fidelity v1 deliberately did not add a producer-side stable
   key, and the payload schema is closed (`extraction_payload.py` :17-27). A new key would require a
   schema bump and a producer change — both explicitly out of scope (extraction design §3, §18).
2. **The repository already has the right precedent for *not* guessing.** The Digital Twin identity
   layer returns `INSUFFICIENT_EVIDENCE` rather than merging when required stable anchors are absent
   (`planning/digital_twin_identity.py` → `IdentityMatchStatus`, `IdentityAnchor`). v1 of the temporal
   layer adopts the same posture: ambiguity is a *result*, not a problem to solve by inference.
3. **A key derived from content is disqualified.** Deriving a temporal key from pose/geometry would
   make identity content-dependent, so any real change would read as remove+add and any coincidence as
   the same entity. That is precisely the "similar-looking snapshots imply continuity" error §5.5
   forbids, one level down.
4. **Fail-closed ambiguity is strictly safer than incorrect tracking**, which is the stated preference:
   an `IDENTITY_AMBIGUOUS` entity is a visible, actionable fact; a wrong pairing is silent corruption
   of every downstream temporal claim.

A future *temporal entity key* (producer-supplied, stable across rename, with its own ambiguity rules)
is a legitimate future capability and requires its own design gate (§18 Q1).

### 7.4 Declared limitations that follow (v1, explicit)

| Situation | v1 behaviour | Not claimed |
| --- | --- | --- |
| object renamed between observations (no other change) | `OBJECT_REMOVED` for the old id + `OBJECT_ADDED` for the new id | rename is **not** detected; no `OBJECT_RENAMED` kind exists |
| object removed and a different object added with the same id | `OBJECT_CHANGED` (field-level) | replacement is **not** distinguishable from change |
| one id duplicated on either side | `IDENTITY_AMBIGUOUS` for that id | no pairing, no partial field comparison |
| `mesh_id` differs while `object_id` matches | `OBJECT_CHANGED` with `mesh_id` in `field_changes` | no claim that the *datablock* changed |
| two objects sharing one mesh datablock (extraction §6) | two independent entities, compared independently | no datablock-level comparison |
| empty-string / whitespace-only id | impossible: canonical parse rejects it (`_exact_str`, :12-17) | — |

### 7.5 Mesh identity in temporal terms

Mesh comparison is **per object**, keyed by the owning `object_id`, over the canonical
`MeshModel` fields `{mesh_id, vertices, faces, materials, …}`. Because `mesh_id` is not datablock
identity, the temporal layer:

* never keys, groups or deduplicates objects by `mesh_id`;
* never infers shared topology from equal vertex tables (that would be an inference, not an observation);
* reports `mesh_id` as an ordinary comparable field, with its v1 caveat (`mesh_id == object_id` in v1,
  extraction §6).

## 8. State Delta model

### 8.1 Definition, record domain, and the boundary record

```text
StateDeltaRecord := the single record emitted for one stream step. Its domain is the union of:

  (1) comparison pairs  (A, B) where A and B are accepted observations of the same stream, B was
                        admitted after A, and ContinuityState(A, B) == SAME_EPOCH
                        => outcome COMPUTED, or OBSERVATION_INVALID if a stage-3 check fails

  (2) boundary pairs    (A, B) where A is the last accepted observation of continuity epoch n and B
                        is the first accepted observation of the immediately following DECLARED
                        epoch n+1 of the same stream
                        => outcome TEMPORAL_DISCONTINUITY when A is supplied and agrees with
                           the FromIdentity projection, OBSERVATION_INVALID /
                           PAIR_INPUT_IDENTITY_MISMATCH when it is supplied but contradicts
                           it, or OBSERVATION_INVALID / PAIR_INPUT_UNAVAILABLE when it is
                           not supplied (§6.8.1)
```

No other pair produces a record: a stream's first observation has no predecessor (no record), a
`DUPLICATE_ACKNOWLEDGED`, `REJECTED_STALE` or `REJECTED_INVALID` arrival produces none (§6.6, §6.8), and
two observations of different streams are never paired (§6.2 `DIFFERENT_STREAM`).

**One normative evaluation-input domain (closed, and the only purity definition in this document).** Every
record is produced by exactly one variant of one closed tagged union, and it is a **pure function of that
variant and of nothing else**:

```text
EvaluationInput :=
    ComparisonInput(A, B, FromIdentity, COMPARISON_CONTRACT_VERSION)         # SAME_EPOCH, A supplied
  | BoundaryInput(A, B, FromIdentity, COMPARISON_CONTRACT_VERSION)           # NEW_EPOCH, A supplied
  | RefusalInput(B, FromIdentity, COMPARISON_CONTRACT_VERSION)               # SAME_EPOCH, A not supplied
  | BoundaryRefusalInput(B, FromIdentity, COMPARISON_CONTRACT_VERSION)       # NEW_EPOCH, A not supplied

FromIdentity := ImmutableProjection(Atlas-owned admission bookkeeping, taken BEFORE the stage-4 mutation)
  # constructed by the admission layer and handed to evaluation as a value; never read from the state
  # itself, and carrying no snapshot content (§6.4, P6)
  last_accepted_observation_id      : string
  last_accepted_state_digest        : 64-lowercase-hex
  last_accepted_continuity_id       : string      # the previous epoch's declaring fields, so that both
  last_accepted_producer_session_id : string      # the identity agreement and a boundary cause are
  last_accepted_ordering_epoch      : integer     # functions of the input alone

StateDelta := F(EvaluationInput)   # ONE function, ONE input domain, defined here and nowhere else
```

| Record-producing path | `EvaluationInput` variant | `pair_input` | `outcome` |
| --- | --- | --- | --- |
| `SAME_EPOCH` + `A` supplied | `ComparisonInput` | `"AVAILABLE"` | `COMPUTED`, or `OBSERVATION_INVALID` when a comparison-path check fails — including the identity agreement, check 2 (§6.8) |
| `SAME_EPOCH` + `A` unavailable | `RefusalInput` | `"UNAVAILABLE"` | `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` |
| `NEW_EPOCH` + `A` supplied | `BoundaryInput` | `"AVAILABLE"` | `TEMPORAL_DISCONTINUITY`, or `OBSERVATION_INVALID` / `PAIR_INPUT_IDENTITY_MISMATCH` when `A` contradicts the projection (the epoch boundary is still established, §6.8.1) |
| `NEW_EPOCH` + `A` unavailable | `BoundaryRefusalInput` | `"UNAVAILABLE"` | `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE`, with the epoch boundary still established (§6.8.1) |

Rules:

* **The union is exhaustive and the variants are disjoint.** `A` is either supplied or not, and the
  stage-2 classification is either `SAME_EPOCH` or `NEW_EPOCH`; those four combinations are exactly the
  four variants. There is no fifth record-producing path and no record outside this union (§6.6, §6.8).
* **`pair_input` is determined by the variant, not carried as an independent parameter** — `"AVAILABLE"`
  for `ComparisonInput` and `BoundaryInput`, `"UNAVAILABLE"` for `RefusalInput` and
  `BoundaryRefusalInput`. A redundant availability parameter could express the illegal combination
  "refusal with content supplied", which this contract must not even be able to state.
* **Every variant carries the immutable `FromIdentity` projection**, and `F` reads nothing outside its
  argument. The refusal variants carry no `A` at all; the content-bearing variants carry `A` and the
  projection. In every case `FromIdentity` is **bookkeeping, not an observation**: it names the expected
  earlier endpoint and the epoch it belonged to, it holds no snapshot content, and it is never a substitute
  for `A` (§6.7.1, R-R2/R-R6).
* **The identity agreement is a function of the input.** For `ComparisonInput` and `BoundaryInput`,
  `A.observation_id` MUST equal `FromIdentity.last_accepted_observation_id` and `A.state_digest` MUST equal
  `FromIdentity.last_accepted_state_digest`. A disagreement yields exactly one record with outcome
  `OBSERVATION_INVALID`, reason `PAIR_INPUT_IDENTITY_MISMATCH` and `pair_input = "AVAILABLE"`, with an
  empty `entity_deltas`, **no field comparison** and — on the boundary path — **no boundary record**; the
  classification, and with it the epoch boundary, is unaffected (§6.8, §6.8.1).
* **Boundary causes are a function of the input, and the cause set is complete.** On `BoundaryInput` the
  boundary-cause reason codes are derived directly from every declared boundary field that differs between
  `B` and `FromIdentity`: `RESTART_PRODUCER_SESSION` for a different `producer_session_id`,
  `SEEK_OR_ORDERING_EPOCH_CHANGE` for a different `ordering_epoch`, and
  `TEMPORAL_DISCONTINUITY_CONTINUITY_ID_CHANGE` for a different `continuity_id`. **Every applicable cause
  code is emitted**, not just one selected cause, and the final `reason_codes` list is sorted canonically.
  No hidden or mutable state, producer field order, dictionary order, or input construction order participates
  in the result (§6.8.1, §12.2).
  comparing `B`'s declaring fields with the projection's recorded epoch fields — `RESTART_PRODUCER_SESSION`
  when `producer_session_id` differs, `SEEK_OR_ORDERING_EPOCH_CHANGE` when `ordering_epoch` differs, and so
  on. No hidden or mutable state participates in it (§6.8.1).
* **No path is defined as a function of an unavailable `A`.** When `A` is not supplied the input is a
  refusal variant, and `F` cannot return `COMPUTED`, a field change or a `NO_CHANGE` entry from it.
* **`F` is the only definition of purity in this document.** §12.1 restates it and adds nothing else.

`StateDelta` is not a function of capture wall-clock, host state, iteration order, any mutable cache, or any
state the layer retained: the layer retains no observation at all (§12.1).

**A `TEMPORAL_DISCONTINUITY` record is a `StateDelta`-shaped boundary record, and it is not a comparison.**
A boundary pair is non-comparable *by construction* — the declared boundary is exactly the statement that
the two endpoints belong to different temporal histories (§6.2). Emitting the record is legitimate (it is
the only way to report that continuity broke without inventing a transition), but everything that depends
on comparability is refused:

* §9 field comparison is **never applied** across a boundary: no field is compared, so no field change and
  no `NO_CHANGE` may be reported for any field;
* `entity_deltas` is empty **by rule** (R-T2): the record asserts *no* state transition, and it must never
  be rendered, summarized or re-exported as a burst of adds/removes/changes;
* `from_state_digest`/`to_state_digest`/`state_digest_changed` are still the raw content identities of the
  two endpoints (§11.2): `true` across a boundary is not evidence of a transition, and `false` does **not**
  merge the epochs (R-T1);
* `observations_skipped` is **not defined** across a boundary — `sequence` counters restart per epoch, so a
  cross-boundary difference of two sequence values is meaningless. The field is `0` on the record, and the
  boundary is named by its reason code (`RESTART_PRODUCER_SESSION`, `SEEK_OR_ORDERING_EPOCH_CHANGE`, …);
* `coverage` carries no per-field result: every set-A field is `INVALID_OBSERVATION` (the comparison could
  not be made) and every set-B field keeps its `UNSUPPORTED_BY_PRODUCER` capability fact, with the *reason*
  in `reason_codes` (§10.2);
* the boundary path takes `BoundaryInput` when `A` is supplied — whether or not it agrees with the
  projection — and `BoundaryRefusalInput` when it is not. A supplied `A` that contradicts the projection
  makes the record an `OBSERVATION_INVALID` / `PAIR_INPUT_IDENTITY_MISMATCH` refusal, and a missing `A`
  makes it an `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` refusal **in place of** the
  `TEMPORAL_DISCONTINUITY` record. Every rule above
  still holds for every such record — no field comparison, an empty `entity_deltas`, `observations_skipped = 0`,
  `source_time_hold = false`, coverage carrying the refusal — and the epoch boundary is established and `B`
  admitted in every case (§6.8.1). The record's *form* depends on what was supplied and on whether it
  agrees; the *boundary* does not.

The record's `continuity` field and its `outcome` are in a fixed correspondence, so a record can never
claim a comparison that was not performed:

| `ContinuityState` (§6.2) | Record | `outcome` |
| --- | --- | --- |
| `SAME_EPOCH` | comparison pair | `COMPUTED`, or `OBSERVATION_INVALID` on a stage-3 failure (§6.8) |
| `NEW_EPOCH` | boundary pair | `TEMPORAL_DISCONTINUITY` when `A` is supplied and agrees with the projection, `OBSERVATION_INVALID` / `PAIR_INPUT_IDENTITY_MISMATCH` when it is supplied but contradicts it, `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` when it is not supplied (§6.8.1) |
| `UNKNOWN` | comparison refused | `OBSERVATION_INVALID` |
| `DIFFERENT_STREAM` | none | — |

```text
StateDelta := {
  delta_schema_version   : "1"
  outcome                : DeltaOutcome               # exactly one, §8.2
  pair_input             : PairInputAvailability      # ALWAYS present: was A's CONTENT supplied? (§6.7.1)
  stream_id              : string
  from_observation_id    : string                     # identity metadata, never A's content (§6.7.1)
  to_observation_id      : string
  from_state_digest      : 64-lowercase-hex           # content identity of A — identity, not content (§6.7.1)
  to_state_digest        : 64-lowercase-hex           # content identity of B (§11.2)
  state_digest_changed   : bool                        # from_state_digest != to_state_digest
  continuity             : "SAME_EPOCH" | "NEW_EPOCH" | "UNKNOWN" | "DIFFERENT_STREAM"
  observations_skipped   : integer >= 0               # max(0, sequence gap - 1) on a COMPUTED record;
                                                       # 0 on a refusal or boundary record (§5.4, §8.1)
  source_time_hold       : bool                        # true iff identical source_time and different
                                                       # state; always false on a boundary record
  identity_ambiguous_ids : sorted list of strings
  entity_deltas          : ordered list of EntityDelta # §8.3, ordering in §8.4
  coverage               : per-field FieldObservationState map   # §10.2 — never optional
  reason_codes           : sorted list of strings      # named, closed vocabulary
}   # + delta_digest (§11.4)
```

`from_state_digest`, `to_state_digest` and `state_digest_changed` are **raw content-identity facts**
copied verbatim from the two observations; they are covered by `delta_digest` (§11.4). They are *not* a
comparison result: `state_digest_changed = true` with an empty field-change set is a legitimate delta —
it says the raw canonical content differs in a way the §9 relation declares equivalent (the pure
`q`/`-q` case of §9.4). `state_digest_changed` must never add, remove or reclassify an entity or field
change, and the semantic comparison must never alter a digest value (§11.5).

**`pair_input` and the `from_*` fields on every record (single-valued).** Every record carries
`pair_input` (§6.7.1), and its `from_*` fields are always defined: a record is emitted only for a step
whose classification succeeded, and classification requires the admission state (§6.7.1). The two positions
differ in exactly one thing — whether the earlier endpoint's *content* was in hand:

| Field | `pair_input = "AVAILABLE"` | `pair_input = "UNAVAILABLE"` |
| --- | --- | --- |
| `from_observation_id` | the supplied `A`'s `observation_id`, which MUST equal `FromIdentity.last_accepted_observation_id` (§8.1); a disagreement is the identity refusal `PAIR_INPUT_IDENTITY_MISMATCH` | `FromIdentity.last_accepted_observation_id` — identity metadata naming the **expected** earlier endpoint |
| `from_state_digest` | as above, for `FromIdentity.last_accepted_state_digest` | `FromIdentity.last_accepted_state_digest` — a content **identity**, never content, and never a licence to reconstruct `A` |
| `to_observation_id`, `to_state_digest` | `B`'s handle and content identity | identical — `B` is always the supplied arrival |
| `state_digest_changed` | `from_state_digest != to_state_digest`, a raw identity fact (§11.2) | the same comparison against `A`'s **recorded** identity: still a fact, and it never implies that a field comparison happened |
| `continuity` | the stage-2 classification | **unchanged** — availability never alters the classification (§6.8.1 clause 6) |
| `entity_deltas` | populated (`COMPUTED`), or empty on a refusal / boundary record | **empty**, and it means "nothing was compared" — never "nothing changed" |
| `observations_skipped` | `max(0, gap - 1)` on `COMPUTED`, else `0` | `0` — the count is a property of an admitted sequence pair and is populated only on `COMPUTED` |
| `source_time_hold` | per §5.5 | always `false` — with no content it cannot be established, and it is never inferred |
| `coverage` | per §10.2 | every set-A field `INVALID_OBSERVATION`, every set-B field `UNSUPPORTED_BY_PRODUCER`, and **no** `OBSERVED_*` entry anywhere (§10.2) |
| `reason_codes` | the failing check's code | exactly `PAIR_INPUT_UNAVAILABLE`, or exactly `PAIR_INPUT_IDENTITY_MISMATCH` when a supplied `A` contradicts the projection; either refusal also carries **all applicable boundary-cause codes** (`RESTART_PRODUCER_SESSION`, `SEEK_OR_ORDERING_EPOCH_CHANGE`, and/or `TEMPORAL_DISCONTINUITY_CONTINUITY_ID_CHANGE`) when the classification is `NEW_EPOCH` |
| `delta_digest` (derived) | canonical hash of the record (§11.4) | the same rule: it commits to the record **as emitted** — including `pair_input` and the identity metadata — and contains no observation content, so it can never be read as evidence that `A` was available |

`outcome` and `pair_input` are correlated but not interchangeable:

| `outcome` | `pair_input` | When |
| --- | --- | --- |
| `COMPUTED` | `"AVAILABLE"` | comparison path, every check passed |
| `TEMPORAL_DISCONTINUITY` | `"AVAILABLE"` | boundary path, `A` supplied |
| `OBSERVATION_INVALID` | `"AVAILABLE"` | a comparison-path check failed, or the supplied `A` contradicted the recorded identity (`PAIR_INPUT_IDENTITY_MISMATCH`) |
| `OBSERVATION_INVALID` | `"UNAVAILABLE"` | no comparison was performed because the earlier endpoint was not supplied — on **either** path (§6.8.1 clause 5) |

**An empty `entity_deltas` is never self-describing.** On a `COMPUTED` record it means "compared, nothing
changed"; on a `TEMPORAL_DISCONTINUITY` record "a boundary, no comparison"; on a `PAIR_INPUT_UNAVAILABLE`
record "no comparison was possible". The `outcome` and `pair_input` fields carry that distinction — never
the emptiness of a list, never the absence of a value, and never a reason code.

**Why not nullable `from_*` fields, and why not a separate result type (decision record).** Three models
were available for this form; the contract takes the first, and records why the others were rejected:

* **Chosen — keep every field present, populate the identity metadata from Atlas-owned bookkeeping, and
  state availability explicitly.** Atlas always knows which observation it expected to compare against;
  that is exactly what `last_accepted_observation_id` / `last_accepted_state_digest` exist for (§6.4,
  R-R4). The schema stays rigid, the one diagnosable fact is kept, and availability lives in a field
  instead of having to be inferred from a null, an empty list or a reason code.
* **Rejected — making `from_*` nullable or absent.** It discards information Atlas legitimately holds,
  makes the schema conditional per record, and leaves "no predecessor" (which produces no record at all,
  §8.1) distinguishable from "predecessor not supplied" only by other means. A null also reads as a gap to
  be filled, which invites exactly the reconstruction this contract forbids (§6.7 P1, R-R6).
* **Rejected — a separate result type for this form.** §8.1 defines one record domain and §8.2 makes the
  outcomes exhaustive for a record; a second result type would give one stream step two wire shapes, force
  every consumer to branch on type before reading any field, and contradict §6.8's "stage 3 always emits a
  record".

Under all three models the same thing must hold, and it holds here: **no field of a record may be
described, documented or implemented as reconstructing, standing in for, or substituting for `A`'s
snapshot** (§6.7.1).

### 8.2 `DeltaOutcome` (delta-level, exactly one)

| `DeltaOutcome` | When | `entity_deltas` |
| --- | --- | --- |
| `COMPUTED` | two accepted observations, `SAME_EPOCH`, pair input supplied, capabilities identical, every stage-3 check passed (§6.8) | populated |
| `TEMPORAL_DISCONTINUITY` | `NEW_EPOCH` — a **declared** continuity boundary (producer restart, seek, declared reset), §6.2. A boundary record, not a comparison (§8.1) | **empty by rule (R-T2)** |
| `OBSERVATION_INVALID` | a **pair-level** refusal of two accepted observations: missing pair input (`PAIR_INPUT_UNAVAILABLE`), a supplied `A` that contradicts the `FromIdentity` projection (`PAIR_INPUT_IDENTITY_MISMATCH`, §8.1), capability mismatch (§10.4), `domain`/`rate` mismatch, scene-scope change (§8.5), unit-system change (§8.5). **Never** for an arrival that failed validation — that is `REJECTED_INVALID` at admission and emits no record (§6.6, §6.8). It also covers the missing-pair-input case on **either** path, where the epoch boundary (if any) is still established and `B` is still admitted (§6.8.1); those records are distinguished from the check-failure ones by `pair_input = "UNAVAILABLE"` (§8.1) | **empty** |

The three outcomes are exhaustive for a **record**. Four situations produce no record at all:
`DIFFERENT_STREAM` (never paired) and the three admission-level non-acceptances
(`DUPLICATE_ACKNOWLEDGED`, `REJECTED_STALE`, `REJECTED_INVALID`, §6.6). Admission-level facts therefore
never appear in this table, which is what keeps `StateDelta(A, B)` a pure function of a *supplied* pair of
accepted observations (§6.7, §12.1) and keeps the stream-processing path single-valued (§6.8).

Every record states whether the earlier endpoint's content was supplied (`pair_input`, §6.7.1), so an empty
`entity_deltas` can never be misread as "nothing changed" (§8.1). One classification can produce one of
three records: a `NEW_EPOCH` step yields `TEMPORAL_DISCONTINUITY` when `A` is supplied and agrees with the
projection, `OBSERVATION_INVALID` / `PAIR_INPUT_IDENTITY_MISMATCH` when it is supplied but contradicts it,
and `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` when it is not supplied — with an identical
admission-state mutation and a still-established boundary in all three cases (§6.8.1). The choice is made by
availability and by the identity agreement alone, never by the comparison checks. Each outcome belongs to a
specific `EvaluationInput` variant and to no other (§8.1): `COMPUTED` only to `ComparisonInput`,
`TEMPORAL_DISCONTINUITY` only to `BoundaryInput`, and `OBSERVATION_INVALID` to every variant — a failed
comparison-path check on `ComparisonInput`, the identity agreement on either content-bearing variant, or a
missing endpoint on either refusal variant.

### 8.3 `EntityDeltaKind` (entity-level facts)

```text
EntityDelta := {
  object_id    : string
  kind         : EntityDeltaKind
  field_changes: ordered list of {field, before, after}    # empty iff kind != OBJECT_CHANGED
  ambiguity    : {count_before, count_after}                # present iff kind == IDENTITY_AMBIGUOUS
}

EntityDeltaKind :=
  OBJECT_ADDED | OBJECT_REMOVED | OBJECT_CHANGED | NO_CHANGE | IDENTITY_AMBIGUOUS
```

Wording discipline (this is a contract, not style): the kinds are **factual state transitions only**.
`OBJECT_ADDED` means "an entity with this id is present in B and absent in A". It must never be
rendered, summarized or re-exported as an event name (§17).

### 8.4 Ordering (deterministic, total)

1. Entity entries are ordered by `object_id` in **Unicode code-point order** (Python `str` ordering;
   UTF-8 byte order agrees — the same rule extraction §5.3 uses for objects).
2. Ties are impossible for `PAIRABLE` ids (uniqueness precondition); `IDENTITY_AMBIGUOUS` entries are
   unique per id by construction.
3. Field entries inside an `OBJECT_CHANGED` are ordered by the **canonical field order** of §9.1.
4. `identity_ambiguous_ids` and `reason_codes` are sorted; `coverage` is a map keyed by field name and
   is therefore order-free.
5. No ordering depends on dictionary insertion order, hash seed, pointer identity or producer order.

### 8.5 Scene-level fields

`scene_id` and `unit_system` are compared **before** object pairing:

* `scene_id` differs inside a comparable pair ⇒ `OBSERVATION_INVALID` / `SCENE_SCOPE_CHANGED` (§6.5).
* `unit_system` differs inside a comparable pair ⇒ `OBSERVATION_INVALID` / `UNIT_SYSTEM_CHANGED` —
  coordinate comparisons across a unit change are meaningless, and silently reporting them as
  "movement" would be a false state transition.
* `coordinate_frame` is **unobservable in v1** (§10.3), so it can never be a change *or* an
  unchanged claim.

## 9. Field comparison rules

### 9.1 Canonical field order and comparison semantics

| # | Field (canonical) | Source | Comparison | Change means |
| --- | --- | --- | --- | --- |
| 1 | `collection` | `ObjectModel.collection` (`Optional[str]`) | exact string equality; `None` ↔ value is a change | the **representative** collection changed (§9.6) |
| 2 | `parent_object_id` | `ObjectModel.parent_object_id` | exact string equality; `None` ↔ value is a change | parent reference changed (not "the object moved in the world") |
| 3 | `location` | `ObjectModel.location` (3 doubles) | exact componentwise equality | translation changed |
| 4 | `scale` | `ObjectModel.scale` (3 doubles) | exact componentwise equality | scale changed |
| 5 | `rotation` | `ObjectModel.rotation` (4 doubles, `(w,x,y,z)`) | exact componentwise equality **modulo the sign equivalence `q ≡ -q`** (§9.5) | rotation changed |
| 6 | `visible` | `ObjectModel.visible` (bool) | exact | visibility changed |
| 7 | `mesh_presence` | `mesh is None` | exact | mesh appeared/disappeared |
| 8 | `mesh_id` | `MeshModel.mesh_id` (str) | exact | mesh identifier changed (v1 caveat §7.5) |
| 9 | `vertices` | `MeshModel.vertices` (ordered) | positional, element-for-element, exact | vertex table changed (incl. reorder and length change) |
| 10 | `faces` | `MeshModel.faces` (ordered tuples) | positional, element-for-element, exact | face table changed (incl. reorder and length change) |
| 11 | `materials` | `MeshModel.materials` (ordered tuple of names) | exact sequence equality | material slot names changed (v1 caveat §9.7) |
| — | `normals`, `uvs`, `local_frame_id` | — | **NOT COMPARED** in v1 — unobservable (§10.3) | never reported as changed *or* unchanged |
| — | `world_bounds` | `SceneModel.world_bounds` | not compared (derived, not digested — extraction §11.1) | — |
| — | `coordinate_frame` | `SceneModel.coordinate_frame` | **NOT COMPARED** in v1 — unobservable (§10.3) | — |
| — | `scene_id`, `unit_system` | scene level | equality checks only (§8.5) | refusal, not a change |

### 9.2 Numeric equality (semantic, exact)

Semantic equality for `location`, `scale`, `rotation` and all vertex components is **exact equality of
the emitted canonical values** (IEEE-754 doubles, compared for value equality).

Rationale (grounded, not conventional): the producer applies the six-decimal half-even rounding policy
of extraction design §8.1 to vertex coordinates before emission, so sub-grid float noise in the source
is already quantized deterministically by the producer, and the canonical model stores what was
emitted. Introducing an epsilon would therefore add a *second*, non-authoritative quantization at the
comparison layer, which could report "unchanged" for a real change and could never be reproduced
exactly by a C++ implementation without agreeing on the epsilon — a silent divergence risk.

Consequences, stated so they cannot be misread:

* tiny numeric differences are **real changes** in v1; they are reported, not suppressed;
* `-0.0` and `0.0` compare equal (IEEE value equality) — this is deliberate and must be identical in
  any port;
* NaN/Infinity can never occur: the canonical parser rejects non-finite values
  (`_exact_finite_number`, `scene_model.py` :20-29), and the payload validator refuses non-finite
  numbers as well; a non-finite value reaching the comparison layer is `OBSERVATION_INVALID`.

### 9.3 Tolerance taxonomy (three kinds, never conflated)

| Kind | In v1 | Where it may appear | Effect on classification |
| --- | --- | --- | --- |
| **semantic equality** | **exact** — the only authority | `location`, `scale`, `rotation` sign rule, `vertices`, `faces`, `materials`, strings, bools | decides `OBJECT_CHANGED` vs `NO_CHANGE` |
| **diagnostic tolerance** | allowed, explicitly non-authoritative | `magnitude` annotations: per-axis absolute deltas, `max_abs_component_delta` | **must not** change classification or digest |
| **presentation-only tolerance** | out of scope | none in this contract | none |

v1 declares **no** diagnostic tolerance *values* (no epsilon constant exists in the contract).
A future revision may define named magnitude thresholds, but they must remain diagnostic: the design
forbids a threshold that can flip a delta's classification.

### 9.4 Quaternion comparison: `q ≡ -q` and nothing else

Two rotations are **semantically equal** iff, componentwise and exactly:

```text
(w,x,y,z)_A == (w,x,y,z)_B          OR          (w,x,y,z)_A == -(w,x,y,z)_B
```

* This is the **only** permitted equivalence. No renormalization, no hemisphere forcing beyond the
  ± identity, no angular tolerance.
* Non-unit raw quaternions are compared **as stored**. Normalizing would equate two *stored* states
  that the canonical layer and `scene_input_digest` deliberately treat as different (extraction design
  §7.2.1 layer 2: the canonical `ObjectModel.rotation` is the RAW tuple and is what the digest
  consumes).
* Sign-equivalence is a **comparison** rule and nothing else. It never touches content identity: when
  the only difference between two rotations is the sign, the delta reports **no `rotation` field change**
  *and* carries `reason_codes += ["ROTATION_SIGN_EQUIVALENT_ONLY"]`, **and** the raw pair shows
  `state_digest_changed = true` with different `from_state_digest`/`to_state_digest`, because
  `temporal_state_digest` is raw content identity and is **not** normalized to make `q` and `-q` agree
  (§11.2). The digest is never allowed to decide equivalence, and the equivalence is never allowed to
  rewrite the digest (§11.5, §11.6).

### 9.5 Mesh comparison (positional; no correspondence inference)

* `vertices`: compare positionally ([0]↔[0], [1]↔[1], …). Length difference ⇒ changed, reported with
  `vertex_count_before` / `vertex_count_after`. A reorder is a change.
* `faces`: compare positionally, each face compared as an ordered tuple. Loop order matters
  (extraction §6: source order is canonical). A uniform re-indexing of a mesh with an unchanged vertex
  table is a change, and it is **not** reported as "topology unchanged".
* No nearest-neighbour, no set comparison, no canonical face rotation, no permutation search: any of
  those would infer a correspondence the observation does not contain. (A *dedicated* capability could
  later define index-renumbering equivalence with its own proof obligations and evidence; it is not
  v1 and it is not this layer's job — §16.)
* Topology findings from the kernel (`MESH_DUPLICATE_VERTEX`, …) are **not** part of a state delta:
  findings are a kernel output over one state, and importing them would mix "health" into "difference".

### 9.6 Material comparison (and the representation-state trap)

`materials` is compared as an ordered sequence of names. Two v1 caveats are normative:

1. **Canonical collapse.** The canonical model stores `materials` as `tuple[str, ...]` and cannot
   distinguish the payload's `materials: []` from an omitted `materials` key (extraction design §4.3
   "canonical-collapse disclosure"). The temporal layer therefore compares *canonical* material state
   and **must take the representability fact from the observation's capability/representation record**
   (§4.5): a delta must report `materials` as `UNSUPPORTED_BY_PRODUCER`/`UNAVAILABLE` per §10 when the
   producer did not represent it, and must never silently report it as unchanged.
2. **Representative-level facts.** `collection` is a *representative* of multi-collection membership
   (extraction design §5.4), so a `collection` change is a change of representative — not proof of a
   membership change, and not proof of a move between collections. The delta says what it observed.

### 9.7 Missing / unavailable values inside a computed delta

* A field that is `UNAVAILABLE` or `UNSUPPORTED_BY_PRODUCER` in **either** observation appears in
  `coverage` with that state and appears in **no** `field_changes` entry.
* A field that is `INVALID_OBSERVATION` marks the record as a **pair-level refusal**: the record's
  outcome is `OBSERVATION_INVALID` with an empty entity list (§8.1), never a partial delta. (An arrival
  that fails validation never reaches a record at all — it is `REJECTED_INVALID` at admission, §6.8.)
* `None` in a canonical `Optional` field (`collection`, `parent_object_id`) is a **value**, not
  "missing": `None` ↔ string is a change.

## 10. Observability and capability semantics

### 10.1 The temporal field universe (closed, v1)

Revision 1 declared one "canonical field universe" that included `world_bounds` and then stated in
§10.3 that `world_bounds` is simply not compared — a field inside the universe that the contract
deliberately never observes. v1 now declares **three explicitly separated sets**, and only the first
two are part of a capability declaration (§4.5) or of the `coverage` map (§10.2).

**A. TEMPORAL COMPARISON FIELD UNIVERSE** — the fields the temporal layer compares:

| Level | Fields |
| --- | --- |
| scene (equality checks, §8.5) | `scene_id`, `unit_system` |
| object | `collection`, `parent_object_id`, `location`, `scale`, `rotation`, `visible`, `mesh_presence` |
| mesh (per object, when both sides have a mesh) | `mesh_id`, `vertices`, `faces`, `materials` |

`object_id` is the pairing key (§7.2), not a compared field. `name` equals `object_id` in v1
(extraction design §3) and is therefore not compared separately; if a producer ever emits a distinct
`name`, comparing it is a schema revision (§15.3). `mesh_presence` is the object-level fact that a mesh
exists or does not exist (the `mesh` key being `null` is the canonical encoding of "no mesh").

**B. DECLARED-UNOBSERVABLE SET** — canonical fields the model allows but the v1 producer contract does
not deliver. They are declared in `unobservable_fields`, appear in `coverage` with
`UNSUPPORTED_BY_PRODUCER`, and are **never** comparable:

| Field | Why |
| --- | --- |
| `normals`, `uvs`, `local_frame_id` | producer-deferred in v1 (extraction design §4.1, §4.2, §4.4) |
| `coordinate_frame` | the payload grammar allows it, but the v1 producer never emits it, so the canonical value is `None` for every live observation |

**C. DERIVED / OUTSIDE THE TEMPORAL CONTRACT** — canonical fields that are derived rather than
observed. They are excluded from the comparison universe, from the capability declaration and from the
`coverage` map. They are not "unobservable"; they are not part of this contract at all:

| Field | Why it is excluded |
| --- | --- |
| `world_bounds` | derived from the object set and object poses (extraction design §11.1: derived, not digested). Comparing it would report a *consequence* as if it were an observation |
| `schema_version` (payload-only) | not a canonical field; never admissible in a snapshot (§4.6) |

Excluding `world_bounds` this way does **not** extend the five-state model of §10.2: there is no
"derived" state, because a derived field is never observed, never declared and never reported. A
capability declaration that lists a set-C field is invalid (§10.5).

### 10.2 `FieldObservationState` (five states, exhaustive, never conflated)

| State | Meaning | Can it appear in `field_changes`? |
| --- | --- | --- |
| `OBSERVED_UNCHANGED` | observed in both observations; semantically equal | no |
| `OBSERVED_CHANGED` | observed in both; semantically different | **yes** |
| `UNAVAILABLE` | the producer contract covers the field, but this observation did not carry it | no |
| `UNSUPPORTED_BY_PRODUCER` | the field is in the DECLARED-UNOBSERVABLE SET (§10.1 set B): the producer contract does not deliver it at all (v1: `normals`, `uvs`, `local_frame_id`, `coordinate_frame`) | no |
| `INVALID_OBSERVATION` | the field could not be compared because the record is a refusal or a boundary record (§8.1); on such a record **every** set-A field has this state | no — the record's outcome is `OBSERVATION_INVALID` or `TEMPORAL_DISCONTINUITY` |

The `coverage` map is defined over the union of set A and set B of §10.1 — and nothing else. Fields of
set C (derived) have no entry: they are outside the contract, not unobserved.

**The central rule (this milestone's hardest red-team point):**

```text
omitted from representation            ≠  observed and unchanged
unsupported by the producer contract   ≠  observed and unchanged
unavailable in this observation        ≠  observed and unchanged
```

`coverage` is therefore **mandatory** on every emitted record, even for `TEMPORAL_DISCONTINUITY` and
`OBSERVATION_INVALID` outcomes (where it records the *reason* the comparison could not be made). A
consumer that reads only `entity_deltas` is reading an incomplete fact; the contract makes the omission
visible rather than silent. A coverage map exists **only** on a record: an arrival that is
`REJECTED_INVALID`, `REJECTED_STALE` or `DUPLICATE_ACKNOWLEDGED` has no record and therefore no coverage
at all (§6.6, §6.8) — there is no partial or placeholder coverage to misread.

On any record that is **not** a comparison, every field of set A is `INVALID_OBSERVATION` and every field of
set B keeps its `UNSUPPORTED_BY_PRODUCER` capability fact; **no** `OBSERVED_CHANGED` or `OBSERVED_UNCHANGED`
entry may appear, because nothing was compared. In particular a `pair_input = "UNAVAILABLE"` record (§8.1)
must not report a single field as observed — that is what would let a missing earlier endpoint look like a
world in which nothing changed.

### 10.3 v1 coverage table (what is actually observable today)

| Field | v1 state | Evidence |
| --- | --- | --- |
| `scene_id`, `unit_system`, `object_id`, `name`, `collection`, `parent_object_id`, `location`, `scale`, `rotation`, `visible` | `OBSERVED_*` | produced by `bpy_extraction` v1; digested per extraction §11.1 |
| `mesh_id`, `vertices`, `faces` | `OBSERVED_*` | mesh key set is exactly `{mesh_id, vertices, faces}` (+ `materials` when §4.3 permits) |
| `materials` | `OBSERVED_*` **or** `UNAVAILABLE` per observation | three encodings, extraction §4.3/§4.5: key omitted when any slot is unrepresentable |
| `normals`, `uvs`, `local_frame_id` | `UNSUPPORTED_BY_PRODUCER` | extraction §4.1/§4.2/§4.4: keys are never emitted in v1 |
| `coordinate_frame` | `UNSUPPORTED_BY_PRODUCER` | the payload grammar allows it (`extraction_payload.py` :17-27) but the v1 producer never emits it, so the canonical value is `None` for every live observation |
| `world_bounds` | **outside the temporal contract** (§10.1 set C): no coverage entry, no capability entry, never declared, never compared | extraction §11.1 (derived, not digested) |

The `coordinate_frame` row is the concrete reason this layer cannot yet compare snapshots produced by
*different engines*: `unit_system` is observable (`METERS`), but the coordinate frame is not, so
"cross-engine snapshot equivalence" is a **non-claim** (§15, §18 Q3).

### 10.4 Capability mismatch between two observations

If two observations declare different `observable_fields` sets, or different `contract_id`, the pair is
**not comparable**: `OBSERVATION_INVALID` / `CAPABILITY_MISMATCH`.

Rationale (same argument extraction §4.3 used for materials): a delta computed over the *intersection*
of two capability sets would be canonically indistinguishable from a full delta, i.e. it would
silently understate the observation. v1 refuses instead of narrowing.

### 10.5 Failure precedence (single-valued)

For one observation, validation is evaluated in this order and the **first** failure wins:

1. envelope schema version unknown/unsupported ⇒ invalid (`UNKNOWN_SCHEMA_VERSION`);
2. required envelope fields missing/malformed (ids, sequence, time) ⇒ invalid
   (`MALFORMED_IDENTITY` / `MISSING_SOURCE_TIME` / `MALFORMED_TIME`);
3. capability declaration inconsistent — overlap, unknown field, a set-C/derived field listed, or a
   universe other than §10.1 set A ∪ set B ⇒ invalid (`CAPABILITY_UNIVERSE_INCOMPLETE`);
4. the digest **recomputed** from `snapshot` under §11.2 ≠ the declared `state_digest` ⇒
   `REJECTED_INVALID` (`STATE_DIGEST_MISMATCH`). There is no "declared invalid" variant to skip this
   check, and the declared value is never trusted as an authority (§4.6);
5. `snapshot` fails canonical parsing (or is not in the single §4.6 representation) ⇒
   `REJECTED_INVALID` (parser error reported verbatim);
6. admission conflicts — a contradictory duplicate, an undeclared sequence regression, or an admission
   state that cannot be established for this stream ⇒ `REJECTED_INVALID` / `REJECTED_STALE` (§6.6);
   never a partial record, never a partial state mutation;
7. **pair-level** refusals are not arrival validation and are evaluated at stage 3 (§6.8). On the `SAME_EPOCH`
   comparison path, a missing pair input (§6.7), capability mismatch between the endpoints (§10.4),
   `domain`/`rate` mismatch, an identity disagreement between the supplied `A` and the `FromIdentity`
   projection (§8.1), scene-scope violation and unit-system violation (§8.5) each produce a record whose
   outcome is `OBSERVATION_INVALID` with an empty entity list. On the `NEW_EPOCH` boundary path, a supplied
   `A` that disagrees with the projection likewise produces `OBSERVATION_INVALID` / `PAIR_INPUT_IDENTITY_MISMATCH`
   with no comparison; **this refusal does not undo the stage-2 admission** — `B` remains admitted and the new
   epoch remains established (§6.8.1). Only the `SAME_EPOCH` identity-mismatch case leaves admission state
   unchanged, because there was no boundary mutation to preserve.

Items 1-6 describe stages 1-2 and always end in `REJECTED_INVALID` with no record; item 7 describes stage-3
pair refusals and always ends in a record with `OBSERVATION_INVALID`. The **boundary path** (§6.8.1)
evaluates none of the `SAME_EPOCH` comparison checks: a `NEW_EPOCH` arrival asks only whether `A` was
supplied and, when it was, whether it agrees with the projection (§8.1). The first failure wins within each
stage and within each path, so no arrival and no pair can produce two outcomes.
## 11. Digest and provenance boundaries

### 11.1 Digest 1 — `scene_input_digest` (FROZEN, unchanged)

* Computed by the kernel over exactly `scene_id`, `unit_system`, `coordinate_frame`, and per object
  `object_id`, `name`, `collection`, `parent`, `location`, `scale`, `rotation`, `visible`, and per mesh
  `mesh_id`, `vertices`, `faces` (`planning/blender/kernel.py` :93-121; extraction design §11.1).
* **No temporal metadata ever enters it**: not `sequence`, not `continuity_id`, not `source_time`, not
  `capture_time`, not `producer_*`, not capability declarations, not the temporal schema version.
  A temporal revision must never move this digest.
* The temporal layer may *carry* `scene_input_digest` as provenance (it is a legitimate canonical
  property) but must not recompute, extend, reorder or redefine it.
* `materials`, `normals`, `uvs`, `local_frame_id` are **not** in it (extraction §11.1) — which is
  precisely why it cannot serve as a temporal comparison (§11.6).

### 11.2 Digest 2 — `temporal_state_digest` (NEW, temporal-level)

Canonicalization (v1, normative; a new canonicalization, not a modification of any existing one):

```text
temporal_state_digest := sha256_hex( json.dumps(projection, sort_keys=True,
                                                 separators=(",", ":"),
                                                 ensure_ascii=True, allow_nan=False) )

projection := {
  "scene_id": ..., "unit_system": ...,
  "objects": [ per object, sorted by (object_id, entity_content_digest):
      {"object_id", "name", "collection", "parent_object_id",
       "location", "scale", "rotation", "visible",
       "mesh": {"mesh_id", "vertices", "faces", "materials"} | null } ]
}
```

Decisions, each with its reason:

* **Objects are sorted by `(object_id, entity_content_digest)`.** Unlike the frozen kernel digest (which
  consumes producer order), the temporal digest is a *content* identity and must not depend on the order a
  producer happened to emit. `entity_content_digest` is the digest of that one object's own canonical
  projection — the same field set, no ordering information, computed on demand and never stored (the
  single primitive of §13.2).

  Revision 2 used `occurrence_index` (the 0-based position among equal ids) as the tie-break, and that was
  **producer-order dependent whenever an `object_id` is duplicated**: the position of two same-id objects
  tracks the producer's emission order, so swapping them could move `temporal_state_digest` while the
  multiset of canonical content was unchanged. Revision 3 replaces it, and the claim is now a mechanism
  rather than an assertion:

  * two objects with the same `object_id` and **different** content are ordered by their content digests,
    so swapping their emission order cannot move `temporal_state_digest`;
  * two objects with the same `object_id` **and** the same content are interchangeable by construction, so
    their relative order cannot move it either;
  * therefore the digest is independent of producer emission order in **all** cases, duplicated ids
    included — the property revision 1 claimed and revision 2 half-delivered.

  The tie-break orders the *digest projection only*. It never reorders the entity comparison (§8.4), the
  canonical object order inside a snapshot (extraction design §5.3), or any payload/report output; and a
  digest difference still never implies a field change (§11.5).
* **`materials` participates** (the kernel digest excludes it), because materials *are* part of the
  observable v1 state and a temporal identity that ignored them would call a material change
  "identical".
* **`normals`/`uvs`/`local_frame_id` do NOT participate**: including their canonical (empty/None)
  values would assert equality of things the producer never observed — the §10.3 error, embedded in a
  hash. Their absence is recorded in `capability`/`coverage`, not in the digest.
* **`coordinate_frame` / `world_bounds` do not participate** (declared-unobservable / derived — §10.1
  sets B and C).
* **Raw content identity: no semantic equivalence is ever applied.** The digest is computed from the raw
  canonical values exactly as stored, so `q` and `-q` produce **different** `temporal_state_digest`
  values (§9.4). This is deliberate: normalizing would make the identity hash disagree with the
  canonical content that the frozen `scene_input_digest` and every correction artifact bind to.
  Semantic equivalence is a *comparison* relation (§9) and is never a digest transformation (§11.5).
* **No envelope metadata participates.** Two observations with identical canonical state have identical
  `temporal_state_digest` **regardless of** any difference in sequence, time, session, producer build or
  capture metadata (§11.5).
* Relationship to §11.1, stated plainly: `temporal_state_digest` is a **superset** of
  `scene_input_digest`'s object/mesh field list by exactly `{materials}`, with a different object
  ordering rule and a different role. Neither is derived from the other; neither substitutes for the
  other.

### 11.3 Digest 3 — `observation_envelope_digest` (provenance identity)

```text
observation_envelope_digest := sha256_hex(canonical_json(envelope_without_this_field))
```

covers: `observation_schema_version`, `stream_id`, `continuity_id`, `sequence`, `source_time`,
`capture_time`, `producer`, `capability`, `state_digest`.

Purpose: identity of the *record as received* (provenance/audit binding, mirroring how the recovery
track binds evidence to identity tuples via `docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md`
§16). It is **not** world-state identity and must never be used to decide whether the world changed.

### 11.4 Digest 4 — `delta_digest`

`delta_digest` is the canonical hash of the emitted `StateDelta` (same §8.2-style encoding: sorted keys,
compact separators, `ensure_ascii=True`, `allow_nan=False`). It therefore covers `from_state_digest`,
`to_state_digest` and `state_digest_changed` along with every other field, so a delta that records a
raw-content change while reporting no semantic field change is referenced by a digest that commits to
**both** facts. It exists so downstream layers can reference a specific delta (bind, receipt, replay
comparison) without re-deriving it. It excludes itself and excludes `capture_time` of either
observation.

A `pair_input = "UNAVAILABLE"` record (§8.1) is hashed exactly as emitted: the digest commits to the
outcome, the availability declaration and the `from_*` identity metadata — and it contains no observation
content, because the record holds none. It must never be described as committing to, standing in for, or
substituting for `A`'s snapshot (§6.7.1), and its value must not depend on whether `A`'s content happened to
be resident in the process.

**`delta_digest` is defined over the emitted record, never over the inputs.** For every `EvaluationInput`
variant (§8.1) it is the canonical hash of the record `F` returns — so it is deterministic for
`ComparisonInput`, `BoundaryInput`, `RefusalInput` and `BoundaryRefusalInput` alike, and two identical
inputs of the same variant always produce the same digest. Nothing outside the emitted record participates
in it. The mutable admission state is never read: the immutable projection the record was built from is a
component of the evaluation input (§8.1), and only the emitted record is hashed.

### 11.5 Content identity vs semantic equivalence (two independent relations)

Revision 1 defined semantic identity *as* digest equality, while §9.4 declared `q ≡ -q` semantically
equal and §11.2 hashed the raw quaternion. Those three statements cannot all hold. v1 now separates
them into two relations that are never conflated:

| Relation | Definition | What it is evidence of |
| --- | --- | --- |
| **content-identical** | `temporal_state_digest` values are equal **and** the capability/representation records are equal (same `contract_id`, same `observable_fields`, same `representation_state`) | the raw canonical content and the declared observability are the same |
| **semantically equivalent** | the §9 comparison relation reports **no** field change for **any** entity of the pair, with capabilities equal | the observed world state is unchanged *under the contract's equivalence rules* |

One direction only holds in general:

* content-identical ⇒ semantically equivalent (the §9 relation is a pure function of content, so equal
  content cannot produce a field change);
* **semantically equivalent ⇏ content-identical**: `q` and `-q` are semantically equivalent with no
  `rotation` change (§9.4) while their `temporal_state_digest` values **differ**, because the digest is
  raw content identity.

Both facts are reported in the delta, and neither overrides the other: for the `q`/`-q` case the delta
carries an empty `rotation` change list, the name `ROTATION_SIGN_EQUIVALENT_ONLY`, and
`state_digest_changed = true` with the two distinct digests (§8.1). The digest is **never** normalized
to force agreement with the semantic relation, and the semantic relation is **never** widened to force
agreement with the digest.

Neither relation is about time, order, session or capture metadata: two observations are **not**
required to share `stream_id`, `continuity_id`, `sequence`, `source_time`, `capture_time`, `producer`,
`observation_id` or `envelope_digest` for either to hold.

Conversely, **continuity is never inferred from either relation**: two content-identical observations
in different continuity epochs remain different epochs (R-T1).

### 11.6 Comparison vs digest: which answers which question

| Question | Answered by | Not answered by |
| --- | --- | --- |
| "is this the same canonical state, for provenance?" | `scene_input_digest` (frozen) | temporal digests |
| "is this the same raw canonical content, including materials?" | `temporal_state_digest` (content identity, never normalized) | `scene_input_digest`; the semantic comparison |
| "is this the same observed state under the contract's equivalence rules?" | the §9 comparison relation (no field changes) | **any** digest |
| "did anything change, and what exactly?" | `StateDelta` field comparison (§9) | **any** digest (a digest can only say "equal / not equal") |
| "does the only difference dissolve under an equivalence rule (e.g. `q ≡ -q`)?" **and** "did the raw content change anyway?" | semantic comparison + `reason_codes` **and** `state_digest_changed` with the digest pair — both facts, neither subordinate | neither relation substitutes for the other (§11.5) |
| "is this record the same record I already saw?" | `envelope_digest` / `observation_id` | content digests |

The frozen `scene_input_digest` is explicitly **not** a substitute for temporal comparison semantics:
its field boundary excludes `materials` (extraction §11.1), it consumes producer order, and it can only
answer equality.

## 12. Determinism rules

### 12.1 Purity

`StateDelta := F(EvaluationInput)` — **one** function over **one** closed input domain, defined in §8.1 and
nowhere else. There is no second purity definition in this document and no record-producing path outside
that union: each record is a pure function of exactly one variant of it (§8.1).

`F` is a function of its input and of nothing else: no wall clock, no host identity, no hash seed, no
dictionary iteration order, no pointer identity, no retained state, and no process-level fact such as
whether some other observation's content happens to be resident. The same input must produce the same
record — same `entity_deltas`, same ordering, same `reason_codes`, same `delta_digest` — in any process, in
any language, on any day.

The evaluator is therefore **stateless**: it holds nothing between steps, and it never reads the mutable
admission state (§6.4) — what it receives is `FromIdentity`, an **immutable projection** of that state taken
before the stage-4 mutation, carried by **all four** variants (§8.1). The state is therefore not an input;
the projection is, and mutating the state after the projection was taken cannot change the record.
When `A` cannot be supplied the step's input is a refusal variant
(`RefusalInput` or `BoundaryRefusalInput`), and `F` returns `OBSERVATION_INVALID` /
`PAIR_INPUT_UNAVAILABLE` for it — never `COMPUTED`, never `NO_CHANGE`, never an approximation, and never a
record derived from an unavailable `A`.

The three concepts are distinct and are never interchanged:

| Concept | What it is | Defined in | May it substitute for an observation? |
| --- | --- | --- | --- |
| **evaluation input** | one variant of the closed union — `A` (when supplied), `B`, the immutable `FromIdentity` projection (always), and the contract version | §8.1 | it *carries* observation content when `A` is supplied, and never otherwise |
| **admission state** | Atlas-owned bookkeeping: boundary fields, last accepted sequence / digest / handle, counters | §6.4 | **no** — the evaluator never reads it; it receives the immutable `FromIdentity` projection instead, and that projection is metadata, not snapshot content and never an operand of a comparison |
| **record output** | the `StateDelta` record `F` returns, including its `delta_digest` | §8.1, §8.2, §11.4 | **no** — a record describes a step; it is never read back as an observation |

### 12.2 Ordering rules (restated as a checklist)

* entities: `object_id` code-point order (§8.4);
* fields within an entity: canonical field order of §9.1 (not alphabetical, not discovery order);
* added/removed entities: interleaved in the same single pass, ordered by `object_id` — never
  "additions first" or "removals first";
* `identity_ambiguous_ids`, `reason_codes`: sorted;
* `coverage`: map (order-free), but any serialization sorts keys;
* no ordering may depend on the producer's object order, on mesh traversal, or on the snapshot's
  insertion order.

### 12.3 Equality rules summary

| Element | Rule |
| --- | --- |
| strings | exact code-point equality |
| bools | exact |
| `None` vs value | different |
| numbers | exact value equality (no epsilon; `-0.0 == 0.0`) |
| quaternions | exact componentwise, modulo `q ≡ -q` (§9.4) |
| vertices | positional, exact, length-sensitive |
| faces | positional, tuple-order-sensitive, length-sensitive |
| materials | ordered sequence equality |
| digests (`state_digest`, `envelope_digest`, `delta_digest`, `scene_input_digest`) | exact hex string equality — raw content identity, **never** normalized (§11.5) |
| `state_digest_changed` | the raw digest comparison; a reported fact, never a comparison result and never an input to classification (§8.1) |

### 12.4 Reason-code vocabulary (closed)

`TEMPORAL_DISCONTINUITY_*`, `TEMPORAL_DISCONTINUITY_CONTINUITY_ID_CHANGE`, `RESTART_PRODUCER_SESSION`, `SEEK_OR_ORDERING_EPOCH_CHANGE`,
`UNDECLARED_SEQUENCE_RESET`, `STALE_SEQUENCE_REJECTED`, `DUPLICATE_IDEMPOTENT_ACK`,
`CONTRADICTORY_SEQUENCE`, `SOURCE_TIME_NON_MONOTONIC`, `SOURCE_TIME_HOLD`, `OBSERVATIONS_SKIPPED`,
`CAPABILITY_MISMATCH`, `CAPABILITY_UNIVERSE_INCOMPLETE`, `STATE_DIGEST_MISMATCH`, `SCENE_SCOPE_CHANGED`,
`UNIT_SYSTEM_CHANGED`, `IDENTITY_AMBIGUOUS_IDS`, `ROTATION_SIGN_EQUIVALENT_ONLY`,
`UNOBSERVABLE_FIELDS_PRESENT`, `MISSING_SOURCE_TIME`, `MALFORMED_TIME`, `MALFORMED_IDENTITY`,
`PAIR_INPUT_UNAVAILABLE`, `PAIR_INPUT_IDENTITY_MISMATCH`, `ADMISSION_STATE_UNAVAILABLE`,
`UNKNOWN_SCHEMA_VERSION`.

`SEQUENCE_REGRESSION` and `DUPLICATE_OBSERVATION` were removed in revision 2: a bare regression no
longer names an epoch change (it is `STALE_SEQUENCE_REJECTED` / `UNDECLARED_SEQUENCE_RESET`), and an
identical duplicate no longer produces a delta to carry a reason code (`DUPLICATE_IDEMPOTENT_ACK` is an
admission acknowledgement, §6.6).

Revision 3 adds `PAIR_INPUT_UNAVAILABLE` (stage 3 could not obtain the pair's earlier endpoint, §6.7) and
`ADMISSION_STATE_UNAVAILABLE` (stage 2 could not classify the arrival at all), and renames the admission
outcome `INVALID` to `REJECTED_INVALID` — a rename of an admission-level fact, not a new fact, required so
that it can never be read as the pair-level `OBSERVATION_INVALID` of §8.2 (§6.6, §6.8).

`PAIR_INPUT_UNAVAILABLE` is emitted on **both** stage-3 paths — the `SAME_EPOCH` comparison path and the
`NEW_EPOCH` boundary path (§6.8.1) — and means the same thing on each: the earlier endpoint was not
supplied. It never means that an epoch boundary went undetected, unestablished or downgraded. Revision 4
adds no reason code.

Revision 5 adds `PAIR_INPUT_IDENTITY_MISMATCH`: a supplied `A` whose `observation_id` or `state_digest`
disagrees with the identity the admission state recorded for the earlier endpoint (§8.1). It names a
contradiction between two Atlas-owned facts, is emitted with `pair_input = "AVAILABLE"`, and never
produces a comparison. No other code is added.

Revision 6 adds no reason code either: unifying the evaluation-input domain (§8.1) formalises how records
are produced and introduces no new fact to name.

Revision 7 adds none: making `FromIdentity` an explicit component of every variant makes an existing input
explicit and names no new fact (§22.6).

Adding a code is a schema revision (§15.3), never an ad-hoc string.

## 13. Low-latency considerations (cost model only — nothing is implemented)

### 13.1 The intended ladder

```text
full canonical snapshot                      cost: O(1) — already exists (producer output)
    |
cheap identity/digest test                   cost: O(V+F) once per observation, then O(1) per pair:
    |                                          compare state_digest, capabilities, continuity
    |                                          -> if equal: COMPUTED / all NO_CHANGE, stop
    v
targeted field comparison only when needed    cost: O(size of the differing entity), not O(whole scene):
    |                                          per-entity content digests (§13.2) let unchanged
    |                                          entities be skipped without deep comparison
    v
deterministic StateDelta                     cost: O(changed fields) to build, O(n log n) to order
```

### 13.2 The one primitive that makes the ladder real

Per-entity `entity_content_digest` — the content identity of a single object (the §11.2 field set
restricted to that object, carrying no ordering information) — is the mechanism that turns "compare two
snapshots" into "compare two lists of hashes, then deep-compare only the mismatches". It has exactly two
contract uses: this short-circuit, and the §11.2 tie-break that makes the temporal state digest
independent of producer emission order even when `object_id`s are duplicated.

It is a *contract-level* primitive, computed on demand and **never stored**: caching entity digests is
precisely the kind of mutable temporal store this milestone defers (§13.4). It changes no semantics: an
entity whose digest matches is reported `NO_CHANGE` without field-by-field work; a mismatch is
deep-compared under §9 and the result is identical to the naive path.

Ordering of work must **not** change the answer: the short-circuit is an optimization of the same pure
function; any implementation that produces a different delta by short-circuiting is non-conforming.

### 13.3 Cost statements this revision does NOT make

No latency, throughput, memory or allocation targets are claimed. This milestone deliberately does not
state numbers it has not measured; a measurement gate (with real snapshots at realistic vertex counts)
is a separate, later step (§18 Q5).

### 13.4 Explicitly deferred (design-later, do-not-implement-now)

Streaming ingestion, back-pressure, ring buffers, caches, mutable temporal databases, background
workers, interval indexes, retention/window policy, delta compression, and any "keep the last N
observations" store. The task's instruction is explicit and this document obeys it: **design the
contract first**. Every one of the above needs its own design gate because each introduces state,
authority over state lifetime, and therefore new failure modes. This deferral is also why the pair's
earlier endpoint is a **supplied input** (§6.7) rather than a stored observation: until a retention gate
exists, the layer's only state is the content-free §6.4 triple plus counters.

## 14. Restart and recovery semantics

The temporal layer must connect cleanly to Atlas's existing recovery architecture, whose central
discipline is: *identity is declared and bound, ambiguity fails closed, and a restart is never treated
as proof about anything else* (`docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md` §4, §9, §16,
§20 Step 6 — "Unambiguous matches may proceed. Ambiguous matches MUST fail closed.").

| Event | Detection | Temporal behaviour |
| --- | --- | --- |
| **Atlas restarts** | Atlas process incarnation changes | `stream_id` and `continuity_id` are Atlas-durable/declared, so comparability is preserved **iff** the next accepted observation declares the same `continuity_id` and the producer's session/epoch are unchanged. The prior `last_accepted_sequence` is restored from durable state or the epoch is re-established. If the admission state cannot be established at all, the arrival is `REJECTED_INVALID` (`ADMISSION_STATE_UNAVAILABLE`) — the stream is re-established from a declared boundary rather than guessed. If the state *is* restorable but the caller cannot supply the pair input, stage 3 emits a record with `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` (**not** a silent `NO_CHANGE`, and never a reconstructed `A`) |
| **Blender restarts** | `producer_session_id` changes (and normally `continuity_id`) | `NEW_EPOCH` ⇒ boundary path (§6.8.1), empty entity list; `producer_instance_ordinal` increments |
| **Unreal restarts** | `producer_session_id` changes | identical rule (boundary path, §6.8.1); on the Unreal side this mirrors the recovery contract's `editor_session_id`-per-process-incarnation discipline, and PID alone is never identity |
| **producer stream resumes** | new session/epoch declared | `NEW_EPOCH`. If the stream already had an accepted observation, the first observation of the new epoch forms a **boundary pair** with the last accepted observation of the previous epoch and produces a `TEMPORAL_DISCONTINUITY` record (§8.1); if it is the stream's first observation ever, there is no predecessor and no record is produced |
| **duplicate re-delivery** | same `sequence` **and** same `state_digest` as the last accepted observation | `DUPLICATE_ACKNOWLEDGED`: idempotent acknowledgement; **no** `StateDelta`, no admission-state change (§6.6) |
| **sequence counter resets** | `sequence` regresses with **unchanged declared** continuity metadata | **`REJECTED_STALE`** (§6.3, §6.6): a bare regression is indistinguishable from a stale re-delivery, so it is neither an epoch change nor a delta. A producer that genuinely resets MUST declare the boundary through `continuity_id`, `producer_session_id` or `ordering_epoch` — then the "different continuity/session observed" row applies |
| **source time resumes** (timeline continues after a stall) | same epoch, `source_time` non-decreasing | comparable; a large forward step is a legal gap (`observations_skipped`), not a discontinuity |
| **stale observation arrives** (older `sequence` inside the same epoch) | `sequence` < `last_accepted_sequence` with unchanged declared continuity metadata | **`REJECTED_STALE`**; zero mutation of admission state (§6.4); no delta, and **no epoch change** — v1 refuses to guess whether it is looking at staleness or at an undeclared reset (§6.3) |
| **different continuity/session observed** | `continuity_id`/`producer_session_id`/`ordering_epoch` differ | `NEW_EPOCH` ⇒ boundary path (§6.8.1), empty entity list |
| **the pair's earlier endpoint is not supplied** | no `A` in the `PairInput` (§6.7) | the arrival is admitted on its own facts and stage 3 emits exactly one `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` record. The stage-2 classification is unchanged: on `SAME_EPOCH` (`ACCEPTED`) the refusal replaces the `COMPUTED` comparison; on `NEW_EPOCH` it replaces the `TEMPORAL_DISCONTINUITY` boundary record while the epoch boundary is still established and `B` is still the latest accepted observation of the new epoch (§6.8.1). The layer must not reconstruct `A` from `last_accepted_state_digest` or any store (R-R2, R-R6). The record's
`from_observation_id` / `from_state_digest` are the admission state's recorded identity metadata, read
before the stage-4 mutation, and `pair_input = "UNAVAILABLE"` states that no content was supplied (§6.7.1,
§8.1) |

Additional normative rules:

* **R-R1 — no intermediate states across a restart or discontinuity.** Atlas may not invent the states
  between the last observation of epoch *n* and the first of epoch *n+1*. The delta is a boundary
  marker, not a transition narrative.
* **R-R2 — recovery is not re-observation.** The temporal layer must never re-derive an observation
  from durable state to "fill a hole"; a missing observation is missing.
* **R-R3 — the temporal layer grants nothing.** Recovery authority (adjudicating orphaned work,
  receipts, claims, retries) stays with the existing recovery coordinator contract; the temporal layer
  may only *report* `TEMPORAL_DISCONTINUITY`.
* **R-R4 — durable state is minimal and content-free.** If Atlas persists anything across restarts, it
  is the §6.4 admission state (identity + counters + one digest), never snapshots or field history.
* **R-R5 — a reset is evidence only when it is declared.** A producer that resets `sequence` without
  changing a declared boundary field produces rejected-stale observations, not a new epoch (§6.3, R-T3).
  Atlas must never manufacture a fresh continuity window from an undeclared reset, because a new window
  would silently re-authorize comparisons the producer never asked for.
* **R-R6 — an observation is never reconstructed.** No path may rebuild a previously accepted observation
  from a digest, a durable record or a store, and no path may substitute a fresh capture for one: a
  comparison whose earlier endpoint cannot be supplied is refused (§6.7 P1/P3). Recovery restores
  *bookkeeping*, never content (R-R4).

## 15. Cross-engine / future C++ parity boundary

### 15.1 What parity means here (semantic, not byte-identical)

A C++ implementation must be able to consume the same canonical snapshot dictionary + observation
envelope and produce a **semantically identical** delta:

* same `DeltaOutcome` and `EntityDeltaKind` for every input pair;
* same field-change set and same ordering;
* same exact-equality semantics (IEEE-754 double comparison, `-0.0 == 0.0`, no epsilon);
* same `q ≡ -q` rule and the same `ROTATION_SIGN_EQUIVALENT_ONLY` reason code;
* same canonicalization rules for the digests of §11 (sorted keys, compact separators, ASCII-only
  escaping, non-finite refusal) so digest **values** agree for the same content — subject to §15.2.

### 15.2 Byte-identical serialization is NOT claimed

The repository's only canonical serializer today is Python's `json` (used by
`planning/blender/scene_report.py` :127-140 and `planning/unreal_evidence_digest.py` →
`_canonicalize`). Float *encoding* is Python-`repr`-based, so asserting byte-identical JSON across
languages would be an unverifiable claim. v1 therefore claims **semantic parity**, and requires a
separate serialization gate (shared, language-independent numeric encoding) before any
byte-identity claim. The same limitation was disclosed for the extraction layer (extraction design
§8.3) and is inherited unchanged here.

### 15.3 Versioning and compatibility

Three independent version numbers, never conflated: `PAYLOAD_SCHEMA_VERSION` (frozen, `"1"`),
`REPORT_FORMAT_VERSION`/`VALIDATOR_VERSION` (frozen, `"1"`), and the temporal pair
`TEMPORAL_OBSERVATION_SCHEMA_VERSION` / `DELTA_SCHEMA_VERSION` (new, `"1"`). A bump of any one is
mandatory before: adding a compared field, changing an equality rule, adding a `DeltaOutcome` or
`EntityDeltaKind`, extending the reason-code vocabulary, or changing a digest's field set. The temporal
layer may not bump a frozen version to make a new temporal concept fit.

## 16. Explicit non-goals

This milestone does **not** authorize or design: semantic events or event detection; impact/collision/
entrance/exit/hit/reaction naming (§17); streaming, buffering, back-pressure, caches, mutable temporal
stores, background workers or retention windows (§13.4); persistence of observations or deltas;
cross-engine geometric normalization or unit/frame conversion; vertex/face correspondence or
index-invariant mesh comparison; rename/replacement discrimination; a stable temporal entity key;
merge of multiple streams; any change to `SceneModel`, the parser, the validator, the payload schema,
the kernel, `scene_input_digest`, or the correction authority/executor/planner; any Blender or Unreal
live run; any write-back to an engine; any authorization, execution, retry, rollback, recovery or
scheduling authority.

## 17. Event Abstraction boundary

The output of this layer is **factual state transition only**:

| Produced by v1 | Forbidden in v1 |
| --- | --- |
| `OBJECT_ADDED`, `OBJECT_REMOVED`, `OBJECT_CHANGED`, `NO_CHANGE`, `IDENTITY_AMBIGUOUS` with field-level `before`/`after` | `impact`, `collision`, `entrance`, `exit`, `hit`, `reaction`, `goal`, `pass`, `shot`, or any other interpreted label |
| `TEMPORAL_DISCONTINUITY` / `OBSERVATION_INVALID` as boundary markers | "play started", "player left the field", "the ball was struck" |
| `reason_codes` from the closed §12.4 vocabulary | free-text causal explanations |

The downstream boundary is:

```text
StateDelta  ->  (future) Event Abstraction     [separate design gate; not designed here]
```

Requirements on that future layer, stated now so it cannot be improvised: it must consume deltas as
**facts**, must carry its own evidence requirements and its own determinism contract, must not weaken
this layer's coverage record (§10.2) when interpreting, and must not read `TEMPORAL_DISCONTINUITY` as
a transition. A label such as "impact" is a *semantic interpretation* that needs its own design,
its own red-team and its own live evidence (§18 Q6).

## 18. Open questions

| # | Question | Why it is open | Suggested next step |
| --- | --- | --- | --- |
| Q1 | Does a rename/replacement distinction require a producer-supplied stable temporal entity key? | v1 cannot distinguish rename from remove+add (§7.4); no such key exists in the frozen contract | a dedicated design gate for a producer-supplied key + schema/payload bump |
| Q2 | Is `stream_id` Atlas-minted or producer-declared when the producer has no notion of a subject? | producer-neutrality vs Atlas ownership | decide in the ingestion-adapter design (not this milestone) |
| Q3 | What establishes cross-engine geometric equivalence? | `coordinate_frame` is unobservable in v1 (§10.3) | a frame/unit contract gate (engine-neutral), then a cross-engine equivalence gate |
| Q4 | What is the retention/window policy for observations and deltas? | deliberately deferred (§13.4, §16) | storage/retention design gate with its own authority boundary |
| Q5 | What are the real cost numbers for §13's ladder? | no measurements exist; this revision claims none | a benchmark gate with realistic vertex counts and a pinned fixture |
| Q6 | What distinguishes a legitimate event from a factual delta at the boundary? | explicitly out of scope (§17) | Event Abstraction design gate |
| Q7 | Do consumers need `source_time` in `SOURCE_SECONDS_EXACT` for engines with no frame concept? | domain set may need re-derivation for live capture | revisit when the first live non-Blender producer is designed |
| Q8 | Should `NO_CHANGE` entities be emitted by default or only on request? | reporting-volume decision with no semantic content | decide with the first real consumer; §8.3 already fixes that semantics do not depend on it |

## 19. Adversarial and red-team requirements

### 19.1 Required attacks (each must be attempted against the *design*, and against any implementation later)

| # | Attack | Design answer | Where |
| --- | --- | --- | --- |
| 1 | duplicate `object_id`s across observations | `IDENTITY_AMBIGUOUS` for that id, no pairing, digest still defined | §7.2, §7.3, §11.2 |
| 2 | rename vs replacement | declared limitation: remove+add; **no** rename inference | §7.4 |
| 3 | object disappearance/reappearance across a gap | direct pair comparison inside an epoch (`observations_skipped`); across an epoch: discontinuity, empty deltas | §5.5, §14 R-R1 |
| 4 | reused ID by a different object | reported as `OBJECT_CHANGED` (v1 cannot tell) — declared, not hidden | §7.4 |
| 5 | collection movement | `collection` change is a representative-level fact only | §9.1, §9.6 |
| 6 | parent changes | compared exactly; `None`↔value is a change | §9.1 |
| 7 | quaternion `q` vs `-q` | sign equivalence in the **comparison relation** only, with a named reason code; the raw content digests still differ (never normalized) | §9.4, §11.2, §11.5 |
| 8 | non-unit raw quaternions | compared as **stored**; no normalization anywhere | §9.4 |
| 9 | tiny numeric noise vs true movement | both are changes (exact semantics); magnitudes are diagnostic only | §9.2, §9.3 |
| 10 | mesh topology mutation | positional comparison; reorder/re-index is a change; no correspondence inference | §9.5 |
| 11 | material-slot changes | ordered comparison + representation-state gate (omitted ≠ unchanged) | §9.6, §10.2 |
| 12 | unavailable and derived fields | five-state coverage for declared fields; never reported as unchanged; **derived** fields (`world_bounds`) are outside the contract entirely and have no coverage entry | §10.1, §10.2, §10.3 |
| 13 | identical snapshots at different times | content-identical, therefore also semantically equivalent (§11.5); **not** evidence of continuity | §5.5 R-T1, §11.5 |
| 14 | stale / out-of-order observations | `REJECTED_STALE`; zero admission-state mutation; **never** an epoch change | §5.5, §6.3, §6.6 |
| 15 | duplicate observations | identical ⇒ `DUPLICATE_ACKNOWLEDGED`: idempotent, admission state unchanged, **no `StateDelta`**; same `sequence` with a different digest ⇒ `REJECTED_INVALID` (`CONTRADICTORY_SEQUENCE`) with **no record**, state unchanged | §5.5, §6.6, §8.1 |
| 16 | sequence gaps vs source-time jumps | a gap is `observations_skipped = max(0, gap - 1)` with no synthesized intermediates, and is never reported as, derived from, or conflated with a source-time jump | §5.4, §5.5, §14 R-R1 |
| 17 | timeline seek | `ordering_epoch` change ⇒ `NEW_EPOCH` ⇒ boundary path (§6.8.1) | §5.1, §5.5, §6.8.1 |
| 18 | engine restart | `producer_session_id` change ⇒ `NEW_EPOCH` ⇒ boundary path (§6.8.1) | §5.5, §6.8.1, §14 |
| 19 | Atlas restart | comparability preserved only via declared/durable continuity: `ACCEPTED` when the boundary fields are restored unchanged, `NEW_EPOCH` ⇒ boundary path (§6.8.1) when a declared field differs, `REJECTED_INVALID` (`ADMISSION_STATE_UNAVAILABLE`) when the admission state cannot be established | §6.8.1, §14 |
| 20 | undeclared sequence reset | `REJECTED_STALE` — **never** an epoch change; only a declared boundary (`continuity_id`, `producer_session_id`, `ordering_epoch`) creates an epoch | §6.3, §6.6 |
| 21 | declared continuity reset | `NEW_EPOCH` ⇒ boundary path (§6.8.1) with an empty entity list: `TEMPORAL_DISCONTINUITY` when `A` is supplied, `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` when it is not; an undeclared reset is rejected, never promoted | §5.5 R-T2/R-T3, §6.2, §6.3, §6.8.1 |
| 22 | producer capability changes | `CAPABILITY_MISMATCH` ⇒ not comparable (no intersection narrowing) | §10.4 |
| 23 | cross-engine snapshot equivalence | non-claim: `coordinate_frame` is in the declared-unobservable set (§10.1 set B); unit agreement only | §10.1, §15 |
| 24 | stale observations | rejected before any comparison; no state mutation, no epoch change | §5.5, §6.3, §14 |
| 25 | a producer declares `state_digest` invalid, or lies about it | `state_digest` is always required and always **recomputed**; there is no producer-declared invalid variant to admit, and a mismatch is `REJECTED_INVALID` (`STATE_DIGEST_MISMATCH`) at stage 1, with **no record** | §4.1, §4.6, §6.8, §10.5 |
| 26 | a consumer reads `state_digest_changed = true` as "something observable changed" | the delta carries the two facts separately; `state_digest_changed` is raw content identity and may never add, remove or reclassify a field change | §8.1, §9.4, §11.5 |
| 27 | a layer that cannot supply the pair's earlier endpoint tries to rebuild it from `last_accepted_state_digest`, from a durable record, or by capturing a fresh "current" state | refused: a digest is not an observation (R-R2, R-R6). The arrival is still admitted on its own facts, and stage 3 emits `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` with an empty entity list — never `NO_CHANGE`, never an empty `COMPUTED` delta, never a synthetic `A` | §6.4, §6.7 P1/P3, §12.1, §14 R-R6 |
| 28 | a consumer treats a `TEMPORAL_DISCONTINUITY` record as a state transition | the record is a boundary record, not a comparison: §9 is never applied across a boundary, `entity_deltas` is empty by rule (R-T2), and the two endpoint digests being different is not a transition | §8.1, §8.2, R-T2 |
| 29 | an implementation reports `observations_skipped` across an epoch boundary from the two endpoints' `sequence` values | not defined across a boundary: `sequence` restarts per epoch, the field is `0` on a boundary record, and the boundary is named by its reason code | §8.1, §5.4 |
| 30 | conflation of admission-level `REJECTED_INVALID` with pair-level `OBSERVATION_INVALID` (or the reverse: reporting a pair refusal as an admission rejection) | one name per stage (§6.8): stages 1-2 emit no record, stage 3 always emits one; a stage-3 refusal never retracts a stage-2 acceptance, and no outcome may be reported for a stage that did not run | §6.6, §6.8, §8.2, §20, §21 |
| 31 | a producer emits the same object multiset with duplicated `object_id`s in a different order and claims the temporal digest is unchanged | the tie-break is content-derived (`object_id`, `entity_content_digest`), so emission order cannot move the digest; true content duplicates are interchangeable by construction; the `occurrence_index` rule of revision 2 (which was order-dependent for duplicated ids) is retracted | §11.2, §13.2 |
| 32 | a `NEW_EPOCH` step whose `A` was not supplied is routed into the comparison path, or the boundary is downgraded to a comparison refusal | `NEW_EPOCH` takes the boundary path and takes precedence over the comparison checks: the epoch boundary is established in every case, and pair-input availability selects **only** the variant and thereby the record form (`TEMPORAL_DISCONTINUITY` with an agreeing `A`, `OBSERVATION_INVALID` / `PAIR_INPUT_IDENTITY_MISMATCH` with a contradicting one, `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` without one) | §6.8, §6.8.1 P6, §8.1 |
| 33 | a `NEW_EPOCH` step is made to run a `SAME_EPOCH` check across the boundary (capability equality, source-time monotonicity, scene scope or unit system) and reports a field or entity change | the boundary path never invokes §9 and never evaluates those checks: they may appear only as cause facts in `reason_codes`, never as a comparison, a field change or a refusal | §6.8, §6.8.1 clauses 2-3, §8.2 |
| 34 | an implementation claims `B` was not admitted after a boundary record or after a pair-input refusal, or that the admission state differs between the two cases | `B` is admitted as the first accepted observation of the new epoch and the admission-state mutation is identical in every case; a stage-3 refusal never retracts a stage-2 acceptance | §6.4, §6.8, §6.8.1 clauses 1 and 5 |
| 35 | a missing-`A` boundary step produces an `observations_skipped` count from the two endpoints' `sequence` values, or synthesizes the observations between the epochs | `observations_skipped` is never computed across a boundary (counters restart per epoch): it is `0` on any record form, and no intermediate observation may be synthesized | §6.8.1 clause 4, §8.1, §14 R-R1 |
| 36 | a consumer reads the empty `entity_deltas` of a `PAIR_INPUT_UNAVAILABLE` record as `NO_CHANGE`, or infers availability from an empty list, a present digest or a reason code | the record states its own availability: `pair_input = "UNAVAILABLE"` with outcome `OBSERVATION_INVALID`, coverage all `INVALID_OBSERVATION` for set A, `observations_skipped = 0`, `source_time_hold = false` — a refusal is never a report of no change | §8.1, §8.2, §10.2 |
| 37 | an implementation "fills in" `from_state_digest` / `from_observation_id` by re-reading a payload or report store, by re-capturing the scene, or by inverting a digest | the `from_*` fields are read from Atlas-owned admission bookkeeping only, before the stage-4 mutation; any other source is a contract violation (R-R2, R-R6), and no field may stand in for `A`'s content | §6.4, §6.7 P1, §6.7.1, §8.1, §14 R-R6 |
| 38 | a consumer treats a known `from_state_digest` as proof that `A`'s content was available, or claims that digest equality implies a comparison was made | a digest is content *identity*, never content, and `pair_input` is the only authority on availability; `state_digest_changed` is a raw identity fact that never implies a field comparison | §6.7.1, §8.1, §11.4 |
| 39 | a caller supplies an `A` that contradicts the recorded identity and the step is compared anyway, including on a `NEW_EPOCH` step | a supplied `A` MUST agree with `last_accepted_observation_id` / `last_accepted_state_digest`; a disagreement is exactly one `OBSERVATION_INVALID` record with `PAIR_INPUT_IDENTITY_MISMATCH`, `pair_input = "AVAILABLE"`, empty `entity_deltas` and no field comparison. On `SAME_EPOCH` the admission state is unchanged; on `NEW_EPOCH` the refusal still leaves `B` admitted and the new epoch established exactly as stage 2 specified | §6.7.1, §6.8.1, §8.1, §12.4 |
| 40 | a record is produced from an input outside the four variants, or a path is defined as a function of an unavailable `A` (e.g. "compare against the recorded digest") | the evaluation-input union is closed and exhaustive: every record comes from exactly one of `ComparisonInput`, `BoundaryInput`, `RefusalInput`, `BoundaryRefusalInput`, and no path may consume an unavailable `A` — a refusal is the only output available to a refusal variant | §8.1, §12.1 |
| 41 | `FromIdentity` (or any admission bookkeeping) is treated as an observation input — fed into a comparison, used as "the earlier state", or read as proof that `A`'s content was available | `FromIdentity` is bookkeeping, not an observation: the content-bearing variants carry `A` itself and use `FromIdentity` only for the identity agreement, and only a comparison or boundary input can ever produce a field change | §6.7.1, §8.1, §12.1 |
| 42 | a record claims availability that its variant cannot express (e.g. `pair_input = "AVAILABLE"` on a refusal record), or an implementation accepts both an `A` and an unavailable marker | `pair_input` is determined by the variant, not carried as a parameter, so the illegal combination is unstateable rather than merely forbidden | §8.1, §8.2 |
| 43 | `delta_digest` is computed from the inputs or from the admission state instead of from the emitted record | the digest is defined over the emitted record only (§11.4), for every variant; the bookkeeping it was read from never participates | §11.4, §12.1 |
| 44 | the evaluator reads mutable admission state during evaluation, or samples it at a different moment than the projection, so the result depends on when the state was read | every variant carries the immutable `FromIdentity` projection and `F` reads nothing outside its argument: the state is never an input, and a result that changes when the state changes is non-conforming | §6.4 P6, §8.1, §12.1 |
| 45 | a boundary cause is taken from hidden or ambient bookkeeping (or invented at emission time) instead of from `B` versus the projection | the cause is derived by comparing `B`'s declaring fields with `FromIdentity`'s recorded epoch fields, so it is a function of the input alone | §6.8.1, §8.1 |
| 46 | `FromIdentity` is constructed after the stage-4 mutation, or from post-mutation values, so `from_*` and the boundary cause describe the new epoch instead of the previous one | the projection is by definition taken **before** the stage-4 mutation; a projection reflecting the new epoch is a different input and would name the wrong earlier endpoint | §6.4, §8.1, §12.1 |
| 47 | a consumer treats `PairInput` as the complete evaluation domain, or routes a refusal through an implicit fifth form | `PairInput` is only the caller-supplied content-bearing subset; the complete record-producing domain is exactly the four-variant `EvaluationInput` union, and every variant carries `FromIdentity` | §6.7, §8.1 |
| 48 | multiple declared boundary fields change at once and the implementation chooses an arbitrary single cause, depends on field/input order, or omits one changed field from the reason set | derive the boundary-cause set independently for each changed declared field, include every applicable cause code, and emit `reason_codes` in canonical sorted order; the result is independent of construction order and there is no primary-cause tie-break | §6.8.1, §8.1, §12.2, §12.4 |

### 19.2 Deterministic test requirements (`T-n`, not implemented by this document)

| ID | Requirement |
| --- | --- |
| T-1 | A/B/C determinism of observation admission: same envelopes+snapshots in different construction orders and different `PYTHONHASHSEED` values produce identical admission records and identical `delta_digest` |
| T-2 | `SAME_EPOCH`/`NEW_EPOCH`/`UNKNOWN`/`DIFFERENT_STREAM` classification table, case by case, including each restart flavor **and** the stale-versus-declared-reset discrimination: a bare regression must classify `REJECTED_STALE`, and the same regression plus a changed declared boundary field must classify `NEW_EPOCH` |
| T-3 | `TEMPORAL_DISCONTINUITY` and `OBSERVATION_INVALID` produce **empty** `entity_deltas` (asserting no synthesized transitions) and satisfy the §8.1 boundary-record rules (`observations_skipped = 0`, `source_time_hold = false`, coverage carrying the refusal reason, §9 never applied); `DUPLICATE_ACKNOWLEDGED` / `REJECTED_STALE` / `REJECTED_INVALID` produce **no record at all** (admission-level outcomes, asserted by the absence of any record for that arrival) |
| T-4 | Duplicate-id handling: pair-ambiguous ids never appear in `field_changes`, and `identity_ambiguous_ids` is sorted and complete |
| T-5 | Field-comparison matrix: one fixture per canonical field, changed and unchanged, with exact `before`/`after` values |
| T-6 | Quaternion sign equivalence (`q` vs `-q`) and non-unit raw comparison, including the reason code **and the distinct raw digests**: the run must assert an empty `rotation` change list, `ROTATION_SIGN_EQUIVALENT_ONLY`, and simultaneously `state_digest_changed = true` with different `from_state_digest`/`to_state_digest` (no normalization anywhere) |
| T-7 | Coverage semantics: omitted/unsupported/unavailable fields never appear as `observed_unchanged`; the §10.3 table is asserted field by field |
| T-8 | Digest partition assertions: `scene_input_digest` unmoved by every temporal metadata field; `temporal_state_digest` moved by state and unmoved by metadata; and `temporal_state_digest` **differs** for `q` vs `-q` while the §9 relation reports no change |
| T-9 | Ordering assertions: entity order, field order, add/remove interleaving, reason-code sorting |
| T-10 | Capability mismatch, scene-scope violation and unit-system violation each fail closed with the named reason code |
| T-11 | Adversarial suite (§19.1) as executable hostile inputs, each asserted to fail closed or produce exactly the bounded state |
| T-12 | Python 3.9 and 3.11 parity for the deterministic suite |
| T-13 | Sequence-gap semantics: an accepted gap yields `observations_skipped = max(0, gap - 1)`; a fixture carrying **both** a sequence gap and an unchanged `source_time` (and one carrying a source-time step with adjacent sequences) must show the two facts reported independently, never derived from one another |
| T-14 | Admission-outcome matrix: identical duplicate, contradictory duplicate, stale regression and declared reset each yield exactly one named `AdmissionOutcome`, and every non-`ACCEPTED` path leaves the admission state byte-identical (including the counters) |
| T-15 | Pair sourcing (§6.7): a step whose `PairInput` omits `A` yields exactly one record with `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` and an empty entity list; the run must also assert that the admission state contains **no** snapshot content and that no path reconstructs `A` from `last_accepted_state_digest` (a fixture mutating the digest must not be able to fabricate a delta) |
| T-16 | Boundary-record shape (§8.1): a declared boundary emits exactly one record with `TEMPORAL_DISCONTINUITY`, an empty `entity_deltas`, `observations_skipped = 0` even when the two endpoints' `sequence` values would suggest a gap, `source_time_hold = false`, and coverage recording the reason; and the run must assert that no field comparison was performed (no `field_changes`, no `NO_CHANGE` entries) |
| T-17 | Stage separation (§6.8): in one fixture, an arrival that fails arrival validation yields `REJECTED_INVALID` with **no record**, while a pair-level failure between two accepted observations yields exactly one record with `OBSERVATION_INVALID`; and after the stage-3 refusal the admission state is asserted unchanged, with the next accepted observation pairing against `B` |
| T-18 | Digest order independence with duplicated ids (§11.2): the same object multiset — including two objects sharing one `object_id` with different content, and two that are content-identical — emitted in two different construction orders must produce identical `temporal_state_digest`; changing the content of one of them must change it; and the run must assert the comparison/entity ordering is unaffected by the tie-break |
| T-19 | The `NEW_EPOCH` boundary path, all three record forms (§6.8.1): one fixture declares a boundary with an agreeing `A` supplied and asserts exactly one `TEMPORAL_DISCONTINUITY` record; the same fixture with `A` supplied but contradicting the projection asserts exactly one `OBSERVATION_INVALID` / `PAIR_INPUT_IDENTITY_MISMATCH` record; and with `A` omitted it asserts exactly one `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` record. All three runs must assert an empty `entity_deltas`, `observations_skipped = 0`, `source_time_hold = false`, coverage carrying the boundary or refusal reason, an **identical** admission-state mutation, and `B` as the latest accepted observation of the new epoch |
| T-20 | `NEW_EPOCH` never runs a `SAME_EPOCH` comparison check (§6.8.1 clauses 2-3): a fixture whose endpoints differ in capability, `unit_system`, `scene_id` and `source_time` ordering **and** sequence values that would suggest a gap must still produce the boundary path's record, with those differences appearing only as cause facts / reason codes — never as a `COMPUTED` outcome, a field change, a `NO_CHANGE` entry or a refusal reason from the comparison path |
| T-21 | Boundary precedence and classification invariance (§6.8.1 P6): a boundary declaration with `A` missing must produce the boundary path's record (not a comparison refusal) and must leave the recorded epoch transition identical to the `A`-supplied run; additionally, the `ACCEPTED` + missing-`A` case must still produce `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` on the comparison path — the two classifications must be distinguishable in the emitted records and in the admission state |
| T-22 | The `PAIR_INPUT_UNAVAILABLE` schema, both classifications (§6.7.1, §8.1): `SAME_EPOCH` + missing `A` and `NEW_EPOCH` + missing `A` must each emit exactly one record with `outcome = "OBSERVATION_INVALID"`, `pair_input = "UNAVAILABLE"`, `from_observation_id` / `from_state_digest` equal to the admission state's recorded pair (read before the stage-4 mutation), `to_*` equal to `B`'s, `continuity` equal to the classification, empty `entity_deltas`, `observations_skipped = 0`, `source_time_hold = false`, coverage with every set-A field `INVALID_OBSERVATION`, set-B fields `UNSUPPORTED_BY_PRODUCER`, **no** `OBSERVED_*` entry, and `reason_codes` containing `PAIR_INPUT_UNAVAILABLE` (plus the boundary cause code on the boundary form); the run must also assert that no field comparison was performed and that the record is not interpretable as `NO_CHANGE` (no `NO_CHANGE` entry, no `field_changes` anywhere) |
| T-23 | Identity metadata cannot fabricate content (§6.7.1): mutating `last_accepted_state_digest`, then `last_accepted_observation_id`, then both, must change only the record's `from_*` fields (and `state_digest_changed`) — never produce an entity delta, a `COMPUTED` outcome, a field change, a `NO_CHANGE` entry or a coverage state other than `INVALID_OBSERVATION`, and never be accepted by any path as a substitute for `A`'s snapshot |
| T-24 | Determinism of the refusal record (§11.4, §12.1): the same `(B, FromIdentity, COMPARISON_CONTRACT_VERSION)` must produce byte-identical canonical serialization and an identical `delta_digest`, across process runs and `PYTHONHASHSEED` values, and the digest must be unchanged whether or not some other observation's content is resident in the process |
| T-25 | Pair-input identity agreement from explicit input data (§8.1, §12.4): a supplied `A` whose `observation_id`, `state_digest`, or both disagree with `FromIdentity` yields exactly one `OBSERVATION_INVALID` record with `PAIR_INPUT_IDENTITY_MISMATCH` and `pair_input = "AVAILABLE"`, an empty `entity_deltas` and no field comparison. On `SAME_EPOCH` the admission state is unchanged; on `NEW_EPOCH` the run must additionally assert that the stage-2 boundary mutation still occurs (`B` becomes the latest accepted observation and the new epoch is established). The decision must come from the `EvaluationInput` values alone — the same mismatch record must be produced whether or not the mutable admission state still agrees with the projection |
| T-26 | The evaluation-input union is exhaustive and disjoint (§8.1): a matrix over the four combinations of classification (`SAME_EPOCH`/`NEW_EPOCH`) and availability (`A` supplied / not supplied) must assert for each exactly one variant (`ComparisonInput`, `BoundaryInput`, `RefusalInput`, `BoundaryRefusalInput`), its `pair_input` value and its outcome; any fifth record-producing path, and any record whose variant is not the one the combination names, must be impossible |
| T-27 | No record path is a function of an unavailable `A` (§8.1, §12.1): `F` applied to each refusal variant must assert that no `COMPUTED` outcome, no field change, no `NO_CHANGE` entry and no coverage state other than `INVALID_OBSERVATION`/`UNSUPPORTED_BY_PRODUCER` can be produced, even when `FromIdentity` carries a digest that matches `B`'s |
| T-28 | Input-level determinism (§11.4, §12.1): two runs with identical `RefusalInput` values and two runs with identical `BoundaryInput` values must each produce byte-identical canonical serialization and identical `delta_digest`, across processes and `PYTHONHASHSEED` values; and equal inputs of the same variant may never produce different records |
| T-29 | Content-bearing inputs are the only source of change, and bookkeeping metadata is never a substitute for content (§8.1, §12.1): `FromIdentity` is legitimate input data and is expected to be used for the identity agreement and the boundary cause, but only `ComparisonInput` may produce populated `entity_deltas`, and a fixture that varies the projection's metadata (handle, digest, epoch fields) — or the admission state behind it — must not add, remove or alter a single field change |
| T-30 | Every variant carries the immutable projection (§8.1): for each of the four (classification × availability) combinations the test must assert that `FromIdentity` is a component of the variant's input, that the record's `from_observation_id` / `from_state_digest` equal its recorded pair, and that the projection contains no snapshot content |
| T-31 | No evaluation path reads admission state directly (§6.4 P6, §12.1): after the projection is constructed, mutating the admission state — sequence, handle, digest, epoch fields and counters — must leave the record and its `delta_digest` byte-identical; and an instrumented check must show that evaluation touches only its argument |
| T-32 | The identity mismatch is detected deterministically from the input (§8.1, §6.8): a supplied `A` disagreeing in `observation_id`, in `state_digest`, and in both must each yield exactly one `OBSERVATION_INVALID` / `PAIR_INPUT_IDENTITY_MISMATCH` record with `pair_input = "AVAILABLE"`, an empty `entity_deltas` and no field comparison — on `ComparisonInput` and on `BoundaryInput` alike, where the epoch boundary must still be established |
| T-33 | The projection never supplies observation content (§6.7.1, §8.1): setting `FromIdentity.last_accepted_state_digest` equal to `B`'s digest, or otherwise varying the projection's metadata, must not populate `entity_deltas` on a refusal variant, must not make a comparison possible when `A` was not supplied, and must not change the boundary cause beyond what `B` versus the projection's fields determines |
| T-34 | The conceptual pair-domain wording remains single-valued (§6.7, §8.1): a fixture must distinguish the caller-supplied `PairInput` content-bearing subset from the complete four-variant `EvaluationInput` domain and must reject any implementation path that invents a fifth record-producing variant or treats refusal variants as `PairInput` values |
| T-35 | `NEW_EPOCH` identity mismatch preserves admission semantics (§6.8.1): a supplied `A` that contradicts `FromIdentity` must yield `OBSERVATION_INVALID` / `PAIR_INPUT_IDENTITY_MISMATCH` with no field comparison while still committing the stage-2 boundary mutation (`B` admitted, epoch established); the equivalent `SAME_EPOCH` mismatch must leave admission unchanged |
| T-36 | Multi-cause boundary determinism (§6.8.1, §12.2): fixtures where any two or all three of `continuity_id`, `producer_session_id`, and `ordering_epoch` differ must emit the complete applicable boundary-cause code set in canonical sorted order, with identical output regardless of source-field construction order; no arbitrary primary cause is permitted |

### 19.3 Live-evidence requirements (`L-n`, not implemented by this document)

| ID | Requirement |
| --- | --- |
| L-1 | A real two-observation sequence from a live Blender 4.4.3 run (read-only, disposable scene) producing a computed delta with a real field change, and the same pair producing an identical delta on a re-run |
| L-2 | A real restart of the producer producing `NEW_EPOCH` (assert the discontinuity, not a transition burst) |
| L-3 | A real seek/timeline discontinuity (or a replay fixture that changes `ordering_epoch`) producing `TEMPORAL_DISCONTINUITY` with an empty entity list |
| L-4 | A live duplicate/material-omission case proving `UNAVAILABLE` is not reported as `OBSERVED_UNCHANGED` |
| L-5 | A frozen-fixture regression: the same observation pair re-evaluated after the gate must reproduce its `delta_digest` byte-for-byte |

## 20. Required conclusions

**What exactly is a Temporal Observation?**
One canonical scene snapshot, wrapped in a versioned envelope that binds it to (a) the stable stream it
belongs to, (b) the continuity epoch it was admitted into, (c) its admission sequence and typed source
time, (d) diagnostic capture metadata, (e) producer provenance, (f) an explicit capability/availability
declaration, and (g) a content digest (`temporal_state_digest`) computed from the canonical state
alone. It is valid only if its snapshot parses canonically **in the single normative representation of
§4.6**, its **recomputed** `state_digest` equals the declared one, and its capability declaration is
consistent with the §10.1 universe. That digest is raw content identity: it is never normalized, and no
producer-declared value is ever trusted over the recomputation.

**What exactly is a State Delta?**
The single record emitted for one stream step. Its domain is the union of two pair kinds (§8.1): a
**comparison pair** — two accepted observations of the same stream in the same epoch, `B` admitted after
`A` — and a **boundary pair** — the last accepted observation of epoch *n* with the first accepted
observation of the immediately following declared epoch *n+1*. The first yields a factual comparison
(or a pair-level refusal); the second yields a **boundary record** that asserts no transition and applies no
field comparison — `TEMPORAL_DISCONTINUITY` when its earlier endpoint is supplied and agrees with the
recorded identity, `OBSERVATION_INVALID` / `PAIR_INPUT_IDENTITY_MISMATCH` when it is supplied but
contradicts it, and `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` when it is not supplied, with the
epoch boundary established and `B` admitted in every case (§6.8.1). Every record states its own availability in `pair_input` and always
carries the earlier endpoint's *identity* metadata, taken from Atlas-owned admission bookkeeping — never its
content, which the record never holds (§6.7.1, §8.1). Formally, every record is `F(EvaluationInput)` for
exactly one variant of a closed four-member input domain — `ComparisonInput`, `BoundaryInput`,
`RefusalInput`, `BoundaryRefusalInput` — each of which carries the immutable `FromIdentity` projection
alongside the arrival and, when supplied, the earlier endpoint's content; and that single function is the
contract's only purity definition (§8.1, §12.1). Every other arrival and pair produces no record at all:
`DIFFERENT_STREAM`, and the admission-level `DUPLICATE_ACKNOWLEDGED` / `REJECTED_STALE` /
`REJECTED_INVALID` (§6.6, §6.8). A record carries: a `DeltaOutcome`; the raw content-identity facts
(`from_state_digest`, `to_state_digest`, `state_digest_changed`); an ordered per-entity list of
`OBJECT_ADDED` / `OBJECT_REMOVED` / `OBJECT_CHANGED` / `NO_CHANGE` / `IDENTITY_AMBIGUOUS` facts with
field-level `before`/`after` values; the skipped-observation and source-time-hold facts; the ambiguity
set; and a mandatory per-field coverage record. It contains no interpretation, and it never uses a digest
to override the comparison relation — or the comparison relation to rewrite a digest.

**When is it legitimate to compare two observations?**
Only when both are valid, share a `stream_id`, are in the **same** continuity epoch (`continuity_id`,
`producer_session_id` and `source_time.ordering_epoch` equal; `sequence` strictly greater — adjacent or
gapped), declare identical capabilities, agree on `scene_id` and `unit_system`, the arriving observation
was `ACCEPTED` (§6.6), **and** the pair's earlier endpoint is **supplied** as the pair input (§6.7) — the
layer cannot compare an observation it does not hold, and it may not reconstruct one. An identical
duplicate, a stale regression or a rejected arrival is never compared. Nothing else grants comparability —
in particular, similar or identical snapshots never do (§5.5 R-T1), and neither does a `sequence`
regression (§5.5 R-T3). A declared boundary is not compared either: it is reported as a boundary, never as a
difference (§6.8.1).

**When must comparison fail closed or reset continuity?**
There are two distinct failure levels, and they are never conflated (§6.8). **Admission-level
(`REJECTED_INVALID`, no record, no admission-state mutation):** missing/malformed time or identity
metadata, a contradictory duplicate (`CONTRADICTORY_SEQUENCE`), a declared digest that disagrees with the
recomputed digest, an unparseable (or non-normative) snapshot, an inconsistent capability declaration,
unknown schema version, or an admission state that cannot be established
(`ADMISSION_STATE_UNAVAILABLE`). **Pair-level (`OBSERVATION_INVALID`, one record with an empty entity
list and an unchanged admission state):** a pair input that was not supplied (`PAIR_INPUT_UNAVAILABLE`),
capability mismatch between the endpoints, non-monotonic source time inside an epoch, `domain`/`rate`
mismatch, scene-scope change, unit-system change — evaluated in the §6.8 order, first failure wins.
Reset continuity (new epoch, `TEMPORAL_DISCONTINUITY` boundary record, empty entity list) **only** on a
**declared** boundary: producer restart, timeline seek, an explicit producer reset, or Atlas restart when
continuity cannot be re-established. If the caller cannot supply that boundary's earlier endpoint, the
boundary still takes effect and the record becomes `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE`
(§6.8.1): missing data never erases, downgrades or re-classifies a declared boundary. Reject without mutation and **without** an epoch change
(`REJECTED_STALE`) on a `sequence` regression whose declared continuity metadata is unchanged, because a
bare regression is not evidence of a reset (R-T3). When the pair's earlier endpoint content was not supplied,
the refusal is a fully specified record — `pair_input = "UNAVAILABLE"`, the recorded identity metadata, an
empty entity list, no observed field — and it never implies that `A` was available or that nothing changed
(§6.7.1, §8.1). A sequence gap is not a discontinuity: it is
`observations_skipped` (§5.4) — and across a boundary it is not a count at all.

**What information is factual state change versus future semantic interpretation?**
Factual: identity of entities, presence/absence, and per-field `before`/`after` values under the exact
equality rules of §9 (including the `q ≡ -q` equivalence), plus the temporal boundary facts
(discontinuity, skip count, source-time hold, ambiguity). Interpretation: everything that names a
*cause or meaning* — impact, collision, entrance, exit, hit, reaction, and any sport- or
production-semantic label. Also factual, and never interpretation: the raw content-identity digests and
`state_digest_changed` (§8.1) — they state what the canonical content **is**, not what it means. The
correct reading of a delta whose `state_digest_changed` is true while a field reports no change is
"the raw content differs in a way the §9 relation declares equivalent"; both facts are kept and neither
overrides the other (§11.5). The boundary is closed by §17, and the vocabulary of this layer is closed by
§8.2/§8.3/§6.6/§12.4.

**What minimum information is required for Atlas to begin reliably reasoning about time?**
A stable `stream_id`; a **declared** continuity boundary (`continuity_id`, `producer_session_id`,
`source_time.ordering_epoch`) that changes on every restart/seek/reset and is never inferred from a
counter regression (§6.3, R-T3); a strictly increasing admission `sequence` per epoch — adjacent or
gapped, with gaps reported as `observations_skipped` and never conflated with source-time jumps (§5.4);
a typed, integer-exact `source_time` with its own ordering epoch; one normative canonical snapshot
representation (§4.6); a content digest **recomputed** from that snapshot, raw and never normalized
(§11.2); an explicit capability/availability declaration over a closed field universe (§10.1); producer
provenance that includes a per-process session identity; and a **caller that can supply the previously
accepted observation** for the next comparison (§6.7), since the layer deliberately stores none. Knowing the
earlier endpoint's identity (its handle and content digest, held in Atlas-owned admission bookkeeping) is a
different fact from holding its content, and only the latter permits a comparison: the contract says so in a
field on every record (`pair_input`, §6.7.1/§8.1) rather than leaving a consumer to infer it, and it passes
the identity as an **immutable input** (`FromIdentity`) rather than letting an evaluator read mutable state
(§8.1, §12.1). Capture
wall-clock is *not* in that list, and never will be.

## 21. Exit criteria

Implementation may begin only after an independent review confirms all of the following:

1. the bounded claim explicitly excludes events, streaming, storage, retention, cross-engine
   normalization and any new identity mechanism (§1.1, §16);
2. the observation envelope is versioned, language-neutral, and separates stream identity, continuity,
   sequence, source time, capture time, snapshot, state digest and provenance (§4);
3. the four time concepts are defined and kept apart, with the twelve required behaviours given
   single-valued outcomes, `sequence` strictly increasing but gappable, gaps reported as
   `observations_skipped = max(0, gap - 1)` and never conflated with a source-time jump (§5);
4. continuity is never inferred from snapshot similarity **nor from a bare `sequence` regression**: a
   reset is recognized only when declared, and discontinuity never yields synthesized transitions
   (§5.5 R-T1/R-T2/R-T3, §6.2, §6.3);
5. temporal identity is `object_id`-keyed with a checked uniqueness precondition and fail-closed
   ambiguity, and the decision **not** to introduce a new stable key is justified from the frozen
   architecture (§7);
6. the delta model's record domain is explicit (comparison pairs and boundary pairs), its outcomes and
   entity kinds are exhaustive and factual, the admission outcomes are closed and single-valued, the
   admission-level `REJECTED_INVALID` and the pair-level `OBSERVATION_INVALID` are separated by stage so
   that the stream path is single-valued, the content-identity facts are present alongside (and
   subordinate to) the comparison result, and the ordering is deterministic and total (§6.6, §6.8, §8);
7. every currently representable canonical field has an exact comparison rule, and unobservable fields
   are excluded from comparison rather than treated as unchanged (§9, §10);
8. observability is a five-state, mandatory coverage record, and capability mismatch fails closed
   instead of narrowing (§10);
9. the four digest concepts are separated with explicit field participation, the temporal state digest
   is raw content identity that is never normalized **and is independent of producer emission order in
   all cases, including duplicated `object_id`s**, content identity is never used as the comparison
   relation (nor the reverse), and no temporal metadata can move `scene_input_digest` (§11, §13.2);
10. determinism is stated as a pure function with closed ordering and equality rules, and no semantic
   tolerance is introduced (§12, §9.3);
11. the cost model is presented without invented numbers, and streaming/caching/storage are explicitly
   deferred (§13, §16);
12. restart/recovery behaviour is defined per event and connected to the existing recovery contract's
   identity discipline, with no fabricated intermediate states (§14);
13. C++ parity is claimed as semantic parity only, with byte-identical serialization explicitly
   deferred to a serialization gate (§15);
14. the Event Abstraction boundary is explicit and its forbidden vocabulary enumerated (§17);
15. the adversarial register covers every attack of §19.1 with a design answer, and the `T-n`/`L-n`
   registers are stated as requirements (not implementations) — `T-1..T-14` (§19.2);
16. the snapshot representation is single and normative, and a producer-declared digest is never
   trusted over the digest Atlas recomputes (§4.6, §10.5);
17. the temporal field universe is closed and explicitly separates compared, declared-unobservable and
   derived fields, with derived fields excluded from the five-state coverage model rather than served
   by a sixth state (§10.1, §10.2);
18. an independent reviewer re-gates this revision — as revision 2 — and does not self-clear it;
19. the source of the compared pair is explicit and consistent with the non-goal against a mutable
   temporal store: the layer's only state is content-free, the earlier endpoint is a supplied input, and
   no path may reconstruct an observation (§6.4, §6.7, §14 R-R6);
20. a `TEMPORAL_DISCONTINUITY` record is explicitly defined as a boundary record over a boundary-pair
   domain, with no field comparison, an empty entity list and no cross-boundary skip count (§8.1);
21. the stream-processing path is single-valued end to end: one outcome name per stage, no record for an
   admission-level rejection, exactly one record for a pair-level refusal, and no retraction of an
   acceptance by a comparison failure (§6.6, §6.8, §8.2);
22. an independent reviewer re-gates this revision — as revision 3 — and does not self-clear it;
23. the `NEW_EPOCH` boundary path is explicit, distinct from the comparison path and deterministic: one
   record either way (`TEMPORAL_DISCONTINUITY` with a supplied endpoint, `OBSERVATION_INVALID` /
   `PAIR_INPUT_UNAVAILABLE` without), no §9 comparison and no cross-boundary check, no cross-epoch skip
   count, `B` admitted and the boundary established in both cases, and `NEW_EPOCH` classification taking
   precedence over the `SAME_EPOCH` checks (§6.8, §6.8.1, §8.1);
24. an independent reviewer re-gates this revision — as revision 4 — and does not self-clear it;
25. the missing-pair-input record is fully specified without reconstructing `A`: `pair_input` states
   availability on every record, the `from_*` fields are admission-owned identity metadata that never stand
   in for content, and no field of a record may be read as evidence that `A`'s snapshot was available
   (§6.7.1, §8.1, §11.4);
26. an independent reviewer re-gates this revision — as revision 5 — and does not self-clear it;
27. the purity domain is single and closed: one evaluation-input union with four disjoint variants, one
   function `F`, no second purity definition, and no record-producing path outside the union — with the
   admission state, the evaluation input and the record output kept explicitly distinct (§8.1, §12.1);
28. an independent reviewer re-gates this revision — as revision 6 — and does not self-clear it;
29. every evaluation-input variant carries the immutable `FromIdentity` projection, the evaluator reads no
   mutable admission state, and both the identity agreement and the boundary cause are determined from the
   input alone (§6.4 P6, §8.1, §12.1);
30. an independent reviewer re-gates this revision — as revision 7 — and does not self-clear it.
31. the conceptual distinction between the `PairInput` content-bearing subset and the complete four-variant `EvaluationInput` domain is explicit and single-valued (§6.7, §8.1);
32. `NEW_EPOCH` identity mismatch is explicitly a pair-level refusal that preserves the stage-2 admission mutation and establishes the new epoch (§6.8.1, §19.1 #39, T-25, T-35);
33. simultaneous boundary-field changes produce the complete applicable cause-code set in deterministic sorted order, with no primary-cause selection (§6.8.1, §12.2, §12.4, T-36);
34. an independent reviewer re-gates this revision — as revision 8 — and does not self-clear it.

## 22. Closure map

| Item | Closed in | How |
| --- | --- | --- |
| purpose / bounded claim / non-claim table | §1, §1.1 | three-deliverable claim; fourteen explicit non-deliveries |
| authority boundary | §2 | five normative rules (B1-B5), read-only, no authority transfer |
| conceptual model and vocabulary | §3 | layer ladder + closed v1 name table |
| temporal observation contract | §4 | field table, identity-field separation, `observation_id` derivation, provenance, capability, snapshot rules |
| time-domain model | §5 | typed integer-exact `source_time`, diagnostic-only `capture_time`, ordering rule (`sequence` strictly increasing, gappable, `observations_skipped = max(0, gap - 1)`), twelve required behaviours, R-T1/R-T2/R-T3 |
| continuity model | §6 | `continuity_id` construction, four continuity states, Atlas-side validation (a reset must be declared), minimal content-free admission state with a single-valued mutation rule, pair input and its five rules (§6.7), the four-stage stream path (§6.8), scope rule, closed `AdmissionOutcome` vocabulary |
| temporal identity model | §7 | uniqueness precondition, `IDENTITY_AMBIGUOUS`, four-argument rejection of a new key, declared limitations, mesh identity |
| state-delta model | §8 | explicit record domain (comparison pairs + boundary pairs), `DeltaOutcome`, the boundary-record rules, `EntityDeltaKind`, structure including the raw content-identity facts (`from_state_digest`/`to_state_digest`/`state_digest_changed`), total ordering, scene-level refusals, admission-level exclusion of duplicates, stale and rejected arrivals |
| field comparison rules | §9 | per-field table, exact numeric equality with rationale, three-kind tolerance taxonomy, `q ≡ -q`, positional mesh comparison, material/collection caveats |
| observability / capability semantics | §10 | three separated field sets (compared / declared-unobservable / derived), five states over their union only, the central "omitted ≠ unchanged" rule, v1 coverage table (incl. `coordinate_frame` and the derived-field exclusion), capability-mismatch refusal, failure precedence |
| digest / provenance boundaries | §11 | `scene_input_digest` frozen; `temporal_state_digest` (field table + content-derived object tie-break + raw-content-identity rule); `envelope_digest`; `delta_digest`; content-identity vs semantic-equivalence separation; comparison-vs-digest table |
| determinism rules | §12 | purity statement, ordering checklist, equality table (incl. digests as raw identity), closed reason-code vocabulary |
| low-latency considerations | §13 | cost ladder, per-entity digest primitive, explicitly no invented numbers, deferred list |
| restart / recovery semantics | §14 | ten events, the duplicate-acknowledgement and pair-input rows (the latter covering both classifications), the declared-reset rule, R-R1..R-R6, connection to the recovery contract's identity discipline |
| cross-language / C++ parity boundary | §15 | semantic parity contract, byte-parity non-claim, three-version scheme |
| explicit non-goals | §16 | enumerated |
| Event Abstraction boundary | §17 | produced/forbidden table + downstream requirements |
| open questions | §18 | eight questions with next steps |
| adversarial / red-team requirements | §19 | 48 attacks with design answers (including the revision-7 input-completion surface and the revision-8 pair-domain, boundary-mutation, enumeration, and multi-cause surfaces), `T-1..T-36`, `L-1..L-5` |
| required conclusions | §20 | six questions answered without ambiguity, re-derived after the revision-2 corrections, the revision-3 resolutions, the revision-4 correction, the revision-5 schema closure, the revision-6 purity unification, the revision-7 input completion and the revision-8 consistency repairs |
| exit criteria | §21 | thirty-four items, including the revision-2, revision-3, revision-4, revision-5, revision-6, revision-7 and revision-8 conditions |
| revisions and baseline | §0 | revision chain (incl. `75744da`, `f26746d`, `f1ed30d`, `6394803`, `cdf376d`, `fd48733`, `44d0a1c` and this revision), frozen-boundary table, scope, citation provenance |
| design revision 2 corrections | §22.1 | eight corrections mapped to the rules that now close them, each with its re-audit and red-team coverage |
| design revision 3 resolutions | §22.2 | five resolutions mapped to the rules that now close them, each with its adversarial requirement and its re-audit |
| design revision 4 correction | §22.3 | the `NEW_EPOCH` boundary path, with the exhaustive single-valuedness re-audit of all eight outcomes |
| design revision 5 correction | §22.4 | the missing-pair-input record schema: `pair_input`, admission-owned `from_*` identity metadata, the two rejected models, and the re-audit of the sections it touches |
| design revision 6 correction | §22.5 | one normative evaluation-input domain: the closed four-variant union, the single function `F`, the variant/path/outcome map, and the re-audit of every purity reference |
| design revision 7 correction | §22.6 | `FromIdentity` as an explicit immutable projection in every variant: the identity agreement, the boundary cause, the authority boundary, and the re-audit of the sections it touches |

### 22.1 Design revision 2 — required corrections and how they are closed

Revision 1 was held pending a design revision with eight required corrections. Each is closed below by
a *single-valued* rule, with the sections, red-team rows and `T-n` requirements re-derived around it.

| # | Required correction | Closed in | How |
| --- | --- | --- | --- |
| R2-1 | sequence semantics contradicted itself (§5.4 "+1" vs §5.5 gaps) | §5.4, §5.5, §8.1, §19.1 #16, T-13 | one rule: `sequence` is strictly increasing for accepted observations but **MAY gap**; `observations_skipped = max(0, gap - 1)`; a sequence gap and a source-time jump are separate facts and are never derived from one another |
| R2-2 | identical duplicates "accepted" while `SAME_EPOCH` required a strictly greater sequence | §5.5, §6.4, §6.6, §8.1, §8.2, §14, T-3, T-14 | identical duplicate ⇒ `DUPLICATE_ACKNOWLEDGED` (idempotent acknowledgement, **no `StateDelta`**, no admission mutation); same sequence with a different digest ⇒ a rejection, an outcome now named `REJECTED_INVALID` (§12.4); `StateDelta(A, B)` stays a pure function of a strictly ordered pair of accepted observations |
| R2-3 | a bare sequence regression could imply `NEW_EPOCH` (indistinguishable from staleness) | §4.2, §5.5 R-T3, §6.2, §6.3, §6.6, §12.4, §14 (table + R-R5), §19.1 #14/#20/#21, §20 | a restart/reset/seek **MUST** declare a continuity boundary (`continuity_id`, `producer_session_id` or `ordering_epoch`); a regression without one is `REJECTED_STALE` — never an epoch, never a discontinuity, no state mutation |
| R2-4 | `q ≡ -q` (semantic equality) vs raw rotation in the digest vs "semantic identity = digest equality" | §9.4, §11.2, §11.5, §11.6, §12.3, §19.1 #7, T-6, T-8 | two independent relations: `temporal_state_digest` is **raw canonical content identity** (never normalized), semantic equivalence is the **§9 comparison relation**; `q` and `-q` may differ in digest while being equivalent, and both facts are reported |
| R2-5 | `state_digest_changed` referenced but absent from the schema | §8.1, §11.4, §12.3, §19.1 #26, §20, T-8 | `from_state_digest`, `to_state_digest` and `state_digest_changed` added to `StateDelta` (and covered by `delta_digest`); they are raw facts that never override semantic comparison |
| R2-6 | `world_bounds` inside the field universe but "simply not compared" | §4.5, §10.1, §10.2, §10.3, §19.1 #12, §20 | three explicit sets — compared universe (A), declared-unobservable (B), derived/outside-contract (C); derived fields are excluded from the universe, the capability declaration and the coverage map, and the five-state model gains **no** sixth state |
| R2-7 | `state_digest_declared_invalid` undefined | §4.1, §4.6, §10.5, §19.1 #25, §21 item 16 | variant removed: `state_digest` is always required, Atlas always recomputes it, and a mismatch is `OBSERVATION_INVALID` / `STATE_DIGEST_MISMATCH`; a producer-declared digest is never authority |
| R2-8 | snapshot was "payload-shaped **or** canonical-model-shaped" | §4.6, §20, §21 item 17 | one normative `CanonicalSceneSnapshot`: exactly the canonical parser's input shape and closed key grammar; payload-shaped or alternative shapes are inadmissible |

**Re-audit of the corrected chain.** §4-§14 were re-read end to end after the corrections, and the
dependent passages were re-derived rather than patched locally: §3 (vocabulary), §4 (snapshot, capability,
identity fields), §5 (ordering, behaviours, R-T1..R-T3), §6 (states, validation, admission state, new
§6.6), §8 (schema, outcomes, admission exclusion), §9.4 (comparison-only equivalence), §10 (three sets,
coverage, precedence), §11 (raw identity, new §11.5, comparison-vs-digest), §12 (equality, reason codes),
§14 (events, R-R5), §19 (attacks and `T-n`), §20 (six conclusions), §21 (exit criteria). The chain is
single-valued at every point where revision 1 was ambiguous: one sequence rule, one duplicate rule, one
reset rule, one snapshot representation, one digest semantics, one comparison relation.

**Version-number interaction, stated explicitly.** Adding reason codes and changing equality/identity
rules would, under §15.3, oblige a version bump — but that obligation binds a *released* contract,
and no implementation of `TEMPORAL_OBSERVATION_SCHEMA_VERSION = "1"` or `DELTA_SCHEMA_VERSION = "1"`
exists anywhere in the repository (this milestone is design-only, §0.3, §15.3). Revisions 2 **and 3**
therefore define v1's single rule set **before** any consumer can exist, and bump nothing — revision 3
adds `PAIR_INPUT_UNAVAILABLE` and `ADMISSION_STATE_UNAVAILABLE` and renames the admission outcome
`INVALID` to `REJECTED_INVALID` under the same argument (§22.2 R3-3). From the first
implementation onward §15.3 governs unchanged: any further change to a compared field, an equality
rule, an outcome kind, the reason-code vocabulary or a digest field set requires a version bump.

### 22.2 Design revision 3 — required resolutions and how they are closed

Revision 2 was held pending a design revision with five required resolutions. Each is closed by a
*single-valued* rule, with the dependent passages, registers and counts re-derived around it.

| # | Required resolution | Closed in | How |
| --- | --- | --- | --- |
| R3-1 | where the previously accepted canonical snapshot comes from when producing a `StateDelta`, without introducing a mutable store/cache (§6.4 vs §8.1) | §6.4, §6.7 (P1-P5), §8.1, §12.1, §13.2, §13.4, §14 (pair-input row + R-R6), §19.1 #27, §21 item 19, T-15 | the admission state is content-free by construction; the pair's earlier endpoint is a **supplied input**; a missing input is a pair-level `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE`; the layer may never reconstruct an observation from a digest, and retention stays a separate (undesigned) concern |
| R3-2 | whether `TEMPORAL_DISCONTINUITY` is a `StateDelta` record although its endpoints are non-comparable (§8.1 vs §6.2) | §8.1 (record-domain union, boundary-record rules, continuity/outcome table), §8.2, §19.1 #28/#29, §21 item 20, T-16 | yes — it is a **boundary record** defined on boundary pairs, not a comparison: §9 is never applied across it, `entity_deltas` is empty by R-T2, the endpoint digests are raw facts that neither assert nor merge continuity, and `observations_skipped` is not defined across a boundary (it is `0`) |
| R3-3 | admission-level `INVALID` versus a pair-evaluator `OBSERVATION_INVALID`, with a single-valued stream path (§6.6 / §8.2 / §20 / §21) | §3, §4.1, §4.6, §5.5, §6.2, §6.6, §6.8 (four stages + fixed stage-3 order), §8.2, §9.7, §10.2, §10.5, §12.4, §20, §21, §19.1 #30, T-17 | one outcome name per stage: `REJECTED_INVALID` (stages 1-2, no record, distinguished by reason code) vs `OBSERVATION_INVALID` (stage 3, always a record, empty entity list); the admission outcome was renamed so the two can never be read as each other; a stage-3 refusal never retracts a stage-2 acceptance, and no outcome may be reported for a stage that did not run |
| R3-4 | whether the temporal state digest is genuinely producer-order independent with duplicated ids (§11.2) | §11.2, §13.2, §19.1 #31, §21 item 9, T-18 | made genuinely independent: the tie-break is `(object_id, entity_content_digest)` — content-derived, with content-identical duplicates interchangeable by construction. The `occurrence_index` rule (order-dependent for duplicated ids) is recorded as retracted, the primitive is named once (`entity_content_digest`, computed on demand, never stored), and the claim's scope is limited to the digest projection — never comparison order |
| R3-5 | the dependent re-audit and the adversarial requirements for these contradictions | §§6, 8, 11, 12, 13, 14, 20, 21 and 22.1 re-read; §19.1 #27-#31; §19.2 T-15..T-18; §21 items 19-22; §22 rows | each resolution carries its own hostile input and its own deterministic requirement, and the registers/counts were updated together (31 attacks, `T-1..T-18`, `L-1..L-5`, 22 exit criteria, ten restart events) |

**Re-audit of the revision-3 surface.** §§6, 8, 11, 12, 13, 14, 20, 21 and all of §22.1 were re-read end
to end after these resolutions, and every passage that named the admission outcome, the delta's domain,
the coverage model, the digest primitive or the digest tie-break was re-derived rather than patched
locally: §3 (vocabulary), §4.1/§4.6 (arrival-level rejection), §5.5 (outcome names), §6.2 (pair-level
`UNKNOWN`), §6.4 (content-free state), §6.6 (record column), §6.7/§6.8 (new), §8.1/§8.2 (record domain),
§9.7/§10.2 (refusal semantics), §10.5 (stage mapping), §11.2/§13.2 (tie-break primitive), §12.1
(statelessness), §12.4 (vocabulary), §13.4 (deferral), §14 (events + R-R6), §19 (registers), §20
(conclusions), §21 (criteria), §22 (closure map). The chain is single-valued at each point revision 2
left ambiguous: one source for the pair, one domain for a record, one name per stage, one ordering rule
per projection, and no outcome reportable for a stage that did not run.

**Nothing in this closure map is an implementation claim.** This revision changes no production file,
no test, no schema and no frozen boundary: it revises one document (§0.3).

### 22.3 Design revision 4 — required correction and how it is closed

Revision 3 was held pending a single correction: `NEW_EPOCH` with a missing `PairInput.A` admitted two
readings, because §6.7 P3 made a missing endpoint a pair-level refusal while §6.8 ran stage 3 for
`NEW_EPOCH` and §8.1/§8.2 assigned `NEW_EPOCH` a `TEMPORAL_DISCONTINUITY` boundary record. It is closed by
one deterministic rule, with every dependent passage re-derived around it.

| # | Required correction | Closed in | How |
| --- | --- | --- | --- |
| R4-1 | `NEW_EPOCH` + missing `PairInput.A` was not single-valued (§6.7 P3 vs §6.8 vs §8.1/§8.2) | §5.5 (the four `NEW_EPOCH` rows + the boundary-path footnote), §6.2, §6.6, §6.7 P3, §6.8 (two mutually exclusive stage-3 paths), §6.8.1 (new), §8.1 (domain, boundary-record clause, correspondence table), §8.2, §10.5, §12.4, §14, §19.1 #32-#35, §19.2 T-19..T-21, §20, §21 item 23, §22 rows | one rule: a `NEW_EPOCH` arrival takes the **boundary path** (§6.8.1). The classification is made at stage 2 from the declared boundary fields alone and is never revised; §9 and every `SAME_EPOCH` comparison check are excluded from it; `B` is admitted as the first accepted observation of the new epoch with an admission-state mutation identical to every `NEW_EPOCH`; the only pair-level question asked is whether `A` was supplied, and it selects the record form alone — `TEMPORAL_DISCONTINUITY` when supplied, `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` when not — with no synthesized transition, no `NO_CHANGE` entry and no cross-epoch `observations_skipped`. Pair-input availability can therefore never erase, downgrade or re-classify a detected boundary, and `NEW_EPOCH` classification takes precedence over the comparison checks |

**Re-audit of single-valuedness (the revision-4 sweep).** Every path through the contract was re-read and
enumerated: `ACCEPTED` + `A` supplied ⇒ comparison path (`COMPUTED`, or one `OBSERVATION_INVALID` record
naming the first failing check); `ACCEPTED` + `A` missing ⇒ one `OBSERVATION_INVALID` /
`PAIR_INPUT_UNAVAILABLE` record; `NEW_EPOCH` + `A` supplied ⇒ one `TEMPORAL_DISCONTINUITY` record;
`NEW_EPOCH` + `A` missing ⇒ one `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` record with the boundary
still established and `B` still admitted; `REJECTED_STALE` ⇒ no record, no epoch change, no state mutation;
`REJECTED_INVALID` ⇒ no record, no state mutation; `DUPLICATE_ACKNOWLEDGED` ⇒ no record, counter only;
`DIFFERENT_STREAM` ⇒ no record. Each path produces exactly one outcome and each outcome is produced by
exactly one path, for the eight outcomes of §6.6 and §8.2 together. Revision 5 completes the schema of the
missing-pair-input form on both paths without reconstructing `A` (§22.4).

### 22.4 Design revision 5 — required correction and how it is closed

Revision 4 was held pending one schema-level correction. It is closed by a single model, with every
dependent passage and register re-derived around it.

| # | Required correction | Closed in | How |
| --- | --- | --- | --- |
| R5-1 | `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE` was permitted on both paths, but §8.1 declared `from_observation_id` / `from_state_digest` mandatory with no defined content for that form — so the contract never said whether they are Atlas-owned identity metadata or evidence that `A` was available | §6.4, §6.7 (new §6.7.1), §6.8, §6.8.1, §8.1 (schema field, per-field semantics, outcome x availability table, decision record), §8.2, §10.2, §11.4, §12.1, §12.4, §14, §19.1 #36-#39, §19.2 T-22..T-25, §20, §21 items 25-26, §22 rows, §22.3 | one model, chosen for consistency rather than convenience: **every record keeps every field**, the mandatory `pair_input` field states whether the earlier endpoint's *content* was supplied, and `from_observation_id` / `from_state_digest` are **identity metadata read from Atlas-owned admission bookkeeping as it stood before the stage-4 mutation** — never a reconstruction of `A`, never a store lookup, and never a stand-in for its snapshot. Identity known and content available are defined as two independent facts (§6.7.1); nullable `from_*` fields and a separate result type were both rejected, with the reasons recorded (§8.1) |

**Re-audit of the sections this correction touches.** §6.4 (what the admission state does and does not
supply), §6.7 and new §6.7.1 (identity versus content, and the availability vocabulary), §6.8 and §6.8.1
(both paths emit a record carrying `pair_input` and admission-sourced `from_*`), §8.1 (schema, per-field
semantics for both positions, the outcome x availability table, and the decision record), §8.2, §10.2 (no
`OBSERVED_*` state on a non-comparison record), §11.4 (the digest commits to the record, not to `A`),
§12.1 (the evaluator inputs for this form, since unified into the §8.1 variant domain), §12.4 (one new code,
`PAIR_INPUT_IDENTITY_MISMATCH`), §14 (the
pair-input row and its schema consequence), §19.1 #36-#39, §19.2 T-22..T-25, §20 (conclusions 2, 4, 6),
§21 (items 25-26), §22 (registers and counts) and §22.3 (pointer to this closure). Revision 4's
single-valuedness result is unchanged: one path and one outcome per step — this revision fixes only what
the record *says* about the earlier endpoint, and it still never reconstructs it.

**Version-number interaction.** Adding a structural field and one reason code would, under §15.3, oblige a
version bump for a *released* contract; no implementation of temporal schema `"1"` exists anywhere
(§22.1), so revision 5, like revisions 2-4, defines v1's single rule set and bumps nothing.

### 22.5 Design revision 6 — required correction and how it is closed

Revision 5 was held pending one formal inconsistency: the contract stated two purity domains for what it
calls one record. It is closed by a single model, with every purity reference re-derived around it.

| # | Required correction | Closed in | How |
| --- | --- | --- | --- |
| R6-1 | §8.1 called `StateDelta` a pure function of `PairInput` `(A, B, COMPARISON_CONTRACT_VERSION)` while §12.1 defined a second evaluator `(B, FromIdentity, COMPARISON_CONTRACT_VERSION)` for the missing-`A` forms — so the refusal records were produced outside the stated purity domain | §6.7, §6.7.1, §6.8, §6.8.1, §8.1 (the domain, the path table, the rules), §8.2, §11.4, §12.1 (single function + the three-concept table), §12.4, §19.1 #40-#43, §19.2 T-26..T-29, §20, §21 items 27-28, §22 rows, §22.4 | one normative **evaluation-input domain**: a closed tagged union of four disjoint variants — `ComparisonInput(A, B, v)`, `BoundaryInput(A, B, v)`, `RefusalInput(B, FromIdentity, v)`, `BoundaryRefusalInput(B, FromIdentity, v)` — and one function `StateDelta := F(EvaluationInput)` defined in §8.1 alone, with §12.1 restating it and adding no second definition. `pair_input` is *determined by* the variant rather than carried as a parameter, so an illegal combination is unstateable; `FromIdentity` is admission bookkeeping (handle, digest and the previous epoch's declaring fields) and never an observation; and no path is a function of an unavailable `A` |

**Re-audit of every purity reference and definition.** §6.7 (the pair describes the two content-bearing
variants), §6.7.1 (`FromIdentity` is bookkeeping, never an observation input), §6.8 (every record comes from
exactly one variant) and §6.8.1 (the boundary path's two variants), §8.1 (the union, its rules, and the
path/variant/outcome map), §8.2 (each outcome belongs to one variant), §11.4 (`delta_digest` is over the
emitted record for every variant), §12.1 (one function, one domain, and the evaluation-input /
admission-state / record-output distinction), §12.4 (no new code), §19.1 #40-#43, §19.2 T-26..T-29, §20
(conclusion 2), §21 (items 27-28), §22 (registers and counts) and §22.4 (its pointer to the unified
domain). Every earlier property is preserved verbatim in effect: the admission state stays content-free,
nothing is reconstructed, `A` is never replaced by a digest or a handle, `NEW_EPOCH` precedence is
unchanged, a missing `A` never yields `COMPUTED` or `NO_CHANGE`, `B` stays admitted on every path, and no
cross-epoch comparison or skip count exists. Revision 7 makes the projection an explicit component of every
variant, so that identity validation and boundary causes are functions of the input alone (§22.6).

**Version-number interaction.** Changing a purity definition is a contract change, but it binds a
*released* contract; no implementation of temporal schema `"1"` exists anywhere (§22.1), so revision 6,
like revisions 2-5, defines v1's single rule set and bumps nothing.

### 22.6 Design revision 7 — required correction and how it is closed

Revision 6 was held pending one remaining formal gap: the two content-bearing variants did not carry
`FromIdentity`, yet the contract requires a supplied `A` to be validated against the recorded earlier
endpoint and requires a boundary cause derived from the previous epoch's identity — while §12.1 forbids
reading mutable admission state. The evaluator therefore lacked the information to be genuinely pure. It is
closed by one model, with every dependent passage re-derived around it.

| # | Required correction | Closed in | How |
| --- | --- | --- | --- |
| R7-1 | `ComparisonInput` and `BoundaryInput` did not carry the admission identity, so the required identity validation and the boundary cause could only come from mutable state that §12.1 says is not an input | §6.4, §6.7 P6, §6.7.1, §6.8 (comparison-path check 2), §6.8.1 (the three boundary record cases), §8.1 (the union, the projection, the map table, four new rules, the field table), §8.2, §10.5, §11.4, §12.1, §12.4, §19.1 #44-#46, §19.2 T-25/T-29 (reconciled) and T-30..T-33, §20, §21 items 29-30, §22 rows, §22.5 | `FromIdentity` is a component of **all four** variants and is defined as an **immutable projection** of Atlas-owned admission bookkeeping taken **before** the stage-4 mutation, handed to evaluation as a value. Admission stays Atlas-owned and is never read by the evaluator; the projection is metadata only (no snapshot content) and can never substitute for `A`. The identity agreement (`A` versus the projection) is comparison-path check 2 and also governs `BoundaryInput`, where a disagreement yields `OBSERVATION_INVALID` / `PAIR_INPUT_IDENTITY_MISMATCH` instead of a boundary record while the boundary is still established. Boundary causes are derived from `B`'s declaring fields against the projection's, so they too are functions of the input |

**Re-audit of the sections this correction touches.** §6.4 (the projection is constructed before stage 4 and
passed in), §6.7 (P6), §6.7.1 (a component of every variant, still never an observation), §6.8 (the
comparison path now runs availability → identity agreement → capability → source time → scope → unit, and
checks 2-6 read only the input), §6.8.1 (the three boundary record forms and what decides them), §8.1 (the
union, the projection definition, the map table, the identity-agreement and boundary-cause rules, the field
table), §8.2 (the identity refusal listed among the pair-level causes), §10.5 (item 7), §11.4 (only the
emitted record is hashed), §12.1 (the projection is the input; the state is not), §12.4 (no new code),
§19.1 #44-#46, §19.2 T-25 and T-29 reconciled plus T-30..T-33, §20 (conclusions 2 and 6), §21 (items
29-30), §22 (registers and counts) and §22.5 (pointer to this closure). Nothing about `A` is reconstructed
anywhere, and the revision-6 formality is unchanged: one function, one closed input domain, one record per
step.

**Three sections beyond the requested list were re-derived as a consequence**, and are disclosed rather
than left inconsistent: §5.5 (two rows), §6.2 (the boundary-path paragraph and the `NEW_EPOCH` row of the
classification table) and §6.6 (the `NEW_EPOCH` row) each enumerate the record forms the boundary path can
emit. Adding the identity refusal would otherwise have left them describing two of three forms — an
incomplete enumeration in the same class as the ambiguities revisions 4-6 closed. Their semantics are
unchanged: they now name all three forms and keep the identical admission-state mutation rule.

**Version-number interaction.** Extending an input signature is a contract change, but it binds a
*released* contract; no implementation of temporal schema `"1"` exists anywhere (§22.1), so revision 7,
like revisions 2-6, defines v1's single rule set and bumps nothing.

**Nothing in this closure map is an implementation claim.** This revision changes no production file,
no test, no schema and no frozen boundary: it revises one document (§0.3).


### 22.7 Design revision 8 — required consistency corrections and how they are closed

Revision 7 was held after independent review identified five consistency defects. Revision 8 closes them as a
design-only correction and deliberately makes no implementation claim.

| # | Required correction | Closed in | How |
| --- | --- | --- | --- |
| R8-1 | stale `StateDelta(A,B)` purity wording in §8.2 and dependent prose | §8.2, §10.5, §12.1, §19.1 #39 and §19.2 T-25/T-35 | every purity reference names the single closed `EvaluationInput` domain and `F(EvaluationInput)`; refusal and boundary identity cases are described without a second or stale pair-only purity formula |
| R8-2 | conceptual `PairInput` wording did not fully reconcile with the four-variant evaluation-input domain | §6.7, §6.8, §8.1, §19.1 #47, §19.2 T-34 | `PairInput` is explicitly the caller-supplied content-bearing subset; `EvaluationInput` is the complete four-variant record-producing domain, and stage 3 consumes only that closed union |
| R8-3 | T-25 / attack #39 incorrectly implied that boundary identity mismatch prevents admission | §6.8.1, §10.5, §19.1 #39, §19.2 T-25/T-35, §21 item 32 | `NEW_EPOCH` is classified and its stage-2 admission mutation occurs before evaluation; identity mismatch changes only the emitted record form and never rolls back `B` or the established epoch. The `SAME_EPOCH` mismatch remains admission-state-neutral |
| R8-4 | older requirements/exit criteria did not enumerate all three `NEW_EPOCH` record forms | §5.5, §6.2, §6.6, §6.8.1, §8.1, §10.5, §19.1, §19.2, §21 | the boundary path is consistently documented as: agreeing `A` ⇒ `TEMPORAL_DISCONTINUITY`; contradictory `A` ⇒ `OBSERVATION_INVALID` / `PAIR_INPUT_IDENTITY_MISMATCH`; missing `A` ⇒ `OBSERVATION_INVALID` / `PAIR_INPUT_UNAVAILABLE`, with the same stage-2 boundary mutation in every case |
| R8-5 | multiple simultaneous boundary-cause fields had no deterministic rule | §6.8.1, §8.1, §12.2, §12.4, §19.1 #48, §19.2 T-36 | each changed declared boundary field contributes its mapped cause code; the complete applicable set is emitted together and sorted canonically. No arbitrary primary cause, field-order dependency, or hidden state is permitted |

The revision-8 re-audit must inspect the entire document for the prior two-form `NEW_EPOCH` wording, pair-domain
terminology, stale admission-mutation claims, and any boundary-cause singularization before independent review.
The document remains **DESIGN REVISION 8 — REVIEW REQUIRED / NO IMPLEMENTATION** until a fresh independent
architectural reviewer clears this revision.