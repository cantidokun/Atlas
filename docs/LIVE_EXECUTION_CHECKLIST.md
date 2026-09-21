# Live Execution Checklist — M7 Scenarios 1–8 (Authorized Run Procedure)

**Status: PRE-FLIGHT / NOT AUTHORIZED TO RUN.**

This checklist is the authoritative human procedure for the FIRST authorized live
execution of Contract V1 §33 Scenarios 1–8 against UE 5.6. It is a runbook: it
does NOT launch Unreal, does NOT submit a render, and does NOT run any live
scenario by itself. Nothing here may be executed unless a human operator
explicitly authorizes the live run. Deterministic pre-flight checks come from
`planning/unreal_live_preflight.py` (`LivePreflight`); scenario expectations come
from `planning/unreal_live_scenario_harness.py` (`SCENARIOS`).

**Revision note (phased arming).** The former single "P1–P14, all before launch"
sequence was internally inconsistent: three gates (authorization_id,
attempt_nonce, attempt_ordinal) describe the durable `AtlasRenderJobRecord`, which
does not exist until the human authorization step creates the render intent, and
the capability gate attempted a live capability RPC before an engine existed.
Arming is therefore explicitly phased. Gate keys are unchanged; the former
P1–P14 map as: P1→A1, P2→A2 (structural seam) + B1 (live negotiation), P3→A3,
P4→A4, P5→A5, P6→A6, P7→A7, P8→A8, P9→C1, P10→C2, P11→C3, P12→A9, P13→A10,
P14→A11.

---

## 1. Phased arming prerequisites

Gates are grouped by the phase in which their inputs genuinely exist. Evaluated
with `LivePreflight.run_phase(<phase>)`; the union view remains
`run()` / `all_pass()` / `blockers()`.

### Phase A — PRE-ENGINE ARM (`PreflightPhase.PRE_ENGINE`)

Evaluable before Unreal is launched. Performs **no** engine RPC (no engine exists
yet) and requires **no** durable record. Stop the run if
`LivePreflight.blockers(PreflightPhase.PRE_ENGINE)` is non-empty; the `live_only`
Phase A gates are confirmed by the operator in Phase B, when the engine and
supervisor actually exist.

| # | Gate key | Prerequisite | How to verify | Stop if |
|---|----------|--------------|---------------|---------|
| A1 | `ue56_project` | UE 5.6 project/binary present | `AtlasUnrealHarness.uproject` exists; `UnrealEditor-Cmd.exe` in `UE_5.6/Engine/Binaries/Win64/` | Missing binary |
| A2 | `capability_schema` | Capability-query **SEAM** available (no live RPC) | the production adapter exposes callable `query_capabilities` + `assert_recovery_capable` | Seam absent (policy is never re-implemented in pre-flight) |
| A3 | `journal_location` | Durable journal location configured | `<ProjectDir>/AtlasWitnessJournal/` (outside `Saved/`) | Missing/unwritable |
| A4 | `output_isolation` | Output isolation root configured | authorized output parent + `<atlas_job_id>/` namespace | Root missing |
| A5 | `receipt_store` | Receipt store path configured | receipt store dir writable | Missing/unwritable |
| A6 | `session_identity` *(live_only)* | Process/session identity capability | Windows `GetProcessTimes` path (process_creation_time_utc) | Unavailable |
| A7 | `contained_job_object` *(live_only)* | Contained Job Object mode available | `deployment_mode == CONTAINED_JOB_OBJECT`, supervisor Job Object handle | Only UNCONTAINED available |
| A8 | `supervisor_quiescence` *(live_only)* | Supervisor / quiescence capability | supervisor can `query_active_processes()` | No supervisor |
| A9 | `hmac_verification` | HMAC witness verification availability | canonical HMAC module importable and keyed by nonce | Import/digest fails |
| A10 | `artifact_hash_png` | Artifact hashing / PNG verification availability | sha256 + `verify_png_completeness` available | Import fails |
| A11 | `clean_store` *(live_only)* | Clean recovery-store state | `AtlasRenderJobStore.list_job_ids() == []` before arming | Pre-existing records |

### Phase B — POST-ENGINE / PRE-SUBMISSION CHECK (`PreflightPhase.POST_ENGINE`)

Evaluable only after Unreal is running and the named-pipe transport is reachable.
Stop the run unless `LivePreflight.all_pass(PreflightPhase.POST_ENGINE)` is True
(live conditions are in scope here, so a live-only failure is a hard stop).

| # | Gate key | Prerequisite | How to verify | Stop if |
|---|----------|--------------|---------------|---------|
| B1 | `capability_negotiation` | Live capability negotiation through the production seam | `LivePreflight(..., authorization_id=<operator-declared id>)` delegates to `adapter.assert_recovery_capable(authorization_id)` | Negotiation fails, seam absent, or no authorization context is declared |
| B2 | operator confirmation of Phase A `live_only` gates | Real engine process, named pipe `\\.\pipe\AtlasUnrealTransport`, real Job Object handle with `query_active_processes()`, real journal dir | `tasklist` + pipe probe + supervisor query | Any of them absent |

B1 **delegates** capability policy: `assert_recovery_capable` is the existing
production recovery authority (also invoked inside
`UnrealRenderSubmissionService.submit_render` step 8 and by the recovery
coordinator). The pre-flight never re-implements capability policy, never invents
an authorization id, and a B1 pass does **not** replace the authoritative,
record-bound assertion performed at submission time.

### Phase C — INTENT / IDENTITY CHECK (`PreflightPhase.POST_INTENT`)

Evaluated only after the human authorization step has created the durable
`AtlasRenderJobRecord`. Stop the run unless
`LivePreflight.all_pass(PreflightPhase.POST_INTENT)` is True. These three remain
hard requirements before submission; the values are **never fabricated** to
satisfy pre-flight.

| # | Gate key | Prerequisite | How to verify | Stop if |
|---|----------|--------------|---------------|---------|
| C1 | `authorization_continuity` | Durable record has non-empty `authorization_id` | load the durable record | Missing |
| C2 | `attempt_nonce` | record has non-empty `attempt_nonce` (HMAC key) | load the durable record | Missing |
| C3 | `attempt_ordinal` | record has int `attempt_ordinal` | load the durable record | Missing/non-int |

### Global rules

Hard blockers stop execution: any non-`live_only` failure in Phase A
(`blockers(PRE_ENGINE)`), any failure at all in Phase B
(`all_pass(POST_ENGINE) == False`), or any failure in Phase C
(`all_pass(POST_INTENT) == False`) STOPS the run. The operator must additionally
confirm the `live_only` gates at the moment the corresponding live condition first
exists. Do not bypass, waive, or manually satisfy a gate.

## 2. Exact order of operations

1. **Pre-engine arm (Phase A):** run `LivePreflight(...).blockers(PRE_ENGINE)`.
   Do not proceed if it is non-empty.
2. **Capture baseline evidence:** `git rev-parse HEAD`, exact UE binary hash,
   journal dir listing, store listing (must be empty), receipt store listing.
3. **Start Unreal in CONTAINED_JOB_OBJECT** via the supervisor (human operation).
   Verify process presence (`tasklist | grep -i unreal`), the named pipe
   `\\.\pipe\AtlasUnrealTransport`, and the live supervisor Job Object handle;
   this confirms the Phase A `live_only` gates (A6–A8, A11).
4. **Confirm live capability negotiation / recovery capability (Phase B):** run
   `all_pass(POST_ENGINE)` with the operator-declared authorization id. Do not
   proceed on failure.
5. **Human authorization + durable intent creation:** authorize ONE render and
   create the durable intent record (PENDING → SUBMITTED) with its nonce and
   ordinal through `UnrealRenderSubmissionService`'s existing persistence path.
6. **Validate authorization/attempt identity (Phase C):** run
   `all_pass(POST_INTENT)` against the durable record. Do not fabricate values.
7. **Submit exactly one render** through `UnrealRenderSubmissionService`. Persist
   the raw `submit_render` response envelope immediately (job id/atlas job id)
   before any diagnostic output. (Submission performs the authoritative
   capability assertion and is the only path permitted to transmit.)
8. **Per-scenario step** (Scenario 1–8 as authorized) — see §3.
9. **Run reconciliation** via `UnrealRenderRecoveryCoordinator.reconcile_single_job`
   (single job) and capture the `RecoveryDecisionResult`.
10. **Capture evidence at every gate** (see §4).
11. **Cleanup** (see §7).

## 3. Scenario operations (authorized live steps)

Each scenario runs the recovery path and compares the REAL coordinator decision to
the harness's declared expectation (`planning/unreal_live_scenario_harness.py`).

- **S1 Normal render:** submit → let UE finish → reconcile → expect Case B →
  `FINALIZED` + exactly 1 receipt → provenance.
- **S2 Unreal restart during render:** kill UE mid-render → reconcile → expect
  WAITING_FOR_ENGINE (or fail closed) → NO receipt.
- **S3 Atlas restart during render:** UE continues while Atlas restarts → reconcile
  the discovered durable job → expect Case A re-attach → NO duplicate submission.
- **S4 Both restart during render:** kill both → reconcile → expect Case J /
  RECOVERY_FAILED → NO receipt.
- **S5 Render finishes while Atlas down:** let UE finish → restart Atlas → reconcile
  → expect Case B from preserved journal → `FINALIZED` + 1 receipt.
- **S6 Artifact, no engine evidence:** artifact on disk, no journal → expect Case D
  → `ORPHANED_ARTIFACTS_PRESENT` → NO receipt.
- **S7 Missing artifact after terminal claim:** journal FINISHED, artifact absent →
  expect Case G → `FAILED` → NO receipt.
- **S8 Duplicate/stale identity:** two journals for one atlas_job_id → expect Case H
  → `RECOVERY_FAILED` → NO adoption.

Note on S1/S5 quiescence: the coordinator's Case K gate runs before any evidence
processing, and S1 carries `quiescent=True`, so the live ordering is
render-finishes → engine shut down → `query_active_processes() == 0` → reconcile.

The deterministic harness already asserts each declared expectation against the
coordinator (tests/m9). The live run is the ONLY thing that additionally proves the
REAL UE 5.6 process produces the expected journal bytes / session identity / file
bytes.

## 4. Evidence to capture at every gate

At each decision point, capture and archive:

- The durable record JSON (all authoritative fields + digest).
- The reconcile catalog `known_jobs` (or PARTIAL/UNREADABLE status).
- The candidate journal entry (phase_history, attempt_ordinal, entry_digest).
- The computed-vs-expected HMAC (never log the nonce itself).
- The independent artifact verification: file path, size, sha256, `verify_png_completeness`.
- The receipt (if issued) — full envelope + digest.
- The `RecoveryDecisionResult` (case_classified, lifecycle/recovery before + after,
  repaired_from_receipt, failure_reason).
- Process/session identity observed vs the record's origin (editor session id,
  process id, process_creation_time_utc).
- Quiescence result: `ProcessQuiescenceResult` (is_quiescent, active_count, mode).
- The phase-scoped pre-flight results (`to_dict(include_phase=True)`) for Phases
  A, B and C.

## 5. What constitutes PASS

Every expected field in the scenario table matches the actual `RecoveryDecisionResult`
AND the receipt/recovery-status/lifecycle expectations in §3 AND the durable store
reflects the terminal/held state exactly once.

## 6. What constitutes FAIL / requires IMMEDIATE STOP

- Any scenario where the coordinator mints a receipt when `receipt_permitted == False`.
- Any scenario that resubmits / mints a new attempt for an unresolved job.
- Any synthetic success (success not backed by verified evidence + disk bytes).
- Any bypass of quiescence, HMAC, or attempt_ordinal verification.
- Any divergence between the observed session identity and the record's origin.
- A bad HMAC treated as ordinary evidence.
- Any workflow/action-runner test, live launch, or Blender run that was not
  explicitly authorized.
- Any attempt to bypass, waive, or manually satisfy a pre-flight gate, or to
  fabricate an authorization id / nonce / ordinal to make a phase pass.
- **STOP IMMEDIATELY and do not proceed** to the next scenario on any of the above.

## 7. Cleanup requirements

- Delete/archive all transient job state, journal files, receipt files, artifacts
  created by the run (or move to a designated archive root).
- Restore `AtlasRenderJobStore` to the empty pre-run baseline for the next scenario.
- Remove the Job Object handle(s); confirm `query_active_processes() == 0`.
- Delete the disposable `.bat` build wrapper if any was created.
- Do NOT leave a `persisted_job_id.txt`-style ad-hoc file; route everything through
  `UnrealRenderSubmissionService` / `AtlasRenderJobStore`.

## 8. Rules preventing accidental retry / resubmission

- Only ONE authorized submission per attempt; the harness/coordinator never submits.
- `reconcile_single_job` is a READ + local transition; it never calls submit.
- A receipt is created ONLY via `store.publish_verified_receipt` (Case B, verified
  evidence required).
- Missing/ambiguous/legacy witnesses fail closed to RECOVERY_FAILED / holds — never
  a retry.
- Deadlines enforce EXHAUSTED with no retry once the ambiguity window closes.
- No `attempt_nonce` value is ever written to a journal, receipt, manifest, or log.
