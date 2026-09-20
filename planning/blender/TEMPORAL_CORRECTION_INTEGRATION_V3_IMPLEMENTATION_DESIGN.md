# Temporal Observation ↔ Blender Correction Integration v3
## Implementation Design / DeepSeek Closure Record

**Status:** IMPLEMENTATION-READY DESIGN GATE  
**Revision:** 3  
**Base:** `321a9ca6ecbc58f52e9c66e1d1116387edcae60d`  
**Scope:** Blender Correction Execution Bridge + Temporal Observation/State Delta integration only.

### 1. Purpose

This revision closes the implementation questions raised by the independent DeepSeek red-team review of Revision 2 while retaining the session-scoped architecture previously cleared by independent review.

The integrated transaction remains:

`disposable Blender process/session -> canonical pre-extraction A -> admit A -> bounded correction -> fresh canonical post-extraction B -> admit B -> StateDelta(A,B) -> dispose`

No Temporal schema, correction receipt schema, evaluator contract, extraction contract, persistence/recovery authority, retry authority, or correction family is expanded.

### 2. Binding architectural rule

A and B are observations of the **same disposable Blender producer session**.

They MUST share:
- `stream_id`
- `continuity_id`
- `ordering_epoch`
- `producer_session_id`
- producer contract/capability identity

A is admitted before the mutator can execute.

B is admitted only from the fresh canonical extraction performed after mutation.

The bridge receipt, plan, authorization, postcondition result, and engine evidence are never valid sources from which B may be constructed.

### 3. Concrete A transport / lifecycle boundary

DeepSeek identified that the existing `CorrectionBridgeResult` only transports the final receipt/evidence.

The implementation therefore adds an **in-process temporal capture adapter around the existing executor extractor** rather than changing the frozen correction executor interface.

The adapter is installed before calling the existing executor:

1. executor invokes extractor for its source-binding/precondition extraction;
2. adapter captures the exact `SceneModel` and canonical temporal snapshot at that extraction point;
3. adapter constructs A from that captured extraction;
4. adapter admits A into an ephemeral in-memory `ObservationStream`;
5. only after A admission succeeds does the executor continue toward mutation;
6. executor invokes the same extractor after mutation;
7. adapter captures the exact fresh post extraction and constructs B;
8. B is admitted;
9. evaluator receives A, B, and the exact `FromIdentity` produced from the A admission baseline.

Thus A is not merely returned after mutation: **A admission occurs before mutation inside the disposable Blender process.**

The outer `CorrectionBridgeResult` transports the already-created A/B observations and admission evidence after the process completes.

### 4. Exact snapshot provenance

The temporal snapshot MUST be derived from the same extraction composition already used by the correction executor:

`extract_scene(bpy) -> payload_to_scene_model(payload) -> _scene_to_canonical(scene)`

The integration adapter MUST NOT reconstruct A or B from:
- correction receipt fields;
- correction plan fields;
- authorization;
- engine evidence;
- report digests;
- target parameters;
- postcondition results.

The adapter captures the canonical snapshot immediately from the `SceneModel` returned by the extractor at the executor's actual extraction point.

A deterministic test MUST verify that replacing the receipt with a stolen/fabricated receipt cannot change B.

### 5. Producer provenance ownership

The Temporal contract requires a valid `ProducerProvenance`, but it does not require a networked/global identity service.

For this one-shot bridge architecture, the **bridge runtime is the provenance issuance authority for its disposable process/session**.

Rules:
- `producer_session_id` is minted inside the Blender process.
- The caller cannot supply or override it.
- Every bridge invocation gets a fresh session identifier.
- The identifier uses process-local identity plus cryptographically strong OS entropy.
- `producer_instance_ordinal = 0` for the single producer process represented by this bridge invocation.
- The same minted session identifier is used for A and B.
- A session identifier is never reused for another bridge invocation.
- The session ends when the Blender process is disposed.

This provides the required uniqueness boundary without introducing an external registry/identity service that has no authority in the frozen Temporal contract.

A deterministic test MUST prove:
- caller-supplied provenance is ignored/rejected;
- two invocations receive different session identifiers;
- A and B in one invocation receive the same session identifier;
- duplicate externally injected session identities cannot replace the runtime-issued identity.

### 6. Source-time and sequence discipline

The source-time domain is now frozen.

**Domain:** `FRAME_INDEX`  
**Rate:** `{num: 1, den: 1}`  
**Value:** the actual Blender `bpy.context.scene.frame_current` observed at each extraction point.  
**Ownership:** Blender producer state; read-only at the integration boundary.  
**Reset:** none; the integration never changes Blender's frame.  
**Monotonicity:** Temporal admission requires B.value >= A.value.  
**Ordering epoch:** `0` for the disposable correction transaction.

Temporal sequence is integration-owned and deterministic:
- A.sequence = 0
- B.sequence = 1

Sequence is a per-session observation ordinal and resets only because the disposable producer session is new.

This means a correction performed at a fixed Blender frame can legitimately have identical A/B source-time values; Temporal admission requires non-decreasing source time, not strict increase.

### 7. Stream and continuity identity

For one correction transaction:
- `stream_id` is the source scene identity used by the bridge transaction.
- `continuity_id` is a transaction-scoped identifier derived from the freshly minted producer session.
- `ordering_epoch = 0`.
- A is therefore `INITIAL_ACCEPTED`.
- B is same-epoch and same-continuity and must be `ACCEPTED` when sequence/source-time/scene scope are valid.

The integration owns only this ephemeral admission stream. It does not write or persist an external `AdmissionState`.

### 8. Observation identity binding

Immediately after A is admitted, the integration records:
- A.observation_id
- A.admission_identity_digest
- A.envelope_digest
- A.state_digest
- A `FromIdentity`

B is accepted only when its producer session, continuity, epoch, scene scope and sequence/source-time relationship match the same transaction.

The evaluator receives the existing frozen `ComparisonInput(A, B, FromIdentity, contract_version)`.

A/B identity binding is therefore enforced by lifecycle, not merely described in prose.

### 9. Postcondition failure policy

Correction receipt authority and measured Temporal state remain separate.

If the mutator fails before a fresh post-extraction:
- no B exists;
- no B admission occurs;
- no StateDelta is produced;
- the correction failure receipt remains authoritative;
- the disposable process is disposed.

If fresh post-extraction succeeds but a correction postcondition subsequently fails:
- B **does exist** because it is an independently measured canonical state;
- B is admitted if Temporal admission is valid;
- StateDelta(A,B) is computed;
- the correction receipt remains `POSTCONDITION_FAILED`;
- the integration exposes both the correction outcome and the measured Temporal outcome;
- no correction retry, rollback, or recovery is introduced.

If the fresh post-extraction itself fails:
- no B exists;
- no StateDelta is produced;
- the process is disposed;
- the transport is ambiguous when mutation already occurred.

This explicitly prevents receipt failure from suppressing or fabricating measured state.

### 10. No-change correction semantics

The existing Temporal admission implementation makes same-sequence identity the duplicate condition.

Because this integration assigns:
- A.sequence = 0
- B.sequence = 1

a correction that completes but produces no canonical state change is **not** `DUPLICATE_ACKNOWLEDGED`.

B is `ACCEPTED` with the same state digest as A. Evaluation then produces a valid same-epoch comparison with no field/entity changes and `state_digest_changed = false`.

`DUPLICATE_ACKNOWLEDGED` remains reserved for actual same-sequence, same-admission-identity redelivery.

This resolves the apparent mF-6 ambiguity using the frozen admission implementation rather than introducing special integration behavior.

### 11. Fabricated-B / receipt-disagreement evidence

The integration MUST carry explicit provenance evidence sufficient for deterministic tests to establish that B came from the executor's fresh extraction point.

Required evidence:
- extraction invocation ordinal;
- pre-extraction capture marker;
- post-extraction capture marker;
- pre/post report digests;
- pre/post state digests;
- producer session identity;
- canonical snapshot digests;
- source of snapshot construction fixed to the extractor adapter.

A negative test will replace or tamper with the correction receipt while holding the fresh extractor result constant. B MUST remain identical.

A second negative test will attempt to construct B from receipt-only data and MUST fail the integration construction path.

### 12. Ambiguity rules

Existing bridge transport ambiguity vocabulary remains authoritative.

Additional runtime rule:
- any exception after mutator invocation begins is ambiguous;
- no fabricated B is emitted unless a successful fresh canonical extraction actually occurred;
- if no post extraction completed, there is no B;
- no retry/rollback/recovery is performed by this integration.

The bridge process is always disposed after one invocation.

### 13. Capability / representation state

The integration reuses the existing extraction-fidelity capability declaration used by the live Temporal harness.

The capability contract is:
`extraction_fidelity_v1`

The observable/unobservable field universe remains exactly the frozen Temporal field universe.

Representation-state information is taken from the extraction payload at the same extraction boundary rather than inferred from correction receipt data.

No new representation-state vocabulary is introduced.

### 14. Evaluator contract correction

The evaluator does not receive literally only A and B.

The existing frozen evaluator input is:
`ComparisonInput(a, b, from_identity, comparison_contract_version)`

Revision 3 uses that exact interface.

No evaluator API/schema change is permitted.

### 15. Language-neutral seam

No new external wire protocol is introduced by this integration.

The additive bridge result remains JSON-compatible and uses existing canonical JSON/digest conventions. C++ interoperability is preserved because the new transport fields are primitive/canonical JSON values and snapshots use the frozen canonical representation.

No protobuf/CDDL dependency is introduced merely to satisfy a documentation claim.

### 16. Deterministic test requirements

The implementation is not complete until deterministic tests cover:

1. A capture occurs before mutator invocation.
2. A admission occurs before mutator invocation.
3. A and B share session/continuity/epoch.
4. B comes from the second extractor invocation.
5. caller-supplied producer session identity cannot override runtime-issued identity.
6. separate bridge invocations receive fresh producer sessions.
7. source_time uses FRAME_INDEX, rate 1/1, and is non-decreasing.
8. sequence is exactly 0 -> 1.
9. content-identical foreign A substitution is refused by identity binding.
10. receipt tampering cannot alter B.
11. receipt-only/fabricated-B construction is rejected.
12. postcondition failure after successful fresh extraction still exposes measured B.
13. post-extraction failure after mutation produces no B and ambiguous transport.
14. mutation failure before post extraction produces no B.
15. unchanged canonical state yields ACCEPTED B plus a no-change delta, not duplicate acknowledgement.
16. persistence/save invariance remains intact.
17. exact canonical snapshot digest is reproducible.
18. existing correction allowlist and authorization boundaries remain unchanged.

### 17. Live-gate requirements

The real Blender gate is credited only after:
1. deterministic CI is green on the exact implementation head SHA;
2. the self-hosted Blender gate runs against that exact SHA;
3. A admission is demonstrated before mutation;
4. B is demonstrated from fresh canonical extraction;
5. producer session provenance is demonstrated;
6. no-save/persistence invariance remains demonstrated;
7. postcondition-failure and no-change cases have deterministic coverage;
8. no live workflow is credited if it was skipped without explicit operator authorization.

### 18. Frozen boundaries / non-goals

This integration MUST NOT:
- modify TemporalObservation schema;
- modify ProducerProvenance schema;
- modify AdmissionState schema;
- modify AdmissionEngine semantics;
- modify evaluator semantics;
- add correction families;
- modify correction receipt schema;
- add retry/rollback/recovery;
- add persistence authority;
- mutate canonical extraction semantics;
- introduce generic Blender tool/schema expansion;
- write persistent AdmissionState;
- allow the bridge caller to provide producer session identity.

### 19. Implementation shape

The minimum implementation surface is:

- extend `CorrectionBridgeResult` with the bounded temporal transaction payload;
- add an ephemeral temporal capture context in `correction_execution_bridge_runtime.py`;
- wrap the existing executor extractor rather than modifying the frozen executor API;
- construct/admit A on the first extractor invocation;
- construct/admit B on the second extractor invocation;
- evaluate A/B using the frozen evaluator input;
- expose deterministic evidence;
- add deterministic tests;
- add/update the operator-gated Blender integration test.

No broader orchestration framework is introduced.

### 20. Gate disposition

DeepSeek's four blocking findings are closed as follows:

- **A transport:** closed by pre-mutation extractor capture + in-process A admission.
- **External provenance authority:** not adopted as an architectural requirement; the bridge process is the bounded issuance authority because the frozen Temporal contract requires valid provenance, not a global identity service.
- **source_time:** frozen to Blender FRAME_INDEX at 1/1 with sequence 0 -> 1.
- **postcondition/fabricated-B:** explicit outcome matrix and extractor-bound snapshot provenance are now mandatory.

DeepSeek's non-blocking findings are incorporated into the deterministic test and implementation requirements above.

**Implementation authorization:** deterministic implementation may begin from this Revision 3 design. Live promotion remains gated by exact-head deterministic CI and the real Blender gate.
