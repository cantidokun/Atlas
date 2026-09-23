# Atlas M12.5 — Unreal Semantic Evidence Verification v1

**Status:** ARCHITECTURE / RECONCILIATION ONLY — implementation NOT authorized  

**Revision:** v1.9 — architecture-remediation round 9: closes V18-1 (§23.1 no longer describes `.request_digest` as an "agreement field": the list is now "read-only record fields available for agreement checks", with each field's actual role stated — `.canonical_digital_twin_id` and `.config_digest` participate in authority-backed agreements, `.sequence_asset_path` is enforced record↔evidence by the authority while the task-side correspondence is `NOT_ESTABLISHED`, and `.request_digest` is readable on the durable record but establishes no agreement in v1 — plus the normative sentence "being readable does not make a field an agreement dimension"). Terminology-only; the architecture, all truth values and all prior closures are unchanged.

**Prior revision (v1.8): architecture-remediation round 8: closes V17-1 (§17's render-job/task agreement framing is now authority-based rather than task-only: a dimension's agreement must be established by the relevant reviewed authority — record↔evidence correspondence where the render authority enforces it, and agreement with the digest-bound source task where a task-side counterpart exists — so a dimension with no task-side field, such as `config_digest_agreement`, is no longer implied to be a task-side field) and V17-2 (the third expectation-source control, "caller expectation vs digest-bound expectation", is brought under the no-vacuous-pass rule: it requires an existing reviewed digest-bound expected value and an observable differential mechanism, so while v1 has no admissible semantic invariant it MUST be recorded `NOT PROVEN`, and an ambient `EXPECTED_VALUE_UNAVAILABLE` refusal is never evidence that the differential control executed). A general control-status truthfulness rule is added for §20 Phases A/C/D, §21, §22, §24 and §25.

**Prior revision (v1.7): architecture-remediation round 7: closes V16-1 (the `artifact_ref` classification now states the `ProductionArtifactManifest` relationship accurately — it IS downstream-linked to the render path, while remaining unlinked to `AtlasRenderJobRecord`, unconsulted by M5's render-evidence verification, and without any reviewed typed correspondence to `artifact_ref`) and V16-2 (the combined "request/config digest" dimension is split: `config_digest_agreement` is `ENFORCED` because the authority compares the observed `config_digest` against the durable record and rejects a mismatch, while `request_digest_agreement` is `NOT_ESTABLISHED` because the render authority validates no request digest and the M12.1 task contract declares no counterpart — so it is never recorded `ENFORCED` and is never reported as a detected mismatch, and the render requirement continues to fail closed in v1).

**Prior revision (v1.6): architecture-remediation round 6: closes V15-1 (the `artifact_ref` classification basis is now factually precise — the render/job authority carries `sequence_asset_path` **and** other output/artifact/receipt-related references, M5's render verification validates none of the latter against an artifact reference, and no reviewed typed correspondence exists — so no correspondence is invented, `artifact_ref` can never become a positive render identity expectation, and the classification must be revisited under any future reviewed artifact/manifest contract) and V15-2 (the sufficiency rule for verified catalog resolution is now mechanical: content-level consistency — entry name, version, class, parameter kinds, exact closed parameter set, byte-identical canonical payload, matching source-content/plan digest — is **necessary and never sufficient**, and positive absence requires the §26 Q10 reviewed resolution binding, so the render-bearing `NOT_APPLICABLE` route stays unreachable in v1).

**Prior revision (v1.5): architecture-remediation round 5: closes V14-1 (the reviewed render identity classification is now complete for **every** render-bearing catalog entry, with an explicit assignment for `unreal.artifact-validate` / `artifact_ref`, and a mandatory fail-closed default for any render-bearing entry that has no assignment), V14-2 (positive catalog provenance must be **independently verified** against the reviewed catalog definition: a caller-presented `catalog_entry`/`catalog_version` claim, a verbatim copy of legitimate values, or a mismatched parameter set is `NOT_ESTABLISHED` and can never produce `NOT_APPLICABLE`), V14-3 (§8.0.1's v1 coverage statement now uses the same **render-bearing** boundary as §17/§24/§27), and V14-4 (the expectation-source refusal class has the explicit token `EXPECTED_VALUE_UNAVAILABLE` in §11, so no control requires an undefined code).

**Prior revision (v1.4): architecture-remediation round 4: closes V13-1 (the render identity **recognition boundary** is now a mechanical three-state rule with a reviewed recognition surface, a reviewed-resolution requirement for render-bearing tasks, and a monotonic fail-closed default: uncertainty may only increase refusal, never acceptance), V13-2 (render-state / task-relative render-verification semantics when a declared identity dimension is unresolved), V13-3 (the registry divergence check is now mandatory and "code-level canonical source" is defined), and V13-4 (the two expectation-source controls must now prove their **specific** refusal code rather than passing on the v1 coverage limitation). MR-4's decision semantics, MR2-1, MR-1, MR-3 and MR-5 are retained and not weakened.

**Prior revision (v1.3): architecture-remediation round 3: closes the two findings of the re-review of the v1.2 tree (MR4-1, MR2-1). A declared sequence/asset identity is now a **declared render identity dimension** with a normative fail-closed rule (`RENDER_TASK_CORRESPONDENCE_NOT_DECIDED` / `RENDER_TASK_CORRESPONDENCE_MISMATCH`), and §9.3 defines a render domain as independently valid only when every declared dimension is decided and every comparison succeeded; registry expectation authority may come only from the reviewed code-level canonical registry value bound by its reviewed constant digest, never from a caller-authorable `metadata.fragments` snapshot (`FRAGMENT_EXPECTATION_SOURCE_NOT_CANONICAL`). MR-1, MR-3, MR-5, the transport-rooted≠authenticated limitation, the disclosure-only trust basis and the no-declared-input-channel rule are unchanged and not weakened; this round only tightens.

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

> **Did the resolved semantic production target actually become true in the observed Unreal state, using only authoritative inputs and without trusting self-reported completion?**

M12.5 answers that question for the (resolved source task, execution plan) pair it is given. It binds that pair to the observations — and to authoritative render evidence where applicable — but it does **not** establish that the pair was authorized or dispatched, and it is not a durable authorization/dispatch record (§25).

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
- **Verification** determines whether those facts satisfy the resolved source task's declared semantic target (§25).
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

The render edge is not exempt from having a defined counterpart, and it is not a disclosure-only edge: under §17's declared-dimension rule the durable job/attempt identity must be established by the relevant reviewed authority on every declared dimension — record↔evidence correspondence where the render authority enforces it, and agreement with the digest-bound source task where a task-side counterpart exists — so a genuinely verified render belonging to a different twin, carrying a different observed `config_digest`, presenting an unestablished request-digest correspondence, or not corresponding on a declared sequence/asset identity cannot satisfy this task's render requirement. A declared dimension that no reviewed typed binding decides fails the render requirement closed (`RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`) rather than being counted as a valid render domain (§9.3, §17, §25).

These bindings are internal-consistency bindings between the supplied source task, the execution plan, the observations, and authoritative render evidence where applicable. They do **not** attest that the source task was authorized or that the plan was dispatched, and they are not a durable authorization/dispatch record (§25).

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
- `plan union ⊋ required_invariants` → `EXTRA_PLAN_VERIFICATION_REQUIREMENT`. The plan requires verification of something the resolved source task's declared target does not.

M12.5 establishes both commitments itself, from the resolved source task and the immutable plan. It must not make the M12.4 runtime mapping mandatory in order to inherit M12.4's comparable reconciliation, and it must not relax either rule when no mapping is present.

### 7.2 Authoritative expected values (normative)

Every required invariant is evaluated against an **authoritative expected value** (or authoritative expected identity) supplied by a digest-bound source — never by the verification request. The admissibility rule, the per-invariant source/path/binding declaration, and the unavailable-value behaviour are defined normatively in §8.0 and enumerated per invariant class in §8.1–§8.6; the resulting v1 coverage limitation is recorded in §8.0.1.

An invariant whose expected value is unavailable, unbound, or not authorized is `UNKNOWN`/`MISSING` and fails closed. It is never satisfied from a caller-supplied expectation, and a caller-supplied expectation is never authoritative. Caller-supplied expectation + caller-supplied observation must never compose into `SATISFIED`.

**Committed is not the same as authoritative (normative).** Inclusion of a value in the source-content commitment makes it tamper-evident and binds the source task to the plan; it does not make a caller-authored value an authoritative expectation. An invariant whose only expected-value source is a free-form or caller-authored field — however well committed — is `UNKNOWN` and fails closed (§8.0, §8.0.1).

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

1. **authoritative expected-value source** — a digest-bound artifact whose commitment already exists OUTSIDE the verification request, reached only through a **reviewed, contract-declared, typed field**. In v1 exactly two sources are admissible:
   - the resolved source task, covered by `compute_source_content_digest(source_task)` (the same commitment M12.3 binds into `plan.source_content_digest`) — and admissible only through a typed field that an existing contract declares and that implementation review has reviewed, as the render requirement does with `task_class` plus `target_state.expects_render` (§8.6); or
   - a **reviewed code-level canonical M12.2 registry value**, obtained only from the canonical registry entry (exact `canonical_id` + `version`), used as a code-level canonical **constant**, and bound before verification begins by recomputing that entry's canonical serialization digest from the code-level canonical source (§8.0.1) and requiring it to equal the reviewed constant digest declared with the invariant definition (limb rules in §8.0.1). **Caller-supplied copies are never an expectation source**: a fragment snapshot carried inside the resolved source payload (`metadata.fragments` or any other caller-authorable location) is **never** the value and **never** its authority; its only permitted role is a **mandatory** divergence check against the reviewed canonical value, which must fail closed on any difference (`FRAGMENT_EXPECTATION_SOURCE_NOT_CANONICAL`, §11). An implementation may not ignore a caller snapshot and still claim compliance (§8.0.1, §20 Phase A).
   Explicitly **NOT** admissible, whatever their commitment status: the caller-authored free-form `metadata` / `parameters` surface (untyped `json`), arbitrary JSON blobs anywhere in the resolved source, and any caller-derived field whose only claim to authority is its inclusion in the source-content digest.
2. **exact source field/path** — the precise path inside that artifact. A path into a free-form mapping is admissible only when a reviewed typed contract declares that exact field; free-form sub-paths of `metadata`/`parameters` are not admissible paths;
3. **binding mechanism** — the exact deterministic rule that derives the expected value from that path and matches it to a declared field of the frozen State Extraction contract (or to an authoritative M5 render-evidence identity, §17);
4. **frozen/committed status** — whether the field is covered by the source-content commitment or by another committed digest. For the registry limb that commitment is the **reviewed constant digest declared with the invariant definition and recomputed from the code-level registry source** (§8.0 limb 2); a live code-level value is not a commitment by itself, and `frozen=True` on a mutable runtime object is not an integrity boundary (§8.0.1);
5. **unavailable-value behaviour** — `UNKNOWN`/`MISSING` and fail closed; never a default, never a best-effort value, never a caller-supplied expectation.

**No declared-input channel exists in v1 (normative).** v1 admits no additional, "explicitly declared", or request-carried expectation input. The following chain MUST NEVER constitute authority:

```text
caller request → expected value → digest computed from the same caller request → verification
```

A request-carried expectation, an expectation blob whose only commitment is a digest the request itself supplies, and any input whose "authority" derives from the verification request are inadmissible whatever their name: the invariant is `UNKNOWN`/`MISSING` and verification fails closed (`EXPECTED_VALUE_UNAVAILABLE`, §11). Caller-supplied expectation + caller-supplied observation must never compose into `SATISFIED`.

**Digest binding is tamper-evidence, not authorization (normative).** The source-content commitment proves that the source task and the execution plan the verifier was given are the committed pair — internally consistent, and unmodified since commitment. It does not make a caller-authored value authoritative, it does not attest authorization or dispatch, and it does not tie the pair to any durable authorization or dispatch record (§25). A caller-authored free-form parameter that is digest-bound into the source task therefore remains a caller-authored value, and it is not an admissible expected value (§8.0.1).

**A caller-authored snapshot is not canonical (normative).** `metadata` is caller-authorable content — M12.1 normalization accepts an arbitrary `metadata` mapping, and the catalog composition path happens to place a fragment snapshot in `metadata.fragments`. Presence in the source-content commitment makes such a snapshot tamper-evident; it does **not** make its content canonical, and no digest computed from caller-provided content may promote it to authority. The registry limb above therefore admits only the reviewed code-level canonical registry value bound by its reviewed constant digest; a caller-supplied copy serves solely as divergence evidence (§8.0.1). The following chain must never constitute authority:

```text
caller metadata.fragments → digest computed from the same caller content → registry expectation authority   [NEVER AUTHORITY]
```

A future expectation source must be an upstream, separately reviewed contract that commits the expectation OUTSIDE the verification request — for example a typed expectation surface on the M12.1 target-state contract, or another committed artifact carrying its own committed digest. M12.5 v1 must not invent one, and must not accept one while it does not exist (§26 Q8).

Evaluation matching stays exact-name. An unregistered name, an invariant whose expected value is unavailable, and an invariant whose expected value cannot be derived by its declared binding mechanism are all `UNKNOWN` → fail closed (§7).

### 8.0.1 v1 admissibility assessment and coverage limitation (normative)

The current contracts (M12.1 task contract, M12.2 catalog/fragment registry, M12.3 plan) carry target-state invariants as **names only**, plus free-form catalog parameters. They carry no **reviewed typed** invariant→expected-value binding and no authoritative requested-entity identity, so §8.0's rule has this consequence. Every exclusion below rests on that **absence of a reviewed typed binding** — not on the absence of the data: several of these values do exist in the resolved source, but only as untyped, caller-authored JSON that no reviewed contract declares as an expectation field (they are committed, and commitment alone confers no authority — §8.0).

**Admissibility summary (v1).** Admissible → the render-evidence requirement only (§8.6). Not admissible → every semantic invariant class (§8.1–§8.5): digital-twin identity, requested entity existence/uniqueness, requested sequence/asset identity, transform equality, hierarchy/parent relationships, material, and Sequencer facts. Consequence: M12.5 v1 has no positively verifiable non-render semantic invariant, and none may be manufactured from the verification request (§8.0).

| Invariant class | Authoritative expected value today | v1 status |
|---|---|---|
| digital-twin identity equality (§8.1) | no reviewed typed binding: the frozen extraction tree exposes world/level/actor paths, and no reviewed contract maps `digital_twin_id` to them | NOT ADMISSIBLE in v1 → `UNKNOWN`, fail closed |
| requested entity existence / uniqueness (§8.1) | no reviewed typed binding: the resolved source declares no requested entity-ID set (its `evidence`/`actions` arguments are `{"capability": …}` / `{"op": …, "target": …}`), so there is no typed expectation field to bind | NOT ADMISSIBLE in v1 → `UNKNOWN`, fail closed |
| requested semantic asset/sequence identity (§8.1) | no reviewed typed binding: `sequence_name` is a free-form string that no reviewed contract binds to `sequence_asset_object_path` | NOT ADMISSIBLE in v1 → `UNKNOWN`, fail closed |
| requested artifact/validation identity (§8.1) | no reviewed typed binding: `artifact_ref` is an untyped, caller-authored `string` with no reviewed typed correspondence to any render-authority field (`sequence_asset_path`, `manifest_reference`, `receipt_reference`, output topology) and no reviewed semantic expectation field | NOT ADMISSIBLE in v1 → `UNKNOWN`, fail closed |
| transform equality (§8.2) | no reviewed typed binding: no reviewed contract declares a transform expectation field, and `camera_slots` / `lighting_rig` exist only as free-form, caller-authored `json` parameters inside `metadata` — committed, but untyped and inadmissible as an expectation (§8.0) | NOT ADMISSIBLE in v1 → `UNKNOWN`, fail closed |
| hierarchy/parent invariants (§8.3) | no reviewed typed binding: no reviewed contract declares an expected-parent field anywhere in the resolved source | NOT ADMISSIBLE in v1 → `UNKNOWN`, fail closed |
| material invariants (§8.4) | no reviewed typed binding: no material expectation field is declared by the resolved source or by any reviewed contract | NOT ADMISSIBLE in v1 → `UNKNOWN`, fail closed |
| Sequencer invariants (§8.5) | no reviewed typed binding: `frame_start`/`frame_end` exist only as free-form parameters, with no reviewed binding to `playback_range.lower_frame`/`upper_frame`, and Sequencer extraction is not live-covered | NOT ADMISSIBLE in v1 → `UNKNOWN`, fail closed |
| render-evidence requirement (§8.6) | **yes**: `is_render_task_class(source_task.task_class)` and `target_state.expects_render`, both covered by the source-content commitment, matched against an authoritative M5 render-evidence revalidation that must also satisfy §17's recognition + declared-dimension rule — twin identity and **config-digest** correspondence are `ENFORCED` today (the authority requires the observed `config_digest` and rejects a mismatch against the durable record), while the **request-digest** correspondence is `NOT_ESTABLISHED` (the authority validates no request digest and the task contract declares no counterpart) and the sequence/asset identity dimension is `NOT_ESTABLISHED` (no reviewed typed binding exists, and concluding that the dimension is definitely absent requires an independently verified catalog resolution, §17) — so the render requirement fails closed (`RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`) | ADMISSIBLE in v1; the sequence/asset identity dimension fails the render requirement closed in v1 |

**"Code-level canonical source" (normative definition).** The **code-level canonical source** is the reviewed, statically code-defined canonical registry value from which the reviewed constant digest is derived. It is *not* a live mutable runtime object, *not* an exported object that can be mutated, *not* caller-provided serialized content, and *not* arbitrary module state. The registrable value is the code-level canonical value; the reviewed constant digest, recomputed from that source and required to be equal, is the binding.

**Registry-limb rules (normative, §8.0 limb 2).** A registry-derived expectation may come only from a **reviewed canonical source whose value is independently defined and whose commitment is not created by the same caller request being verified**: the exact `canonical_id` + `version` entry of the canonical registry, used as a code-level constant, and bound before verification begins by recomputing that entry's canonical serialization digest from the **code-level canonical source** and requiring equality with the reviewed constant digest declared with the invariant definition (deep isolation, or hash-binding at input-parse time — a shallow copy is not sufficient for a nested mapping).

**Divergence check is mandatory (normative).** If a caller-authorable fragment snapshot exists anywhere in the resolved source payload, the verifier MUST compare it with the reviewed canonical value of the corresponding registry entry and MUST fail closed on any difference (`FRAGMENT_EXPECTATION_SOURCE_NOT_CANONICAL`, §11). If no caller snapshot exists, only the reviewed canonical value is used. Ignoring an existing caller snapshot and claiming compliance does not satisfy this rule. **Live mutable module state is never authoritative expectation data**, and **a caller-authored snapshot is never an authoritative expectation**: `frozen=True` on a mutable runtime object is not an integrity boundary — `object.__setattr__` defeats it, and in-place mutation of a mutable field's contents is likewise visible through a canonical-registry accessor that hands back the live exported object — and a digest computed solely from caller-provided content (for example `metadata.fragments`) does not make that content canonical. `metadata.fragments` may be used only to detect divergence from the code-level canonical value. Negative controls must demonstrate that (a) mutating live registry state after commitment cannot alter the verification expectation or the result, and (b) a caller-authored `metadata.fragments` snapshot cannot become an authoritative expectation (§20 Phase A).

**v1 coverage limitation (recording obligation, never presented as a pass).** With the currently admissible set, M12.5 v1 cannot reach `SATISFIED` for a non-render semantic task, and the semantic domain of a render-bearing task stays `UNKNOWN` → fail closed. The render half is equally closed in v1, and the boundary is **every render-bearing task**, not only catalog `unreal.render-execute`: where a reviewed typed/closed identity surface establishes a declared sequence/asset dimension the dimension must be resolved or the render requirement fails closed (every `unreal.render-execute` task declares `sequence_name`); where a reviewed per-entry classification establishes that the entry declares no such dimension (`unreal.artifact-validate` / `artifact_ref`) the dimension is still `NOT_ESTABLISHED`, because `NOT_APPLICABLE` additionally requires an independently verified catalog resolution that v1 cannot authenticate (§17, §26 Q10); and where the entry is render-bearing but unassigned the dimension is `NOT_ESTABLISHED`. Positive task-relative render verification is therefore unavailable in v1 wherever the required task↔render identity binding does not exist — in v1 that is every render-bearing task — so the render requirement fails closed and the render domain is not independently valid (§9.3, §17). V1 therefore implements and proves the closed contract — invariant-set commitment, expectation admissibility, identity binding, declared-dimension fail-closed behaviour, contradiction/divergence handling, refusal vocabulary, determinism, non-authority — while every non-admissible invariant fails closed. No predicate may be invented to change this, no caller expectation may be accepted as authority, and no placeholder predicate from M12.1's `TargetStateEvaluator` may be promoted (§7, §16).

Admitting additional invariants requires a separately reviewed extension that gives them a digest-bound expectation source **through a reviewed typed field** — either a typed expectation surface on the M12.1 target-state contract, or a separately reviewed digest-bound semantic-input contract. The v1 resolved-source-task limb cannot serve as that source for free-form data: digest-binding a caller-authored parameter changes its tamper-evidence, not its authorship or its typing (§8.0). That extension is an **upstream contract change and is out of scope for M12.5 v1** (§26). In every case the commitment must live outside the verification request: v1 has no declared-input channel (§8.0).

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

**Reachability note (v1).** Outcomes 9.1 and 9.3 require a semantically satisfied domain; under the §8.0.1 v1 coverage limitation no non-render invariant is admissible, so v1 reaches neither of them. For a non-render semantic task the semantic domain stays `UNKNOWN` → fail closed. For a render-bearing task the render half is refused as well: whenever a required render identity dimension is `NOT_ESTABLISHED` (§17 — the v1 condition for every task that declares a sequence/asset identity, and for any render-bearing task without reviewed catalog provenance), the render requirement fails closed and the render domain is not independently valid. V1 therefore reaches outcome 9.2 **only when task-relative render identity is resolved and the render requirement is not refused**; otherwise the render outcome is the refusal classification (§17, §11). Outcome 9.2, when reached, is an **evidence-level** identification of M5 render evidence and is **not** a task-relative render verification: it must never be emitted, or read, as "this render satisfies this task" while any declared render identity dimension is unresolved (§9.3, §10.1, §25). The outcome classes are normative contract surface, not a v1 claim.

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

This outcome is reachable only when the render requirement is not refused. If any declared render identity dimension is `NOT_ESTABLISHED` (§17), the render requirement fails closed and this outcome must **not** be emitted for that task: the raw M5 evidence may remain identifiable as evidence, but it is not this task's render verification (§9.3, §10.1, §25).

Result:

```
RENDER_EVIDENCE_VERIFIED
SEMANTIC_TARGET_NOT_SATISFIED
OVERALL_TASK_COMPLETION = NOT_ESTABLISHED
```

### 9.3 Both independently verified

Only when both required evidence domains are independently valid may M12.5 report the semantic task as satisfied.

**When a render domain is independently valid (normative).** For a render-bearing task, the render domain counts as independently valid only when all of the following hold:

```text
every declared render identity dimension is decided (ENFORCED, §17)
AND every required comparison succeeded
AND no declared identity dimension remains undecided / NOT_ESTABLISHED
AND the render evidence is admissible under §17's consumption rule
```

A declared identity dimension that is undecided (`NOT_ESTABLISHED`) **never** counts as a valid render domain: it fails the render requirement closed, and the composition rule above must not fire. `NOT DECIDED` is not a third acceptable state — the only states are `ENFORCED`, `NOT_ESTABLISHED` (fail closed) and `NOT_APPLICABLE` (positively established absence, §17).

**Task-relative render verification vs raw M5 evidence (normative).** When a required render identity dimension is `NOT_ESTABLISHED` (or any declared dimension fails), then for that task:

```text
render requirement                       = NOT SATISFIED
task-relative render-domain verification  = refusal / non-success
render domain                             = NOT independently valid
§9.3 composition                          = MUST NOT count it
```

Raw M5 evidence that was obtained through the authoritative path may still be identified as *evidence* (its job/attempt/evidence identity and `evidence_trust_basis.render_evidence = DURABLE_RECORD_BACKED`, §10.4), because that identification describes how the evidence was obtained; it is **evidence-level only**. It must never be presented, labelled, or read as task-relative render verification — i.e. as "this render satisfies this mission/task" — while any declared render identity dimension is unresolved. The two must remain distinguishable in the result (§10.1, §10.4, §25).

For render-bearing verification, the phrase **verified render evidence** is normative and does not mean an `UnrealEvidence(verified=True)` instance, a snapshot carrying `"verified": true`, a transport-success flag, or any other caller-controlled boolean. Such a value is never sufficient authority. It also requires §17's declared-dimension rule: render evidence belonging to a different twin, carrying a different observed `config_digest`, presenting an unestablished request-digest correspondence, or failing a declared sequence/asset correspondence is not this task's verified render evidence, and where no reviewed typed binding decides a declared dimension the render requirement fails closed (`RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`, §11) rather than being satisfied by a merely valid render (§17, §25).

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

**Render-state rule (normative).** `VERIFIED` may be emitted only when every declared render identity dimension is decided (`ENFORCED`) and every required comparison succeeded. When the render requirement fails closed for any reason — including any declared dimension that is `NOT_ESTABLISHED` (§17) — the render state MUST be a non-success value (`NOT_VERIFIED`, or an explicit refusal class frozen at implementation review) and `VERIFIED` MUST NOT be emitted. Raw M5 evidence obtained through the authoritative path may still be carried in the evidence fields (`render_job_identity`, `render_attempt_identity`, `render_evidence_identity`, `evidence_trust_basis.render_evidence = DURABLE_RECORD_BACKED`), but that carriage is evidence-level and MUST NOT be read as task-relative render verification (§9.3, §10.4, §25).

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
- invalid extraction payload (`INVALID_OBSERVATION`);
- extraction contract revision mismatch;
- observation scope mismatch;
- missing requested entity;
- conflicting duplicate observation (the same required requirement with unequal canonical-state digests; repeated identical observation identities are NOT a failure — §7);
- observation identity mismatch (`IDENTITY_MISMATCH`);
- observation identity not transport-rooted (a copied/untrusted identity claim disagreeing with the transport-derived value — §5.3; `OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED`);
- observation scope divergence (two observations claiming one requirement with different scope identities — §5.5; `OBSERVATION_SCOPE_DIVERGENCE`);
- observation not bound to any required requirement while presented as required (§5.4);
- canonical digest mismatch;
- unsupported invariant;
- `EXPECTED_VALUE_UNAVAILABLE` — an invariant registered without an authoritative expected-value source, or an expected value that is unavailable / not derivable by its declared binding mechanism (§7.2, §8.0, §8.0.1). This is the single refusal classification for both the absent-source and the unavailable-value case; no second synonym is defined, and every control that requires a specific expectation-source classification requires exactly this token;
- caller-supplied expectation present for any invariant (§8.0);
- expectation whose only source is a free-form or caller-authored field (including committed catalog `metadata.parameters`), or a live mutable registry value rather than the reviewed code-level canonical value (§8.0 limb 2, §8.0.1);
- registry expectation sourced from a caller-authored snapshot (for example `metadata.fragments`) rather than the reviewed code-level canonical registry value bound by its reviewed constant digest, or an existing caller snapshot that diverges from that canonical value (the divergence check is mandatory — `FRAGMENT_EXPECTATION_SOURCE_NOT_CANONICAL`, §8.0 limb 2, §8.0.1);
- render identity dimension ambiguous or unrecognized — the verifier cannot establish that the dimension is definitely absent, or a render-bearing resolved source task lacks an independently verified catalog resolution (the dimension is `NOT_ESTABLISHED`, never `NOT_APPLICABLE` — §17);
- render-bearing catalog entry without a reviewed per-entry identity-class assignment (an unassigned render-bearing entry is `NOT_ESTABLISHED` and fails closed, and must never default to `NOT_APPLICABLE` — §17);
- catalog-provenance claim that cannot be independently verified against the reviewed catalog definition — caller-presented `catalog_entry`/`catalog_version`, a verbatim copy of legitimate values, a parameter set that does not equal the entry's reviewed closed set, or content that is byte-identical to the reviewed definition's output with a matching canonical JSON/digest (`content-level consistency ≠ verified catalog resolution`; the dimension is `NOT_ESTABLISHED`, never `NOT_APPLICABLE` — §17);
- content-level consistency or a matching source-content/plan digest presented as proof of catalog resolution or resolver provenance — a digest proves consistency/tamper-evidence of the supplied content only (§17, §25);
- value carried in a parameter that the per-entry classification records as NOT a render identity dimension (for example `artifact_ref`) used as a declared render identity, as satisfaction evidence, or to establish that another task's identity dimension is absent — refused (§17);
- render requirement not satisfied because a render identity dimension is undecided — no reviewed typed binding establishes the correspondence (`RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`, §17);
- request-digest correspondence unestablished (`request_digest_agreement` = `NOT_ESTABLISHED`) — no authority validates a request digest and the M12.1 task contract declares no request-digest counterpart, so it may never be recorded `ENFORCED` and the unenforced state is never presented as a detected mismatch (§17);
- render state emitted as a success value, or raw M5 evidence presented as task-relative render verification, while a declared render identity dimension is unresolved — refused (§9.3, §10.1);
- render requirement not satisfied because a declared render identity dimension was decided and the values demonstrably differ (`RENDER_TASK_CORRESPONDENCE_MISMATCH`, §17);
- missing invariant input;
- contradictory observation;
- stale observation, where staleness is established by a detectable identity, scope, or request-correlation disagreement (a consistently relabelled stale payload is NOT detectable — §5.3);
- empty required-invariant set;
- incomplete required-invariant set (source declares invariants the plan does not carry — §7.1; `INCOMPLETE_REQUIRED_INVARIANT_SET`);
- extra plan verification requirement (plan requires verification that the resolved source task's declared target does not — §7.1; `EXTRA_PLAN_VERIFICATION_REQUIREMENT`);
- plan render classification mismatch (plan `render_plan` disagrees with the digest-bound source classification — §7.3; `PLAN_RENDER_CLASSIFICATION_MISMATCH`);
- render evidence missing when required (`RENDER_EVIDENCE_MISSING`);
- render evidence not independently verified;
- render evidence identity not derived from the authoritative M5 verification path (§17);
- render-job identity mismatch;
- render-attempt identity mismatch;
- verifier input contains forbidden authority material;
- caller-supplied producer-owned result structure (`observation_identity`, `render_evidence_identity`, `evidence_trust_basis`, `provenance`) — rejected structurally;
- malformed provenance;
- unsupported future State Extraction fields.

**Token convention (normative).** Every refusal classification a control, criterion or gate requires MUST be named in this list. Outcome vocabulary (`SATISFIED`, `NOT_SATISFIED`, `UNKNOWN`, `MISSING`, `INVALID`), the render-state members (`NOT_REQUIRED`, `RENDER_EVIDENCE_REQUIRED`, `NOT_VERIFIED`, `VERIFIED`, `INVALID`), the render identity dimension states (`ENFORCED`, `NOT_ESTABLISHED`, `NOT_APPLICABLE`) and the evidence trust basis members are defined in §7.2, §10, §10.1, §10.4 and §17; they are states, not refusal classes, and a control that asserts one of them asserts state semantics (§17 for dimension states). Control statuses (`PROVEN` / `NOT PROVEN`) are a separate **coverage** vocabulary: they record whether a control's own mechanism was exhibited, they are not refusal classes and not result states, and `NOT PROVEN` never satisfies an acceptance criterion and licenses no positive outcome (§20 Phase A, §21). The two expectation-source controls and the registration-refusal class both use the single token `EXPECTED_VALUE_UNAVAILABLE` defined above.

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

**Render job ↔ task agreement (normative).** A verified render result is admissible for a render-bearing semantic task only when the agreement of **every declared render identity dimension** is established by the relevant reviewed authority: record↔evidence correspondence where the render authority enforces it, and agreement with the digest-bound source task where a task-side counterpart exists. Not every dimension has a task-side counterpart — `config_digest_agreement` is a record↔evidence correspondence (the task contract declares no digest) — and a dimension with neither a task-side counterpart nor an authority-enforced correspondence must be `NOT_ESTABLISHED` and fail the render requirement closed. Every component below is derived from existing authoritative records — the M12.1/M12.3 source-payload fields and `AtlasRenderJobRecord` (`.canonical_digital_twin_id`, `.sequence_asset_path`, `.config_digest`, `.atlas_job_id`, `.attempt_ordinal`; `.request_digest` is carried on the durable record but is **not** validated by the render authority). No new authority, field, or record is introduced, and M12.5 must not reconstruct any of these values itself:

```text
twin_agreement        AtlasRenderJobRecord.canonical_digital_twin_id
                          == source_task.digital_twin_id
                          == plan.digital_twin_id                    ENFORCED
config_digest_agreement
                      the observed state's `config_digest` is a mandatory M5 identity
                      field and is compared to AtlasRenderJobRecord.config_digest;
                      a mismatch is rejected by the authority — verified against the
                      render-evidence verifier's mandatory-key/equality checks.
                                                                     ENFORCED
request_digest_agreement
                      the render authority validates NO request digest (the verifier
                      never reads `request_digest`) and the M12.1 task contract
                      declares no request-digest counterpart, so no positive
                      request-digest correspondence exists in v1. This dimension may
                      never be recorded `ENFORCED`, and its unenforced state is never
                      reported as a detected mismatch: absence of enforcement is not
                      detection.                                     NOT_ESTABLISHED
sequence_agreement    AtlasRenderJobRecord.sequence_asset_path vs the task's declared
                      sequence/asset identity. A declared dimension with no reviewed
                      typed binding that decides the correspondence is NOT_ESTABLISHED
                      and fails the render requirement closed.       NOT_ESTABLISHED
```

**v1 render-requirement consequence (normative).** With `config_digest_agreement` proven and both `request_digest_agreement` and `sequence_agreement` `NOT_ESTABLISHED`, the render requirement is **not satisfied** and `render_state` must not be `VERIFIED` (§10.1) — for every render-bearing task. A digest read from the durable record is never evidence of a correspondence the authority does not check: the absence of request-digest enforcement may never be represented as proof of correspondence, and no render-state success may rest on `request_digest_agreement`. Establishing that correspondence requires an upstream reviewed request-digest binding (§26 Q11); M12.5 must not invent one.

**Reviewed recognition surface (normative).** A sequence/asset identity dimension is *recognized* only through the following reviewed surfaces, fixed at implementation review alongside the invariant registry (§8):

```text
S1  a reviewed typed target-state field on the M12.1 task contract
S2  a reviewed catalog parameter class: the exact parameter contract of the resolved
    M12.2 catalog entry — its `required_parameters` + `parameter_kinds`, which the
    catalog enforces as a CLOSED set (unexpected parameters are rejected; a
    declared sequence parameter must be a non-empty string), restricted to those
    reviewed parameter classes that denote a sequence/asset identity. The
    assignment is PER ENTRY and MUST be explicit for every render-bearing catalog
    entry (per-entry reviewed identity classification below); a field is never
    classified as an identity dimension merely because its name looks
    asset-shaped, and never classified as absent merely because no canonical key
    is present
S3  an explicitly reviewed sequence/asset identity field enumerated as such in the
    reviewed recognizer surface
```

**Recognition rule — three states (normative).** The verifier must classify a render identity dimension into exactly one of:

```text
DEFINITELY DECLARED       a reviewed surface (S1/S2/S3) positively identifies the
                          identity dimension
                              -> evaluate it (enforcement below)

DEFINITELY NOT DECLARED   the reviewed contract positively establishes that the
                          resolved source task does not declare this identity
                          dimension. For a render-bearing task ALL FOUR conditions
                          must hold:
                            (1) the task went through a reviewed catalog entry for
                                its class;
                            (2) that entry/version/class identity is INDEPENDENTLY
                                VERIFIED against the reviewed catalog DEFINITION
                                (a caller-presented `catalog_entry`/
                                `catalog_version` claim, or the same values copied
                                by hand, is a CLAIM and is never verification);
                            (3) the declared parameter set exactly equals that
                                entry's reviewed closed parameter set; and
                            (4) no other committed content could plausibly carry
                                the identity (monotonic safety rule below)
                              -> `NOT_APPLICABLE`

AMBIGUOUS / UNRECOGNIZED  the verifier cannot establish that the identity dimension
                          is definitely absent
                              -> `NOT_ESTABLISHED`
                              -> `RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`
                                 (or `RENDER_TASK_CORRESPONDENCE_MISMATCH` where
                                 the correspondence is decidable and fails)
                              -> fail closed
```

The third state MUST NEVER become `NOT_APPLICABLE`.

**Reviewed resolution for render-bearing tasks (normative).** For a render-bearing task, complete render identity resolution requires an independently verified catalog resolution or another reviewed typed contract that establishes the complete render identity surface. A render-bearing resolved source task that lacks that provenance/contract surface is classified `NOT_ESTABLISHED` and the render requirement fails closed. It must never be inferred that "not catalog-resolved" implies "no sequence identity exists": that inference is unsafe and is prohibited.

**Catalog provenance must be verified, not read (normative).** A catalog-provenance **claim** is any caller-presented `catalog_entry`/`catalog_version` metadata on the task, including the exact strings copied from a legitimate catalog entry. A claim is **never** provenance and is never self-authenticating: `metadata` is caller-authorable M12.1 content (§8.0), and a faithful copy of legitimate values is byte-identical to a genuinely resolved task. **Verified catalog resolution** requires the verifier to match the claim against the **reviewed catalog definition** — entry name, that entry's task class, the catalog version, its `required_parameters` and `parameter_kinds`, and exact equality of the task's declared parameter set with that entry's closed set — where all of those values are read from the reviewed catalog code and never from the task's metadata. Consequences, normatively: `provenance claim ≠ verified catalog resolution`; a claim, a copied claim, or a parameter set that differs from the reviewed closed set can never produce `NOT_APPLICABLE`; and in v1 the verifier cannot distinguish genuine resolver provenance from a faithful caller copy, because no reviewed resolution binding exists (§26 Q10). The verifier may therefore establish *consistency with a reviewed entry*, but it may not conclude *verified resolution* — so the positive-absence branch stays closed for render-bearing tasks in v1, and the dimension is `NOT_ESTABLISHED` and fails closed.

**Content-level consistency is necessary and NEVER sufficient (normative).** A caller can reproduce every content-level property the reviewed catalog definition permits: the correct entry name, the correct catalog version, the correct task class, the correct parameter names and kinds, the exact reviewed closed parameter set, a byte-identical canonical JSON serialization, the same source-content digest, and therefore the same plan identity. None of it establishes genuine catalog resolution, because `metadata` is caller-authorable M12.1 content (§8.0) and the reviewed resolver's output is reproducible by hand. Therefore:

```text
caller content matching the reviewed catalog definition
    ≠
verified catalog resolution

source/plan digest consistency
    ≠
resolver provenance / catalog authenticity
```

A source-content or plan digest proves consistency and tamper-evidence of the supplied content; it does **not** prove that the Atlas catalog resolver actually produced that content. No verifier may treat a content-level match — however exact — as resolution.

**Positive-absence boundary (normative).** For a resolved source task to be classified `DEFINITELY NOT DECLARED` — and therefore, for a render-bearing task, to reach `NOT_APPLICABLE` — the verifier MUST hold an actual **reviewed resolution binding** of the kind described by §26 Q10: a resolver-issued commitment carried on the reviewed catalog path and verifiable from reviewed code alone, which a caller cannot reproduce. Content-level consistency, a byte-identical canonical payload, and a matching digest are **never** substitutes for that binding. Until the §26 Q10 binding exists, verified catalog resolution is unavailable, so the dimension is `NOT_ESTABLISHED` → `RENDER_TASK_CORRESPONDENCE_NOT_DECIDED` → the render requirement fails closed. §26 Q10 is therefore not documentation convenience but the upstream dependency that must exist before the positive-absence branch can be permitted at all; no Q10 implementation is part of M12.5 v1.

**Per-entry reviewed identity classification (normative).** Every render-bearing catalog entry MUST have an explicit reviewed identity-class assignment. An entry that is render-bearing but unassigned MUST be treated as `NOT_ESTABLISHED` and MUST fail closed; it MUST NOT default to `NOT_APPLICABLE`. The implementation review may add entries, but no unreviewed entry may silently inherit a classification. Render-bearingness is enumerated by `is_render_task_class(...)`; at the current catalog revision the complete, verified classification of every catalog entry is:

| catalog entry (class) | reviewed closed parameter set | render identity dimension(s) | explicitly NOT a render identity dimension | can an independently verified resolution establish definite absence of the sequence/asset dimension? | v1 outcome |
|---|---|---|---|---|---|
| `unreal.render-execute` (`render-execute`) | `{twin_id: string, sequence_name: string}` | `twin_id` (twin identity, enforced against `canonical_digital_twin_id`); `sequence_name` (sequence/asset identity dimension) | — | **NO** — the entry declares the dimension, so absence is contradicted | DEFINITELY DECLARED → evaluate → no reviewed typed task↔record binding exists → `NOT_ESTABLISHED` → `RENDER_TASK_CORRESPONDENCE_NOT_DECIDED` → render requirement fails closed |
| `unreal.artifact-validate` (`artifact-validate`) | `{twin_id: string, artifact_ref: string}` | `twin_id` (twin identity, enforced) | `artifact_ref` — an asset-shaped, **caller-authored** `string` parameter (the entry's objective is "wrap an existing artifact validation/verification step"). It is **not** a render identity dimension, on this verified basis: the render/job authority record carries `sequence_asset_path` as its sequence-asset identity **and** other output/artifact/receipt-related references — `output_parent_directory`, `output_directory`, `expected_output_spec`, `manifest_reference`, `receipt_reference`; M5's render-evidence verification (`verify_render_job_evidence`) validates twin identity, the observed `config_digest` and output topology, and does **not** validate `manifest_reference`, `receipt_reference` or any request digest; and **no reviewed typed correspondence exists between `artifact_ref` and any render-authority field** (nor to the separate `ProductionArtifactManifest` artifact-identity surface). That surface **is** downstream-linked to the render path: it is constructed by `ProductionArtifactManifest.from_unreal_render_receipt(...)` from an `UnrealRenderReceipt` plus M5-verified `UnrealEvidence`, it requires verified render evidence, and it binds its `artifact_path` to the evidence's observed outputs (with lineage tests rejecting artifact-path and evidence substitution). It is however **not** linked to `AtlasRenderJobRecord`, is **not** consulted by M5's render-evidence verification, and carries **no** reviewed typed correspondence to `artifact_ref`; the record's optional `manifest_reference` is populated by no planning module today. Neither `artifact_ref → ProductionArtifactManifest` nor `manifest_reference → artifact_ref` is a reviewed binding, and the manifest must never be treated as an M12.5 expectation authority. M12.5 MUST NOT invent such a correspondence; without a reviewed typed binding `artifact_ref` can never become a positive render identity expectation, and the value stays caller-authored content — inadmissible as an expectation and as positive identity, handled by §8.0.1 → `UNKNOWN` → fail closed. **Future-proofing:** because `NOT_APPLICABLE` is the only acceptance-side render identity state, if a reviewed artifact/manifest correspondence contract is introduced upstream this classification MUST be revisited under that reviewed contract; no artifact/manifest binding is part of v1, and a reviewer MUST re-verify the render-authority surface (the fields above and M5's validation surface) before freezing this classification | **by classification yes, in v1 not reachable** — the reviewed assignment establishes that the entry declares no sequence/asset identity dimension, but the positive-absence branch additionally requires independently verified catalog resolution, which v1 cannot authenticate (§26 Q10) | `NOT_ESTABLISHED` in v1 → render requirement fails closed; the `artifact_ref` value remains a caller-authored semantic/artifact assertion, NOT admissible as a render dimension, handled by §8.0.1 → `UNKNOWN` → fail closed |
| `unreal.scene-prepare`, `unreal.environment-configure`, `unreal.camera-configure`, `unreal.lighting-configure`, `unreal.sequence-configure` | not render-bearing — `is_render_task_class(...)` is false for these classes (the render classification, not the fragment set, is the criterion: `unreal.artifact-validate` is render-bearing although its fragment set contains only `scene_setup`) | — | — | not applicable: a non-render task has no render requirement, so the render sequence/asset dimension is not evaluated. `unreal.sequence-configure` does carry `sequence_name`, but that is a **semantic** declaration handled by §8.0.1 (NOT ADMISSIBLE → `UNKNOWN`, fail closed), never a render identity dimension | no render dimension |
| any future or unknown render-bearing class | — | — | — | — | **UNASSIGNED** → `NOT_ESTABLISHED` → fail closed (never `NOT_APPLICABLE`) |

Two consequences of the table are normative. First, a parameter that the reviewed classification records as NOT a render identity dimension is never compared against render records, never counts as a declared render identity, and never supplies evidence that any other task's identity dimension is absent; its value stays caller-authored content whose assertion is handled by §8.0.1 and fails closed in v1. Second, the classification decides only **which** dimension is evaluated — it never decides the outcome, which the three-state rule, the reviewed-resolution requirement and the monotonic default continue to govern.

**Monotonic safety rule (normative).** Any committed content that could plausibly carry a sequence/asset identity but lies outside the reviewed recognition surface MUST be treated as a declared-but-unresolved identity dimension and MUST fail closed. The recognizer may over-include and cause refusal; it may not under-include and cause acceptance. More uncertainty must always mean more refusal, never more acceptance: a caller must never gain acceptance by making an identity less recognizable — for example by renaming a canonical field to a non-canonical key, by placing the value under an unrecognized key, or by supplying a task that never passed through the reviewed catalog.

**Expectation enforcement (normative).** The render requirement is satisfied only when the correspondence to `AtlasRenderJobRecord.sequence_asset_path` is authoritatively decided by a **reviewed typed binding** and the comparison succeeds:

```text
identity dimension DEFINITELY DECLARED or AMBIGUOUS/UNRECOGNIZED
  + no reviewed typed binding decides the correspondence
      -> render requirement NOT SATISFIED -> fail closed
         (`RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`, §11)

identity dimension DEFINITELY DECLARED
  + the correspondence is decidable and the values demonstrably differ
      -> render requirement NOT SATISFIED -> fail closed
         (`RENDER_TASK_CORRESPONDENCE_MISMATCH`, §11)
```

**Trigger vs expectation (normative).** A free-form/caller-authored identity-like field — including a catalog parameter such as `sequence_name` — is a **refusal trigger only**. It may move the result toward refusal and must never be used as an authoritative expected sequence, a positive sequence identity, satisfaction evidence, or proof of correspondence. Correspondingly, a caller-authored string that happens to equal `AtlasRenderJobRecord.sequence_asset_path` does **not** establish correspondence: a matching caller-authored value must never manufacture `ENFORCED`, and without a reviewed typed binding the outcome is `RENDER_TASK_CORRESPONDENCE_NOT_DECIDED` even when the strings are identical. `same caller string ≠ authoritative correspondence`.

A value carried by a parameter that the per-entry reviewed classification records as **NOT** a render identity dimension (for example `artifact_ref`) is likewise never an expectation, never a positive identity, never satisfaction evidence, and is never compared against render records; it may only move the outcome toward refusal, and its semantic assertion is handled by §8.0.1 and fails closed.

A declared identity dimension may **never** be classified `NOT_APPLICABLE`, and an undecided declared dimension may never be treated as satisfied, as merely "unproven but acceptable", or as a valid render domain (§9.3). Each dimension must be recorded, in the result and in the live-gate record, as exactly one of:

```text
ENFORCED         the reviewed typed binding exists and the comparison succeeded
NOT_ESTABLISHED  DEFINITELY DECLARED or AMBIGUOUS/UNRECOGNIZED, but no reviewed
                 typed binding decides it -> fail closed (or the correspondence was
                 decided and the comparison failed)
NOT_APPLICABLE   DEFINITELY NOT DECLARED: the reviewed contract positively
                 establishes that the resolved source task declares no such identity
                 dimension. For a render-bearing task this requires an entry whose
                 reviewed per-entry classification declares no sequence/asset
                 identity dimension, AND independently verified catalog resolution,
                 AND exact equality with that entry's closed parameter set, AND no
                 other plausibly-identity committed content (§17 recognition rule).
                 NOT reachable in v1 for render-bearing tasks: verified resolution is
                 not establishable (§26 Q10), so the state is not emitted. This
                 state stays reachable for domains whose absence is positively
                 established by a reviewed contract elsewhere (for example no render
                 requirement at all, or a non-render evidence trust basis)
```

`NOT_APPLICABLE` therefore requires positive reviewed evidence of absence. Absence of evidence is `NOT_ESTABLISHED`, never `NOT_APPLICABLE`.

**Vocabulary namespace (normative).** These dimension states are a distinct vocabulary from §10.4's evidence-trust-basis members (`DURABLE_RECORD_BACKED`, `NOT_ESTABLISHED`, `NOT_APPLICABLE`) and from `overall_state`'s `NOT_ESTABLISHED`: a dimension state describes the status of one declared render identity dimension, never the strength of the evidence and never the overall completion state.

An authoritative M5-verified render that belongs to a **different twin**, carries a **different config digest** (`config_digest_agreement` is authority-enforced), presents an **unestablished request-digest correspondence** (`request_digest_agreement` is `NOT_ESTABLISHED` — an unestablished dimension is never a detected mismatch and never a proven correspondence), or does not correspond on a **declared sequence/asset identity**, is **never** evidence for this task's render requirement: the render requirement fails closed (`RENDER_EVIDENCE_MISSING`, `RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`, or `RENDER_TASK_CORRESPONDENCE_MISMATCH`, §11) instead of being satisfied by a merely valid render. No binding may be invented to make an undecided dimension decidable, and no M5 check may be recreated. M5 remains the sole render verifier — this rule adds identity agreement only, and it does not make M12.5 a second render verifier.

**v1 consequence (recording obligation, never a pass).** There is today no reviewed typed sequence/asset identity field on the M12.1 target-state contract (`UnrealTargetStateSpec` carries only `description`, `invariant_names`, `expects_render`), so for **every render-bearing task** the sequence/asset identity dimension is `NOT_ESTABLISHED` and the render requirement fails closed:

- where a reviewed typed/closed identity surface establishes a declared sequence/asset dimension — every catalog `unreal.render-execute` task, which declares `sequence_name`, and any other render-bearing task whose recognized surface declares such an identity — the dimension must be resolved or the render requirement fails closed, and no reviewed typed task↔record binding exists, so it fails closed;
- where the reviewed per-entry classification establishes that the entry declares no such dimension (`unreal.artifact-validate` / `artifact_ref`), `NOT_APPLICABLE` still requires independently verified catalog resolution, which v1 cannot authenticate (§26 Q10), so the dimension is `NOT_ESTABLISHED` and the render requirement fails closed;
- where a render-bearing entry has no reviewed assignment, `NOT_ESTABLISHED` (never `NOT_APPLICABLE`).

Positive task-relative render verification is therefore unavailable in v1 wherever the required task↔render identity binding does not exist — in v1 that is every render-bearing task, whatever its committed content happens to look like. That is a v1 capability limitation: it must be recorded as such, and the render domain must not be reported as independently valid for such a task (§9.3, §25). Restoring positive render-state coverage requires the **upstream contract changes** named in §26 Q9 (a reviewed typed sequence/asset identity on the M12.1 target-state contract, carried into the render-request construction path) and §26 Q10 (a reviewed resolution binding); M12.5 must not invent either.

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

Mandatory controls added by this revision (§7.1, §7.2, §7.3, §8.0, §8.0.1, §5.3, §5.5):

- **incomplete requirement set** — source declares `[A, B]`, plan contributes only `[A]`: MUST NOT become `SATISFIED` (`INCOMPLETE_REQUIRED_INVARIANT_SET`);
- **extra requirement** — plan contributes a requirement the source does not declare: MUST fail closed (`EXTRA_PLAN_VERIFICATION_REQUIREMENT`);
- **caller expectation vs digest-bound expectation (differential control — `NOT PROVEN` in v1)** — the request carries an expectation that disagrees with the digest-bound expected value: the caller value MUST be ignored and MUST NOT be able to produce `SATISFIED`. This control requires all four of: (1) an actual reviewed digest-bound expected value that exists; (2) a comparison of the caller-supplied expectation against that reviewed source; (3) an observable specific refusal when the caller expectation is inadmissible; and (4) an explicit live-gate record of whether that mechanism was exhibited. In v1 no admissible semantic invariant exists (§8.0.1), so no digest-bound expected value can exist and the control's differential mechanism cannot be exercised: the control MUST be recorded as **NOT PROVEN**, never as passing. An ambient `EXPECTED_VALUE_UNAVAILABLE` refusal is NOT evidence that this differential control executed (§21, §24);
- **no authoritative expectation** — an invariant with no authoritative expected-value source: MUST fail closed with the **specific** classification `EXPECTED_VALUE_UNAVAILABLE` (§7.2, §8.0), never satisfied from a default or a caller value;
- **caller-authored free-form source parameter** — a free-form parameter carried in the resolved source task (`metadata` / `parameters`) and digest-bound into the source-content commitment: MUST NOT become an authoritative expected value merely because it is committed. The control passes only when the refusal is classified `EXPECTED_VALUE_UNAVAILABLE` for the free-form expectation itself (§8.0, §8.0.1);
- **specific-code requirement (no green for the wrong reason)** — for the **three** expectation-source controls above, a refusal produced *solely* by the §8.0.1 v1 coverage limitation (a generic `UNKNOWN` because no semantic invariant is admissible at all) does **not** satisfy the control. The live-gate record must capture the specific refusal classification, and a control that cannot exhibit its own mechanism is recorded as **NOT PROVEN** rather than as passing. Two normative distinctions: `ambient v1 refusal ≠ control mechanism exhibited`, and `no admissible digest-bound expectation source → the differential mechanism cannot be exercised → control status = NOT PROVEN`. `NOT PROVEN` is informational about control coverage only — it never satisfies an acceptance criterion, never counts as a pass, and never licenses a positive outcome;
- **control-status truthfulness (normative)** — every control in this phase (and in Phases C and D) is recorded as proven only where its mechanism was genuinely exhibited. A control whose differential signal requires an upstream capability that does not exist in v1 — for example the caller-expectation differential control above, and the registry-mutation / `metadata.fragments` controls where the canonical binder cannot be exercised offline — is recorded as `NOT PROVEN`; ambient fail-closed behaviour alone is never evidence that a control's mechanism executed. This rule does not require every control to be executable offline, and no artificial coverage may be manufactured to make a control appear proven;
- **live registry mutation after commitment** — mutating live M12.2 registry state after the source task and plan were committed (including in-place mutation of a mutable field's contents, not only `object.__setattr__`): MUST NOT alter any verification expectation or the verification result (§8.0 limb 2);
- **caller-authored `metadata.fragments` snapshot** — a resolved source task whose `metadata.fragments` content is caller-authored or rewritten and digest-bound into the source-content commitment: MUST NOT become an authoritative expectation. A registry-derived expectation must come only from the reviewed code-level canonical registry value bound by its reviewed constant digest, and the **mandatory** divergence check must fail closed on any difference between an existing caller snapshot and that canonical value (`FRAGMENT_EXPECTATION_SOURCE_NOT_CANONICAL`, §8.0 limb 2, §8.0.1);
- **declared sequence/asset identity with no decidable correspondence** — a render-bearing source task that declares a sequence/asset identity (for example a catalog `sequence_name` parameter) whose correspondence to the job record's `sequence_asset_path` no reviewed typed binding decides: MUST NOT satisfy the render requirement → fail closed (`RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`, §17);
- **non-canonical/unrecognized identity key** — a render-bearing task whose sequence/asset identity is placed under a non-canonical or unrecognized key, with no reviewed provenance: MUST be `NOT_ESTABLISHED` and fail closed (`RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`). It MUST NOT be classified `NOT_APPLICABLE`, MUST NOT be recorded as `ENFORCED`, and MUST NOT count as a valid render domain (§17);
- **renamed canonical field** — a canonical sequence field renamed to a non-canonical key: renaming MUST NOT make the identity dimension disappear; the outcome MUST be `NOT_ESTABLISHED` / fail closed (§17 recognition rule, monotonic safety);
- **non-catalog render-bearing task** — a render-bearing resolved source task with no reviewed catalog-resolution proof and no other reviewed typed render-identity contract: MUST be `NOT_ESTABLISHED` and fail closed. It MUST NOT be inferred that absent catalog provenance means absent identity, and the absence of provenance MUST NOT produce `NOT_APPLICABLE` (§17);
- **unassigned render-bearing catalog entry** — a render-bearing class/entry with no reviewed per-entry identity-class assignment: MUST be `NOT_ESTABLISHED` and fail closed. It MUST NOT default to `NOT_APPLICABLE` (§17);
- **caller-supplied catalog provenance** — a hand-built render-bearing task carrying caller-authored `catalog_entry` and/or `catalog_version` metadata without independently verified catalog resolution: MUST be `NOT_ESTABLISHED` (`RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`), never `NOT_APPLICABLE` (§17);
- **copied legitimate provenance** — the same task carrying `catalog_entry`/`catalog_version`/class values copied verbatim from a legitimate catalog entry: MUST still be `NOT_ESTABLISHED`. Exact strings copied by a caller MUST NOT manufacture verified provenance, and the control's record MUST state that v1 cannot distinguish a faithful copy from genuine resolution (§26 Q10);
- **byte-identical positive-absence attack** — a hand-built render-bearing task carrying the exact real `catalog_entry`, `catalog_version` and task class, the exact reviewed parameter set and kinds, byte-identical canonical content, and the same source-content digest and plan identity as the catalog-resolved equivalent, with no actual reviewed resolution binding: MUST be `NOT_ESTABLISHED` (`RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`) and MUST NOT be classified `NOT_APPLICABLE`. The control's record MUST state that content-level consistency — including a matching canonical JSON and digest — is necessary and never sufficient for verified catalog resolution (§17, §26 Q10);
- **digest-as-provenance attack** — a source-content or plan digest presented as evidence that the reviewed catalog resolver produced the task: MUST be refused as provenance evidence. A digest proves consistency and tamper-evidence of the supplied content only; resolver provenance requires the §26 Q10 binding (§17, §25);
- **provenance with a mismatched parameter set** — a claim naming a reviewed render-bearing entry while the declared parameter set differs from that entry's reviewed closed set: MUST fail closed (§17);
- **non-identity-classified parameter** — a value carried in a parameter the per-entry classification records as NOT a render identity dimension (for example `artifact_ref`) presented as a declared render identity, as satisfaction evidence, or as evidence that another task's identity dimension is absent: MUST be refused, and its semantic assertion MUST fail closed via §8.0.1 (§17);
- **matching caller-authored value** — a caller-authored sequence value exactly equal to `AtlasRenderJobRecord.sequence_asset_path`, with no reviewed typed binding: MUST be `RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`. A matching caller-authored string MUST NOT manufacture `ENFORCED` (`same caller string ≠ authoritative correspondence`, §17);
- **trigger vs expectation** — a caller-authored identity-like field used as a refusal trigger: MUST NOT be used as an authoritative expected sequence, a positive sequence identity, satisfaction evidence, or proof of correspondence; a trigger may only move the outcome toward refusal (§17, §8.0);
- **stale payload + relabelled envelope — NOT DETECTABLE, not a fail-closed control** — a stale canonical observation presented with a current-looking, internally consistent request/session/scope envelope is not detectable by M12.5 v1 (§5.3, §6.2). This case MUST NOT be presented as a control that proves detection or refusal; the live-gate record must state the property is unproven rather than enforced (§25). What must fail closed are the *detectable* variants, which are the controls that follow: copied identity claim, request-correlation mismatch, scope divergence, contract-revision mismatch, and conflicting duplicate observations;
- **copied identity claim** — envelope identity fields hand-copied and disagreeing with the transport-derived values: MUST fail closed (`OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED`);
- **request-correlation mismatch** — the transport response does not correlate to the Atlas-issued extraction request (disagreeing `request_id`, `operation_name`, `entity_ids`, or `schema_version`): MUST fail closed (`OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED`);
- **contract-revision mismatch** — `extraction_schema_version` not equal to the accepted revision: MUST fail closed (`INVALID_OBSERVATION` / `IDENTITY_MISMATCH`);
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
- observation whose envelope identity disagrees with the transport-derived values (including engine-version disagreement) — the *detectable* stale/misrouted variants;
- request-correlation mismatch against the Atlas-issued extraction request;
- contract-revision mismatch;
- a stale canonical observation presented with a relabelled current envelope identity — recorded as **NOT DETECTABLE** (§5.3, §6.2): the record must state that this case is not detected, and must not report it as a detected or refused case;
- conflicting observations carrying the same request identity;
- scope-divergent observations claiming the same requirement;
- an invariant whose authoritative expected value is absent or unbound;
- an invariant whose only expectation source is a committed free-form caller-authored parameter (§8.0);
- render-bearing task without verified render evidence;
- render evidence bound to wrong job/attempt identity;
- caller-constructed `UnrealEvidence(verified=True)` or equivalent snapshot presented as if it were M5+ verified evidence.

Each negative control must fail closed, with the single exception of the stale-relabelled-envelope case, which is recorded as **NOT DETECTABLE** rather than proven (§5.3, §6.2, §25).

A stale-observation/other-session control should be exercised with a second real extraction session when the live harness can provide one. If the fixture cannot safely provide a second live session, deterministic Phase-A coverage is an acceptable substitute, but the live-gate record must explicitly state that live stale-session coverage was not available rather than implying that it was proven. In either case the record must also state the §5.3 limitation: the extraction path provides no authenticated session identity, so what is proven is transport-rooted correlation and identity comparison, not authenticated anti-replay freshness. The record must state plainly that a stale payload presented with an internally consistent relabelled envelope is **not detectable** by M12.5 v1: it is an unproven property and never a passing control, and no wording in the record may imply that stale relabelling was positively detected.

The live suite should also assert that session/engine/request metadata cannot be smuggled into `canonical_state`; the frozen extractor's reserved-key refusal remains a defense at the observation boundary.

### Phase D — render-bearing composition

Only after the non-render verifier is independently clear should a separate live composition gate consume an existing verified render result.

That composition gate must not modify the M5+ verifier or recovery path.

The gate must prove §17's declared-dimension rule (twin identity and **config-digest** correspondence are `ENFORCED` today (`config_digest_agreement`: the authority rejects an observed `config_digest` that differs from the durable record) while **request-digest** correspondence and any declared sequence/asset identity are `NOT_ESTABLISHED` (`request_digest_agreement`; no authority validates a request digest), so the render requirement fails closed), must record each declared dimension's state separately (`ENFORCED` / `NOT_ESTABLISHED` / `NOT_APPLICABLE`), and must include these negative controls:

- **authoritative M5-verified render belonging to a different twin, or whose observed `config_digest` differs from the durable record** — presented as if it were this task's render result: MUST NOT satisfy this task's render requirement → fail closed (`RENDER_EVIDENCE_MISSING`). Dimension `config_digest_agreement`: this half is genuinely enforced by the authority and must be recorded as a detected refusal;
- **request-digest correspondence (dimension `request_digest_agreement`; UNPROVEN — must not be claimed as detected)** — a render presented with a request digest that differs from the durable record: the render authority validates no request digest, so M12.5 CANNOT claim this as detected or refused *on that ground*; the dimension is `NOT_ESTABLISHED` / unproven and MUST be recorded as such. This control MUST NOT be recorded as passing merely because another unresolved render dimension already causes refusal, and no wording may imply that request-digest enforcement was demonstrated (§17, §25);
- **correct twin + correct durable request/config identity + M5-verified render + wrong sequence/asset** — a declared sequence/asset dimension that demonstrably differs (where a reviewed typed binding decides the comparison): MUST NOT satisfy this task's render requirement → fail closed (`RENDER_TASK_CORRESPONDENCE_MISMATCH`, §11);
- **correct twin + ambiguous or unbound declared sequence/asset identity** — a declared sequence/asset dimension that no reviewed typed binding decides: MUST NOT satisfy this task's render requirement → fail closed (`RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`, §11). This is the v1 condition for every task that declares a sequence/asset identity, so the gate must record it as `NOT_ESTABLISHED` — never as a disclosed-but-accepted dimension, and never as `NOT_APPLICABLE` (§17);
- **genuine M5-verified render + task declares a sequence/asset identity + no reviewed task↔sequence binding** — the raw M5 evidence may remain identifiable as evidence (render job/attempt/evidence identity; `evidence_trust_basis.render_evidence = DURABLE_RECORD_BACKED`), but the task-relative render requirement MUST be refused (`RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`), the render domain MUST NOT be independently valid, `render_state` MUST NOT be `VERIFIED`, and §9.3 composition MUST be blocked (§9.3, §10.1, §17);

**Phase D determinism criterion (normative).** Determinism for a render-bearing verification means: identical immutable inputs **and** identical authoritative M5 evidence identity **and** unchanged durable artifact state as read by the M5 authority ⇒ byte-identical M12.5 result. Because the M5 authority reads durable artifacts, the live record must capture the M5 evidence identity (job identity, attempt identity, evidence identity per §17) and the artifact state that authority verified, so a later discrepancy can be attributed to changed artifacts rather than to a non-deterministic verifier. Phase A/B/C determinism — which does not depend on durable artifacts — remains strictly byte-identical for identical inputs.

---

## 21. Offline acceptance criteria

Before implementation can clear:

- target-state evaluation is deterministic;
- the required-invariant set is defined from the resolved source task and EQUALS the plan's per-step `verification_requirements` union, with both directions failing closed;
- all required invariants are evaluated;
- every evaluated invariant uses an authoritative digest-bound expected value reached through a reviewed typed contract field; a caller-supplied expectation is never used and cannot produce a pass;
- no expected value is derived from a free-form or caller-authored field, however it is committed (including catalog `metadata.parameters`);
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
- registry-derived expectations come only from the reviewed code-level canonical registry value bound by its reviewed constant digest before verification; no expectation is ever read from a caller-authorable snapshot (`metadata.fragments` or any other caller-supplied copy), and mutating live registry state after commitment cannot change the expectation or the result;
- every declared render identity dimension is decided with a successful comparison, or the render requirement fails closed; no declared dimension is recorded as valid, satisfied, or `NOT_APPLICABLE`;
- a declared render identity dimension that no reviewed typed binding decides fails the render requirement closed (`RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`), and a demonstrable mismatch fails it closed (`RENDER_TASK_CORRESPONDENCE_MISMATCH`);
- render composition records each declared render identity dimension as `ENFORCED` / `NOT_ESTABLISHED` / `NOT_APPLICABLE`, and never claims identity binding is proven while a declared dimension is `NOT_ESTABLISHED`;
- every control's status is recorded truthfully: proven only where its differential mechanism was genuinely exhibited, and `NOT PROVEN` where the required upstream capability (for example an admissible digest-bound expectation source) does not exist; `NOT PROVEN` is never counted as satisfying this or any other acceptance criterion, and an ambient fail-closed outcome is never presented as control evidence;
- the record states `config_digest_agreement` (proven; authority-enforced against the durable record) and `request_digest_agreement` (`NOT_ESTABLISHED`; the authority validates no request digest and the task contract declares no counterpart) **separately**, never merges them into one enforced dimension, and never claims request-digest correspondence or detection;
- an identity dimension that cannot be shown to be *definitely absent* is `NOT_ESTABLISHED` and fails closed; `NOT_APPLICABLE` requires positive reviewed evidence of absence (for a render-bearing task: a reviewed per-entry classification declaring no such dimension, AND independently verified catalog resolution, AND exact equality with that entry's closed parameter set, AND no other plausibly-identity committed content), so uncertainty never increases acceptance;
- every render-bearing catalog entry has an explicit reviewed per-entry identity-class assignment, an unassigned render-bearing entry fails closed as `NOT_ESTABLISHED` rather than defaulting to `NOT_APPLICABLE`, and no unreviewed entry inherits a classification;
- catalog provenance is independently verified against the reviewed catalog definition (entry name, task class, catalog version, parameter names and kinds, exact closed-set equality), and caller-presented or verbatim-copied `catalog_entry`/`catalog_version` content never yields `NOT_APPLICABLE` (`provenance claim ≠ verified catalog resolution`);
- no content-level match is ever treated as verified catalog resolution: entry name, catalog version, task class, parameter names and kinds, exact closed-set equality, a byte-identical canonical payload, and a matching source-content or plan digest are necessary and never sufficient, and positive absence requires the §26 Q10 reviewed resolution binding, which v1 does not have;
- the render-authority surface is re-verified before the per-entry identity classification is frozen: the implementation review re-checks the render/job record's asset, output, artifact and receipt references and M5's validation surface, and revisits the `artifact_ref` classification if a reviewed artifact/manifest correspondence contract appears;
- a parameter that the reviewed classification records as NOT a render identity dimension is never compared against render records, never treated as a render identity declaration, and never used to establish that another declaration is absent;
- no caller-authored value can produce `ENFORCED`; a caller-authored string equal to the job record's `sequence_asset_path` does not establish correspondence;
- the monotonic property is demonstrated: making an identity declaration less recognizable (renamed key, non-canonical key, non-catalog task) yields a strictly less permissive outcome than the recognized declaration;
- render state is a non-success value whenever the render requirement fails closed, and raw M5 evidence identity is never presented or read as task-relative render verification;
- an existing caller-authorable fragment snapshot is compared with the reviewed canonical registry value and any divergence fails closed (`FRAGMENT_EXPECTATION_SOURCE_NOT_CANONICAL`);
- the expectation-source controls prove their specific refusal classification — the single §11 token `EXPECTED_VALUE_UNAVAILABLE`, defined there for both the absent-source and the unavailable-value case — and a generic `UNKNOWN` produced only by the §8.0.1 coverage limitation does not satisfy them; no control requires a code token that §11 does not define;
- forbidden authority material is rejected on both keys and values;
- verification result is immutable in the §10.3 sense (derived serialization; mutating a stored field after construction does not change the canonical serialization or digest);
- verification result canonical JSON is stable;
- repeated identical verification produces byte-identical output;
- the §8.0.1 v1 coverage limitation is recorded in the acceptance record rather than silently omitted;
- the live record states that a stale payload with an internally consistent relabelled envelope is NOT DETECTABLE, rather than implying it was detected (§5.3, §20 Phase A/C);
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
24. Can a caller-authored free-form field (for example a catalog `metadata.parameters` value) become an authoritative expected value merely because it is digest-bound into the source-content commitment (§8.0, §8.0.1)?
25. Can live mutable M12.2 registry state, mutated after commitment, alter a verification expectation or the verification result (§8.0 limb 2, §8.0.1)?
26. Can an authoritative M5-verified render belonging to a different twin, carrying a different observed `config_digest`, presenting an unestablished request-digest correspondence, or failing a declared sequence/asset correspondence satisfy this task's render requirement — and does an undecided declared dimension fail the requirement closed rather than count as a valid render domain (§17, §9.3)?
27. Can any statement in the design or in a live-gate record be read as claiming that a consistently relabelled stale observation was detected (§5.3, §6.2, §25)?
28. Can a render whose declared identity dimensions are only partially decided satisfy the render requirement, or be counted as an independently valid render domain for §9.3 composition — including a render that is correct on twin and on the authority-enforced `config_digest` but presents an unestablished request-digest correspondence and a wrong or ambiguous declared sequence/asset identity (§17, §9.3)?
29. Can a caller-authored `metadata.fragments` snapshot (or any other caller-provided copy) become a registry expectation authority merely because it is digest-bound (§8.0 limb 2, §8.0.1)?
30. Can a caller make a declared sequence/asset identity unrecognizable — by renaming a canonical field, using a non-canonical key, or supplying a render-bearing task without reviewed catalog provenance — and thereby obtain `NOT_APPLICABLE`, a satisfied render requirement, or a valid render domain (§17)?
31. Can raw M5 evidence identity (or `evidence_trust_basis.render_evidence = DURABLE_RECORD_BACKED`) be read as task-relative render verification while a declared render identity dimension is unresolved (§9.3, §10.1)?
32. Can an existing caller snapshot that diverges from the reviewed canonical registry value survive an expectation (§8.0 limb 2, §8.0.1)?
33. Do the expectation-source controls prove their specific refusal classification, or can they pass on the v1 coverage limitation alone (§20 Phase A, §21)?

34. Can a caller present catalog-provenance-looking metadata — including values copied verbatim from a legitimate catalog entry — and thereby obtain `NOT_APPLICABLE`, a satisfied render requirement, or a valid render domain, and is a provenance claim distinguished from independently verified catalog resolution (§17, §26 Q10)?

35. Can a render-bearing catalog entry without a reviewed per-entry identity-class assignment default to `NOT_APPLICABLE`, or can a parameter the classification records as NOT a render identity dimension (for example `artifact_ref`) be read as a declared render identity or compared against render records (§17)?

36. Can a caller reproduce every content-level property of a catalog-resolved task — exact entry name, catalog version, task class, parameter names and kinds, exact closed parameter set, byte-identical canonical payload, the same source-content digest and plan identity — and thereby obtain `NOT_APPLICABLE` or a satisfied render requirement, and is content-level consistency distinguished from verified catalog resolution by an explicit sufficiency rule (§17, §20 Phase A)?

37. Is the render-authority surface re-verified before the per-entry identity classification is frozen, and is the `artifact_ref` classification revisited if a reviewed artifact/manifest correspondence contract is introduced (§17, §21, §26 Q10)?

38. Is every control's status truthful — proven only where its differential mechanism was actually exhibited, and `NOT PROVEN` where the required upstream capability does not exist — and can an ambient fail-closed outcome or a `NOT PROVEN` control be mistaken for evidence that a mechanism executed, or for satisfaction of an acceptance criterion (§20 Phase A, §21, §24)?

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
authoritative render job/attempt     AtlasRenderJobRecord.atlas_job_id / .attempt_ordinal (durable
identity records                     job/attempt identity) and the read-only record fields available
                                     for agreement checks:
                                       .canonical_digital_twin_id  participates in an authority-backed
                                                                   agreement (twin agreement)
                                       .sequence_asset_path        enforced record↔evidence by the M5
                                                                   authority; the task-side sequence
                                                                   correspondence is NOT_ESTABLISHED
                                       .config_digest              participates in an authority-backed
                                                                   agreement (config-digest agreement)
                                       .request_digest             READABLE ON THE DURABLE RECORD BUT
                                                                   ESTABLISHES NO AGREEMENT in v1
                                                                   (`request_digest_agreement` =
                                                                   `NOT_ESTABLISHED`: the render
                                                                   authority performs no request-digest
                                                                   comparison)
                                     plus the durable record(s) behind them, all read-only (§17).
                                     **Being readable does not make a field an agreement dimension.**
                                     M12.5 must never copy the record's authority material
                                     (`authorization_id`, `attempt_nonce`,
                                     `last_accepted_lease_token`) into the result or any producer-owned
                                     structure (§11, §13).
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
- negative controls proven, with the stale-relabelled-envelope case recorded as **NOT DETECTABLE** rather than as a passing control (§5.3, §20 Phase A/C);
- no mutation or receipt side effect;
- **explicitly not claimed:** a positive `SATISFIED` semantic verification. Under §8.0.1 no non-render invariant is admissible today, so a live positive is unreachable in v1; a live record must state that plainly rather than substitute a fixture-supplied expectation or a placeholder predicate. Claiming a live positive requires the upstream digest-bound expectation source (§26 Q8) first.

### Live render composition
- existing M5+ verified render evidence consumed without modifying the existing verifier;
- every declared render identity dimension recorded as exactly one of `ENFORCED` / `NOT_ESTABLISHED` / `NOT_APPLICABLE` (§17) — identity binding must **not** be reported as "proven" while any declared dimension is `NOT_ESTABLISHED`;
- §17's declared-dimension negative controls proven: wrong twin, an observed `config_digest` differing from the durable record, wrong declared sequence/asset identity, and an ambiguous/unbound declared sequence/asset identity each fail the render requirement closed;
- the record states each control's status truthfully — `NOT PROVEN` for any control whose mechanism could not be exercised in v1 (for example the caller-expectation differential control while no admissible digest-bound expectation source exists) — and never presents ambient fail-closed behaviour as evidence that a control's mechanism executed (§20 Phase A, §21);
- the record states the digest dimensions separately and truthfully: `config_digest_agreement` proven (authority-enforced), `request_digest_agreement` `NOT_ESTABLISHED` / unproven because no authority validates a request digest — never reported as a detected mismatch, never merged with the config digest, and never the basis of a success state (§17, §25);
- the record states that content-level consistency with the reviewed catalog definition — including a byte-identical canonical payload or a matching digest — is necessary and never sufficient for verified catalog resolution, and that the render-bearing `NOT_APPLICABLE` identity route is unreachable while the §26 Q10 binding does not exist (§17, §26 Q10);
- the record states that in v1 the sequence/asset dimension is `NOT_ESTABLISHED` for **every render-bearing task** — whether the task declares the dimension (`unreal.render-execute`; no reviewed typed binding exists) or its reviewed per-entry classification declares none while verified catalog resolution cannot be established (`unreal.artifact-validate` / `artifact_ref`) or the entry is unassigned — so the render requirement fails closed there and the render domain is not independently valid (§9.3, §17);
- render state is a non-success value whenever the render requirement fails closed, and the record distinguishes raw M5 evidence identity from task-relative render verification;
- the recognition rule's monotonic property is demonstrated: an ambiguous or unrecognized identity declaration yields more refusal, never more acceptance (§17);
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
- that a semantic verification result is a receipt, an authorization, or a substitute for M5 evidence verification (§18);
- **that the supplied resolved source task was authorized, or that the supplied execution plan was dispatched** — M12.5 binds source task ↔ execution plan ↔ observations ↔ authoritative render evidence where applicable, and nothing further; it does not validate, mint, or reference an authorization ID, and it is not a durable authorization or dispatch record;
- that the supplied (source task, plan) pair corresponds to any durable authorization, dispatch, job, or task record;
- that a caller-authored free-form field is an authoritative expectation because it is digest-bound into the source-content commitment (§8.0);
- that a render job's sequence/asset correspondence to the task was verified where no reviewed typed binding decides it — such a declared dimension is `NOT_ESTABLISHED` and the render requirement fails closed (§17);
- that the render requirement is satisfied, or that the render domain is independently valid, while any declared render identity dimension is undecided (§9.3, §17);
- **that a control was proven where its mechanism could not be exercised** — an ambient fail-closed outcome, or the absence of an admissible digest-bound expectation source, is never evidence that a differential control executed; such controls are recorded `NOT PROVEN`, and `NOT PROVEN` satisfies no acceptance condition and licenses no positive outcome (§20 Phase A, §21);
- **that request-digest correspondence is enforced, proven, or detected** — the render authority validates no request digest and the M12.1 task contract declares no counterpart, so `request_digest_agreement` is `NOT_ESTABLISHED` / unproven; its lack of enforcement is never presented as a proven correspondence, a detected mismatch, or a passing control (§17);
- that render-job identity binding was proven where a declared render identity dimension remains `NOT_ESTABLISHED` (§17, §24);
- that a declared render identity dimension is `NOT_APPLICABLE` when the resolved source task does declare that identity (§17);
- that a caller-authored `metadata.fragments` snapshot is authoritative because it is digest-bound into the source-content commitment (§8.0 limb 2);
- **that the design discovers every possible semantic identity encoding.** It claims only that (a) the reviewed identity surfaces S1–S3 are recognized, (b) ambiguous or unrecognized possible identity content fails closed rather than being treated as absent, and (c) no caller-authored value can establish positive identity correspondence without a reviewed typed binding (§17);
- that `render_state = VERIFIED`, or any `evidence_trust_basis` value, is task-relative render verification while a declared render identity dimension is unresolved — raw M5 evidence identity remains evidence-level only (§9.3, §10.1, §10.4);
- that a matching caller-authored string establishes sequence/asset correspondence (`same caller string ≠ authoritative correspondence`, §17);
- that an unresolved or unrecognized identity declaration reduces the scope of verification — uncertainty may only increase refusal, never acceptance (§17);
- **that a caller-provided catalog-provenance claim is verified provenance** — a caller-presented or verbatim-copied `catalog_entry`/`catalog_version` is a claim, never verification, and never establishes `NOT_APPLICABLE`; content-level consistency with the reviewed catalog definition, including a byte-identical canonical payload, is necessary and never sufficient (`provenance claim ≠ verified catalog resolution`, §17);
- **that a matching digest proves catalog provenance or authenticity** — a source-content or plan digest establishes consistency and tamper-evidence of the supplied content, not that the Atlas catalog resolver produced it (§17);
- **that `artifact_ref` has a render-authority correspondence** — no reviewed typed binding maps it to `sequence_asset_path`, `manifest_reference`, `receipt_reference` or any other render-authority field, and M12.5 does not invent one (§17, §8.0.1);
- **that an unassigned or unrecognized render-bearing entry declares no identity** — an unassigned render-bearing entry is `NOT_ESTABLISHED` and fails closed (§17);
- **that a parameter the reviewed classification records as NOT a render identity dimension (for example `artifact_ref`) is compared against render records or can make a render identity positive** — such a value may only refuse (§17, §8.0.1).

---

## 26. Open design questions for the independent review

These are intentionally left open for the independent review/reconciliation gate rather than silently decided in implementation.

**Closed by this revision** (recorded so the next review can test the closure rather than re-litigate it):

1. *Which exact target-state invariant names are stable for v1?* — Still implementation-review work for the registry contents, but the admissibility rule is now fixed (§8.0) and the v1 assessment is recorded (§8.0.1). An invariant without a digest-bound expectation source **reached through a reviewed typed contract field** cannot be registered, and a committed-but-free-form caller-authored field is not such a source.
2. *Which State Extraction envelope/session fields are authoritative for observation binding?* — Closed: the transport response envelope is the root (§5.3), with each component's sourcing enumerated, the copied-claim prohibition, and the non-authentication limitation recorded in §5.3/§25.
5. *Minimum safe render-evidence identity surface?* — Closed: §17 defines the closed `job_identity` / `attempt_identity` / `evidence_identity` triple, derived by M12.5 from the authoritative path, together with the enforceable render job↔task agreements (twin agreement, and the **config-digest** agreement enforced by the authority against the durable record — the request-digest correspondence is `NOT_ESTABLISHED` because the authority validates no request digest and the task declares no counterpart, §17), with the sequence/asset correspondence explicitly disclosed as not decided in v1; a bare caller-settable `verified` flag is inadmissible by construction.
7. *What proves a live M12.5 run performed no mutation?* — Closed in form: §20 Phase B asserts no mutation, no receipt, byte-stable repeats, and the §10.3 derived-serialization behaviour.

**Closed by the v1.2 remediation (MR-1–MR-5 of the independent review at `c0c4cd65879aaa42e22ea5f7d9a40a89be287bd5`)** — recorded so the next review can test the closure rather than re-litigate it:

- **MR-1** — the resolved-source-task limb admits only reviewed typed contract fields; the free-form caller-authored `metadata`/`parameters` surface is inadmissible however it is committed, and digest binding is stated as tamper-evidence between supplied artifacts, not authorization (§7.2, §8.0, §8.0.1).
- **MR-2** — registry-derived expectations must come from a bound/committed snapshot; live mutable module state is never authoritative, and `frozen=True` is not an integrity boundary (§8.0 limb 2, §8.0.1).
- **MR-3** — the stale-relabelled-envelope case is recorded as NOT DETECTABLE and is no longer a fail-closed control; the controls and gate wording cover only the detectable variants (§20 Phase A/C, §24, §25).
- **MR-4** — §17 defines the render job↔task agreement from existing authoritative records only; the declared sequence/asset dimension was initially *disclosed* rather than failed closed, and was tightened to a normative fail-closed rule in the v1.3 round below (§17, §20 Phase D, §24).
- **MR-5** — §25 records that M12.5 establishes no authorization or dispatch and is not a durable authorization/dispatch record.

**Closed by the v1.3 remediation (MR4-1, MR2-1 of the re-review of the v1.2 tree)** — recorded so the next review can test the closure rather than re-litigate it:

- **MR4-1** — a declared sequence/asset identity is a **declared render identity dimension** with a normative fail-closed rule: undecidable → `RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`; decided and different → `RENDER_TASK_CORRESPONDENCE_MISMATCH`; neither may satisfy the render requirement, and §9.3 defines a render domain as independently valid only when every declared dimension is decided and every comparison succeeded. A declared dimension may never be `NOT_APPLICABLE` (§17, §9.3, §20 Phase D, §24, §25).
- **MR2-1** — registry expectation authority may come only from the reviewed code-level canonical registry value bound by its reviewed constant digest; a caller-authorable snapshot (`metadata.fragments`) is never an expectation source, only divergence evidence (`FRAGMENT_EXPECTATION_SOURCE_NOT_CANONICAL`, §8.0 limb 2, §8.0.1, §11, §20 Phase A).

**Closed by the v1.4 remediation (V13-1…V13-4 of the re-review of the v1.3 tree)** — recorded so the next review can test the closure rather than re-litigate it:

- **V13-1** — the render identity **recognition boundary** is now mechanical and monotone: a reviewed recognition surface (S1 reviewed typed target-state field, S2 reviewed catalog parameter class over the entry's closed parameter set, S3 explicitly reviewed identity field), a three-state rule (`DEFINITELY DECLARED` → evaluate; `DEFINITELY NOT DECLARED` → `NOT_APPLICABLE` only on positive reviewed evidence of absence; `AMBIGUOUS/UNRECOGNIZED` → `NOT_ESTABLISHED` → fail closed), a reviewed-resolution requirement for render-bearing tasks (no catalog provenance → `NOT_ESTABLISHED`, never an inference of absence), a monotonic fail-closed default (the recognizer may over-include and refuse, never under-include and accept), and the trigger-vs-expectation separation (a free-form value can only move the outcome toward refusal; a matching caller string can never manufacture `ENFORCED`). Controls: non-canonical key, renamed canonical field, non-catalog render-bearing task, matching caller value, trigger-vs-expectation (§17, §20 Phase A, §11, §21, §22 Q30, §25).
- **V13-2** — render-state / task-relative semantics: `render_state = VERIFIED` only when every declared render identity dimension is decided; when a declared dimension is `NOT_ESTABLISHED` the render requirement is refused, the render domain is not independently valid, §9.3 composition is blocked, and raw M5 evidence remains identifiable as *evidence* only, never as task-relative render verification. §9's reachability note and §9.2 are corrected, and a Phase-D control plus §21 criteria are added (§9, §9.2, §9.3, §10.1, §20 Phase D, §21, §24, §25).
- **V13-3** — the registry divergence check is now **mandatory** with its refusal classification (`FRAGMENT_EXPECTATION_SOURCE_NOT_CANONICAL`), and "code-level canonical source" is defined normatively as the reviewed statically code-defined canonical value (not a live mutable runtime object, not an exported mutable object, not caller content, not arbitrary module state); `frozen=True`-is-not-an-integrity-boundary, deep-isolation/hash-binding, and the limit of the caller snapshot's role are retained (§8.0 limb 2, §8.0.1, §11, §20 Phase A).
- **V13-4** — green-for-the-wrong-reason is removed from the two expectation-source controls: they must exhibit their **specific** refusal classification (`EXPECTED_VALUE_UNAVAILABLE`), a generic `UNKNOWN` produced only by the §8.0.1 coverage limitation does not satisfy them, and an unprovable control must be recorded as not proven rather than as passing (§20 Phase A, §21).

**Closed by the v1.5 remediation (V14-1…V14-4 of the re-review of the v1.4 tree)** — recorded so the next review can test the closure rather than re-litigate it:

- **V14-1** — the reviewed identity classification is now complete and per entry for **every** render-bearing catalog entry, not one example: `unreal.render-execute` declares the sequence/asset dimension `sequence_name` (closed set `{twin_id, sequence_name}`, both `string`, enforced as a closed set with non-empty-string validation), and `unreal.artifact-validate` does **not** declare a render identity dimension — `artifact_ref` is an artifact/validation reference with no reviewed typed counterpart in the render-job authority (whose only asset-identity field is `sequence_asset_path`), so it is recorded explicitly as NOT a render identity dimension and its assertion is handled by §8.0.1's inadmissible class. Any render-bearing entry without an assignment is `NOT_ESTABLISHED` and fails closed and must never default to `NOT_APPLICABLE`; no unreviewed entry inherits a classification (§17, §11, §20 Phase A, §21).
- **V14-2** — the positive-absence branch no longer rests on caller-presentable metadata: catalog provenance must be **independently verified** against the reviewed catalog definition (entry name, task class, catalog version, parameter names/kinds, exact closed-set equality), a caller-presented or verbatim-copied `catalog_entry`/`catalog_version` claim is never verification (`provenance claim ≠ verified catalog resolution`), a mismatched parameter set fails closed, and in v1 verified resolution is not establishable, so `NOT_APPLICABLE` is unreachable for render-bearing tasks (§17, §11, §20 Phase A, §21, §25, §26 Q10).
- **V14-3** — §8.0.1's v1 coverage statement now uses the same render-bearing boundary as §17/§24/§27: for every render-bearing task the sequence/asset dimension is `NOT_ESTABLISHED` and the render requirement fails closed, whether the task declares the dimension, declares none but lacks verified resolution, or is unassigned (§8.0.1, §17, §24, §27).
- **V14-4** — the expectation-source refusal class has an explicit token in §11: `EXPECTED_VALUE_UNAVAILABLE` covers both the absent-authoritative-source and the unavailable-value case, no second synonym is defined, and every control that demands a specific expectation-source classification demands exactly that token (§11, §20 Phase A, §21).

**Closed by the v1.6 remediation (V15-1, V15-2 of the re-review of the v1.5 tree)** — recorded so the next review can test the closure rather than re-litigate it:

- **V15-1** — the `artifact_ref` classification basis is now factually precise and no longer claims the record has a single asset-related field: the render/job authority carries `sequence_asset_path` as its sequence-asset identity **and** other output/artifact/receipt-related references (`output_parent_directory`, `output_directory`, `expected_output_spec`, `manifest_reference`, `receipt_reference`); M5's render-evidence verification validates twin identity, the observed `config_digest` and output topology, and validates none of the artifact/receipt references **nor any request digest**; and **no reviewed typed correspondence** exists between `artifact_ref` and any render-authority field (nor to the separate `ProductionArtifactManifest` surface, which is downstream-linked to the render path but not to `AtlasRenderJobRecord`). This record's original digest phrasing and manifest-linkage clause are corrected by the v1.7 entries below. M12.5 therefore invents no correspondence, `artifact_ref` can never become a positive render identity expectation (it stays inadmissible → `UNKNOWN` → fail closed, and §8.0.1 now carries an explicit requested-artifact/validation-identity row), and the row requires the classification to be revisited under any future reviewed artifact/manifest correspondence contract, with §21 adding the obligation to re-verify the render-authority surface before freezing it (§17, §8.0.1, §21, §25, §26 Q10).
- **V15-2** — the sufficiency rule is now mechanical rather than inferred: content-level consistency — entry name, catalog version, task class, parameter names and kinds, exact closed-set equality, a byte-identical canonical payload, a matching source-content digest and the same plan identity — is **necessary and never sufficient** for verified catalog resolution; `caller content matching the reviewed catalog definition ≠ verified catalog resolution` and `source/plan digest consistency ≠ resolver provenance / catalog authenticity`; the positive-absence boundary requires the §26 Q10 reviewed resolution binding; and §26 Q10 is recorded as the actual upstream dependency for the branch, not documentation convenience. Controls: byte-identical positive-absence attack, digest-as-provenance attack (§17, §11, §20 Phase A, §21, §24, §25).

**Closed by the v1.7 remediation (V16-1, V16-2 of the re-review of the v1.6 tree)** — recorded so the next review can test the closure rather than re-litigate it:

- **V16-1** — the `ProductionArtifactManifest` relationship is now stated accurately: the surface **is** downstream-linked to the render path (`from_unreal_render_receipt(...)` consumes an `UnrealRenderReceipt` plus M5-verified `UnrealEvidence`, requires verified render evidence, and binds `artifact_path` to the evidence's observed outputs, with lineage tests rejecting artifact-path and evidence substitution), while it is **not** linked to `AtlasRenderJobRecord`, is **not** consulted by M5's render-evidence verification, and carries **no** reviewed typed correspondence to `artifact_ref` (nor is the record's optional `manifest_reference`, populated by no planning module, a binding). Neither `artifact_ref → ProductionArtifactManifest` nor `manifest_reference → artifact_ref` is a reviewed binding, the manifest is not an M12.5 expectation authority, and the v1 conclusion is unchanged: `artifact_ref` remains `NOT ADMISSIBLE` → `UNKNOWN` → fail closed, with the §21 obligation to re-verify the complete render/artifact authority surface before freezing the classification (§17, §8.0.1, §21, §25).
- **V16-2** — the combined "request/config digest" dimension is split into two explicit dimensions with separate truth values: `config_digest_agreement` = `ENFORCED` (the observed state's `config_digest` is a mandatory identity field compared against the durable record, mismatch rejected) and `request_digest_agreement` = `NOT_ESTABLISHED` (the render authority validates no request digest and the M12.1 task contract declares no request-digest counterpart, so no positive correspondence exists in v1). No statement anywhere claims request-digest enforcement, detection or correspondence; the Phase-D control is split so the config half is a genuinely detected refusal and the request half is recorded `NOT_ESTABLISHED` / unproven and must not pass merely because another unresolved dimension causes refusal. The render-requirement consequence is normative: config digest proven + request digest `NOT_ESTABLISHED` + sequence `NOT_ESTABLISHED` ⇒ render requirement not satisfied and `render_state` ≠ `VERIFIED`. This is a truthfulness correction about the existing authority surface — it does not describe an implementation feature that now exists, and the missing upstream binding is recorded as §26 Q11 (§17, §11, §8.0.1, §20 Phase D, §21, §24, §25, §26 Q11).

**Closed by the v1.8 remediation (V17-1, V17-2 of the re-review of the v1.7 tree)** — recorded so the next review can test the closure rather than re-litigate it:

- **V17-1** — §17's agreement framing is authority-based, not task-only: a render identity dimension is admissible only when its agreement is established by the relevant reviewed authority (record↔evidence correspondence where the render authority enforces it; agreement with the digest-bound source task where a task-side counterpart exists). It is stated explicitly that `config_digest_agreement` has no task-side counterpart (it is a record↔evidence correspondence), that a dimension with neither a task-side counterpart nor an authority-enforced correspondence must be `NOT_ESTABLISHED` and fail closed, and the §7 render-edge statement uses the same framing. The per-dimension rules are unchanged: twin agreement `ENFORCED`, `config_digest_agreement` `ENFORCED`, `request_digest_agreement` `NOT_ESTABLISHED`, `sequence_agreement` `NOT_ESTABLISHED` (§7, §17).
- **V17-2** — the third expectation-source control ("caller expectation vs digest-bound expectation") is brought under the no-vacuous-pass rule with four explicit requirements (an existing reviewed digest-bound expected value; a comparison of the caller expectation against that reviewed source; an observable specific refusal when the caller expectation is inadmissible; an explicit record of whether the mechanism was exhibited). Because v1 has no admissible semantic invariant (§8.0.1, §26 Q8) the differential mechanism cannot be exercised, so the control is recorded **NOT PROVEN** and an ambient `EXPECTED_VALUE_UNAVAILABLE` refusal is expressly not evidence that it executed. The scope of the specific-code requirement is widened from two to three controls, and a general control-status truthfulness rule is added for Phases A/C/D with matching criteria, review question, live-record obligation and non-claim; `NOT PROVEN` is informational about control coverage only, adds no acceptance path, and remains a future validation obligation for the point when an admissible expectation source exists (§20 Phase A, §21, §22, §24, §25).

**Closed by the v1.9 remediation (V18-1 of the re-review of the v1.8 tree)** — terminology only:

- **V18-1** — §23.1's permitted read-only surface no longer calls `.request_digest` an "agreement field". It lists "read-only record fields available for agreement checks" and states each field's actual role: `.canonical_digital_twin_id` and `.config_digest` participate in authority-backed agreements, `.sequence_asset_path` is enforced record↔evidence by the M5 authority while the task-side correspondence is `NOT_ESTABLISHED`, and `.request_digest` is readable on the durable record but establishes no agreement in v1 (`request_digest_agreement` = `NOT_ESTABLISHED`). A normative sentence adds that being readable does not make a field an agreement dimension, and a global terminology audit confirmed that no other statement in the design suggests request-digest verification: the canonical truth values remain twin `ENFORCED`, config-digest `ENFORCED`, request-digest `NOT_ESTABLISHED`, sequence `NOT_ESTABLISHED`. No architecture change (§23.1, §17).

**Still open** (design-review inputs, not authorization to expand scope):

3. Should the verification result store a full immutable invariant result tree, or only canonical result codes plus a separately recoverable evaluation trace?
4. For non-render semantic tasks, is the M12.5 result itself sufficient as downstream provenance, or is a separate lightweight Atlas semantic-task record required later?
6. Which semantic task classes can be live-validated in v1 without requiring new Unreal transport fields — given that no non-render invariant is admissible until an expectation source exists (§8.0.1)?
8. **Upstream, out of scope for M12.5 v1:** admitting non-render semantic invariants requires a digest-bound expectation source. The candidate directions are a typed expectation surface on the M12.1 target-state contract, or a separately reviewed digest-bound semantic-input contract. Either is an upstream contract change requiring its own design gate; M12.5 must not invent it, and must not accept caller-supplied expectations in the meantime (§8.0). v1 has no declared-input channel, and any future expectation commitment must live outside the verification request.

9. **Upstream, out of scope for M12.5 v1 — required for future positive render-state coverage:** there is no reviewed typed sequence/asset identity field on the M12.1 target-state contract (`UnrealTargetStateSpec` carries only `description`, `invariant_names`, `expects_render`), so a declared sequence/asset identity cannot be decided and the render requirement fails closed (§17). Closing that requires a reviewed typed sequence/asset identity on the M12.1 target-state contract, carried by the render-request construction path so that `AtlasRenderJobRecord.sequence_asset_path` is bound to it by the same commitment. That is an upstream contract change with its own design gate: M12.5 must not invent it, and the absence of the field must cause the render requirement to fail closed (as it now does) rather than leave the dimension merely unproven.

10. **Upstream, out of scope for M12.5 v1 — the actual dependency for the positive-absence branch:** the positive-absence `NOT_APPLICABLE` branch for a render-bearing task requires independently verified catalog resolution, but M12.1 `metadata` is caller-authorable, the reviewed resolver's output is reproducible byte-for-byte by hand (an identical canonical payload, the same source-content digest, the same plan identity), and no content-level check can therefore distinguish a claim from genuine resolution (§17). This question is **not** documentation convenience: until it is satisfied the verifier cannot establish verified catalog resolution at all, so the render identity dimension stays `NOT_ESTABLISHED`, the render requirement fails closed, and the positive-absence branch cannot be permitted. Closing it requires a reviewed resolution binding — a resolver-issued, reviewed commitment carried on the reviewed catalog path and verifiable from reviewed code alone. That is an upstream contract change with its own design gate; M12.5 must not invent it, and **no Q10 implementation is part of M12.5 v1**.

11. **Upstream, out of scope for M12.5 v1 — required before a request-digest correspondence can ever be established:** the render authority validates no request digest (the verifier never reads `request_digest`; the durable record validates it only as a non-empty string and propagates it) and the M12.1 task contract declares no request-digest counterpart, so `request_digest_agreement` is `NOT_ESTABLISHED` and the render requirement fails closed on it. Closing that requires an upstream reviewed request-digest binding carried from the render-request construction path into a field an authority actually validates. M12.5 must not invent one, and **no request-digest binding is part of v1**.

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

The v1.2 remediation additionally closes the five minor findings (MR-1–MR-5) returned by the independent review at `c0c4cd65879aaa42e22ea5f7d9a40a89be287bd5`, without relaxing any authority boundary:

4. **expectation authority is restricted to reviewed typed contract fields** — a free-form or caller-authored surface is inadmissible however it is committed, and digest binding is tamper-evidence rather than authorization (§8.0, §7.2);
5. **registry expectations must come from a bound/committed snapshot** — live mutable module state is never authoritative expectation data (§8.0 limb 2, §8.0.1);
6. **the stale-relabelled-envelope control no longer claims detection** — it is recorded as NOT DETECTABLE, and the controls cover only the detectable variants (§5.3, §20, §24, §25);
7. **the render job↔task agreement is defined** from existing authoritative records — twin identity and config-digest correspondence enforced, the request-digest correspondence and the sequence/asset correspondence not established in v1 (the request-digest split is corrected in the v1.7 record below) — with a wrong-twin / wrong-config-digest negative control, and M5 remains the sole render verifier (§17, §20 Phase D);
8. **the authorization/dispatch non-claim is explicit** — M12.5 binds source task ↔ execution plan ↔ observations ↔ authoritative render evidence, and nothing further (§6.1, §25).

The v1.3 remediation closes the two findings of the re-review of that tree, tightening the render dimension without relaxing any boundary:

9. **a declared render identity dimension fails closed when it cannot be decided** — a declared sequence/asset identity with no reviewed typed binding yields `RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`, a demonstrable mismatch yields `RENDER_TASK_CORRESPONDENCE_MISMATCH`, and an undecided declared dimension never counts as a valid render domain (§17, §9.3, §24);
10. **registry expectation authority is the reviewed code-level canonical value** — a caller-authored `metadata.fragments` snapshot is never an expectation source, only divergence evidence, and no digest computed from caller-provided content promotes content to authority (§8.0 limb 2, §8.0.1, §11).

The v1.4 remediation closes the four findings of the re-review of that tree, establishing the monotone safety ordering (definitely recognized → evaluate; definitely absent → `NOT_APPLICABLE`; ambiguous or unrecognized → `NOT_ESTABLISHED` → fail closed):

11. **the render identity recognition boundary is mechanical and monotone** — recognition is restricted to the reviewed surfaces S1–S3; absence may be concluded only from positive reviewed evidence (for render-bearing tasks: reviewed catalog provenance over the entry's closed parameter set); everything else is `NOT_ESTABLISHED` and fails closed, so a caller can never gain acceptance by making an identity less recognizable (§17, §20 Phase A, §11);
12. **render-state semantics are closed** — `VERIFIED` requires every declared dimension decided, and raw M5 evidence identity is always distinguishable from, and never a substitute for, task-relative render verification (§9.3, §10.1, §20 Phase D, §25);
13. **the registry divergence check is mandatory and "code-level canonical source" is defined** — an existing caller snapshot must be compared with the reviewed canonical value and any divergence fails closed (§8.0 limb 2, §8.0.1).

The v1.5 remediation completes the reviewed classification and closes the four precision findings of the re-review of that tree, without relaxing any boundary:

14. **the reviewed identity classification is complete for every render-bearing catalog entry** — `unreal.render-execute` declares a sequence/asset identity dimension (`sequence_name`), `unreal.artifact-validate` does not (`artifact_ref` is an artifact/validation reference with no reviewed typed counterpart in the render-job authority), every other catalog entry is not render-bearing, and any render-bearing entry without an assignment is `NOT_ESTABLISHED` rather than `NOT_APPLICABLE` (§17);
15. **catalog provenance must be verified, not read** — a caller-presented or verbatim-copied `catalog_entry`/`catalog_version` claim is never verification, and the positive-absence branch additionally requires independently verified resolution, which v1 cannot authenticate, so `NOT_APPLICABLE` is unreachable for render-bearing tasks in v1 (§17, §11, §26 Q10);
16. **the v1 coverage statement uses the render-bearing boundary, and the expectation-source refusal class has an explicit §11 token** — `EXPECTED_VALUE_UNAVAILABLE` is defined once for both the absent-source and the unavailable-value case, and every control references a defined token (§8.0.1, §11, §20 Phase A, §21, §24).

The v1.6 remediation closes the two precision findings of the re-review of that tree, without relaxing any boundary:

17. **the `artifact_ref` classification rests on a verified factual basis and is explicitly revisitable** — the render-authority surface is described accurately (sequence-asset identity plus output/artifact/receipt references, none bound to `artifact_ref` by any reviewed typed contract, and M5 validates none of them against it), no correspondence is invented, the value stays inadmissible → `UNKNOWN` → fail closed, and the classification must be revisited under any future reviewed artifact/manifest contract after the reviewer re-verifies that surface (§17, §8.0.1, §21, §25, §26 Q10);
18. **the sufficiency rule for verified catalog resolution is explicit** — content-level consistency, byte-identical canonical content and matching digests are necessary and never sufficient, and positive absence requires the reviewed resolution binding of §26 Q10, so the render-bearing `NOT_APPLICABLE` route remains unreachable in v1 (§17, §11, §20, §21, §24, §25).

The v1.7 remediation closes the two minor findings of the re-review of that tree:

19. **the `ProductionArtifactManifest` relationship is stated accurately** — downstream-linked to the render path via `UnrealRenderReceipt` + M5-verified `UnrealEvidence` and bound to the evidence's observed outputs, but not linked to `AtlasRenderJobRecord`, not consulted by M5's render-evidence verification, and with no reviewed typed correspondence to `artifact_ref`; nothing implies an existing binding and the manifest is not an expectation authority (§17, §21, §25);
20. **config-digest and request-digest correspondence are now separate dimensions with separate truth values** — `config_digest_agreement` `ENFORCED` (authority-enforced against the durable record), `request_digest_agreement` `NOT_ESTABLISHED` (no authority validates a request digest; no task-side counterpart), with the Phase-D control split accordingly, the render requirement still failing closed in v1, and the missing upstream binding recorded as §26 Q11 (§17, §11, §8.0.1, §20, §21, §24, §25).

The v1.8 remediation closes the two minor findings of the re-review of that tree, without relaxing any boundary:

21. **the render-job/task agreement framing is authority-based** — a dimension's agreement is established by the relevant reviewed authority (record↔evidence correspondence where the render authority enforces it; agreement with the digest-bound source task where a task-side counterpart exists), no dimension is implied to have a task-side field it does not have (for example `config_digest_agreement`), a dimension with neither is `NOT_ESTABLISHED` and fails closed, and the per-dimension truth values are unchanged (§7, §17);
22. **no control may pass vacuously** — the caller-expectation differential control requires an existing reviewed digest-bound expected value and an observable mechanism, is recorded `NOT PROVEN` while v1 has no admissible semantic invariant, and a general control-status truthfulness rule requires every control to be recorded proven only where its mechanism was exhibited, with `NOT PROVEN` satisfying no acceptance criterion and licensing no positive outcome (§20 Phase A, §21, §22, §24, §25).

The v1.9 remediation closes the single terminology finding of the re-review of that tree:

23. **§23.1 states each record field's actual role** — `.canonical_digital_twin_id` / `.config_digest` are authority-backed agreements, `.sequence_asset_path` is record↔evidence-enforced with the task-side correspondence `NOT_ESTABLISHED`, and `.request_digest` is readable but establishes no agreement in v1; being readable is not an agreement dimension (§23.1, §17).

The capability limitation itself is **not** closed by this revision, and both halves of the composition are now closed in v1: v1 has no positively verifiable non-render semantic invariant (unsupported or unbound requirements stay `UNKNOWN` and fail closed, §8.0.1), and for every render-bearing task the render identity dimension is `NOT_ESTABLISHED` — whether the task declares a sequence/asset identity (`unreal.render-execute` does), or its reviewed per-entry classification declares none while verified resolution cannot be established (`unreal.artifact-validate`, whose `artifact_ref` is not a render identity dimension), or the entry is render-bearing but unassigned — so the render requirement fails closed and the render domain is never independently valid, and no raw M5 evidence identity can be read as task-relative render verification (§17, §9.3, §10.1). The result discloses the weaker evidence trust basis of the observation domain (§10.4). Restoring positive semantic coverage requires the upstream expectation authority (§26 Q8); restoring positive render-state coverage requires the upstream typed sequence/asset identity (§26 Q9) and, wherever a reviewed classification declares no sequence/asset dimension, a reviewed resolution binding (§26 Q10). Neither may be closed by inventing a predicate, by accepting a request-derived expectation, by treating a committed caller-authored parameter as authoritative, or by treating a caller-authored fragment snapshot as canonical.

The intended result is:

```text
facts → target-state evaluation → bound semantic verification result
```

not:

```text
facts → new executor / new scheduler / new recovery / new receipt system
```

**Implementation remains unauthorized until this document receives an independent architectural/red-team CLEAR.**
