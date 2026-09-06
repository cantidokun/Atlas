# Live Execution Checklist — M7 Scenarios 1–8 (Authorized Run Procedure)

**Status: PRE-FLIGHT / NOT AUTHORIZED TO RUN.**

This checklist is the authoritative human procedure for the FIRST authorized live
execution of Contract V1 §33 Scenarios 1–8 against UE 5.6. It is a runbook: it
does NOT launch Unreal, does NOT submit a render, and does NOT run any live
scenario by itself. Nothing here may be executed unless a human operator
explicitly authorizes the live run. Deterministic pre-flight checks come from
`planning/unreal_live_preflight.py` (`LivePreflight`); scenario expectations come
from `planning/unreal_live_scenario_harness.py` (`SCENARIOS`).

---

## 1. Setup prerequisites (ALL must be TRUE before arming)

| # | Prerequisite | How to verify | Stop if |
|---|--------------|---------------|---------|
| P1 | UE 5.6 project/binary present | `AtlasUnrealHarness.uproject` exists; `UnrealEditor-Cmd.exe` in `UE_5.6/Engine/Binaries/Win64/` | Missing binary |
| P2 | AtlasTransportServer capability schema advertised | capability RPC returns render/recovery caps | Capability query fails |
| P3 | Durable journal location exists | `<ProjectDir>/AtlasWitnessJournal/` exists (outside `Saved/`) | Missing/unwritable |
| P4 | Output isolation root configured | authorized output parent + `<atlas_job_id>/` namespace | Root missing |
| P5 | Receipt store path configured | receipt store dir writable | Missing/unwritable |
| P6 | Process/session identity available | Windows `GetProcessTimes` path (process_creation_time_utc) | Unavailable |
| P7 | Contained Job Object mode available | `deployment_mode == CONTAINED_JOB_OBJECT`, supervisor Job Object handle | Only UNCONTAINED available |
| P8 | Supervisor / quiescence capability | supervisor can `query_active_processes()` | No supervisor |
| P9 | Authorization continuity | durable record has non-empty `authorization_id` | Missing |
| P10 | attempt_nonce handling | record has non-empty `attempt_nonce` (HMAC key) | Missing |
| P11 | attempt_ordinal propagation | record has int `attempt_ordinal` | Missing/non-int |
| P12 | HMAC witness verification | canonical HMAC module importable and keyed by nonce | Import/digest fails |
| P13 | Artifact hashing / PNG verification | sha256 + `verify_png_completeness` available | Import fails |
| P14 | Clean recovery-store state | `AtlasRenderJobStore.list_job_ids() == []` before arming | Pre-existing records |

`LivePreflight.all_pass()` must return True for every non-`live_only` gate, and the
operator must confirm the `live_only` gates at run time. Any hard blocker
(`blockers()` non-empty) STOPS the run.

## 2. Exact order of operations

1. **Arm gate:** confirm P1–P14. Do not proceed past any FAIL.
2. **Capture baseline evidence:** `git rev-parse HEAD`, exact UE binary hash,
   journal dir listing, store listing (must be empty), receipt store listing.
3. **Start Unreal in CONTAINED_JOB_OBJECT** via the supervisor (human operation).
   Verify process presence (`tasklist | grep -i unreal` and the named pipe
   `\\.\pipe\AtlasUnrealTransport`).
4. **Authorize submission** (human): create the durable intent record (PENDING →
   SUBMITTED) with nonce + ordinal, then submit ONE render through
   `UnrealRenderSubmissionService`. Persist the raw `submit_render` response
   envelope immediately (job id/atlas job id) before any diagnostic output.
5. **Per-scenario step** (Scenario 1–8 as authorized) — see §3.
6. **Run reconciliation** via `UnrealRenderRecoveryCoordinator.reconcile_single_job`
   (single job) and capture the `RecoveryDecisionResult`.
7. **Capture evidence at every gate** (see §4).
8. **Cleanup** (see §7).

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