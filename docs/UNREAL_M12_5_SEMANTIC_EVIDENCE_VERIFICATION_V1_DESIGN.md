# Atlas M12.5 — Unreal Semantic Evidence Verification v1

**Status:** ARCHITECTURE / RECONCILIATION ONLY — implementation NOT authorized  
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

A mismatch at any required identity edge is a verification failure, not a warning.

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

---

## 7. Target-state verification model

M12.5 reuses only the **evaluation model** of the existing Atlas `TargetStateEvaluator` concept: every required invariant is evaluated, all required invariants must pass, and an unevaluable condition fails closed. It does **not** reuse or promote the existing placeholder predicate bodies as authoritative semantic verification.

M12.5 invariant evaluation must use a closed, exact-name-matched registry of implementation-reviewed invariant definitions. It must never use substring/fuzzy/alias matching or caller-supplied executable predicates. An unrecognized invariant name is `UNKNOWN` and therefore fails closed.

The verifier evaluates **all required invariants**.

Observation contradiction rule: if two or more observations share the same semantic task identity, observation scope identity, and request identity but carry unequal canonical-state digests or otherwise divergent authoritative facts, the input set is **CONTRADICTORY** and must fail closed. The verifier must never choose a best-case observation, newest observation, or first observation to manufacture a satisfied result. A duplicate request with equivalent authoritative content may be treated as a duplicate only when the canonical observation identities are equal.

Success requires:

```
required-invariant set is NON-EMPTY
AND
every required invariant = SATISFIED
AND
all required observations are valid
AND
all required identity bindings are valid
AND
no required invariant is UNKNOWN
AND
no contradiction is present
```

An empty required-invariant set is **not a successful verification state**. It is an invalid/unknown verification input and must fail closed. This mirrors M12.1's existing `__no_invariants__` fail-closed behavior. The verifier must never obtain `SATISFIED` merely because zero invariants were evaluated.

Any one of:

- FAILED;
- UNKNOWN;
- MISSING;
- CONTRADICTORY;
- UNBOUND;

causes semantic verification to fail closed.

There is no best-effort success mode.

---

## 8. Invariant classes

M12.5 should support a **closed invariant registry** rather than arbitrary executable predicates. The v1 registry is fixed during implementation review. Matching is exact-name only; an unrecognized invariant name is `UNKNOWN` and fails closed. No generic, prefix, substring, alias, or caller-defined predicate may satisfy an invariant that is not explicitly registered.

This registry constraint applies even when two invariant names appear semantically similar: a requested name is satisfied only by its exact reviewed definition.

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

---

## 9. Render-bearing semantic tasks

M12.4 explicitly fails closed for render-bearing runtime mapping.

M12.5 must preserve that boundary.

A render-bearing semantic task may therefore produce three independently distinguishable outcomes:

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
  observation_digests
  render_evidence_identity?
  invariant_results
  semantic_state
  render_state
  overall_state
  failure_codes
  provenance
  canonical_digest
```

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

### 10.2 Determinism

For identical:

- resolved task;
- execution plan;
- source-content digest;
- observation envelopes;
- existing render evidence identities;

the M12.5 result and canonical digest must be byte-identical.

No current time, process-global state, filesystem enumeration order, random nonce generation, model output, or network call may affect the verification result.

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
- duplicate request identity;
- observation identity mismatch;
- canonical digest mismatch;
- unsupported invariant;
- missing invariant input;
- contradictory observation;
- stale observation;
- empty required-invariant set;
- render evidence missing when required;
- render evidence not independently verified;
- render-job identity mismatch;
- render-attempt identity mismatch;
- verifier input contains forbidden authority material;
- malformed provenance;
- unsupported future State Extraction fields.

For provenance and authority-material checks, M12.5 must define its own closed typed provenance schema and reuse the repository's existing authority-key predicates. The broad `is_forbidden_authority_key` predicate is mandatory for untrusted caller-supplied or unknown metadata surfaces. For M12.5's own declared envelope/binding/provenance fields, the implementation must use an explicit closed allowlist or the repository's high-confidence `_is_high_confidence_forbidden_key` tier because legitimate M12 metadata includes `session_identity`, `scope_identity`, and `attempt_id`. Each tier must have an adversarial test. Unknown provenance keys are rejected structurally, and caller-supplied metadata must not be accepted into the result's canonical digest merely because it is syntactically JSON-compatible.

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

The structural isolation mechanism is normative: the M12.5 authority-isolation test must inspect source ASTs using an explicit forbidden-module/import allowlist pattern, modelled on the existing M7 keeper authority-isolation test rather than the weaker package-walk mechanism in the existing M12 test. The gate must include a positive-control fixture containing a forbidden import and demonstrate that the AST scan detects it, including an aliased import and a deferred `importlib.import_module(...)` form. A green test that only proves forbidden modules are absent from the list of already-walked `planning.m12.*` names is insufficient.

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

The provenance input/output surface is a closed typed structure. M12.5 must reject unknown provenance keys and recursively reject authority-shaped material using the repository's existing validation mechanism. Provenance values are accepted only from validated observation/result structures; arbitrary caller metadata must not be copied into the canonical result merely for traceability.

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

It consumes the immutable mapping as lineage/provenance and derives verification requirements from authoritative source contracts, not mutable mapping fields.

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

Prove exact result codes and canonical digests.

### Phase B — real Unreal observation input

Use the already-proven UE 5.6.1 State Extraction fixture session.

The live test must:

1. provision the existing extraction fixture only through its approved opt-in mechanism;
2. request factual state;
3. capture the exact extraction observation envelope;
4. independently feed that immutable observation to the M12.5 verifier;
5. assert target-state outcomes;
6. assert byte-stable repeated verification;
7. assert that semantic verification itself performs no mutation;
8. assert no new render receipt is created by M12.5.

### Phase C — negative live controls

At minimum:

- missing entity;
- wrong entity identity;
- mismatched semantic task identity;
- mismatched source-content digest;
- modified observation digest;
- stale observation from another extractor/engine session;
- conflicting observations carrying the same request identity;
- render-bearing task without verified render evidence;
- render evidence bound to wrong job/attempt identity;
- caller-constructed `UnrealEvidence(verified=True)` or equivalent snapshot presented as if it were M5+ verified evidence.

Each negative control must fail closed.

A stale-observation/other-session control should be exercised with a second real extraction session when the live harness can provide one. If the fixture cannot safely provide a second live session, deterministic Phase-A coverage is an acceptable substitute, but the live-gate record must explicitly state that live stale-session coverage was not available rather than implying that it was proven.

The live suite should also assert that session/engine/request metadata cannot be smuggled into `canonical_state`; the frozen extractor's reserved-key refusal remains a defense at the observation boundary.

### Phase D — render-bearing composition

Only after the non-render verifier is independently clear should a separate live composition gate consume an existing verified render result.

That composition gate must not modify the M5+ verifier or recovery path.

---

## 21. Offline acceptance criteria

Before implementation can clear:

- target-state evaluation is deterministic;
- all required invariants are evaluated;
- UNKNOWN never collapses to PASS;
- identity mismatches fail closed;
- source-content digest is recomputed;
- plan identity is recomputed or independently validated;
- State Extraction canonical digest is recomputed;
- render evidence is never self-attested;
- forbidden authority material is rejected;
- verification result is immutable;
- verification result canonical JSON is stable;
- repeated identical verification produces byte-identical output;
- no execution/recovery/authorization authority imports exist;
- structural AST authority-isolation gate passes, including the forbidden-import positive control and deferred-import detection;
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
- the exact-name closed invariant registry defined and reviewed for M12.5 v1; each registered invariant must be justified against a field actually supported by the frozen State Extraction contract, an independently verified render-evidence identity, or an explicitly declared non-render semantic input; unsupported invariant requirements remain UNKNOWN and fail closed;
- render evidence verifier;
- evidence/receipt identity models;
- the existing recursive closed-provenance/forbidden-authority validator.

It should not copy those authorities.

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
- real UE 5.6.1 State Extraction observation consumed;
- positive semantic verification proven;
- negative controls proven;
- no mutation or receipt side effect.

### Live render composition
- existing M5+ verified render evidence consumed without modifying the existing verifier;
- correct render-job/attempt identity binding proven;
- semantic result only becomes satisfied when all declared conditions are independently established.

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
- that the live State Extraction fixture covers cases explicitly marked not-yet-live-covered, refusal-verified, or blocked by engine/API limitation.

---

## 26. Open design questions for the independent review

These are intentionally left open for the independent review/reconciliation gate rather than silently decided in implementation:

1. Which exact target-state invariant names are sufficiently stable for M12.5 v1, and which belong to future task-specific extensions?
2. Which State Extraction envelope/session fields are authoritative enough for observation binding without expanding the frozen extraction contract?
3. Should the verification result store a full immutable invariant result tree, or only canonical result codes plus a separately recoverable evaluation trace?
4. For non-render semantic tasks, is the M12.5 result itself sufficient as downstream provenance, or is a separate lightweight Atlas semantic-task record required later?
5. What is the minimum safe render-evidence identity surface M12.5 should consume without depending on implementation-private verifier details? The answer must not permit a bare caller-settable `verified` flag to become authority.
6. Which semantic task classes can be live-validated in v1 without requiring new Unreal transport fields?
7. What exact evidence proves that a live M12.5 verification run performed no mutation?

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

The intended result is:

```
facts → target-state evaluation → bound semantic verification result
```

not:

```
facts → new executor / new scheduler / new recovery / new receipt system
```

**Implementation remains unauthorized until this document receives an independent architectural/red-team CLEAR.**
