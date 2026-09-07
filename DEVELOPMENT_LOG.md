## 2026-09-07 - M11.2 provider execution (shadow mode)
- Added planning/m11_router/provider/ (config, invocation, shadow) + benchmark execution + tests.
- Shadow/advisory only: never replaces Hermes execution, never touches Atlas production authority.
- Full suite 1389 passed (1348 + 41). No workflow/action-runner tests, no live Unreal, no Blender.
- Authority-leak scan clean (only docstring prohibitions / dimension names / marker substrings).

## 2026-09-07 - M11.1 model router core
- Implemented planning/m11_router/ core (profile, risk, routing, escalation, telemetry, evidence gate,
  escalation packet, router facade, benchmark skeleton).
- 136 M11 deterministic tests; full suite 1348 passed (no regressions).
- Authority isolation enforced by tests (no production module imports, no authority methods).
- Model execution / provider invocation / corpus run / Hermes integration deferred to M11.2.

## 2026-09-07 - M11 design hardened (PR #81)
- M11 design PR #81 hardened before implementation (docs only; no code change).
- Frozen risk->tier: R1-R7 deterministic (worst-dim max drives tier; hard selectors force L2/L3; unknown => L3 fail-closed;
  multiple selectors take max; model self-confidence never input).
- Model capability = validated static profiles (tier/provider/model_id/capability_floor/supported_classes/token_budget/timeout).
- Finite escalation budget MAX_ESCALATIONS_PER_TASK=3; terminal NEEDS_HUMAN_REVIEW on exhaustion / L3-fail / insufficient evidence;
  no blind rerun, no downgrade.
- Telemetry append-only with task_id/attempt_id/escalation_id; immutable risk/tier fields; corrections/escalations append new records.
  9 explicit router failure modes (all fail closed), 9 objective acceptance criteria.
- Docs consistency checks: 20/20 sections in order, code fences even, 0 malformed tables. No production code / no live scenario / no Unreal / no workflow tests.

## 2026-09-07 - M11 adaptive model-router design (investigation + design)
- Created docs/ATLAS_M11_ADAPTIVE_MODEL_ROUTING_DESIGN.md (19 sections + appendices).
- Investigation-only: no production code changed, no live scenario, no Unreal launch, no PR merge.
- Insertion: Hermes dev-loop, pure adviser; cannot call authority ops, mint receipts, schedule, or issue authorization (Contract V1 §2).
- Design: 4-tier (L0-L3) cheapest-capable routing, deterministic risk taxonomy, hard escalation, evidence-based confidence,
  adaptive token budgets, escalation packets, privacy-safe telemetry (no secrets/nonce/keys), benchmark corpus methodology.
- Validation: 1212 deterministic tests unaffected (no code change); markdown structure + fence balance checked.

## 2026-09-06 - M10 S4 Case J remediation
- Genuine S4 s4b live dual-restart produced a torn non-terminal journal (job 899e6a81, ACCEPTED-only).
- Recovery classified torn job Case G -> terminal FAILED; contract requires Case J -> RECOVERY_PENDING.
- Fixed coordinator: _candidate_is_terminal guard before _handle_finished_candidate; torn/interrupted
  (finished=False / phase not FINISHED/FAILED) -> Case J (RECOVERY_PENDING, ambiguity++, no receipt, no retry);
  genuine terminal Case G still fail-closed; normal Case B unchanged.
- tests/m10/test_m10_case_j_torn_journal.py (9 tests); focused 9 passed; suites 263 passed; full 1198 passed.
- No live scenario re-run; deterministic-only remediation.

# Atlas Development Log

## September 6, 2026 — Milestone 7 hardening/pre-flight

M7 **hardening/pre-flight** repairs the three production gaps M6 discovered, as a
deterministic prerequisite to the live M7 Scenarios. No live Unreal/Blender
execution; no `UnrealEditor` launch; no process kill/restart; no
workflow/action-runner tests. Full detail: `docs/UNREAL_M7_HARDENING.md`.

### A. Framed catalog integrity
- `UnrealRenderRecoveryCoordinator._query_catalog` now deep-thaws the observed state
  and validates `payload_byte_length`/`payload_sha256` against the canonical
  `known_jobs` payload (deterministic compact JSON). Valid framed catalogs are
  accepted; malformed/incomplete/tampered framing fails closed to UNREADABLE → Case J.
- `canonical_known_jobs_payload()` is the single canonical serializer.

### B. C++ witness journal history (append-only)
- `WriteJournalEntry` maintains an append-only `phase_history` array with monotonic
  `phase_sequence` (ACCEPTED=1, STARTED=2, FINISHED/FAILED=3); duplicate/out-of-order
  phases rejected; malformed history fails closed (never truncates prior witness
  entries); durable atomic write retained. `ReconcileRenderJobs` exposes the retained
  history and derives current state from the latest phase. `journal_schema_version` → 2.
- Journal-history C++ automation tests (AppendHistory, MonotonicSequence,
  DuplicateRejection, LifecycleOrdering, StructuralValidation, MalformedHistory,
  ReconcileRetainedHistory) **compile-verified** via UnrealBuildTool; 16 C++
  automation tests total. Not executed under the editor in this milestone.

### C. Execution/submission deadline enforcement
- The coordinator now evaluates persisted deadlines deterministically; an unresolved
  job whose submission or execution deadline has expired transitions to
  `RECOVERY_FAILED` + `recovery_status=EXHAUSTED`, with no retry/receipt/finalization.
  `submission_deadline` bounds the unsubmitted phase; `execution_deadline` bounds the
  execution/recovery phase. `now_utc` is injectable for deterministic tests.

### Validation
- `tests/m7/`: **59 passed** (final head).
- `tests/m6/`: **79 passed** (framing test updated to reflect the repair).
- Existing M4/M5 Unreal suites: **154 passed**.
- Full `pytest -m "not integration"`: **1088 passed** (final head).
- C++ module build: **UnrealBuildTool succeeded** (UBT_EXIT_CODE=0).

Two additional M7 journal-integrity passes hardened structural validation (typed
`phase_history` fail-closed before `GetArrayField`; parseable-but-malformed history
rejected, never overwritten, ReconcileRenderJobs -> PARTIAL) and added lossless
legacy schema-1 -> schema-2 migration (prior phase retained, never discarded). See
`docs/UNREAL_M7_HARDENING.md`.

### M7 status
Live UE 5.6 restart/recovery **Scenarios 1–8 are NOT run** and require explicit
human authorization. No `UnrealEditor` launch; no workflow/action-runner tests.

Historical dated handoff snapshots are archival records and should remain unchanged.

## September 6, 2026 — Milestone 6 deterministic fault-injection/concurrency test suite

Milestone 6 (Contract V1 §31 matrix + §32 C++ automation boundary) is implemented as a deterministic test suite under `tests/m6/` on `main` + dedicated M6 branch. No production code was modified; no workflow/action-runner tests; no live Unreal/Blender execution; no M7 live restart scenarios.

This entry includes a **corrective test-correctness/status-honesty pass**: per-item §31/§32 status is now recorded honestly in `docs/UNREAL_M6_TEST_STATUS.md`. Several test names/assertions were strengthened or reworded so their claims match what they actually assert (e.g. the two-coordinator test now actually attempts a second store-gated publication and asserts rejection; the framed-catalog and deadline-expiry tests no longer claim fully-exercised positive behavior).

### Coverage (honest, per item)

- **FULLY EXERCISED** §31 items: 1,2,3,4,5,6,11,12,13,14,15,17,18,19,20,21,22,25.
- **PARTIALLY EXERCISED** §31 items: 7,8,9,10 (fail-closed asserted; positive gate not isolable through the Python coordinator, and/or the C++ parallel only compile-verified), 16 (Cases A/B/C/H/J/K + quiescence + rogue asserted; some sub-cases inferred/partial), 23 (persistence + no-auto-retry; the positive `EXHAUSTED` expiry gate is missing in production).
- **PARTIALLY EXERCISED / DEFECT** §31 item 24: framed-integrity path is inert due to the mappingproxy serialization defect; M6 asserts only the SAFE fail-closed outcome and does NOT claim the positive framing path.
- **CANT EXERCISE (contract/implementation gap)** §32 journal append/history retention: C++ journal overwrites a single per-pair file; no append-only `phase_history`/`phase_sequence` exists. No test cements this divergence.

See `docs/UNREAL_M6_TEST_STATUS.md` for the full item-by-item table.

### Validation (this corrective pass)

- M6 suite: **79 passed**.
- Full deterministic repository suite: **1029 passed**.
- Existing Unreal recovery/evidence suites: re-run green.

### Production defects discovered by M6 (flagged, not fixed — test-only milestone)

1. Coordinator frame-integrity check cannot serialize frozen `observed_state` (mappingproxy) to canonical JSON; a framing-field response always fails closed to Case J (safe) but the code path is inert — positive framing verification NOT exercised.
2. C++ `WriteJournalEntry` overwrites a single `<atlas>__<unreal>.json` per job-pair instead of Contract §30 append-only `phase_history`/monotonic `phase_sequence`.
3. `execution_deadline` is persisted but expired-window enforcement (`EXHAUSTED` transition) is not implemented; §31 item 23 is therefore only partially exercised.

These require production remediation (M7 hardening), not test weakening.

### M7 status

Live UE 5.6 restart/recovery Scenarios 1–8 are NOT yet run. Do not run them without explicit authorization; do not run workflow/action-runner tests.

Historical dated handoff snapshots are archival records and should remain unchanged.

## September 6, 2026 — Milestone M4/M5 merged to main

The current development line is `main`.

### Cross-process Unreal render-job recovery (M4) — MERGED

Milestone 4 cross-process Unreal render-job recovery is implemented and merged to `main` via PR #67, following `docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md`:

- durable `AtlasRenderJobRecord` state with atomic replacement and stale-writer rejection;
- durable Atlas intent written before transport submission;
- Atlas-generated immutable `atlas_job_id` and attempt identity;
- single-coordinator lease/fencing plus per-job exclusive ownership;
- process/session incarnation identity, including real process-creation identity;
- contained Windows Job Object quiescence proof and fail-closed uncontained handling;
- durable witness journal outside `Saved/` with `ACCEPTED`, `STARTED`, `FINISHED`, and `FAILED` phases;
- attempt nonce with HMAC-protected witness payloads;
- per-attempt output isolation and engine-attested manifests;
- full-catalog reconciliation with stability checks and rogue/unmanaged detection;
- explicit orphan/ambiguity states (`ORPHANED_ARTIFACTS_PRESENT`, `RECOVERY_FAILED`);
- receipt identity binding with create-if-absent semantics;
- no automatic resubmission after uncertain transport acceptance.

This is regression/implementation-verified (deterministic suite). It is NOT yet declared production-capable: M6 (deterministic fault-injection test suite) and M7 (live UE 5.6 restart/recovery Scenarios 1–8) remain pending per Contract V1 §33–§34.

### Independent evidence verification (M5) — MERGED

PR #68 merged the authoritative independent evidence-verification boundary (`verify_render_job_evidence` in `planning/unreal_evidence_contract.py`). `verified=True` is only produced when a concrete `AtlasRenderJobRecord`, supported evidence source class, full identity binding, exact output-topology/frame-count, output-path isolation, engine-attested manifest, independent disk hash/size, and complete PNG/IDAT stream checks all pass. It is never supplied by the transport.

### Stage 17 Unreal lineage status

- implementation/regression verification — complete;
- historical normal-render live proof — complete (real UE 5.6 render/provenance, prior to M4);
- M6 deterministic fault-injection testing — still pending;
- M7 live UE 5.6 restart/recovery Scenarios 1–8 — still pending.

Historical dated handoff snapshots are archival records and should remain unchanged.

## September 4, 2026 — Stage 17 Unreal lineage and controller-boundary hardening

The active development line is now `main` and Stage 17 remains in progress.

### Unreal Stage 17 status

The Unreal Engine 5.6 render/receipt boundary remains live-proven for the implemented render workflow. The production-artifact provenance layer is implemented and regression-verified but still awaits the final human UE 5.6 provenance proof.

The provenance chain is:

```text
verified inspect_render_job evidence
  ↓
matching UnrealRenderReceipt
  ↓
ProductionArtifactManifest
  ↓
durable ProductionArtifactStore
  ↓
reload
  ↓
exact lineage verification
```

`UnrealEvidence` and `UnrealRenderReceipt` expose canonical detached snapshot/from_snapshot boundaries with fail-closed validation. The disposable `live_unreal_production_artifact_proof.py` harness consumes an already verified evidence/receipt pair and does not execute, authorize, schedule, or recover Unreal work.

### Controller-to-Unreal boundary

Mainline `AgentControllerHost` was hardened so protected Unreal production intent and the production marker come only from the host-owned `TrustedUnrealContext`.

Model-supplied protected intent cannot replace the trusted intent. Conflicting model intent is retained only as diagnostic mismatch state. Model-supplied production flags cannot disable the host-owned production marker.

`UnrealProductionControllerIntegration` adds a second admission check requiring the complete host-owned protected context before executor invocation:

```text
production
authorized_production
intent
sequence_asset_path
```

Missing or invalid trusted context is rejected before execution.

These changes add no second authorization system, scheduler, recovery engine, or Unreal execution path.

### PR #50 disposition

The historical controller-host architecture in PR #50 remains isolated. Its branch has diverged substantially from current `main`, so it will be integrated selectively rather than through a blanket merge. The validated invariants needed by the current architecture are being transplanted incrementally.

### Validation status

Previously reported deterministic Stage 17 provenance/snapshot checkpoints remain valid for the commits they covered. The newest September 4 controller trust-boundary changes have not yet received a new local Windows test result in this session.

No workflow/action-runner tests are to be run for the live gate unless explicitly authorized.

### End-of-night resume point

Next session:

1. Pull latest `main`.
2. Run focused deterministic controller trust-boundary tests.
3. Execute the human UE 5.6 Stage 17 provenance proof using evidence from the existing proven render boundary.
4. Run `live_unreal_production_artifact_proof.py` against the verified evidence/receipt pair.
5. Confirm manifest persistence, reload, exact lineage, and digest identities.
6. Continue selective integration of validated PR #50 architecture only after the Stage 17 proof checkpoint.

Historical dated handoff snapshots are archival records and should remain unchanged.

## September 3, 2026 — Qwen Proposal, Atlas Authorization, Runtime, Recovery, and Artifact Lineage

Atlas completed the current Stage 16 Qwen integration contract and advanced into Stage 17 production-artifact lineage.

### Stage 16 provider milestone

The local Qwen/Ollama provider produces an intent-only `QwenProductionProposal` containing the canonical workflow, optional version, and typed workflow parameters. Provider output is treated as untrusted and is validated against the trusted soccer-production catalog before release.

The current canonical catalog contract is:

```text
broadcast-goal-preparation@1

file_name       -> string
object_name     -> string
target_location -> vector3
target_rotation -> vector3
```

The live proposal-only smoke test was user-verified locally.

### Atlas authorization handoff

`qwen/production_handoff.py` establishes a provenance-bound seam between the validated Qwen proposal and Atlas authority. The handoff validates proposal/catalog provenance, records digests, independently recompiles before authorization, rejects model-supplied authorization fields, and delegates to the existing Atlas authorization path.

The handoff is also durably reconstructable through `QwenProductionTaskHandoff.from_snapshot(...)`. Persisted proposal, semantic-task, compiled-task, and digest fields are revalidated and recompiled fail-closed before they can re-enter Atlas recovery.

### Full Qwen-authorized production runtime — LIVE VERIFIED

`scripts/run_live_qwen_production_runtime.py` was user-verified against Blender 4.4.

Verified live chain:

```text
Qwen proposal
  ↓
trusted catalog validation
  ↓
semantic ProductionTaskDefinition
  ↓
Atlas ActionAuthorization
  ↓
existing AutonomousTaskRuntime
  ↓
real Blender mutation
  ↓
fresh independent verification
  ↓
fixture restoration
```

Observed live verification:

```text
workflow=broadcast-goal-preparation
workflow_version=1
qwen_proposal=verified
catalog_validation=verified
semantic_task=verified
atlas_authorization=verified
existing_task_runtime=verified
blender_execution=verified
independent_final_verification=verified
```

The live mutation targeted `Goal_Left_post` at `[0.5, 5.302, 0.0]` with rotation `[0.0, 0.0, 15.0]`, then restored the observed fixture state to location `[0.25, 5.302, 0.0]` and rotation `[0.0, 0.0, 0.0]`.

### Qwen-originated cross-process recovery — LIVE VERIFIED

`scripts/run_live_qwen_production_recovery_restart.py` exercises the established Atlas recovery path with persisted Qwen provenance.

Phase 1 obtains a live Qwen proposal, crosses normal Atlas authorization, executes the first real Blender action, intentionally fails the later action before Blender invocation, and persists the blocked continuation plus Qwen provenance.

Phase 2 starts a fresh Python process, reconstructs the canonical handoff, obtains a fresh Qwen recovery recommendation, validates that recommendation against the persisted task contract, acquires fresh authoritative evidence, derives only the unfinished action from the persisted authorized workflow, explicitly issues a new Atlas replan authorization, executes the replacement action, independently verifies the complete target state, and restores the fixture.

User-verified output included:

```text
LIVE QWEN PRODUCTION RECOVERY VERIFIED
object=Goal_Left_post
workflow=broadcast-goal-preparation
workflow_version=1
qwen_provenance_recovered=verified
initial_authorization_recovered=verified
process_restart=verified
qwen_recovery_recommendation=verified
qwen_recovery_recommendation_advisory_only=verified
fresh_recovery_evidence=verified
qwen_workflow_target_revalidated=verified
completed_prerequisite_not_replayed=verified
replan_authorization=atlas-qwen-recovery-replan
replacement_execution=verified
independent_final_verification=verified
fixture_restored_location=[0.25, 5.302, 0.0]
fixture_restored_rotation=[0.0, 0.0, 0.0]
```

This establishes that Qwen can participate in recovery reasoning without receiving recovery authority. Atlas still owns recovery classification, evidence acquisition, replan authorization, execution, and final verification.

GitHub Actions Atlas Tests #1439 passed after the live-guided recovery increment.

### Recovery architecture rule

Do not add a Qwen-specific executor, authorization system, scheduler, or recovery controller. Qwen remains an intent/proposal source; Atlas remains the sole production authority and recovery owner.

## Stage 17 — Production artifact lineage foundation

The next architectural gap identified after Stage 16 was provenance between the canonical Digital Twin and its concrete production representations. Atlas already had task provenance, evidence, and engine-specific receipts, but no small reusable cross-engine lineage contract.

`planning/production_artifact.py` introduces `ProductionArtifactManifest` as a non-executable lineage record. It binds:

- a stable canonical Digital Twin identifier;
- a concrete artifact representation and path;
- upstream source-artifact relationships;
- workflow/version/parameter provenance;
- independently generated evidence and receipt digests;
- engine and engine-version metadata.

The manifest is deterministic and independently digestable, supports fail-closed reconstruction from persisted snapshots, rejects malformed or unknown fields, and rejects self-referential or duplicate source relationships.

`tests/test_production_artifact.py` provides regression coverage. The manifest deliberately exposes no execution, authorization, scheduling, or recovery behavior.

### Stage 17 engine hardening

The Blender and Unreal artifact factories now enforce their engine identity at construction time. Their lineage-verification helpers also enforce the engine identity on persisted or tampered manifests. Unreal artifact construction requires verified `inspect_render_job` evidence and requires the manifest artifact path to appear in independently observed render `output_files`.

`ProductionArtifactStore` provides durable versioned manifest persistence with atomic replacement, flushed writes, fail-closed reload validation, and deterministic manifest integrity checking.

### Stage 17 Unreal proof harness — IMPLEMENTED

PR #55 added `live_unreal_production_artifact_proof.py`, a disposable non-authorizing harness that consumes an already verified `UnrealEvidence` snapshot plus matching `UnrealRenderReceipt`, constructs `ProductionArtifactManifest`, persists/reloads it through `ProductionArtifactStore`, independently verifies exact lineage, and prints the artifact/evidence/receipt/manifest digest identities.

Focused harness regression coverage passed on Python 3.9 and 3.11 before PR #55 was merged into `main`.

This is an architectural foundation, not a claim that the real Unreal production-artifact path has been live verified. The remaining human gate is to feed evidence from the existing proven UE 5.6 render workflow into the harness and confirm the persisted manifest and exact lineage against a real production artifact.

## Stage 15 — Semantic Soccer Production Tasks

Stage 15 established `ProductionTaskDefinition`, reusable production-task fragments, target-state evaluators, canonical soccer-production templates, and the versioned workflow catalog.

The semantic task layer compiles directly into the existing `AtlasTaskDefinition` and therefore reuses the existing execution/authorization/recovery runtime.

The real Blender 4.4 environment live-verified the versioned workflow path, including semantic provenance, dependency validation, multi-operation execution, independent verification, recovery, and exact fixture restoration.

## Stage 14 — Dependency-aware task composition

Stage 14 added explicit action prerequisites through `ActionSpec.depends_on` while keeping execution serial and deterministic.

Dependency declarations participate in authorization and integrity digests, and completed prerequisites are recovered from trusted successful checkpoints.

The live dependency task and cross-process dependency-recovery paths were verified against Blender 4.4.

## Stage 13 — Multi-step partial-progress recovery

Stage 13 demonstrated that a completed action is not blindly replayed after a later action fails. Durable checkpointing, process restart, fresh evidence, explicit replan authorization, replacement execution, independent verification, and fixture restoration were all verified.

## M8 — Witness attestation + engine attempt identity (Unreal cross-process recovery)

Stage 18 (Unreal cross-process render-job recovery) M8 closes the two attestation
gaps deferred at the end of M7. Implemented deterministically (no live Unreal):

- **Engine attempt ordinal:** `attempt_ordinal` (Atlas-authoritative, carried
  verbatim from the durable record) is threaded through submit_render → C++
  `FRenderJobState` → witness journal → `reconcile_render_jobs` → Atlas binding.
  Unreal never invents/increments/reinterprets it; a mismatch vs the durable record
  fails closed (UNTRUSTED_WITNESS). It never authorizes execution or retry.
- **Real HMAC-SHA256 witness attestation:** `entry_digest =
  HMAC-SHA256(key = UTF8(attempt_nonce), message = canonical_bytes)`. The nonce is
  Atlas-generated, used ONLY as the HMAC key, and NEVER written to
  journal/receipt/manifest/logs. C++ implements RFC-2104 HMAC over BCrypt SHA-256.
- **Canonical serialization (Python/C++ byte-identical):**
  `field(\x1f field)*\x1e` over the 10 signed fields, manifest entries
  `path\x1csize\x1csha256\x1d`, UTF-8, locale-independent. A fixed conformance
  vector produces the same canonical bytes and the same HMAC in both languages.
- **Legacy journals** (lacking attempt_ordinal/HMAC) are legacy/unsupported
  witnesses: never ENGINE_JOURNAL_ATTESTED, fail closed as untrusted, no
  success/receipt/finalization/retry. Intentional; does not weaken M7 fail-closed.
- **Coordinator gates:** the reconciler verifies attempt_ordinal equality, then
  the HMAC using the persisted record attempt_nonce; missing/malformed/mismatched
  HMAC or ordinal, and malformed canonical payloads, all fail closed.
- **Deterministic tests:** `tests/m8/` (19: conformance + witness/secret gates).
  Full `pytest -m "not integration"` = 1107 passed. UBT build `UBT_EXIT_CODE=0`
  (C++ automation compile-verified only).
- **NOT run:** live M7 Scenarios 1–8, no `UnrealEditor` launch, no
  workflow/action-runner tests, no Blender.

## M9 — Live recovery readiness & scenario harness (pre-flight)

Stage 18 (Unreal cross-process render-job recovery) M9 is a PRE-FLIGHT milestone
that prepares for the first authorized live execution of Contract V1 §33 Scenarios
1–8 WITHOUT running any live scenario.

- **Deterministic scenario harness** (`planning/unreal_live_scenario_harness.py`):
  Scenarios 1–8 modeled as declarative specs (initial state, process/session
  condition, journal condition, artifact condition, quiescence, expected case /
  lifecycle / recovery_status / receipt / finalization / retry). Each is driven
  through the REAL `UnrealRenderRecoveryCoordinator` and the declared outcome is
  asserted to equal the coordinator's actual decision (no invented semantics).
- **Pre-flight checks** (`planning/unreal_live_preflight.py`, `LivePreflight`):
  P1–P14 gates (UE 5.6 project, capability schema, journal location, output
  isolation, receipt store, session identity, contained Job Object, supervisor/
  quiescence, authorization continuity, attempt_nonce, attempt_ordinal, HMAC,
  artifact hashing/PNG, clean store). Non-mutating, `all_pass()`/`blockers()`.
- **Checklist** (`docs/LIVE_EXECUTION_CHECKLIST.md`): setup, order of operations,
  evidence per gate, PASS/FAIL/STOP, cleanup, no-accidental-retry rules.
- **Safety-proof tests** (tests/m9, 34): prove the harness cannot authorize a
  render, resubmit an uncertain job, synthesize success, mint a receipt without
  verified evidence, bypass quiescence, or bypass HMAC/attempt_ordinal
  verification.
- **Readiness matrix**: S1/S5/S6/S7 READY_FOR_LIVE (only real UE runtime
  unproven); S2/S4/S8 BLOCKED (live outcome depends on real torn/duplicated
  journal states); S3 NOT_PROVEN (needs a real in-flight+restart state).
- **Live-transition boundary audit** (docs/UNREAL_M9_READINESS.md): real named
  pipe, real Job Object quiescence, real GetProcessTimes identity, real durable
  journal under kill, C++ automation (compile-verified only), real render output,
  real wall-clock deadline — all safe deterministic but unproven live.
- **Deterministic validation**: tests/m9 34, tests/m6 79, tests/m7 59, tests/m8 19,
  full `pytest -m "not integration"`. No C++ changes in M9 → no UBT rebuild.
- **NOT run**: any live scenario, UnrealEditor launch, workflow/action-runner test,
  Blender, or kill/restart. Cross-process recovery remains not-production-capable
  until the human-authorized live §33 execution passes.

## M10 — Live S1 run + remediation of Defects A & B

Stage 18 (Unreal cross-process render-job recovery) M10 was the FIRST authorized
live execution. The corrected live S1 render PASSED against real UE 5.6:
- real MRQ render completed (no crash once launched without -nullrhi);
- FINISHED witness journal written (ACCEPTED→STARTED→FINISHED);
- HMAC-SHA256 attestation verified against the persisted attempt_nonce;
- 23 artifacts independently verified (SHA-256 + size match);
- no synthetic success; zero receipts fabricated; no orphan processes.

Reconciliation then stopped at two independently-demonstrated PRODUCTION defects
(nothing was patched to force a pass mid-run):

Defect A — READ/WRITE transport boundary: `_query_catalog` used `apply_authorized`
(WRITE-only) for the READ `reconcile_render_jobs`, so every live catalog query
raised and failed closed to Case J. Fixed: `adapter.inspect` (READ path) is used.

Defect B — live reconcile catalog dropped M8 attestation fields: the C++ in-memory
registry overlay `ConsolidatedJobs.Add` overwrote the richer journal-derived
attested entry (attempt_ordinal, entry_digest, session identity, phase_history,
output_manifest) with a sparse snapshot. Fixed: the overlay no longer clobbers an
existing journal-derived entry, and relays attempt_ordinal from the live state.

Remediation: tests/m10 (17) + C++ `FAtlasUE56ReconcileAttestationPreservedTest`
(UBT-compiled). Existing test adapters updated to wire the reconcile read through
`inspect`. Full `pytest -m "not integration"` = 1158 passed. UBT_EXIT_CODE=0.

NO live scenario executed during remediation. S1 must be rerun after merge before
S2–S8 (which remain NOT EXECUTED). Failed/blocked S1 forensic evidence preserved.

## M10 remediation — Defect C (adapter argument boundary)

Off the back of the live S1 verification rerun (which proved Defect A READ/inspect
and Defect B catalog-attestation-preservation are RESOLVED live), reconciliation was
still blocked by a NEW production defect:
- Defect C root cause: `UnrealAdapterProduction._build_request` copied
  `operation.arguments` verbatim and carried `entity_ids` only at the transport
  top level — it never relayed them into the nested `arguments.entity_ids` the C++
  `ValidateRequest` requires for every operation. The live engine returned
  `ERR_MISSING_ARGUMENT` ("arguments.entity_ids must be an array of strings").
- Fix (adapter transport boundary, generic): `_build_request` now injects nested
  `arguments["entity_ids"]` from the operation's `entity_ids` (verbatim, no
  synthesis) and FAILS CLOSED if an existing `arguments.entity_ids` conflicts.
  No C++ change; authorization/correlation/schema checks unchanged; coordinator
  unaware of transport internals.
- Deterministic regression: tests/m10 Defect C (7), derived from the exact live
  failure (EngineLikeTransport enforces the nested entity_ids contract). Full
  `pytest -m "not integration"` = 1165 passed. UBT not required (Python-only).
- Live status: A PASS, B PASS, C fixed (S1 must be rerun after merge before S2-S8).
  No live scenario was executed during remediation; S2-S8 NOT executed.

## M10 remediation — Defect D (frame-count mismatch)

Off the back of the live S1 final run (which proved Defects A/B/C RESOLVED live),
reconciliation reached the final independent evidence-verification gate and
correctly failed closed because the authoritative frame count was 24 while the real
MRQ render produced 23 frames (frames 1..23).

Root cause: the Atlas-authorized inclusive frame topology was never transmitted or
applied.
- `submit_render` (Python) did NOT send start_frame/end_frame to Unreal.
- C++ `SubmitRender` built the MRQ job from the persisted AtlasRenderConfig + engine
  defaults and never applied the authorized range -> MRQ used a half-open end bound
  and dropped frame 24.

Fix:
- Python `UnrealRenderSubmissionService.submit_render` now sends
  `start_frame`/`end_frame` from expected_output_spec.
- C++ `SubmitRender` parses them and applies the inclusive [start, end] to the MRQ
  job (bUseCustomPlaybackRange, CustomStartFrame, CustomEndFrame); missing values
  keep engine defaults.
- Evidence verifier NOT weakened: frame_count = end - start + 1 remains mandatory;
  a 23-frame result still fails closed.

Regression: tests/m10 Defect D (7) prove the transmit, the inclusive engine
semantics, 24 passes, 23 still fails, and no verifier relaxation. Full
`pytest -m "not integration"` = 1172 passed. UBT_EXIT_CODE=0 (C++ changed).

Live status: A PASS, B PASS, C PASS, D REMEDIATED (one final S1 rerun required after
merge). No live scenario run during remediation; S2-S8 NOT executed. The 23-frame
render + journal + HMAC + forensics are preserved as diagnostic evidence.

## M10 remediation — Defect D v2 (sequence playback range)

A further fresh live S1 (Run B) proved A/B/C and D-Python-transmit resolved, but
the v1 fix (applying the authorized inclusive range to the MRQ OUTPUT setting)
remained insufficient: MRQ logs "Registering range: [800,19200)" — the SEQUENCE
playback range (80-tick units) — which is the source MRQ enumerates RENDER SHOT
FRAMES from. The output-setting custom range does not change shot enumeration.

Fix (engine boundary, isolation-safe):
- In `SubmitRender`, when Atlas supplies start_frame/end_frame, duplicate the
  source `ULevelSequence` into `GetTransientPackage()` (never mutating the shared
  asset), `SetPlaybackRange(AtlasStartFrame, end-start+1)` (inclusive coverage of
  end; the range upper bound is exclusive), and `Job->SetSequence(transient copy)`.
- Retained the v1 output-setting range (independently reported).
- Also fixed the SAME exclusive-upper-bound off-by-one in `SetSequencerPlaybackRange`

Isolation: mutation targets only a transient duplicate keyed per-job
(`AtlasSeq_<atlas_job_id>_<start>_<end>`); the source sequence asset is untouched;
subsequent jobs cannot inherit a prior job's range.

Verifier remains strict: frame_count = end-start+1; a 23-frame result still fails.
expected_output_spec unchanged.

Regression: tests/m10 Defect D v2 (8) prove the inclusive-conversion
(size = end-start+1, upper = end+1), the transmit, non-mutation of the source
asset, per-job isolation, 24 passes / 23 fails, and no verifier relaxation.
Full `pytest -m "not integration"` = 1180 passed. UBT_EXIT_CODE=0 (C++ changed).

Live status: A PASS, B PASS, C PASS, D-transmit PASS, D v2 REMEDIATED (another
FRESH live S1 rerun required after merge). No live scenario run during remediation;
S2-S8 NOT executed. All 23-frame renders + journals + HMAC + forensics preserved.

## M10 remediation — Defect D v3 (MRQ output-frame range — exclusive upper)

s1_final3 live run proved A/B/C + D-transmit + D-v2 (transient sequence range [1,25)
registered) but STILL 23 files. Investigation of the actual UE 5.6 source
(UMoviePipelinePrimaryConfig::GetEffectivePlaybackRange, MoviePipelineTiming.cpp)
found the authoritative lever: MRQ enumerates OUTPUT frames from the OUTPUT
SETTING's custom range converted to ticks, returning [CustomStart, CustomEnd) with
an EXCLUSIVE upper; the output loop stops before producing at CurrentTickInRoot >=
EndTick. So MRQ produces exactly CustomEndFrame - CustomStartFrame files.

- D-v1 set CustomEndFrame=end (24) -> 24-1 = 23 (off-by-one).
- D-v2 set the SEQUENCE playback range (a transient duplicate), which
  GetEffectivePlaybackRange IGNORES when bUseCustomPlaybackRange is set -> no effect.
- D-v3: set CustomEndFrame = end + 1 (exclusive upper) -> end-start+1 frames
  (1..24 -> 24).

Isolation: the modified output setting is on TransientConfig (a DuplicateObject of
the shared config); the shared/source sequence asset is NEVER mutated; per-job.

Verifier remains strict: frame_count = end-start+1; 23 frames still fails;
expected_output_spec unchanged.

Regression: tests/m10 Defect D3 (9) + updated D2 (8) prove the half-open arithmetic,
the exclusive-upper fix, 24 passes / 23 fails, and no verifier relaxation. Full
`pytest -m "not integration"` = 1189 passed. UBT_EXIT_CODE=0 (C++ changed).

Live status: A PASS, B PASS, C PASS, D-transmit PASS, D-v2 active-but-insufficient,
D-v3 REMEDIATED (another FRESH live S1 rerun required after merge). No live scenario
run during remediation; S2-S8 NOT executed. All forensics preserved.

## Unreal — Current baseline

Unreal Engine 5.6 render configuration, MRQ submission, dynamic job IDs, asynchronous inspection, artifact verification, evidence-bound render receipts, and durable receipt persistence are proven locally for the implemented boundary.

Cross-process Unreal render-job recovery is implemented and merged via Milestone 4 (PR #67); the authoritative independent evidence-verification boundary via M5 (PR #68); deterministic fault-injection via M6 (PR #70); deterministic hardening via M7 (PR #71); witness attestation + engine attempt identity via M8 (PR #72). M9 adds pre-flight scenario/readiness tooling. All are regression-verified but NOT yet declared production-capable: live UE 5.6 restart/recovery Scenarios 1–8 (Contract V1 §33) require explicit human authorization and must not be run as workflow/action-runner tests.

## Development rules

- Qwen proposes; Atlas validates and authorizes; Blender/Unreal execute through controlled adapters.
- Never give Qwen direct execution or authorization authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from a transport/write response alone.
- Preserve independent verification and the evidence ledger.
- Keep engine-specific execution behind adapter/tool boundaries.
- Preserve canonical Digital Twin identity separately from DCC/engine artifacts.
- Keep dependency-aware execution serial until concurrency is independently justified.
- Keep lineage/provenance separate from execution authority.
- Keep project handoffs and readmes synchronized with verified milestones.
