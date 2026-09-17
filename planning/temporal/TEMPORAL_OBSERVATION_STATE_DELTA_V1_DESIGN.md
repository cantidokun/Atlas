# Atlas — Temporal Observation + State Delta v1 (Design Gate)

**Status:** DESIGN REVISION 1 — REVIEW REQUIRED / NO IMPLEMENTATION
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
| *(this revision)* | Temporal Observation + State Delta v1 design gate | this document only — §22 |

This document was authored on branch `feat/temporal-observation-state-delta-design` created from
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
| `state_digest` | content identity of the canonical state (temporal-level, §11.2) | §11 |
| `envelope_digest` | identity of the observation record as received, including metadata | §11.3 |
| `observation_id` | derived, stable handle for one observation inside its stream | §4.3 |
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
  sequence                   : integer >= 0
  source_time                : SourceTime            # §5.1
  capture_time               : CaptureTime           # §5.2, diagnostic only
  producer                   : ProducerProvenance    # §4.4
  capability                 : CapabilityContract    # §4.5 / §10
  snapshot                   : CanonicalSnapshot     # §4.6
  state_digest               : 64-lowercase-hex      # §11.2
}   # + exactly one of state_digest | state_digest_declared_invalid
```

### 4.2 Identity fields that are NOT interchangeable

| Field | Scope | Survives producer restart | Survives Atlas restart | Identity-bearing for world state |
| --- | --- | --- | --- | --- |
| `stream_id` | one observed subject (scene/twin/capture) | yes (declared) | yes (durable, Atlas-owned) | no — scope only |
| `continuity_id` | one continuous temporal history | **no** (must change on producer restart) | yes | no — comparability gate only |
| `sequence` | one continuity epoch | **no** (reset on epoch change) | yes | no — order only |
| `state_digest` | one canonical state | yes | yes | **yes** (§11.2) |
| `observation_id` | one observation record | derived | derived | no |

`stream_id` and `continuity_id` are **producer-declared but Atlas-validated** (§6.3): a producer that
keeps `continuity_id` constant across a process restart is detected by the `sequence` regression rule,
not trusted.

### 4.3 `observation_id`

```text
observation_id := "obs:" + first_16_hex(sha256(canonical_tuple))
canonical_tuple := ("v1", stream_id, continuity_id, sequence)
```

`observation_id` is a *handle*, not evidence of state: two different states may share nothing but they
never share an `observation_id` inside a stream (the triple is unique by admission, §6.4), while two
observations with the **same** `state_digest` and different handles are legitimate duplicates (§5.5).
Nothing may compare states via `observation_id`.

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
  observable_fields         : sorted list of canonical field names the producer CLAIMS to observe
  unobservable_fields       : sorted list of canonical field names the producer DECLARES it does not observe
  representation_state      : sorted list of payload encoding facts, e.g.
                              "materials:omitted", "materials:empty", "normals:key-absent",
                              "uvs:key-absent", "local_frame_id:key-absent"
}
```

`observable_fields ∪ unobservable_fields` must equal the canonical field universe declared in §10.1,
and the two lists must be disjoint — otherwise the capability declaration is invalid and the
observation fails closed (§10.5). This is the mechanism that prevents §5's central failure mode:
reading *omitted* as *unchanged*.

### 4.6 `snapshot` — the canonical snapshot

`snapshot` carries the canonical scene payload **as the canonical layer produced it** (the same shape
`payload_to_scene_model` accepts, minus the payload-only `schema_version`, or the canonical model's
own dictionary form). Requirements:

1. `snapshot` MUST be parseable by the canonical parser with no modification (`parse_scene_report_input`
   semantics). A snapshot that fails canonical parsing makes the observation `OBSERVATION_INVALID`, with
   the parser's own error reported verbatim.
2. The temporal layer MUST NOT add, remove, default or repair any field. In particular it MUST NOT
   inject omitted canonical fields (`normals`, `uvs`, `local_frame_id`) to "complete" the snapshot.
3. `state_digest` MUST equal the digest computed from `snapshot` under §11.2; a mismatch makes the
   observation `OBSERVATION_INVALID` (`STATE_DIGEST_MISMATCH`).
4. The snapshot is **not** re-serialized into `scene_input_digest`'s input space: `scene_input_digest`
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

Within one continuity epoch, admission order is **`sequence`**, strictly increasing by 1 for accepted
observations. Ordering by `source_time.value` is *not* the admission rule (it is an independent,
declared-ordering property that must be non-decreasing, §5.6). A chain of observations for delta
computation is built from ascending `sequence` inside one epoch; **no chain ever crosses an epoch
boundary**.

### 5.5 Required behaviours (single-valued outcomes)

| Situation | Required outcome | Delta consequence |
| --- | --- | --- |
| normal forward progression | accept; `sequence` +1 within epoch; `source_time` non-decreasing | compare with previous accepted observation |
| identical `source_time` on consecutive observations, **same state** | accept | `COMPUTED`; all entities `NO_CHANGE` |
| identical `source_time` on consecutive observations, **different state** | accept, flag `source_time_hold = true` on the delta | `COMPUTED` with real field changes; the delta must **not** claim time advanced |
| skipped source interval (`sequence` gap, same epoch) | accept, flag `observations_skipped = n` | direct pair comparison only; **no intermediate state may be synthesized** |
| out-of-order observation (`sequence` <= last accepted inside same epoch) | **reject** (`OBSERVATION_REJECTED_OUT_OF_ORDER`) | no delta; continuity unchanged; no mutation of any admission state |
| duplicate observation (same `sequence` **and** same `state_digest`) | accept as idempotent duplicate | `COMPUTED`, all entities `NO_CHANGE`, `duplicate = true` |
| duplicate `sequence` with a **different** `state_digest` | **fail closed**: `OBSERVATION_INVALID` (`CONTRADICTORY_SEQUENCE`) | no delta; the stream is not advanced |
| source timeline seek/scrub (`ordering_epoch` changes, or `source_time.value` decreases) | **new continuity epoch** | `TEMPORAL_DISCONTINUITY`; empty entity list |
| engine restart (`producer_session_id` changes) | **new continuity epoch** | `TEMPORAL_DISCONTINUITY`; empty entity list |
| Atlas restart | Atlas-owned admission state restored or re-established; `continuity_id` unchanged iff the producer's `producer_session_id` and `ordering_epoch` are unchanged | comparable iff continuity identical; otherwise `TEMPORAL_DISCONTINUITY` |
| discontinuity/reset declared by the producer | **new continuity epoch** | `TEMPORAL_DISCONTINUITY`; empty entity list |
| missing/invalid time metadata | **fail closed**: `OBSERVATION_INVALID` (`MISSING_SOURCE_TIME` / `MALFORMED_TIME`) | no delta; never default to zero |

Two rules make this table single-valued, and both are normative:

* **R-T1 (no inferred continuity).** Continuity is derived **only** from `stream_id`,
  `continuity_id`, `producer_session_id`, `source_time.ordering_epoch` and the `sequence` regression
  rule. **Similar or identical snapshots must never be treated as evidence of continuity**, and an
  identical `state_digest` across two epochs does not merge them.
* **R-T2 (no fabricated transitions).** A comparison across an epoch boundary produces
  `TEMPORAL_DISCONTINUITY` with an **empty entity list**. A discontinuity must not be reported as a
  burst of `OBJECT_ADDED`/`OBJECT_REMOVED`/`OBJECT_CHANGED` — that would manufacture a state transition
  Atlas did not observe.

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
| `SAME_EPOCH` | `stream_id` equal, `continuity_id` equal, `producer_session_id` equal, `ordering_epoch` equal, `sequence` strictly greater | yes |
| `NEW_EPOCH` | `stream_id` equal, any of `continuity_id` / `producer_session_id` / `ordering_epoch` differ, **or** `sequence` regressed while the others are equal | no — emit `TEMPORAL_DISCONTINUITY` |
| `UNKNOWN` | metadata missing/malformed, or `domain`/`rate` mismatch between the pair, or capability mismatch | no — emit `OBSERVATION_INVALID` with the reason |
| `DIFFERENT_STREAM` | `stream_id` differs | no comparison at all; not an error, but never a delta |

### 6.3 Validation duties (Atlas-side, fail closed)

* `stream_id`, `continuity_id`, `producer_session_id` MUST be non-empty exact strings; whitespace-only
  is invalid.
* A **sequence regression with otherwise-identical continuity metadata** is classified `NEW_EPOCH`
  (never silently accepted as out-of-order — out-of-order rejection applies to *interleaved* arrivals
  inside one epoch, §5.5) **and** the delta across it is a discontinuity.
* The temporal layer MUST NOT derive continuity from snapshot content, from `source_time` proximity,
  from `capture_time` proximity, or from producer-instance ordinals it observed itself.

### 6.4 Stream admission state (Atlas-owned, minimal)

```text
StreamAdmissionState := {
  stream_id, continuity_id, producer_session_id, ordering_epoch : as above
  last_accepted_sequence : integer | null
  last_accepted_state_digest : 64-hex | null
  accepted_count, rejected_count : integer
}
```

This is the **minimum** state needed to admit or reject the next observation. It contains no snapshot
content, no field history, no cache and no derived temporal model — a deliberate v1 restriction (§13.4).
An observation is rejected if it fails any §6.2 condition; a rejected observation must leave this state
**byte-identical** (no partial mutation on rejection).

### 6.5 Scope rule

`stream_id` denotes exactly one observed subject. `snapshot.scene_id` changing within one
`SAME_EPOCH` pair is a scope violation: `OBSERVATION_INVALID` (`SCENE_SCOPE_CHANGED`). A different
subject is a different stream, not a delta.

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

### 8.1 Definition

```text
StateDelta(A, B) := the factual difference between two observations of the SAME stream
                    that are comparable under §6
```

`StateDelta` is a **pure function** of `(A, B, COMPARISON_CONTRACT_VERSION)`. It is not a function of
capture wall-clock, host state, iteration order, or any mutable cache (§12.1).

```text
StateDelta := {
  delta_schema_version   : "1"
  outcome                : DeltaOutcome               # exactly one, §8.2
  stream_id              : string
  from_observation_id    : string
  to_observation_id      : string
  continuity             : "SAME_EPOCH" | "NEW_EPOCH" | "UNKNOWN" | "DIFFERENT_STREAM"
  observations_skipped   : integer >= 0               # sequence gap inside the epoch (§5.5)
  source_time_hold       : bool                        # identical source_time, different state
  identity_ambiguous_ids : sorted list of strings
  entity_deltas          : ordered list of EntityDelta # §8.3, ordering in §8.4
  coverage               : per-field FieldObservationState map   # §10.2 — never optional
  reason_codes           : sorted list of strings      # named, closed vocabulary
}   # + delta_digest (§11.4)
```

### 8.2 `DeltaOutcome` (delta-level, exactly one)

| `DeltaOutcome` | When | `entity_deltas` |
| --- | --- | --- |
| `COMPUTED` | both observations valid, `SAME_EPOCH`, capabilities identical | populated |
| `TEMPORAL_DISCONTINUITY` | `NEW_EPOCH` (restart, seek, reset, sequence regression) | **empty by rule (R-T2)** |
| `OBSERVATION_INVALID` | either observation invalid, or `UNKNOWN` comparability (capability mismatch, domain/rate mismatch, missing metadata) | **empty** |

The three outcomes are exhaustive for a pair. A fourth situation — `DIFFERENT_STREAM` — is not a delta
at all: the comparison is refused and reported as such (no `StateDelta` is produced).

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
* Sign-equivalence has a **visible, non-silent** consequence for digests: when the only difference
  between two rotations is the sign, the delta reports **no `rotation` field change** *and* carries
  `reason_codes += ["ROTATION_SIGN_EQUIVALENT_ONLY"]` with `state_digest_changed = true`. Semantic
  equality and digest identity are different questions, answered separately (§11.6).

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
* A field that is `INVALID_OBSERVATION` in either observation makes the whole observation invalid
  (§10.5) — it never yields a partial delta.
* `None` in a canonical `Optional` field (`collection`, `parent_object_id`) is a **value**, not
  "missing": `None` ↔ string is a change.

## 10. Observability and capability semantics

### 10.1 The canonical field universe (closed, v1)

Scene level: `scene_id`, `unit_system`, `coordinate_frame`, `world_bounds`.
Object level: `object_id`, `name`, `collection`, `parent_object_id`, `location`, `scale`, `rotation`,
`visible`, `mesh`.
Mesh level: `mesh_id`, `vertices`, `faces`, `normals`, `uvs`, `materials`, `local_frame_id`.

### 10.2 `FieldObservationState` (five states, exhaustive, never conflated)

| State | Meaning | Can it appear in `field_changes`? |
| --- | --- | --- |
| `OBSERVED_UNCHANGED` | observed in both observations; semantically equal | no |
| `OBSERVED_CHANGED` | observed in both; semantically different | **yes** |
| `UNAVAILABLE` | the producer contract covers the field, but this observation did not carry it | no |
| `UNSUPPORTED_BY_PRODUCER` | the producer contract does not deliver the field at all (v1: `normals`, `uvs`, `local_frame_id`, `coordinate_frame`) | no |
| `INVALID_OBSERVATION` | the field (or the observation containing it) failed validation | no — observation invalid |

**The central rule (this milestone's hardest red-team point):**

```text
omitted from representation            ≠  observed and unchanged
unsupported by the producer contract   ≠  observed and unchanged
unavailable in this observation        ≠  observed and unchanged
```

`coverage` is therefore **mandatory** on every `StateDelta`, even for `TEMPORAL_DISCONTINUITY` and
`OBSERVATION_INVALID` outcomes (where it records the *reason* the comparison could not be made). A
consumer that reads only `entity_deltas` is reading an incomplete fact; the contract makes the omission
visible rather than silent.

### 10.3 v1 coverage table (what is actually observable today)

| Field | v1 state | Evidence |
| --- | --- | --- |
| `scene_id`, `unit_system`, `object_id`, `name`, `collection`, `parent_object_id`, `location`, `scale`, `rotation`, `visible` | `OBSERVED_*` | produced by `bpy_extraction` v1; digested per extraction §11.1 |
| `mesh_id`, `vertices`, `faces` | `OBSERVED_*` | mesh key set is exactly `{mesh_id, vertices, faces}` (+ `materials` when §4.3 permits) |
| `materials` | `OBSERVED_*` **or** `UNAVAILABLE` per observation | three encodings, extraction §4.3/§4.5: key omitted when any slot is unrepresentable |
| `normals`, `uvs`, `local_frame_id` | `UNSUPPORTED_BY_PRODUCER` | extraction §4.1/§4.2/§4.4: keys are never emitted in v1 |
| `coordinate_frame` | `UNSUPPORTED_BY_PRODUCER` | the payload grammar allows it (`extraction_payload.py` :17-27) but the v1 producer never emits it, so the canonical value is `None` for every live observation |
| `world_bounds` | not compared (derived, not digested) | extraction §11.1 |

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

1. envelope schema version unknown/unsupported ⇒ invalid;
2. required envelope fields missing/malformed (ids, sequence, time) ⇒ invalid;
3. capability declaration inconsistent (overlap, unknown field, incomplete universe) ⇒ invalid;
4. `state_digest` ≠ digest of `snapshot` (§11.2) ⇒ invalid;
5. `snapshot` fails canonical parsing ⇒ invalid (parser error reported verbatim);
6. scene-scope / unit-system violations vs the compared observation ⇒ invalid (§8.5).

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
  "objects": [ per object, sorted by (object_id, occurrence_index):
      {"object_id", "name", "collection", "parent_object_id",
       "location", "scale", "rotation", "visible",
       "mesh": {"mesh_id", "vertices", "faces", "materials"} | null } ]
}
```

Decisions, each with its reason:

* **Objects are sorted** by `(object_id, occurrence_index)`. Unlike the frozen kernel digest (which
  consumes producer order), the temporal digest is a *content* identity that must not depend on the
  order a producer happened to emit; `occurrence_index` is the 0-based position among equal ids, so the
  digest stays defined even when ids are duplicated.
* **`materials` participates** (the kernel digest excludes it), because materials *are* part of the
  observable v1 state and a temporal identity that ignored them would call a material change
  "identical".
* **`normals`/`uvs`/`local_frame_id` do NOT participate**: including their canonical (empty/None)
  values would assert equality of things the producer never observed — the §10.3 error, embedded in a
  hash. Their absence is recorded in `capability`/`coverage`, not in the digest.
* **`coordinate_frame`**/`world_bounds` do not participate (unobservable / derived).
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
compact separators, `ensure_ascii=True`, `allow_nan=False`). It exists so downstream layers can
reference a specific delta (bind, receipt, replay comparison) without re-deriving it. It excludes
itself and excludes `capture_time` of either observation.

### 11.5 When are two observations semantically identical?

Two observations are **semantically identical** (the same observed world state) iff:

1. their `temporal_state_digest` values are equal, **and**
2. their capability/representation records are equal (same `contract_id`, same `observable_fields`,
   same `representation_state`).

They are **not** required to share `stream_id`, `continuity_id`, `sequence`, `source_time`,
`capture_time`, `producer`, `observation_id` or `envelope_digest`. Semantic identity is a statement
about *content plus declared observability* — never about time, order, session or capture metadata.

Conversely, **continuity is never inferred from semantic identity**: two semantically identical
observations in different continuity epochs remain different epochs (R-T1).

### 11.6 Comparison vs digest: which answers which question

| Question | Answered by | Not answered by |
| --- | --- | --- |
| "is this the same canonical state, for provenance?" | `scene_input_digest` (frozen) | temporal digests |
| "is this the same observed state, including materials?" | `temporal_state_digest` | `scene_input_digest`; semantic comparison |
| "did anything change, and what exactly?" | `StateDelta` field comparison (§9) | **any** digest (a digest can only say "not equal") |
| "does the only difference dissolve under an equivalence rule (e.g. `q ≡ -q`)?" | semantic comparison + `reason_codes` | digests (they differ) |
| "is this record the same record I already saw?" | `envelope_digest` / `observation_id` | content digests |

The frozen `scene_input_digest` is explicitly **not** a substitute for temporal comparison semantics:
its field boundary excludes `materials` (extraction §11.1), it consumes producer order, and it can only
answer equality.

## 12. Determinism rules

### 12.1 Purity

`delta = f(A, B, COMPARISON_CONTRACT_VERSION)`. No wall clock, no host identity, no hash seed, no
dictionary iteration order, no pointer identity. The same pair must produce the same delta — same
`entity_deltas`, same ordering, same `reason_codes`, same `delta_digest` — in any process, in any
language, on any day.

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
| digests | exact hex string equality |

### 12.4 Reason-code vocabulary (closed)

`TEMPORAL_DISCONTINUITY_*`, `RESTART_PRODUCER_SESSION`, `SEEK_OR_ORDERING_EPOCH_CHANGE`,
`SEQUENCE_REGRESSION`, `CONTRADICTORY_SEQUENCE`, `SOURCE_TIME_NON_MONOTONIC`, `SOURCE_TIME_HOLD`,
`OBSERVATIONS_SKIPPED`, `DUPLICATE_OBSERVATION`, `CAPABILITY_MISMATCH`, `STATE_DIGEST_MISMATCH`,
`SCENE_SCOPE_CHANGED`, `UNIT_SYSTEM_CHANGED`, `IDENTITY_AMBIGUOUS_IDS`, `ROTATION_SIGN_EQUIVALENT_ONLY`,
`UNOBSERVABLE_FIELDS_PRESENT`, `MISSING_SOURCE_TIME`, `MALFORMED_TIME`, `UNKNOWN_SCHEMA_VERSION`.

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

Per-entity `entity_state_digest` (same field set as §11.2 restricted to one object) is the mechanism that
turns "compare two snapshots" into "compare two lists of hashes, then deep-compare only the mismatches".
It is a *contract-level* primitive (may be computed on demand, need not be stored), and it changes no
semantics: an entity whose digest matches is reported `NO_CHANGE` without field-by-field work; a
mismatch is deep-compared under §9 and the result is identical to the naive path.

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
authority over state lifetime, and therefore new failure modes.

## 14. Restart and recovery semantics

The temporal layer must connect cleanly to Atlas's existing recovery architecture, whose central
discipline is: *identity is declared and bound, ambiguity fails closed, and a restart is never treated
as proof about anything else* (`docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md` §4, §9, §16,
§20 Step 6 — "Unambiguous matches may proceed. Ambiguous matches MUST fail closed.").

| Event | Detection | Temporal behaviour |
| --- | --- | --- |
| **Atlas restarts** | Atlas process incarnation changes | `stream_id` and `continuity_id` are Atlas-durable/declared, so comparability is preserved **iff** the next accepted observation declares the same `continuity_id` and the producer's session/epoch are unchanged. The prior `last_accepted_sequence` is restored from durable state or the epoch is re-established; if it cannot be, the next pair is `UNKNOWN` ⇒ `OBSERVATION_INVALID` (**not** a silent `NO_CHANGE`) |
| **Blender restarts** | `producer_session_id` changes (and normally `continuity_id`) | `NEW_EPOCH` ⇒ `TEMPORAL_DISCONTINUITY`, empty entity list; `producer_instance_ordinal` increments |
| **Unreal restarts** | `producer_session_id` changes | identical rule; on the Unreal side this mirrors the recovery contract's `editor_session_id`-per-process-incarnation discipline, and PID alone is never identity |
| **producer stream resumes** | new session/epoch declared | new epoch; first observation of the epoch has no predecessor and produces no delta |
| **sequence counter resets** | `sequence` regresses with equal continuity metadata | `NEW_EPOCH` (§6.3) ⇒ discontinuity; never read as out-of-order interleaving |
| **source time resumes** (timeline continues after a stall) | same epoch, `source_time` non-decreasing | comparable; a large forward step is a legal gap (`observations_skipped`), not a discontinuity |
| **stale observation arrives** (older `sequence` inside the same epoch) | `sequence` ≤ `last_accepted_sequence` | **rejected**; zero mutation of admission state (§6.4); no delta, no continuity change |
| **different continuity/session observed** | `continuity_id`/`producer_session_id`/`ordering_epoch` differ | `NEW_EPOCH` ⇒ discontinuity, empty entity list |

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
| 7 | quaternion `q` vs `-q` | sign equivalence, with a named reason code and unchanged digests | §9.4 |
| 8 | non-unit raw quaternions | compared as **stored**; no normalization anywhere | §9.4 |
| 9 | tiny numeric noise vs true movement | both are changes (exact semantics); magnitudes are diagnostic only | §9.2, §9.3 |
| 10 | mesh topology mutation | positional comparison; reorder/re-index is a change; no correspondence inference | §9.5 |
| 11 | material-slot changes | ordered comparison + representation-state gate (omitted ≠ unchanged) | §9.6, §10.2 |
| 12 | unavailable representation fields | five-state coverage; never reported as unchanged | §10.2, §10.3 |
| 13 | identical snapshots at different times | semantically identical (§11.5); **not** evidence of continuity | §5.5 R-T1, §11.5 |
| 14 | out-of-order observations | rejected; zero admission-state mutation | §5.5, §6.4 |
| 15 | duplicate observations | idempotent `NO_CHANGE` when identical; `OBSERVATION_INVALID` when contradictory | §5.5 |
| 16 | skipped observations | `observations_skipped = n`, no synthesized intermediates | §5.5, §14 R-R1 |
| 17 | timeline seek | `ordering_epoch` change ⇒ new epoch ⇒ discontinuity | §5.1, §5.5 |
| 18 | engine restart | `producer_session_id` change ⇒ new epoch ⇒ discontinuity | §5.5, §14 |
| 19 | Atlas restart | comparability preserved only via declared/durable continuity; otherwise `UNKNOWN` ⇒ invalid | §14 |
| 20 | sequence reset | `NEW_EPOCH`, never out-of-order interleaving | §6.3 |
| 21 | continuity reset | same rule; `TEMPORAL_DISCONTINUITY` with empty entity list | §5.5 R-T2, §6.2 |
| 22 | producer capability changes | `CAPABILITY_MISMATCH` ⇒ not comparable (no intersection narrowing) | §10.4 |
| 23 | cross-engine snapshot equivalence | non-claim: `coordinate_frame` unobservable; unit agreement only | §10.3, §15 |
| 24 | stale observations | rejected before any comparison; no state mutation | §5.5, §14 |

### 19.2 Deterministic test requirements (`T-n`, not implemented by this document)

| ID | Requirement |
| --- | --- |
| T-1 | A/B/C determinism of observation admission: same envelopes+snapshots in different construction orders and different `PYTHONHASHSEED` values produce identical admission records and identical `delta_digest` |
| T-2 | `SAME_EPOCH`/`NEW_EPOCH`/`UNKNOWN`/`DIFFERENT_STREAM` classification table, case by case, including sequence regression and each restart flavor |
| T-3 | `TEMPORAL_DISCONTINUITY` and `OBSERVATION_INVALID` produce **empty** `entity_deltas` (asserting no synthesized transitions) |
| T-4 | Duplicate-id handling: pair-ambiguous ids never appear in `field_changes`, and `identity_ambiguous_ids` is sorted and complete |
| T-5 | Field-comparison matrix: one fixture per canonical field, changed and unchanged, with exact `before`/`after` values |
| T-6 | Quaternion sign equivalence (`q` vs `-q`) and non-unit raw comparison, including the reason code and digest behaviour |
| T-7 | Coverage semantics: omitted/unsupported/unavailable fields never appear as `observed_unchanged`; the §10.3 table is asserted field by field |
| T-8 | Digest partition assertions: `scene_input_digest` unmoved by every temporal metadata field; `temporal_state_digest` moved by state and unmoved by metadata |
| T-9 | Ordering assertions: entity order, field order, add/remove interleaving, reason-code sorting |
| T-10 | Capability mismatch, scene-scope violation and unit-system violation each fail closed with the named reason code |
| T-11 | Adversarial suite (§19.1) as executable hostile inputs, each asserted to fail closed or produce exactly the bounded state |
| T-12 | Python 3.9 and 3.11 parity for the deterministic suite |

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
alone. It is valid only if its snapshot parses canonically, its digest matches, and its capability
declaration is consistent.

**What exactly is a State Delta?**
The deterministic, factual difference between two observations of the same stream that are comparable
under §6: a `DeltaOutcome`, an ordered per-entity list of `OBJECT_ADDED` / `OBJECT_REMOVED` /
`OBJECT_CHANGED` / `NO_CHANGE` / `IDENTITY_AMBIGUOUS` facts with field-level `before`/`after` values,
the skipped-observation and source-time-hold facts, the ambiguity set, and a mandatory per-field
coverage record. It contains no interpretation.

**When is it legitimate to compare two observations?**
Only when both are valid, share a `stream_id`, are in the **same** continuity epoch (`continuity_id`,
`producer_session_id` and `source_time.ordering_epoch` equal; `sequence` strictly greater), declare
identical capabilities, and agree on `scene_id` and `unit_system`. Nothing else grants comparability —
in particular, similar or identical snapshots never do (§5.5 R-T1).

**When must comparison fail closed or reset continuity?**
Fail closed (`OBSERVATION_INVALID`, no delta) on: missing/malformed time or identity metadata,
contradictory duplicate `sequence`, non-monotonic source time inside an epoch, digest/snapshot
mismatch, capability mismatch or change, scene-scope change, unit-system change, unknown schema
version. Reset continuity (new epoch, `TEMPORAL_DISCONTINUITY`, empty entity list) on: producer restart,
Atlas-restart without restorable continuity, timeline seek, sequence regression, or any declared
reset. Reject without mutation (`OBSERVATION_REJECTED_OUT_OF_ORDER`) on interlaced stale arrivals.

**What information is factual state change versus future semantic interpretation?**
Factual: identity of entities, presence/absence, and per-field `before`/`after` values under the exact
equality rules of §9 (including the `q ≡ -q` equivalence), plus the temporal boundary facts
(discontinuity, skip count, source-time hold, ambiguity). Interpretation: everything that names a
*cause or meaning* — impact, collision, entrance, exit, hit, reaction, and any sport- or
production-semantic label. The boundary is closed by §17, and the vocabulary of this layer is closed by
§8.3/§12.4.

**What minimum information is required for Atlas to begin reliably reasoning about time?**
A stable `stream_id`; a continuity epoch identifier that changes on every restart/seek/reset; a
strictly increasing admission `sequence` per epoch; a typed, integer-exact `source_time` with its own
ordering epoch; the canonical snapshot itself; a content digest computed from the canonical state; an
explicit capability/availability declaration; and producer provenance that includes a per-process
session identity. Capture wall-clock is *not* in that list, and never will be.

## 21. Exit criteria

Implementation may begin only after an independent review confirms all of the following:

1. the bounded claim explicitly excludes events, streaming, storage, retention, cross-engine
   normalization and any new identity mechanism (§1.1, §16);
2. the observation envelope is versioned, language-neutral, and separates stream identity, continuity,
   sequence, source time, capture time, snapshot, state digest and provenance (§4);
3. the four time concepts are defined and kept apart, with the twelve required behaviours given
   single-valued outcomes (§5);
4. continuity is never inferred from snapshot similarity, and discontinuity never yields synthesized
   transitions (§5.5 R-T1/R-T2, §6.3);
5. temporal identity is `object_id`-keyed with a checked uniqueness precondition and fail-closed
   ambiguity, and the decision **not** to introduce a new stable key is justified from the frozen
   architecture (§7);
6. the delta model's outcomes and entity kinds are exhaustive and factual, with deterministic total
   ordering (§8);
7. every currently representable canonical field has an exact comparison rule, and unobservable fields
   are excluded from comparison rather than treated as unchanged (§9, §10);
8. observability is a five-state, mandatory coverage record, and capability mismatch fails closed
   instead of narrowing (§10);
9. the four digest concepts are separated with explicit field participation, and no temporal metadata
   can move `scene_input_digest` (§11);
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
   registers are stated as requirements (not implementations);
16. an independent reviewer re-gates this revision and does not self-clear it.

## 22. Closure map

| Item | Closed in | How |
| --- | --- | --- |
| purpose / bounded claim / non-claim table | §1, §1.1 | three-deliverable claim; fourteen explicit non-deliveries |
| authority boundary | §2 | five normative rules (B1-B5), read-only, no authority transfer |
| conceptual model and vocabulary | §3 | layer ladder + closed v1 name table |
| temporal observation contract | §4 | field table, identity-field separation, `observation_id` derivation, provenance, capability, snapshot rules |
| time-domain model | §5 | typed integer-exact `source_time`, diagnostic-only `capture_time`, ordering rule, twelve required behaviours, R-T1/R-T2 |
| continuity model | §6 | `continuity_id` construction, four continuity states, Atlas-side validation, minimal admission state, scope rule |
| temporal identity model | §7 | uniqueness precondition, `IDENTITY_AMBIGUOUS`, four-argument rejection of a new key, declared limitations, mesh identity |
| state-delta model | §8 | `DeltaOutcome`, `EntityDeltaKind`, structure, total ordering, scene-level refusals |
| field comparison rules | §9 | per-field table, exact numeric equality with rationale, three-kind tolerance taxonomy, `q ≡ -q`, positional mesh comparison, material/collection caveats |
| observability / capability semantics | §10 | five states, the central "omitted ≠ unchanged" rule, v1 coverage table (incl. `coordinate_frame`), capability-mismatch refusal, failure precedence |
| digest / provenance boundaries | §11 | `scene_input_digest` frozen; `temporal_state_digest` (field table + sorting rule); `envelope_digest`; `delta_digest`; semantic-identity definition; comparison-vs-digest table |
| determinism rules | §12 | purity statement, ordering checklist, equality table, closed reason-code vocabulary |
| low-latency considerations | §13 | cost ladder, per-entity digest primitive, explicitly no invented numbers, deferred list |
| restart / recovery semantics | §14 | eight events, R-R1..R-R4, connection to the recovery contract's identity discipline |
| cross-language / C++ parity boundary | §15 | semantic parity contract, byte-parity non-claim, three-version scheme |
| explicit non-goals | §16 | enumerated |
| Event Abstraction boundary | §17 | produced/forbidden table + downstream requirements |
| open questions | §18 | eight questions with next steps |
| adversarial / red-team requirements | §19 | 24 attacks with design answers, `T-1..T-12`, `L-1..L-5` |
| required conclusions | §20 | six questions answered without ambiguity |
| exit criteria | §21 | sixteen items |
| revisions and baseline | §0 | revision chain, frozen-boundary table, scope, citation provenance |

**Nothing in this closure map is an implementation claim.** This revision changes no production file,
no test, no schema and no frozen boundary: it adds one document (§0.3).
