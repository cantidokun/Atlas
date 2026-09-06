# M10 Remediation — Defects A + B (live-reconciliation blockers)

## Live S1 status (context)

The corrected live S1 render PASSED:
- real UE 5.6 MRQ render completed; FINISHED journal written (ACCEPTED→STARTED→FINISHED);
- HMAC-SHA256 attestation verified against persisted attempt_nonce;
- 23 artifacts independently verified (SHA-256 + size match);
- no synthetic success; zero receipts fabricated.

Reconciliation was BLOCKED by two independently-demonstrated PRODUCTION defects.
This milestone fixes both WITHOUT rerunning S1 (S1 must be rerun after merge before
S2–S8). No workflow/action-runner tests, no UnrealEditor launch, no Blender.

## Defect A — READ/WRITE transport boundary

### Root cause
`planning/unreal_render_recovery_coordinator.py` `_query_catalog` (line 483) called
`self.adapter.apply_authorized(op, auth_id)` for the READ-only operation
`reconcile_render_jobs`. `UnrealAdapterProduction.apply_authorized` is, correctly,
WRITE-only and raises:
    apply_authorized accepts WRITE operations only
So every live reconciliation catalog query raised → `_query_catalog` returned `None`
→ Case J / RECOVERY_PENDING, never reaching the verified Case B finalization path.

The adapter's own boundary was correct: `inspect()` = READ-only, `apply_authorized()`
= WRITE-only. The coordinator used the wrong method.

### Fix (production)
- `_query_catalog` now calls `self.adapter.inspect(op, auth_id)` (the READ transport
  path). Authorization is unchanged; inspect still requires a valid authorization_id
  on every request (`_build_request`). No second authority path created.
- `apply_authorized` remains restricted to authorized WRITE mutations
  (`submit_render`) and still rejects READ/VERIFY.

### Data path (before → after) — Defect A
- Before: coordinator `_query_catalog` → `adapter.apply_authorized` (WRITE) →
  raises → None → Case J.
- After:  coordinator `_query_catalog` → `adapter.inspect` (READ) → catalog →
  reconciliation proceeds.

## Defect B — live reconcile catalog dropped required M8 attestation fields

### Root cause
In C++ `FAtlasTransportServer::ReconcileRenderJobs` (AtlasTransportServer.cpp), the
in-memory registry overlay built a SPARSE known_jobs entry (job_id, atlas_job_id,
authorization_id, sequence_asset_path, config_digest, output_directory, status,
progress, success, finished, failed, state_source, output_files, output_manifest)
and then `ConsolidatedJobs.Add(Key, JobObj)` REPLACED the richer journal-derived
attested entry for the same atlas_job_id. The durable journal entry carries
`attempt_ordinal`, `entry_digest`, `editor_session_id`, `process_creation_time_utc`,
`phase`, `phase_sequence`, `output_manifest`, `phase_history` — but the overlay
clobbered it with a transient snapshot missing exactly the M8 attestation/session
fields Atlas needs to reconstruct + HMAC-verify the attested witness.

### Fix (production, C++)
1. **Journal wins over transient overlay:** the in-memory overlay now only
   `ConsolidatedJobs.Add(Key, JobObj)` when the key is NOT already present from the
   durable journal scan (`if (!ConsolidatedJobs.Contains(Key))`). The durable journal
   is the authoritative attested witness; the live registry is transient.
2. **Overlay relays real attempt_ordinal:** the overlay now
   `SetNumberField("attempt_ordinal", LiveState->AttemptOrdinal)` from the job state
   it genuinely holds. Nothing synthesized; `entry_digest` is correctly left to the
   journal (it is a per-write journal artifact, not stored on the in-memory state).

### Data path (before → after) — Defect B
- Before: journal-derived attested entry (attempt_ordinal, entry_digest, session,
  phase_history, manifest) → overwritten by sparse in-memory snapshot → catalog
  lacks attestation fields → coordinator cannot HMAC-verify → Case J / UNTRUSTED.
- After:  journal-derived attested entry is preserved (overlay does not clobber);
  overlay still supplies live jobs whose journal is not yet flushed, now including
  attempt_ordinal. Atlas reconstructs + verifies the ACTUAL observed HMAC against the
  persisted attempt_nonce.

## Deterministic tests added (tests/m10/)
- `test_m10_defect_a_transport_boundary.py` (5):
  1. reconcile_render_jobs (read) dispatches through inspect;
  2. read ops cannot dispatch via apply_authorized;
  3. write ops still require authorization;
  4. transport validation/correlation not bypassed;
  5. coordinator `_query_catalog` source uses inspect, not apply_authorized.
- `test_m10_defect_b_catalog_attestation.py` (12):
  1. live-shaped catalog contains attempt_ordinal;
  2. contains entry_digest (HMAC);
  3. contains editor/process identity;
  4. phase_history survives serialization/deserialization intact;
  5. Atlas verifies the actual observed HMAC against persisted attempt_nonce → Case B
     FINALIZED + exactly one receipt;
  6. omission of any required field (attempt_ordinal/entry_digest/session/
     manifest) fails closed (UNTRUSTED_WITNESS / no receipt);
  7. tampered HMAC fails closed;
  8. quiescence not bypassed (Case K).

Also updated existing test adapters that had encoded Defect A:
- `tests/m6/fault_fixtures.py` `ScriptedCoordinatorAdapter`: added an `inspect`
  (READ) method mirroring `apply_authorized`; both route to a shared response
  builder. apply_authorized still tracked for genuine-write assertions.
- `tests/m8/test_m8_witness_gates.py`, `tests/m9/test_m9_scenario_harness.py`,
  `tests/test_unreal_recovery_coordinator.py`: the reconcile-catalog mocks now
  configure `adapter.inspect.return_value` instead of `apply_authorized.return_value`
  (they had encoded the Defect A bug).

C++ automation: `FAtlasUE56ReconcileAttestationPreservedTest` proves a FINISHED
journal entry is NOT clobbered by a matching in-memory overlay — the catalog retains
attempt_ordinal, entry_digest, output_manifest, phase_history. Compile-verified via
UBT (not executed under the editor).

## UBT result
`UBT_EXIT_CODE=0` — UnrealBuildTool module build succeeded on the final tree with the
Defect B C++ fix + the new C++ automation test.

## Regression
- tests/m10: 17 passed
- tests/m6: 79, tests/m7: 59, tests/m8: 19, tests/m9: 34
- all Unreal recovery/evidence/submission/receipt suites: green
- full `pytest -m "not integration"`: 1158 passed

## Explicit statements
- NO live Unreal scenarios were executed during remediation.
- NO UnrealEditor launch; NO Blender; NO workflow/action-runner tests.
- S1 must be rerun after this PR merges, before S2–S8.
- Failed/blocked S1 forensic evidence preserved in live_run_state/ (not overwritten);
  the successful render artifacts + journal were not modified to make defects
  disappear.