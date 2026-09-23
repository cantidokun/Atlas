# Atlas M12.5 — Unreal Semantic Evidence Verification v1

**Status:** ARCHITECTURE / RECONCILIATION ONLY — implementation NOT authorized  

**Revision:** v1.1 — architecture-remediation round: required-invariant-set commitment, authoritative-expectation admissibility, transport-rooted observation identity, render-classification binding, closed result-side identity structures.

**Review status:** this revision must receive a fresh independent architectural/red-team review at its exact head; no gate verdict is claimed by this document.

**Base:** current `main` @ `89ca71180cebd00619d7f839819549cf4ede4be9`  
**Context:** PR #136 is merged; post-merge Atlas Tests run #2231 completed successfully.  
**Depends on:** M12.1–M12.4, Unreal State Extraction Fidelity v1 Revision 3.3, and the existing M4–M10 verification/recovery/receipt boundaries.

---

## 1. Purpose

M12.5 defines the missing **semantic verification boundary** between Atlas's Unreal semantic-task layer and a verified semantic outcome.

The problem is now sharply bounded:

- M12.1 defines the semantic task contract.
- M12.2 defines the canonical soccer-production catalog and fragments.
- M12.3 defines the immutable semantic execution plan and source-content commitment.
- M12.4 maps that plan onto the existing runtime without becoming an executor or verifier.
- Unreal State Extraction Fidelity v1 now provides a bounded, deterministic, read-only factual Unreal-state source.
- M4–M10 already provide authoritative render-job recovery, artifact/evidence verification, receipts, and provenance for render-bearing work.

What remains is to establish, independently and deterministically:

> **Did the authorized semantic production target actually become true in the observed Unreal state, using only authoritative inputs and without trusting self-reported completion?**

M12.5 answers that question.

It does **not** create a new runtime, execution authority, render verifier, recovery system, receipt authority, or persistence authority.

---

## 2. Normative architectural position

The M12.5 authority chain is:

```
semantic proposal
    ↓
M12.1 validated semantic task
    ↓
M12.3 immutable execution plan
    ↓
M12.4 runtime mapping
    ↓
existing Atlas / Unreal execution path
    ↓
authoritative observations
    ├── State Extraction Fidelity v1 factual state
    └── existing M5+ verified render evidence, when applicable
    ↓
M12.5 semantic target-state verification
    ↓
immutable semantic verification result
    ↓
existing downstream provenance / receipt consumers
```

The key separation is:

- **Observation** establishes facts that were read from the controlled engine boundary.
- **Verification** determines whether those facts satisfy the authorized semantic target.
- **Execution** changes the world and remains owned by existing runtime/authorization boundaries.
- **Render evidence verification** proves render artifacts and remains owned by the existing M5+ verifier.
- **Receipt issuance** remains downstream of the existing verified-render evidence path.

M12.5 may consume all of those things; it must not replace them.

---

## 3. Scope

### 3.1 In scope

M12.5 v1 covers:

1. deterministic evaluation of semantic target-state invariants;
2. validation of the input observation contract before evaluation;
3. identity binding between:
   - semantic task,
   - execution plan,
   - source-content digest,
   - execution/runtime mapping where present,
   - observation scope/session identity,
   - observed-state digest;
   - and resolution plus commitment of the required-invariant set (§7.1) and of its authoritative expected values (§7.2, §8.0);
4. fail-closed handling of absent, malformed, ambiguous, stale, contradictory, or unevaluable observations;
5. deterministic semantic verification results;
6. provenance sufficient to reproduce the verification decision;
7. composition with existing verified render evidence for render-bearing tasks;
8. explicit refusal of claims that exceed the available evidence.

### 3.2 Out of scope

M12.5 does not:

- execute Unreal operations;
- invoke the transport;
- authorize execution;
- mint or reinterpret authorization IDs;
- schedule or select execution workers;
- submit Movie Render Queue jobs;
- retry renders;
- perform render-job recovery;
- adopt a job after process failure;
- independently verify PNGs or render artifact hashes;
- issue UnrealRenderReceipt objects;
- replace ProductionArtifactManifest authority;
- replace M5 evidence verification;
- mutate the semantic task or execution plan after resolution;
- modify the frozen State Extraction Fidelity v1 contract;
- introduce a second Unreal state-extraction authority;
- introduce a second durable task/job store;
- use model confidence as evidence;
- make Temporal Observation + State Delta v1 an authority for semantic success.

---

## 4. Current source contracts

M12.5 consumes four already-defined contract families.

### 4.1 Semantic task

Source: `planning/m12/semantic_task.py`

Authoritative semantic inputs include:

- canonical task identity;
- semantic task class;
- digital-twin identity;
- semantic task version;
- requested intent;
- target-state specification;
- declared evidence requirements;
- declared action set;
- allowed action tools;
- allowed mutations;
- dependencies;
- catalog/provenance metadata.

M12.5 does not reinterpret the proposal. It verifies the resolved semantic task that Atlas already accepted.

### 4.2 Execution plan

Source: `planning/m12/execution_plan.py`

M12.5 binds to:

- `plan_id`;
- source task identity/version;
- catalog version;
- digital-twin identity;
- immutable `source_content_digest`;
- ordered semantic steps;
- target-state contributions;
- dependency relationships;
- verification requirements;
- fragment provenance.

The plan is descriptive, immutable, and non-executable. M12.5 must reject any verification request whose plan commitment does not match the supplied resolved source.

Two bindings on this contract are normative for M12.5 (§7.1, §7.3): the plan's per-step `verification_requirements` union must EQUAL the resolved source task's declared target-state invariant names (either-direction mismatch fails closed), and the plan's `render_plan` flag is not the render authority — it must agree with the digest-bound source classification or verification fails closed.

### 4.3 Runtime mapping

Source: `planning/m12/runtime_adapter.py`

M12.5 may consume the M12.4 mapping as provenance and runtime lineage evidence.

The mapping remains:

- aggregate where the existing runtime only represents the semantic task as an aggregate `AtlasTaskDefinition`;
- non-authoritative for verification;
- non-executable;
- immutable from the caller's perspective.

M12.5 must never infer successful semantic execution merely because a runtime mapping exists.

### 4.4 Unreal State Extraction Fidelity v1

Sources:

- `docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_DESIGN.md`
- `planning/unreal_state_extraction/`
- `docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_LIVE_GATE.md`
- `docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_VALIDATION_MATRIX.md`

Revision 3.3 is frozen and implemented.

The extractor provides factual read-only state from the authoritative editor-world scope. The Python boundary validates the closed schema and canonicalizes the payload.

M12.5 treats an extraction payload as **observation input**, not as proof that the semantic target is satisfied.

The extractor's own canonical digest is an observation identity. It is not a semantic verdict.

---

## 5. Observation model

M12.5 operates on immutable observation envelopes.

A conceptual observation envelope contains:

```text
ObservationEnvelope
  contract_revision
  extractor_identity
  engine_identity
  session_identity
  scope_identity
  request_identity
  canonical_state
  canonical_state_digest
  source_provenance
```

The exact wire structure is implementation work and is not frozen by this document.

### 5.1 Required properties

An acceptable observation must be:

- schema-valid;
- canonicalizable under the frozen State Extraction rules;
- internally self-consistent;
- bound to the requested entity/world scope;
- associated with an accepted extractor contract revision;
- associated with an identifiable engine/session envelope where the source contract exposes it;
- immutable for the duration of verification.

The observation envelope is deliberately split from the canonical state tree. Identity and boundary metadata such as `contract_revision`, `extractor_identity`, `engine_identity`, `session_identity`, `scope_identity`, and `request_identity` live at the envelope/boundary level and **must never be inserted into or used to enrich `canonical_state`**. The frozen State Extraction contract rejects reserved session/timestamp-style keys in the payload tree; M12.5 must preserve that boundary rather than reopening it.

`canonical_state_digest` is an observation identity derived from the canonical state payload under the frozen State Extraction canonicalization rules. Any caller-supplied digest is only a redundant assertion: M12.5 must recompute it and compare, never treat the supplied value as authoritative.

### 5.2 No trust in self-reported semantic status

Fields such as:

- `verified`;
- `target_satisfied`;
- `success`;
- `complete`;
- `passed`;

inside model-produced or execution-produced semantic metadata are never authoritative.

M12.5 derives the semantic result exclusively from validated observations and the frozen source contracts.

### 5.3 Identity provenance root (normative)

The six identity components of the observation envelope are **not** free-form caller metadata, and MUST NOT be treated as authoritative merely because they carry the right names. Each is sourced **only** from the State Extraction transport response envelope (`planning/unreal_transport_contract.py:63-107`; frozen extraction design §4.1), correlated to the Atlas-issued extraction request through the existing authoritative correlation validator (`validate_response_correlation`, `planning/unreal_transport_contract.py:114-139`):

```text
component            authoritative root (transport response envelope)
-------------------  ------------------------------------------------------------
request_identity     response.request_id, correlated to the request_id of the
                     Atlas-issued extraction request
session_identity     response.session_identity (editor_session_id, process_id,
                     process_creation_time_utc, server_start_time_utc,
                     engine_version, project_identity), canonically serialized
scope_identity       response.operation_name + response.entity_ids (the requested
                     extraction scope), canonically serialized
engine_identity      response.session_identity.engine_version, which MUST agree with
                     canonical_state.world.engine_version / engine_build_version
extractor_identity   canonical_state.extraction_kind (+ extraction_schema_version)
contract_revision    canonical_state.extraction_schema_version (must equal the
                     accepted revision; revision 1 today)
```

Rules:

1. The verifier derives each component itself, from the **transport response object** paired with the extraction result. It never copies an identity value out of the verification request.
2. A caller-supplied or hand-copied envelope field is an **untrusted identity claim**. If it disagrees with the transport-derived value, verification fails closed (`OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED`). A copied claim is never used as an expectation.
3. `canonical_state_digest` is recomputed under the frozen canonicalizer from the extraction value tree; a supplied digest is only a redundant assertion (§5.1).
4. Session/process/timestamp metadata remains **envelope-only**. It must never be inserted into, or used to enrich, `canonical_state` (§5.1, §15); the frozen reserved-key refusal is preserved.

**Transport-rooted ≠ authenticated.** The frozen extraction path provides no cryptographic authentication of the envelope's session identity — there is no HMAC/nonce on the extraction path, and the extraction digest deliberately commits to nothing about the request, transport, session or clock (frozen extraction design §6.5). The precise claim M12.5 v1 makes is therefore: **the observation payload corresponds to the transport response object and the correlated extraction request it was given.** The claim it does **not** make is: that the payload independently came from the current engine session. M12.5 establishes transport-rooted, internally correlated identity — not authenticated anti-replay freshness: a caller able to fabricate both a payload and a matching transport response object cannot be distinguished from a genuine pair by M12.5 alone, and no authentication infrastructure is added here. This limitation must be stated in the live-gate record and in §25, §6.2 must be read subject to it, and M12.5 v1 must not claim authenticated staleness detection. Establishing it would require a separately reviewed authenticated extraction-record capability outside M12.5 and outside the frozen extraction contract.

### 5.4 Expected observation identity and the required observation set (normative)

1. The **required observation set** is derived by the verifier from the registered invariant definitions only (§8): each registered invariant declares which extraction kind and which scope it consumes. It is never derived from the supplied observations.
2. A supplied observation is matched to a requirement by `(extraction_kind, scope_identity)`. An observation matching no requirement is **excluded** from evaluation and from the result: it may not be evaluated, merged into another observation, or used to satisfy anything.
3. A requirement with no matching observation leaves its invariants `MISSING` → fail closed.
4. An expected observation identity is admissible only when its expected scope is itself bound to a digest-bound source (§8.0). Where no authoritative committed expectation exists — as today for session identity — the design does not invent one: the expectation is the transport-derived identity of the correlated extraction, and the limitation in §5.3 stands.

### 5.5 Scope divergence (normative)

Differing scopes are classified, never left implicit:

- Two observations matching the **same** requirement with **equal** identity tuples are the same observation (duplicates collapse; §7).
- Two observations matching the **same** requirement with **unequal** canonical-state digests are `CONTRADICTORY` → fail closed (§7).
- Two observations claiming the **same requirement** with **different** `scope_identity` values are `OBSERVATION_SCOPE_DIVERGENCE` → fail closed. The verifier never selects one of them.
- Distinct requirements may legitimately carry distinct scopes (for example an actor-state requirement and a sequencer-state requirement). That is two requirement slots, not divergence.

---

## 6. Identity and binding

M12.5 must preserve distinct identities.

These identities may not be collapsed:

- canonical digital-twin identity;
- semantic task identity;
- semantic task version;
- execution-plan identity;
- source-content digest;
- runtime mapping identity/digest;
- Unreal extraction session identity;
- extraction request identity;
- observed-state digest;
- Unreal render-job identity;
- Unreal render-attempt identity;
- render receipt identity;
- production artifact identity.

### 6.1 Required verification bindings

For every verification result, M12.5 must be able to show:

```
semantic task
    ↔ source-content digest
    ↔ execution plan
    ↔ observation request/scope
    ↔ observed-state digest
```

For render-bearing tasks:

```
semantic task
    ↔ source-content digest
    ↔ execution plan
    ↔ render-job / attempt identity
    ↔ existing verified render evidence
    ↔ semantic observation(s)
```

A mismatch at any required identity edge is a verification failure, not a warning. The identity components bound at the plan/task edges are recomputed under the M12.3 source commitment, and the observation-edge components are transport-rooted per §5.3; a hand-copied envelope value is an untrusted claim, not an identity.

### 6.2 Stale observation protection

A state observation from a different:

- task;
- digital twin;
- scope;
- session;
- request;
- source-content revision;

must not be reused silently.

M12.5 does not infer that a later or earlier state is equivalent merely because the target-state names are the same.

**Transport-rooted is not authenticated (§5.3).** This section must not be implemented, tested, or claimed as cryptographic or independent proof of session identity. Its enforceable content is: (a) identity comparison over transport-derived values (§5.3), and (b) the correlation check against the Atlas-issued extraction request. Precisely: M12.5 verifies that the observation payload corresponds to the transport response object and the correlated extraction request it was given; it does **not** establish independently that the payload came from the current engine session. A payload that is internally consistent with the envelope it is presented with — including a correctly relabelled stale payload — is therefore not detectable by M12.5, and must be recorded as an unproven property rather than an enforced one (§25).

---

## 7. Target-state verification model

M12.5 reuses only the **evaluation model** of the existing Atlas `TargetStateEvaluator` concept: every required invariant is evaluated, all required invariants must pass, and an unevaluable condition fails closed. It does **not** reuse or promote the existing placeholder predicate bodies as authoritative semantic verification.

M12.5 invariant evaluation must use a closed, exact-name-matched registry of implementation-reviewed invariant definitions. It must never use substring/fuzzy/alias matching or caller-supplied executable predicates. An unrecognized invariant name is `UNKNOWN` and therefore fails closed.

The verifier evaluates **all required invariants**.

### 7.1 Required-invariant set (normative)

The required-invariant set has exactly one authoritative source:

```text
required_invariants := the resolved source task's target_state.invariant_names
```

It is **not** derived from the M12.3 plan, from the M12.4 runtime mapping, from compiled task metadata, from the observation, or from the verification request.

Two commitments are mandatory, and both are the verifier's **own** obligation (§16):

1. **Source commitment.** M12.5 recomputes `compute_source_content_digest(source_task)` and requires it to equal `plan.source_content_digest`. A mismatch fails closed (`IDENTITY_MISMATCH`).
2. **Invariant-set reconciliation.** The required-invariant set must **EQUAL** — set equality, not overlap, not subset — the union of the immutable plan's per-step `verification_requirements`:

```text
frozenset(source_task.target_state.invariant_names)
    == frozenset(name for step in plan.steps for name in step.verification_requirements)
```

A difference in **either** direction fails closed:

- `required_invariants ⊋ plan union` → `INCOMPLETE_REQUIRED_INVARIANT_SET`. A declared target invariant that the plan's steps do not carry would otherwise never be evaluated, which would allow a non-empty but incomplete requirement set to be reported as satisfied.
- `plan union ⊋ required_invariants` → `EXTRA_PLAN_VERIFICATION_REQUIREMENT`. The plan requires verification of something the authorized target does not declare.

M12.5 establishes both commitments itself, from the resolved source task and the immutable plan. It must not make the M12.4 runtime mapping mandatory in order to inherit M12.4's comparable reconciliation, and it must not relax either rule when no mapping is present.

### 7.2 Authoritative expected values (normative)

Every required invariant is evaluated against an **authoritative expected value** (or authoritative expected identity) supplied by a digest-bound source — never by the verification request. The admissibility rule, the per-invariant source/path/binding declaration, and the unavailable-value behaviour are defined normatively in §8.0 and enumerated per invariant class in §8.1–§8.6; the resulting v1 coverage limitation is recorded in §8.0.1.

An invariant whose expected value is unavailable, unbound, or not authorized is `UNKNOWN`/`MISSING` and fails closed. It is never satisfied from a caller-supplied expectation, and a caller-supplied expectation is never authoritative. Caller-supplied expectation + caller-supplied observation must never compose into `SATISFIED`.

### 7.3 Render-bearingness (normative)

Render-bearingness is derived **only** from the digest-bound resolved source task:

```text
render_task := is_render_task_class(source_task.task_class)
             (which M12.1 binds to target_state.expects_render, semantic_task.py:191-200,
              and which the source commitment covers)
```

The plan's `render_plan` field is **not** the render authority. It is outside plan identity (`_build_plan_id` excludes it) and can be changed while `plan_id`, `source_content_digest` and `steps` remain unchanged. If a supplied plan's `render_plan` disagrees with the digest-bound source classification, verification fails closed (`PLAN_RENDER_CLASSIFICATION_MISMATCH`).

Observation contradiction rule: if two or more observations share the same semantic task identity, observation scope identity, and request identity and their **canonical-state digests differ**, the input set is **CONTRADICTORY** and must fail closed. Digest inequality alone is sufficient to establish contradiction; no secondary "fact divergence" heuristic is required to make the refusal decision. The verifier must never choose a best-case observation, newest observation, or first observation to manufacture a satisfied result.

Repeated presentation of **identical** observation identities is not a failure: when all seven components of the tuple below are equal the instances are the same observation and collapse to one. Only a *conflicting* duplicate — the same requirement with unequal canonical-state digests — is a refusal (§11). Observations that are neither required nor duplicates of a required observation are excluded from evaluation (§5.4); a scope-divergent claim on one requirement is classified per §5.5, never resolved by selection.

For M12.5 v1, the canonical observation-identity tuple is exactly:
```
(contract_revision,
 extractor_identity,
 engine_identity,
 session_identity,
 scope_identity,
 request_identity,
 canonical_state_digest)
```
Two observations may be treated as equivalent duplicates only when every element of this tuple is equal. If all tuple elements are equal, repeated instances are the same observation identity for verification purposes; otherwise they are distinct observations and any duplicate request with equal task/scope/request identity but unequal canonical-state digest is contradictory.

Each component is sourced from the authoritative root defined in §5.3 (transport response envelope + frozen canonicalization), never from a caller-copied field.

Success requires:

```text
required-invariant set is NON-EMPTY
AND
required-invariant set EQUALS the plan's per-step verification_requirements union
AND
the source commitment recomputes to plan.source_content_digest
AND
every required invariant = SATISFIED
AND
every required invariant was evaluated from an authoritative expected value (§8.0)
AND
all required observations are valid, transport-rooted, and matched to a required requirement
AND
all required identity bindings are valid
AND
the supplied plan's render classification agrees with the digest-bound source (§7.3)
AND
no required invariant is UNKNOWN or MISSING
AND
no contradiction or scope divergence is present
```

An empty required-invariant set is **not** a successful verification state. It is an invalid/unknown verification input and must fail closed. The same applies to a non-empty set that is **incomplete** relative to the declared target state, and to a set that the plan does not carry exactly (§7.1). This mirrors M12.1's existing `__no_invariants__` fail-closed behavior. The verifier must never obtain `SATISFIED` merely because zero invariants were evaluated, and must never obtain `SATISFIED` by evaluating a mere subset of the declared target-state invariants.

Any one of:

- FAILED;
- UNKNOWN;
- MISSING;
- CONTRADICTORY;
- UNBOUND;
- INCOMPLETE_REQUIRED_INVARIANT_SET;
- EXTRA_PLAN_VERIFICATION_REQUIREMENT;
- PLAN_RENDER_CLASSIFICATION_MISMATCH;
- OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED;
- OBSERVATION_SCOPE_DIVERGENCE;
- EXPECTED_VALUE_UNAVAILABLE;

causes semantic verification to fail closed.

There is no best-effort success mode.

---

## 8. Invariant classes

M12.5 should support a **closed invariant registry** rather than arbitrary executable predicates. The v1 registry is fixed during implementation review. Matching is exact-name only; an unrecognized invariant name is `UNKNOWN` and fails closed. No generic, prefix, substring, alias, or caller-defined predicate may satisfy an invariant that is not explicitly registered.

This registry constraint applies even when two invariant names appear semantically similar: a requested name is satisfied only by its exact reviewed definition.

### 8.0 Invariant admissibility rule (normative)

An invariant may be **registered** in the v1 registry only when all five declarations exist and can be reviewed:

1. **authoritative expected-value source** — a digest-bound artifact whose commitment already exists OUTSIDE the verification request. In v1 exactly two sources are admissible:
   - the resolved source task, covered by `compute_source_content_digest(source_task)` (the same commitment M12.3 binds into `plan.source_content_digest`); or
   - an M12.2 canonical fragment/registry field (code-level canonical authority).
2. **exact source field/path** — the precise path inside that artifact;
3. **binding mechanism** — the exact deterministic rule that derives the expected value from that path and matches it to a declared field of the frozen State Extraction contract (or to an authoritative M5 render-evidence identity, §17);
4. **frozen/committed status** — whether the field is covered by the source-content commitment or by another committed digest;
5. **unavailable-value behaviour** — `UNKNOWN`/`MISSING` and fail closed; never a default, never a best-effort value, never a caller-supplied expectation.

**No declared-input channel exists in v1 (normative).** v1 admits no additional, "explicitly declared", or request-carried expectation input. The following chain MUST NEVER constitute authority:

```text
caller request → expected value → digest computed from the same caller request → verification
```

A request-carried expectation, an expectation blob whose only commitment is a digest the request itself supplies, and any input whose "authority" derives from the verification request are inadmissible whatever their name: the invariant is `UNKNOWN`/`MISSING` and verification fails closed (`EXPECTED_VALUE_UNAVAILABLE`, §11). Caller-supplied expectation + caller-supplied observation must never compose into `SATISFIED`.

A future expectation source must be an upstream, separately reviewed contract that commits the expectation OUTSIDE the verification request — for example a typed expectation surface on the M12.1 target-state contract, or another committed artifact carrying its own committed digest. M12.5 v1 must not invent one, and must not accept one while it does not exist (§26 Q8).

Evaluation matching stays exact-name. An unregistered name, an invariant whose expected value is unavailable, and an invariant whose expected value cannot be derived by its declared binding mechanism are all `UNKNOWN` → fail closed (§7).

### 8.0.1 v1 admissibility assessment and coverage limitation (normative)

The current contracts (M12.1 task contract, M12.2 catalog/fragment registry, M12.3 plan) carry target-state invariants as **names only**, plus free-form catalog parameters. They carry no invariant→expected-value binding and no authoritative requested-entity identity, so §8.0's rule has this consequence:

**Admissibility summary (v1).** Admissible → the render-evidence requirement only (§8.6). Not admissible → every semantic invariant class (§8.1–§8.5): digital-twin identity, requested entity existence/uniqueness, requested sequence/asset identity, transform equality, hierarchy/parent relationships, material, and Sequencer facts. Consequence: M12.5 v1 has no positively verifiable non-render semantic invariant, and none may be manufactured from the verification request (§8.0).

| Invariant class | Authoritative expected value today | v1 status |
|---|---|---|
| digital-twin identity equality (§8.1) | none: the frozen extraction tree exposes world/level/actor paths, not a digital-twin identity, and no reviewed binding maps `digital_twin_id` to them | NOT ADMISSIBLE in v1 → `UNKNOWN`, fail closed |
| requested entity existence / uniqueness (§8.1) | none: the resolved source carries no requested entity-ID set (`evidence`/`actions` arguments are `{"capability": …}` / `{"op": …, "target": …}`) | NOT ADMISSIBLE in v1 → `UNKNOWN`, fail closed |
| requested semantic asset/sequence identity (§8.1) | none: `sequence_name` is a free-form string with no reviewed binding to `sequence_asset_object_path` | NOT ADMISSIBLE in v1 → `UNKNOWN`, fail closed |
| transform equality (§8.2) | none: expected binary64 values exist nowhere in the resolved source (`camera_slots` / `lighting_rig` are untyped `json` parameters) | NOT ADMISSIBLE in v1 → `UNKNOWN`, fail closed |
| hierarchy/parent invariants (§8.3) | none: no authoritative expected parent is declared anywhere in the resolved source | NOT ADMISSIBLE in v1 → `UNKNOWN`, fail closed |
| material invariants (§8.4) | none | NOT ADMISSIBLE in v1 → `UNKNOWN`, fail closed |
| Sequencer invariants (§8.5) | partial: `frame_start`/`frame_end` parameters exist, but there is no reviewed binding to `playback_range.lower_frame`/`upper_frame`, and Sequencer extraction is not live-covered | NOT ADMISSIBLE in v1 → `UNKNOWN`, fail closed |
| render-evidence requirement (§8.6) | **yes**: `is_render_task_class(source_task.task_class)` and `target_state.expects_render`, both covered by the source-content commitment, matched against an authoritative M5 render-evidence revalidation (§17) | ADMISSIBLE in v1 |

**v1 coverage limitation (recording obligation, never presented as a pass).** With the currently admissible set, M12.5 v1 cannot reach `SATISFIED` for a non-render semantic task, and the semantic domain of a render-bearing task stays `UNKNOWN` → fail closed. V1 therefore implements and proves the closed contract — invariant-set commitment, expectation admissibility, identity binding, contradiction/divergence handling, refusal vocabulary, determinism, non-authority — while every non-admissible invariant fails closed. No predicate may be invented to change this, no caller expectation may be accepted as authority, and no placeholder predicate from M12.1's `TargetStateEvaluator` may be promoted (§7, §16).

Admitting additional invariants requires a separately reviewed extension that gives them a digest-bound expectation source — either a typed expectation surface on the M12.1 target-state contract, or a separately reviewed digest-bound semantic-input contract. That is an **upstream contract change and is out of scope for M12.5 v1** (§26). In every case the commitment must live outside the verification request: v1 has no declared-input channel (§8.0).

### 8.1 Identity invariants

Examples:

- requested digital-twin identity is the observed identity;
- requested entity IDs exist;
- requested entity IDs are unique and canonical;
- requested semantic asset/sequence identity matches observed identity.

### 8.2 Transform invariants

Examples:

- exact binary64 location;
- exact binary64 rotation;
- exact binary64 scale;
- explicit distinction of signed zero and quaternion sign where the State Extraction contract preserves them.

M12.5 must not normalize values before comparison when the source contract preserves source-fidelity distinctions.

### 8.3 Hierarchy invariants

Examples:

- parent state is NONE;
- parent is explicitly bound to a canonical entity;
- required parent relationships exist;
- required parent relationships do not point to an unexpected entity.

### 8.4 Material invariants

M12.5 uses only the deterministic source-side material representation defined by State Extraction Fidelity v1.

It must not invent a rendered-material or Nanite interpretation that the frozen v1 contract deliberately excludes.

### 8.5 Sequencer invariants

Sequencer verification must consume only the extraction representation that the frozen contract actually supports.

An unsupported or unavailable Sequencer fact is UNKNOWN, not automatically SATISFIED.

### 8.6 Render-completion invariants

Render completion is not established by M12.5.

Where a semantic task requires a render:

- M12.5 may consume existing verified render evidence;
- the existing M5+ verifier remains the authority for artifact/evidence validity;
- the render-job identity and attempt identity must remain bound;
- render receipt issuance remains downstream and outside M12.5.

The render domain is tracked separately as `render_state` (§9, §10.1). For §8.0's admissibility assessment it is the one requirement whose expectation is digest-bound today — the source task's render classification, `is_render_task_class(source_task.task_class)` bound to `target_state.expects_render` — which is why §8.0.1 marks it admissible while every semantic invariant class is not.

---

## 9. Render-bearing semantic tasks

M12.4 explicitly fails closed for render-bearing runtime mapping.

M12.5 must preserve that boundary.

Render-bearingness is decided by §7.3 — from the digest-bound resolved source task, never from a mutable plan flag. A supplied plan whose `render_plan` disagrees with the digest-bound source classification fails closed (`PLAN_RENDER_CLASSIFICATION_MISMATCH`) before any render consideration. The presence or absence of an M12.4 runtime mapping never changes this classification.

A render-bearing semantic task may therefore produce three independently distinguishable outcomes.

**Reachability note (v1).** Outcomes 9.1 and 9.3 require a semantically satisfied domain. Under the §8.0.1 v1 coverage limitation no non-render invariant is admissible, so v1 reaches outcome 9.2 (render evidence verified, semantic domain UNKNOWN → fail closed) and the refusal outcomes; 9.1/9.3 become reachable only once at least one admissible semantic invariant exists. The outcome classes are normative contract surface, not a v1 claim.

### 9.1 Semantic state verified, render not verified

Target-state inspection succeeds, but no valid verified render evidence is available.

Result:

```
SEMANTIC_STATE_SATISFIED
RENDER_EVIDENCE_MISSING
OVERALL_TASK_COMPLETION = NOT_ESTABLISHED
```

### 9.2 Render verified, semantic target not verified

Existing M5+ evidence proves the render artifact, but one or more semantic target-state invariants fail or remain unknown.

Result:

```
RENDER_EVIDENCE_VERIFIED
SEMANTIC_TARGET_NOT_SATISFIED
OVERALL_TASK_COMPLETION = NOT_ESTABLISHED
```

### 9.3 Both independently verified

Only when both required evidence domains are independently valid may M12.5 report the semantic task as satisfied.

For render-bearing verification, the phrase **verified render evidence** is normative and does not mean an `UnrealEvidence(verified=True)` instance, a snapshot carrying `"verified": true`, a transport-success flag, or any other caller-controlled boolean. Such a value is never sufficient authority.

Even then:

- M12.5 does not issue the render receipt;
- M12.5 does not become the artifact verifier;
- the existing receipt/provenance boundary remains authoritative.

---

## 10. Verification result contract

M12.5 should produce a deterministic immutable result conceptually shaped as:

```text
UnrealSemanticVerificationResult
  verifier_revision
  task_identity
  task_version
  digital_twin_id
  plan_id
  source_content_digest
  runtime_mapping_digest?
  required_invariant_names
  observation_identity
  observation_digests
  render_job_identity?
  render_attempt_identity?
  render_evidence_identity?
  evidence_trust_basis
  invariant_results
  semantic_state
  render_state
  overall_state
  failure_codes
  provenance
  canonical_digest
```

The nested structures are closed and producer-owned, with exactly these members:

```text
observation_identity       contract_revision, extractor_identity, engine_identity,
                           session_identity, scope_identity, request_identity,
                           canonical_state_digest
render_evidence_identity   job_identity, attempt_identity, evidence_identity
evidence_trust_basis       semantic_observation, render_evidence   (§10.4)
provenance                 the enumerated closed structure of §13
render_job_identity / render_attempt_identity are the authoritative M5 durable
job/attempt identities (§17) carried as evidence metadata, never minted here.
```

Each member's value is derived by M12.5 from validated inputs per §5.3/§10.4/§13/§17. None of these structures, and none of their members, may be accepted from a caller: a caller-supplied value for any of them is rejected structurally (§11).

### 10.1 Result states

The exact enum names should be frozen during implementation review, but the architecture requires at least:

- `SATISFIED`
- `NOT_SATISFIED`
- `UNKNOWN`
- `INVALID_OBSERVATION`
- `IDENTITY_MISMATCH`
- `CONTRADICTORY`
- `RENDER_EVIDENCE_REQUIRED`

A separate render state may distinguish:

- `NOT_REQUIRED`
- `NOT_VERIFIED`
- `VERIFIED`
- `INVALID`

The states above are the semantic/render outcome classes. The refusal classifications of §7/§11 (for example `INCOMPLETE_REQUIRED_INVARIANT_SET`, `OBSERVATION_SCOPE_DIVERGENCE`, `PLAN_RENDER_CLASSIFICATION_MISMATCH`, `EXPECTED_VALUE_UNAVAILABLE`) are carried deterministically in `failure_codes`; they never map to `SATISFIED`.

### 10.2 Determinism

For identical:

- resolved task;
- execution plan;
- source-content digest;
- observation envelopes;
- existing render evidence identities;

the M12.5 result and canonical digest must be byte-identical.

No current time, process-global state, filesystem enumeration order, random nonce generation, model output, or network call may affect the verification result. The render-bearing composition path (§20 Phase D) has its own determinism criterion, stated there, because it consumes durable artifact state through the M5 authority.

### 10.3 Immutability mechanism (normative)

"Immutable" for the purposes of this contract means:

1. the result is constructed only inside the verifier, from validated inputs, and is never accepted from a caller;
2. the result type is sealed against subclassing, so a subclass cannot reintroduce or override a field or serializer;
3. every security-relevant value in the canonical serialization is **derived** at serialization time from the validated canonical inputs and module constants — never read back from a mutable stored field. A frozen dataclass field is not an integrity boundary: `object.__setattr__` defeats `frozen=True`, and a serializer that reads the stored field will then emit the rewritten value (independently demonstrated against `planning.unreal_evidence_contract.UnrealEvidence`);
4. the canonical digest is computed over that derived structure.

A result whose serialization reads a stored flag therefore does not satisfy this section, even if the dataclass is declared frozen.

### 10.4 Evidence trust basis (normative)

A consumer must not be able to read transport-correlated observation evidence as equivalent in strength to durable-record-backed render evidence. §10's separate `semantic_state` and `render_state` fields name **outcomes**, not evidence strength — two `VERIFIED` outcomes can rest on differently strong evidence — so relying on those fields plus prose is insufficient once an admissible invariant makes a positive outcome reachable. The result therefore carries one closed, derived classification:

```text
evidence_trust_basis
  semantic_observation : TRANSPORT_CORRELATED
  render_evidence      : DURABLE_RECORD_BACKED | NOT_ESTABLISHED | NOT_APPLICABLE
```

Members (v1, fixed):

- `TRANSPORT_CORRELATED` — the semantic/observation domain. The payload corresponds to the transport response object and the correlated extraction request it was given; session identity is **not** authenticated (§5.3). This is the only value v1 may emit for the semantic domain, and it is explicitly NOT equivalent in strength to `DURABLE_RECORD_BACKED`.
- `DURABLE_RECORD_BACKED` — the render domain. The render evidence was obtained from the M5 authority with a durable job/attempt identity revalidated through that authority (§17).
- `NOT_ESTABLISHED` — render-bearing task with no admissible verified render evidence.
- `NOT_APPLICABLE` — the task is not render-bearing.

Rules:

1. The classification is **derived** by M12.5 from how each domain's evidence was obtained. It is never accepted from a caller; a caller-supplied value is rejected structurally (§11).
2. It is **disclosure only**: it grants no authority, and holding `DURABLE_RECORD_BACKED` does not make the semantic target satisfied, nor does it make the semantic domain anything other than `TRANSPORT_CORRELATED`.
3. It never upgrades a claim. Its only permitted effect is to make the weaker strength visible; no rule may read it as evidence, as a verdict, or as an authorization.
4. A future authenticated extraction capability would add a member to `semantic_observation` and must arrive through its own reviewed upstream change; v1 fixes exactly the members above and adds no authentication infrastructure.

---

## 11. Failure model

M12.5 fails closed for all authority or evidence ambiguity.

Required refusal/failure classes include:

- unknown semantic task;
- plan/source-content mismatch;
- invalid plan identity;
- invalid extraction payload;
- extraction contract revision mismatch;
- observation scope mismatch;
- missing requested entity;
- conflicting duplicate observation (the same required requirement with unequal canonical-state digests; repeated identical observation identities are NOT a failure — §7);
- observation identity mismatch;
- observation identity not transport-rooted (a copied/untrusted identity claim disagreeing with the transport-derived value — §5.3);
- observation scope divergence (two observations claiming one requirement with different scope identities — §5.5);
- observation not bound to any required requirement while presented as required (§5.4);
- canonical digest mismatch;
- unsupported invariant;
- invariant registered without an authoritative expected-value source (§8.0);
- expected value unavailable / expectation not derivable by its declared binding mechanism (§7.2, §8.0);
- caller-supplied expectation present for any invariant (§8.0);
- missing invariant input;
- contradictory observation;
- stale observation;
- empty required-invariant set;
- incomplete required-invariant set (source declares invariants the plan does not carry — §7.1);
- extra plan verification requirement (plan requires verification the authorized target does not declare — §7.1);
- plan render classification mismatch (plan `render_plan` disagrees with the digest-bound source classification — §7.3);
- render evidence missing when required;
- render evidence not independently verified;
- render evidence identity not derived from the authoritative M5 verification path (§17);
- render-job identity mismatch;
- render-attempt identity mismatch;
- verifier input contains forbidden authority material;
- caller-supplied producer-owned result structure (`observation_identity`, `render_evidence_identity`, `evidence_trust_basis`, `provenance`) — rejected structurally;
- malformed provenance;
- unsupported future State Extraction fields.

For provenance and authority-material checks, M12.5 must define its own closed typed provenance schema and reuse the repository's existing authority-key predicates.

The declared M12.5 envelope allowlist is exactly:
```
contract_revision
extractor_identity
engine_identity
session_identity
scope_identity
request_identity
canonical_state
canonical_state_digest
source_provenance
```

The declared M12.5 verification/result identity allowlist is exactly:
```
verifier_revision
task_identity
task_version
digital_twin_id
plan_id
source_content_digest
runtime_mapping_digest
required_invariant_names
observation_identity
observation_digests
render_job_identity
render_attempt_identity
render_evidence_identity
evidence_trust_basis
invariant_results
semantic_state
render_state
overall_state
failure_codes
provenance
canonical_digest
```

It matches §10's result shape exactly. The nested structures named in §10 (`observation_identity`, `render_evidence_identity`, `evidence_trust_basis`, `provenance`) are themselves closed and enumerable: their members are declared in §10/§13, they are constructed only by M12.5 from validated inputs, and they are therefore on the declared tier as **producer-owned** structures. No caller may supply them (§10).

Only these explicitly declared fields — and the enumerated members of the producer-owned nested structures — may use the M12.5 high-confidence/allowlist tier. Any other caller-supplied or unknown metadata surface must use the broad `is_forbidden_authority_key` predicate and the closed typed-schema check. Unknown keys are rejected structurally. A surface must not be routed to the declared-field tier merely because its name resembles an allowed field, and no nested mapping inside a caller-controlled surface inherits the declared tier from its parent.

Screening is required at **both** levels on every untrusted surface:

- **keys** — the broad predicate (`session_identity`, `scope_identity`, `attempt_id` and the credential/authority vocabulary are all rejected there). Those names are legitimate only on the two declared surfaces: the observation envelope's identity fields (derived by M12.5 from the transport response per §5.3, not accepted from a caller) and the producer-owned result structures listed above.
- **values** — recursive authority-token screening of scalar string values, so authority-shaped material cannot ride in a value whose key looks benign.

`source_provenance` is a declared envelope field whose **content** is caller-controlled. It is therefore validated by the closed typed schema plus the broad predicate and value screening at every depth, and nothing inside it may be copied into the canonical result or into any producer-owned structure merely for traceability (§13).

Each tier must have an adversarial test, including attempts to smuggle authority-shaped keys through nested mappings, aliases/separator/casing variants, and otherwise undeclared fields, plus attempts to place an authority-shaped token in a scalar value, plus attempts to supply a caller-owned `observation_identity`/`render_evidence_identity`/`evidence_trust_basis`/`provenance` structure. Caller-supplied metadata must not be accepted into the canonical result digest merely because it is syntactically JSON-compatible.

No failure class may downgrade to a pass.

---

## 12. Authority isolation

M12.5 must pass a structural authority-isolation review.

The verifier must not expose or import execution authority such as:

- authorization issuance;
- task scheduler;
- autonomous executor;
- render submission;
- recovery coordinator;
- receipt store;
- production-artifact store as a source of authority;
- transport server;
- subprocess/process lifecycle controls.

A semantic verification result is downstream information, not authorization.

The verifier may consume snapshots or immutable records created by those authorities, but it may not mutate or command them.

The structural isolation mechanism is normative: the M12.5 authority-isolation test must inspect source ASTs using an explicit forbidden-module/import allowlist pattern, modelled on the existing M7 keeper authority-isolation test rather than the weaker package-walk mechanism in the existing M12 test. A green test that only proves forbidden modules are absent from the list of already-walked `planning.m12.*` names is insufficient — that mechanism is a tautology (the walked set can only ever contain `planning.m12.*` names, so a non-M12 authority name can never appear in it; verified against the current tree).

The gate must detect, over every source file in the M12.5 implementation surface:

- ordinary imports — `import X`, `from X import Y`;
- aliased imports — `import X as Z`, `from X import Y as Z`;
- deferred dynamic imports — `importlib.import_module("X")`, `__import__("X")`, `from importlib import import_module` used with a forbidden string, and any string constant equal to a forbidden module name or its prefix.

Positive controls are mandatory, each demonstrated to make the gate FAIL when injected into a fixture copy of the implementation surface, and to leave the real tree PASSING:

```text
(a) a module-level ordinary import of a forbidden module;
(b) an aliased import of a forbidden module;
(c) a deferred importlib.import_module(...) call inside a function;
(d) a string constant naming a forbidden module.
```

Non-vacuity is also mandatory: the gate must assert that the scanned file set is non-empty and includes every module of the §23 implementation surface, so a scan that silently resolves to zero files cannot pass. Note that the M7 keeper helper `_all_imports` only walks `ast.Import`/`ast.ImportFrom` (`tests/m7/test_m7_keeper_authority_isolation.py:91-102`) and therefore does NOT see form (c); the M12.5 gate must extend that pattern rather than copy it verbatim.

---

## 13. Provenance model

Verification provenance should preserve:

- verifier revision;
- semantic task canonical identity;
- source-content digest;
- execution-plan digest/identity;
- runtime mapping digest when present;
- extraction contract revision;
- extractor/engine identity;
- observation request and scope identity;
- observed-state digests;
- existing render evidence identity when applicable;
- verifier outcome;
- invariant-level outcomes;
- deterministic failure codes.

Provenance is explanatory and reproducibility-oriented.

The provenance input/output surface is a closed typed structure. M12.5 must reject unknown provenance keys and recursively reject authority-shaped material. Provenance values are accepted only from validated observation/result structures; arbitrary caller metadata must not be copied into the canonical result merely for traceability.

The result-side provenance structure is closed and its members are exactly:

```text
verifier_revision
task_identity
task_version
digital_twin_id
plan_id
source_content_digest
runtime_mapping_digest
required_invariant_names
extraction_contract_revision
extractor_identity
engine_identity
observation_session_identity
observation_scope_identity
observation_request_identity
observation_digests
render_job_identity
render_attempt_identity
render_evidence_identity
evidence_trust_basis
outcome
invariant_outcomes
failure_codes
```

Every member is derived by M12.5 from validated inputs (the transport-rooted observation identity of §5.3, the §10 nested structures, the invariant results, and the deterministic failure codes). This structure is producer-owned and therefore sits on the declared tier (§11); it is never populated from caller metadata and is never accepted from a caller.

Two vocabulary notes that follow from §11's tier rule: `observation_session_identity` / `observation_scope_identity` are legitimate members of this producer-owned structure (the broad predicate rejects the bare names `session_identity` / `scope_identity` on untrusted surfaces only), and the reusable public validation surface is `is_forbidden_authority_key` (public in `planning.m12`) plus M12.5's own closed typed schema and recursive walk. The adapter's recursive validators (`_validate_caller_provenance`, `_validate_mapping_provenance`) are module-private and mapping-bound; they are the pattern to mirror, not an API to import.

It must never become a second authorization or recovery record.

---

## 14. Canonicalization and hashing

M12.5 must reuse existing deterministic canonicalization primitives wherever possible.

The implementation must not create competing canonicalizers for:

- semantic task content;
- execution-plan content;
- State Extraction payloads;
- verification results.

Where a new result digest is required, the result must be:

1. built from an explicitly defined JSON-compatible structure;
2. canonicalized deterministically;
3. hashed with the repository's existing strict hashing convention;
4. included in the immutable result identity.

The result digest input is **derived** at serialization time from the validated canonical inputs and module constants (§10.3). It must not be assembled by reading security-relevant values back off mutable objects after validation — the same discipline the input side already requires below.

No caller-supplied digest is authoritative.

Any supplied digest is a redundant assertion that must be recomputed and compared.

Inputs must be parsed/validated into an immutable canonical value graph before evaluation. Verification must evaluate that canonical frozen representation rather than re-reading mutable caller-visible objects after validation. The deterministic suite must include a validate-then-mutate adversarial case and prove that the verification result is unchanged or the mutation is refused because the verifier no longer holds a valid immutable input.

---

## 15. Relationship to State Extraction Fidelity v1

State Extraction Fidelity v1 remains frozen.

M12.5 may depend on the extraction contract but does not revise:

- editor-world authority;
- world scope rules;
- entity-ID canonicalization;
- binary64 transform encoding;
- parent three-state semantics;
- material source-side projection;
- Sequencer refusal semantics;
- payload size limits;
- refusal/error vocabulary.

A semantic invariant that needs a field not present in the frozen extractor is **not** solved by silently reconstructing that field from unrelated engine APIs.

The correct outcomes are:

- reuse an existing supported field;
- explicitly mark the invariant unsupported/unknown;
- or create a separately reviewed future State Extraction extension.

M12.5 must not smuggle a new engine-readable field into the semantic verifier.

M12.5 must not reopen the frozen session boundary in either direction: it may not insert session/engine/request/scope metadata into `canonical_state` (the frozen reserved-key refusal is preserved — schema.py:43-52, `_reject_reserved_keys` invoked at :662 — and the legacy session-augmenting path stays refused, digest.py:41/95-103), and it may not derive semantic verification value from session-varying material. Observation identity lives in the envelope and in the result's producer-owned identity/provenance structures (§5.3, §10, §13), never inside the canonical state payload, and the canonical-state digest stays independent of session, request, transport and clock (frozen extraction design §6.5).

---

## 16. Relationship to M12.4

M12.4 is an adapter and remains non-verifying.

The authority chain is deliberately:

```
M12.3 plan
    ↓
M12.4 runtime mapping
    ↓
runtime execution
    ↓
observation
    ↓
M12.5 verification
```

M12.5 must not call M12.4 as an executor.

The mapping is an **optional** input ("where present" — §3.1, §4.3, §10). M12.5 derives its verification requirements from the resolved source task as defined in §7.1 and establishes the source commitment and the invariant-set reconciliation **itself**. It must not make the mapping mandatory in order to inherit M12.4's comparable reconciliation, must not accept a mapping's reconciled view as a substitute for §7.1's equality rule, and must not treat mapping presence as evidence of execution, verification, authorization, or semantic completion. Render classification comes from the digest-bound source (§7.3), never from the mapping.

The M12.4 placeholder target-state evaluator is **not** an authoritative verification mechanism and must not be promoted implicitly.

---

## 17. Relationship to existing M5+ render verification

Existing M5+ render evidence verification remains the sole authority for:

- artifact topology;
- frame count;
- output path isolation;
- PNG structure;
- file size;
- file hash;
- engine-attested output manifest;
- render evidence identity.

M12.5 may require a verified render-evidence result, but it must not recreate these checks.

**Normative consumption rule:** for M12.5 v1, render evidence is admissible only when it is demonstrably the output of the existing authoritative M5+ `verify_render_job_evidence()` call path, or when the exact same durable job-record / render-job-attempt identity can be independently revalidated through that authority. A bare `UnrealEvidence` object, a persisted snapshot, `verified=True`, `source="caller-supplied"`, or transport-success metadata is never sufficient proof of verification provenance.

The implementation must therefore consume an authoritative verification result/identity, not a caller-settable verification flag. If the existing evidence object cannot carry that provenance without ambiguity, the v1 render-composition implementation must fail closed rather than invent a second render-verification authority.

**Render evidence identity surface (normative, closed).** Because `UnrealEvidence` itself carries no proof of who minted it, M12.5 must derive the render identity from the authoritative path and must never accept it from a caller:

```text
job_identity      := AtlasRenderJobRecord.atlas_job_id      (durable M5 job identity)
attempt_identity  := AtlasRenderJobRecord.attempt_ordinal   (durable M5 attempt identity)
evidence_identity := canonical digest of the evidence snapshot returned BY the M5
                     authority for that job/attempt, recomputed by M12.5
```

The derived triple must agree with the durable record M12.5 revalidated through the authority. A caller-supplied job/attempt/evidence identity, a persisted snapshot on its own, or an `UnrealEvidence` instance not obtained through the authority path fails closed (§11). M12.5 must not construct `UnrealEvidence(verified=True)` itself, must not retain a receipt, and must not issue one. The render leg's trust basis is disclosed as `DURABLE_RECORD_BACKED` (§10.4) and must never be presented as equivalent in strength to the semantic observation leg's `TRANSPORT_CORRELATED`.

This is a hard anti-duplication boundary.

---

## 18. Relationship to receipts and artifact lineage

M12.5 does not issue `UnrealRenderReceipt`.

For render-bearing tasks:

```
M5+ evidence verifier
      ↓
verified UnrealEvidence
      ↓
existing receipt authority
      ↓
ProductionArtifactManifest
```

M12.5 sits beside that chain as a semantic verifier.

The semantic verification result may be referenced by downstream provenance, but it cannot become a replacement receipt or artifact manifest.

---

## 19. Relationship to Temporal Observation + State Delta v1

Temporal Observation + State Delta v1 remains a separate observation/history system.

M12.5 does not require Temporal authority to establish semantic success.

A future integration may record semantic verification outcomes as observations, but:

- Temporal admission does not authorize semantic completion;
- a Temporal state delta does not prove Unreal target-state satisfaction;
- M12.5 does not mutate Temporal state.

Temporal integration is therefore **out of scope for M12.5 v1**.

---

## 20. Live-gate strategy

The architecture should be implemented against the existing State Extraction v1 live gate rather than creating a second Unreal extraction harness.

### Phase A — deterministic contract tests

Construct representative:

- valid state observations;
- missing entities;
- wrong entity IDs;
- wrong transforms;
- parent mismatch;
- material mismatch;
- unsupported Sequencer request;
- stale observation;
- source-content mismatch;
- plan identity mismatch;
- contradictory observations;
- malformed provenance;
- forbidden authority material;
- empty required-invariant set with otherwise valid observation/bindings;
- two observations with the same task/scope/request identity but divergent canonical-state digests;
- directly constructed `UnrealEvidence(verified=True)` and equivalent persisted snapshot, both of which must be refused as render-verification authority.

Mandatory controls added by this revision (§7.1, §7.2, §7.3, §8.0.1, §5.3, §5.5):

- **incomplete requirement set** — source declares `[A, B]`, plan contributes only `[A]`: MUST NOT become `SATISFIED` (`INCOMPLETE_REQUIRED_INVARIANT_SET`);
- **extra requirement** — plan contributes a requirement the source does not declare: MUST fail closed (`EXTRA_PLAN_VERIFICATION_REQUIREMENT`);
- **caller expectation vs digest-bound expectation** — the request carries an expectation that disagrees with the digest-bound expected value: the caller value MUST be ignored and MUST NOT be able to produce `SATISFIED`;
- **no authoritative expectation** — an invariant with no authoritative expected-value source (every non-admissible class in §8.0.1): MUST be `UNKNOWN`/`MISSING` and fail closed, never satisfied from a default or a caller value;
- **stale payload + relabelled envelope** — a stale canonical observation presented with a current-looking request/session/scope envelope: MUST fail closed;
- **copied identity claim** — envelope identity fields hand-copied and disagreeing with the transport-derived values: MUST fail closed (`OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED`);
- **scope divergence** — two observations claiming one requirement with different scope identities: MUST fail closed (`OBSERVATION_SCOPE_DIVERGENCE`);
- **tampered plan render flag** — a supplied plan whose `render_plan` disagrees with the digest-bound source classification: MUST fail closed (`PLAN_RENDER_CLASSIFICATION_MISMATCH`);
- **caller-owned result structures** — a caller-supplied `observation_identity`, `render_evidence_identity`, `evidence_trust_basis`, or `provenance` structure: MUST be rejected structurally.

Prove exact result codes and canonical digests, and prove that repeated verification of the same inputs yields byte-identical results within one process and across separate processes.

### Phase B — real Unreal observation input

Use the already-proven UE 5.6.1 State Extraction fixture session.

The live test must:

1. provision the existing extraction fixture only through its approved opt-in mechanism;
2. request factual state;
3. capture the exact extraction observation envelope **together with the transport response object it was derived from**, so the verifier re-derives the identity components per §5.3 rather than accepting copies;
4. independently feed that immutable observation to the M12.5 verifier;
5. assert target-state outcomes;
6. assert byte-stable repeated verification;
7. assert that semantic verification itself performs no mutation;
8. assert no new render receipt is created by M12.5.

Phase B must also assert the §10.3 immutability mechanism behaviourally: after construction, mutating a stored field on the result object must not change the result's canonical serialization or digest.

### Phase C — negative live controls

At minimum:

- missing entity;
- wrong entity identity;
- mismatched semantic task identity;
- mismatched source-content digest;
- modified observation digest;
- stale observation from another extractor/engine session;
- a stale canonical observation presented with a relabelled current envelope identity;
- conflicting observations carrying the same request identity;
- scope-divergent observations claiming the same requirement;
- an invariant whose authoritative expected value is absent or unbound;
- render-bearing task without verified render evidence;
- render evidence bound to wrong job/attempt identity;
- caller-constructed `UnrealEvidence(verified=True)` or equivalent snapshot presented as if it were M5+ verified evidence.

Each negative control must fail closed.

A stale-observation/other-session control should be exercised with a second real extraction session when the live harness can provide one. If the fixture cannot safely provide a second live session, deterministic Phase-A coverage is an acceptable substitute, but the live-gate record must explicitly state that live stale-session coverage was not available rather than implying that it was proven. In either case the record must also state the §5.3 limitation: the extraction path provides no authenticated session identity, so what is proven is transport-rooted correlation and identity comparison, not authenticated anti-replay freshness.

The live suite should also assert that session/engine/request metadata cannot be smuggled into `canonical_state`; the frozen extractor's reserved-key refusal remains a defense at the observation boundary.

### Phase D — render-bearing composition

Only after the non-render verifier is independently clear should a separate live composition gate consume an existing verified render result.

That composition gate must not modify the M5+ verifier or recovery path.

**Phase D determinism criterion (normative).** Determinism for a render-bearing verification means: identical immutable inputs **and** identical authoritative M5 evidence identity **and** unchanged durable artifact state as read by the M5 authority ⇒ byte-identical M12.5 result. Because the M5 authority reads durable artifacts, the live record must capture the M5 evidence identity (job identity, attempt identity, evidence identity per §17) and the artifact state that authority verified, so a later discrepancy can be attributed to changed artifacts rather than to a non-deterministic verifier. Phase A/B/C determinism — which does not depend on durable artifacts — remains strictly byte-identical for identical inputs.

---

## 21. Offline acceptance criteria

Before implementation can clear:

- target-state evaluation is deterministic;
- the required-invariant set is defined from the resolved source task and EQUALS the plan's per-step `verification_requirements` union, with both directions failing closed;
- all required invariants are evaluated;
- every evaluated invariant uses an authoritative digest-bound expected value; a caller-supplied expectation is never used and cannot produce a pass;
- an invariant with no authoritative expected value is UNKNOWN/MISSING and fails closed;
- UNKNOWN never collapses to PASS;
- identity mismatches fail closed;
- observation identity is transport-rooted; a copied identity claim is rejected;
- conflicting duplicates and scope divergence are classified and fail closed;
- source-content digest is recomputed;
- plan identity is recomputed or independently validated;
- State Extraction canonical digest is recomputed;
- render classification is taken from the digest-bound source, and a disagreeing plan flag fails closed;
- the result's nested identity/provenance structures are closed, producer-owned, and rejected if caller-supplied;
- the result discloses the evidence trust basis of each domain (§10.4), and transport-correlated observation evidence is never presented as durable-record-backed;
- render evidence is never self-attested;
- forbidden authority material is rejected on both keys and values;
- verification result is immutable in the §10.3 sense (derived serialization; mutating a stored field after construction does not change the canonical serialization or digest);
- verification result canonical JSON is stable;
- repeated identical verification produces byte-identical output;
- the §8.0.1 v1 coverage limitation is recorded in the acceptance record rather than silently omitted;
- no execution/recovery/authorization authority imports exist;
- structural AST authority-isolation gate passes, including the forbidden-import positive controls (ordinary, aliased, deferred `importlib.import_module`, string constant) and the non-vacuity assertion;
- no M4–M10 production authority modules are modified;
- no State Extraction v1 frozen contract is changed.

---

## 22. Required adversarial review questions

An independent red-team review must answer at least:

1. Can a caller pair a valid semantic task with an observation from another task?
2. Can a caller substitute a different source task while retaining the original plan identity?
3. Can a caller substitute a different observation while retaining the original observation digest?
4. Can caller-controlled provenance smuggle authorization, receipt, nonce, HMAC, credential, scheduler, recovery, or artifact authority?
5. Can UNKNOWN become SATISFIED through default values?
6. Can an unsupported State Extraction field be inferred from a secondary engine API?
7. Can M12.5 accidentally duplicate render artifact verification?
8. Can a render job be treated as verified merely because transport succeeded?
9. Can a receipt be created from an M12.5 semantic result alone?
10. Can M12.5 issue, mutate, or schedule execution authority?
11. Can repeated verification of the same inputs yield different canonical results?
12. Can a stale observation from another session be accepted?
13. Can a model-controlled target-state definition change the verifier's own authority boundaries?
14. Can M12.4's aggregate runtime mapping be mistaken for per-fragment execution proof?
15. Can a successful semantic state be reported when the required render evidence is missing?
16. Can future/unknown State Extraction fields be silently ignored in a way that creates a false pass?
17. Can a source-declared target invariant be dropped from the evaluated requirement set, or an extra requirement added, without failing closed (§7.1)?
18. Can any invariant be evaluated against a caller-supplied expectation instead of a digest-bound one (§7.2, §8.0)?
19. Can a stale canonical payload be presented as current by relabelling the envelope, and is the §5.3 limitation recorded as a limitation rather than implied to be proven?
20. Can an unregistered, unbound, or non-admissible invariant reach SATISFIED through a default, a partial evaluation, or an "unavailable expectation" fallback (§8.0.1)?
21. Can a plan's `render_plan` flag override the digest-bound source render classification (§7.3)?
22. Can a caller supply `observation_identity`, `provenance`, `render_evidence_identity`, or `evidence_trust_basis` and have it survive into the result (§10, §11, §13)?
23. Does the result disclose, machine-readably, that transport-correlated observation evidence is not equivalent in strength to durable-record-backed render evidence, and can any rule read `evidence_trust_basis` as evidence, a verdict, or an authorization (§10.4)?

A required-change finding blocks implementation authorization until remediated and re-reviewed.

---

## 23. Implementation package after CLEAR

Only after the architecture receives an independent CLEAR should implementation begin.

The expected minimal implementation surface is:

```text
planning/m12/verification.py
planning/m12/verification_result.py
tests/m12/test_m12_5_verification.py
tests/m12/test_m12_5_identity_binding.py
tests/m12/test_m12_5_authority_isolation.py
tests/m12/test_m12_5_adversarial.py
```

A live gate should be added only after the deterministic verifier is independently green.

The implementation should reuse existing:

- State Extraction parsing/canonicalization;
- source-content digest calculation;
- plan identity calculation;
- the **evaluation model only** (all-required-invariants / fail-closed semantics) from `TargetStateEvaluator`, never its placeholder predicate bodies;
- the exact-name closed invariant registry defined and reviewed for M12.5 v1 under the §8.0 admissibility rule; non-admissible or unavailable invariant requirements remain UNKNOWN and fail closed (§8.0.1);
- the M5 render evidence verifier (§17), consumed only through `verify_render_job_evidence()`;
- authoritative render job/attempt identity records, read-only, as evidence metadata.

It should not copy those authorities.

### 23.1 Permitted read-only authority surfaces (normative)

M12.5 may reference only the following, and only read-only:

```text
planning.m12.*                      M12.1-M12.4 contracts: normalize_unreal_semantic_request,
                                    UnrealProductionTaskDefinition, compute_source_content_digest,
                                    UnrealExecutionPlan, map_unreal_execution_plan (optional
                                    lineage), is_forbidden_authority_key. NOT modified by M12.5.
planning.unreal_state_extraction    frozen extraction boundary (validation, canonicalization,
                                    digest). NOT modified.
planning.unreal_transport_contract  response envelope types + validate_response_correlation (§5.3).
planning.unreal_evidence_contract   the M5 render-evidence authority, consumed only through
                                    verify_render_job_evidence() and its returned UnrealEvidence (§17).
                                    M12.5 never constructs UnrealEvidence(verified=True) itself.
authoritative render job/attempt     AtlasRenderJobRecord.atlas_job_id / .attempt_ordinal and the
identity records                     durable record(s) behind them, read-only.
```

### 23.2 Forbidden surfaces (normative)

M12.5 must not import, expose, reference or command:

```text
planning.unreal_render_submission            render submission
planning.unreal_render_receipt_store         receipt publication/store
planning.unreal_render_receipt               receipt identity module — M12.5 has no receipt
                                             need; reference identity types only if a future
                                             reviewed design proves a need, and never construct
                                             or issue a receipt
planning.unreal_render_recovery_coordinator  recovery policy/decisions
schedulers / retry controllers / autonomous execution loops / controller bridge
the transport server, subprocess and containment/process-lifecycle controls
the production-artifact store as a source of authority
```

M12.5 may reference an identity type as **evidence metadata** — it may carry a job/attempt identity it did not mint — but it may never construct or issue a receipt, artifact manifest, or authorization, and a semantic verification result is never authorization.

### 23.3 Public reusable validation surface (normative)

`is_forbidden_authority_key` (public via `planning.m12`) plus M12.5's own closed typed schema and recursive key+value walk. The adapter's recursive validators (`_validate_caller_provenance`, `_validate_mapping_provenance`) are module-private and mapping-bound; they are the pattern to mirror, not an API to import.

---

## 24. Promotion gate

Implementation authorization requires all of the following:

### Architecture
- M12.5 design reviewed by an independent architectural/red-team agent;
- no required-change findings remain;
- authority boundaries explicitly accepted.

### Deterministic implementation
- complete M12.5 focused suite green;
- relevant M12 and Unreal suites green;
- full deterministic non-integration suite green;
- no authority-import violations.

### Live non-render gate
- real UE 5.6.1 State Extraction observation consumed and transport-rooted (§5.3);
- the closed contract proven on live input: invariant-set commitment and both-direction equality, expectation admissibility, refusal vocabulary, contradiction and scope-divergence classification, and the honest outcome for a non-admissible invariant set;
- negative controls proven;
- no mutation or receipt side effect;
- **explicitly not claimed:** a positive `SATISFIED` semantic verification. Under §8.0.1 no non-render invariant is admissible today, so a live positive is unreachable in v1; a live record must state that plainly rather than substitute a fixture-supplied expectation or a placeholder predicate. Claiming a live positive requires the upstream digest-bound expectation source (§26 Q8) first.

### Live render composition
- existing M5+ verified render evidence consumed without modifying the existing verifier;
- correct render-job/attempt identity binding proven;
- semantic result only becomes satisfied when all declared conditions are independently established — and, per §8.0.1, the semantic domain stays `UNKNOWN` until at least one admissible semantic invariant exists.

No one gate substitutes for another.

---

## 25. Mandatory non-claims

This architecture must not claim:

- that State Extraction itself verifies semantic success;
- that a semantic task is complete because transport succeeded;
- that a render artifact is valid because M12.5 says so;
- that M12.5 replaces M5–M10;
- that M12.5 authorizes mutation;
- that M12.5 creates receipts;
- that target-state names are evidence;
- that unsupported extraction fields can be inferred safely;
- that partial semantic state is equivalent to success;
- that Temporal state is semantic proof;
- that model confidence is evidence;
- that the live State Extraction fixture covers cases explicitly marked not-yet-live-covered, refusal-verified, or blocked by engine/API limitation;
- that the extraction envelope's session/request identity is authenticated — it is transport-rooted and internally correlated only, and authenticated anti-replay freshness is not established by v1 (§5.3);
- that a stale observation was detected when the presented envelope is internally consistent with a stale payload (§5.3);
- that M12.5 v1 can report SATISFIED for a non-render semantic task while no non-render invariant is admissible (§8.0.1);
- that a conflicting or scope-divergent observation set was resolved by selecting an observation (§5.5, §7);
- that transport-correlated observation evidence has the same strength or authority as durable-record-backed render evidence (§10.4);
- that a semantic verification result is a receipt, an authorization, or a substitute for M5 evidence verification (§18).

---

## 26. Open design questions for the independent review

These are intentionally left open for the independent review/reconciliation gate rather than silently decided in implementation.

**Closed by this revision** (recorded so the next review can test the closure rather than re-litigate it):

1. *Which exact target-state invariant names are stable for v1?* — Still implementation-review work for the registry contents, but the admissibility rule is now fixed (§8.0) and the v1 assessment is recorded (§8.0.1). An invariant without a digest-bound expectation source cannot be registered.
2. *Which State Extraction envelope/session fields are authoritative for observation binding?* — Closed: the transport response envelope is the root (§5.3), with each component's sourcing enumerated, the copied-claim prohibition, and the non-authentication limitation recorded in §5.3/§25.
5. *Minimum safe render-evidence identity surface?* — Closed: §17 defines the closed `job_identity` / `attempt_identity` / `evidence_identity` triple, derived by M12.5 from the authoritative path; a bare caller-settable `verified` flag is inadmissible by construction.
7. *What proves a live M12.5 run performed no mutation?* — Closed in form: §20 Phase B asserts no mutation, no receipt, byte-stable repeats, and the §10.3 derived-serialization behaviour.

**Still open** (design-review inputs, not authorization to expand scope):

3. Should the verification result store a full immutable invariant result tree, or only canonical result codes plus a separately recoverable evaluation trace?
4. For non-render semantic tasks, is the M12.5 result itself sufficient as downstream provenance, or is a separate lightweight Atlas semantic-task record required later?
6. Which semantic task classes can be live-validated in v1 without requiring new Unreal transport fields — given that no non-render invariant is admissible until an expectation source exists (§8.0.1)?
8. **Upstream, out of scope for M12.5 v1:** admitting non-render semantic invariants requires a digest-bound expectation source. The candidate directions are a typed expectation surface on the M12.1 target-state contract, or a separately reviewed digest-bound semantic-input contract. Either is an upstream contract change requiring its own design gate; M12.5 must not invent it, and must not accept caller-supplied expectations in the meantime (§8.0). v1 has no declared-input channel, and any future expectation commitment must live outside the verification request.

These questions are design-review inputs, not authorization to expand scope.

---

## 27. Current conclusion

M12.5 is the logical next Unreal architecture gate because the repository now has all of the required upstream pieces:

- a validated semantic task;
- a canonical execution plan;
- a non-authoritative runtime mapping;
- a frozen deterministic Unreal factual-state extractor;
- an existing authoritative render-evidence verifier.

The missing boundary is the deterministic, independent decision that those observed facts satisfy the semantic production target.

This revision closes the three architecture-level design defects identified in the previous exact-head review, and explicitly bounds the remaining v1 capability limitations:

1. **the required-invariant set is now defined and bound** — it is the resolved source task's declared target-state invariants, bound to the source-content commitment and required to EQUAL the plan's per-step verification requirements, failing closed in both directions (§7.1);
2. **every evaluated invariant must have a digest-bound authoritative expectation** — a caller-supplied expectation is never admissible, and invariants without an authoritative expectation are UNKNOWN and fail closed, with the resulting v1 coverage limitation recorded (§7.2, §8.0, §8.0.1);
3. **observation identity is transport-rooted and its limitation is stated** — the envelope identity components are re-derived from the correlated transport response, copied claims fail closed, scope divergence and conflicting duplicates are classified, and the absence of authenticated anti-replay freshness is recorded rather than implied to be proven (§5.3, §5.4, §5.5).

The capability limitation itself is **not** closed by this revision: v1 has no positively verifiable non-render semantic invariant and no declared-input expectation channel, so unsupported or unbound requirements stay `UNKNOWN` and fail closed, and the result discloses the weaker evidence trust basis of the observation domain (§8.0, §8.0.1, §10.4). Closing it requires the upstream expectation authority (§26 Q8) — it must not be closed by inventing a predicate or accepting a request-derived expectation.

The intended result is:

```text
facts → target-state evaluation → bound semantic verification result
```

not:

```text
facts → new executor / new scheduler / new recovery / new receipt system
```

**Implementation remains unauthorized until this document receives an independent architectural/red-team CLEAR.**
