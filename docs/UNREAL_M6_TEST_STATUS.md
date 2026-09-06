# Milestone 6 — Deterministic Fault-Injection/Concurrency Test Suite: Honest Coverage & Status

This document is the **authoritative status** of Milestone 6 (Contract V1 §31 Required
Deterministic Tests and §32 Required C++ Unreal Automation Tests). It supersedes any
earlier wording that over-claimed contract coverage. It distinguishes, per item:

- **FULLY EXERCISED** — a test deterministically drives the positive contract behavior
  AND its fail-closed path (or both are directly asserted against the real boundary).
- **PARTIALLY EXERCISED** — the fail-closed/safety behavior is verified, but the full
  positive contract behavior is not (because a production seam is missing, a gate is
  not isolable through the coordinator, or a runtime-only C++ test is compile-verified
  but not executed under the editor in M6).
- **CANT EXERCISE (production missing)** — a contract requirement whose production
  implementation does not exist or directly contradicts M6's deterministic constraints.
- **DEFECT FOUND BY M6** — M6 exposed a real production defect; M6 asserts the safe
  fail-closed consequence, and the positive path is explicitly NOT claimed as verified.

M6 is a **test-correctness/status-honesty pass**: it does not modify production behavior
(git diff contains only `tests/m6/`, two C++ test-scope files + header, and docs). No
workflow/action-runner tests; no live Unreal/Blender execution; M7 live Scenarios 1–8 not run.

---

## §31 Required Deterministic Tests — status per item

| # | Contract §31 item | M6 test(s) | Status | Notes |
|---|---|---|---|---|
| 1 | record validation and immutable round-trip | `item01_immutable_roundtrip_preserves_authoritative_fields`, `item01_record_rejects_traversal_in_job_id` | **FULLY EXERCISED** | digest recompute on tamper + round-trip asserted |
| 2 | atomic store update and corruption detection | `item02_atomic_roundtrip_and_store_envelope`, `item02_corruption_detected_and_quarantined_non_destructive`, `item02_authoritative_digest_mismatch_quarantined` | **FULLY EXERCISED** | atomic replace + non-destructive quarantine asserted |
| 3 | concurrent record update conflict | `item03_stale_writer_rejection_is_deterministic`, `item03_concurrent_update_preserves_monotonicity_and_no_corruption`, `item03_coordinator_fencing_token_monotonic`, `item03_two_coordinators_cannot_both_finalize`, `item03_rogue_unmanaged_job_detected_not_adopted` | **FULLY EXERCISED** | `two_coordinators` actually re-derives a second receipt and asserts the second store-gated publication is REJECTED (not just that one receipt exists) |
| 4 | coordinator single-instance enforcement | `item04_coordinator_single_instance_lock`, `item04_per_job_claim_excludes_concurrent_worker` | **FULLY EXERCISED** | coordinator + per-job lock exclusion asserted |
| 5 | duplicate `submit_render` serialization | `item05_duplicate_submission_is_serialized_idempotently`, `item05_duplicate_with_conflicting_parameters_rejected` | **FULLY EXERCISED** | same-id → 1 dispatch; conflict → rejected |
| 6 | terminal-state non-regression | `item06_terminal_state_cannot_regress`, `item06_verify_finalized_requires_attributable_job_identity` | **FULLY EXERCISED** | terminal regress blocked; finalize requires job identity |
| 7 | journal malformed/partial/unreadable handling | `item07_unreadable_journal_is_case_j_pending`, `item07_partial_journal_is_case_j_pending`, `item07_catalog_corruption_read_error_is_case_j` | **PARTIALLY EXERCISED** | Python asserts fail-closed Case J + RECOVERY_PENDING. The §32 C++ `MalformedJournalHandlingTest` additionally asserts `journal_status==PARTIAL` on a malformed journal file but is only **compile-verified** (not executed under editor in M6) |
| 8 | journal session mismatch | `item08_session_identity_mismatch_fails_closed` | **PARTIALLY EXERCISED** | asserted to surface as `UNTRUSTED_WITNESS` (HMAC desync) + RECOVERY_FAILED. Not isolable as a distinct "session binding" gate through the coordinator in Python |
| 9 | journal identity mismatch | `item09_atlas_job_id_mismatch_not_adopted`, `item09_sequence_asset_path_mismatch_case_ef`, `item09_config_digest_mismatch_case_ef`, `item09_process_creation_time_mismatch_fails_closed` | **PARTIALLY EXERCISED** | sequence/config drill the `Case E/F` positive binding gate. `atlas_job_id` mismatch → not a candidate (Case D, no adoption). process_creation_time → `UNTRUSTED_WITNESS` (HMAC desync). Full "identity binding" positive is split across gates |
| 10 | acceptance-before-launch invariant | `item10_finished_candidate_never_adopted_without_accepted_evidence` | **PARTIALLY EXERCISED** | fail-closed asserted (never finalized, no receipt). The reason is a missing/desynced attestation; the ACCEPTED-phase enforcement specifically is not isolable in Python (the §32 C++ `WitnessJournalAcceptedBeforeDispatchTest` covers it but is compile-verified only in M6) |
| 11 | terminal FINISHED journal requirement | `item11_terminal_requires_finished_journal_attestation`, `item11_finished_journal_hmac_roundtrip_is_reproducible` | **FULLY EXERCISED** | bad-HMAC → `UNTRUSTED_WITNESS` + RECOVERY_FAILED, no receipt; HMAC determinism asserted |
| 12 | artifact output-directory isolation | `item12_*` (traversal, outside-dir, ADS/device-namespace, extra-file, duplicate) | **FULLY EXERCISED** | each directly asserted against `verify_render_job_evidence` |
| 13 | artifact hash match/mismatch | `item13_*` (hash mismatch, size mismatch, stale-replay) | **FULLY EXERCISED** | asserted against the verifier |
| 14 | truncated PNG rejection | `item14_*` (truncated, corrupt IDAT, non-signature) | **FULLY EXERCISED** | PNG/IDAT completeness asserted |
| 15 | exact expected frame/output topology | `item15_*` (single, multiframe, count-mismatch, missing keys, bool-as-int) | **FULLY EXERCISED** | positive + fail-closed against verifier |
| 16 | Case A–J reconciliation | `item16_case_a`, `item16_case_b`, `item16_case_c`, `item16_case_h`, `item16_case_j`, `item16_case_k`, `item16_quiescence_ambiguity_uncontained`, `item16_*rogue` | **PARTIALLY EXERCISED** | Cases A,B,C,H,J,K + quiescence asserted. **Cases D and E/F are exercised via the journal/artifact modules** (`item17_case_d`, `item09_*case_ef`). Cases G/I are partial/inferred: G is the general fail-closed path (see item 17 / HMAC tests); I is not separately asserted |
| 17 | artifact-only recovery never produces a receipt | `item17_artifact_only_no_receipt_case_d`, `item17_rogue_unmanaged_job_not_silently_adopted` | **FULLY EXERCISED** | Case D + non-mutation + no receipt; rogue not adopted |
| 18 | authorization revalidation for new execution | `item18_authorization_id_binds_immutably_and_blocks_swap`, `item18_new_execution_requires_existing_authorization_path` | **FULLY EXERCISED** | auth-id immutable bind; empty-auth rejected |
| 19 | receipt create-if-absent race | `item19_receipt_create_if_absent_is_atomic`, `item19_concurrent_receipt_publish_never_corrupts`, `item19_receipt_digest_collision_fails_closed` | **FULLY EXERCISED** | `create_if_absent_is_atomic` now asserts a SECOND store-gated publication of the same receipt is rejected by fencing (not merely that one file exists); concurrency never corrupts; digest collision → `AtlasRenderJobStoreError` |
| 20 | crash between receipt persistence and record finalization | `item20_receipt_first_repairs_finalization_after_crash`, `item20_receipt_first_rejects_identity_conflict`, `item20_crash_inside_publish_never_leaves_partial_receipt`, `item20_receipt_store_rejects_missing_required_fields`, `item20_receipt_must_bind_verified_evidence_identity` | **FULLY EXERCISED** | receipt-first repair, identity-conflict rejection, atomic partial-file fail-closed, verified-evidence gate |
| 21 | stale durable writer rejection | `item21_stale_writer_via_per_job_claim_fencing` (+ item03/22) | **FULLY EXERCISED** | revision CAS + claim fencing + stale-write rejected |
| 22 | transport-unavailable waiting behavior | `item22_transport_timeout/disconnect_waits_without_resubmission`, `item22_uncertain_wait_does_not_mutate_to_terminal_or_resubmit`, `item22_stale_writer_rejected_after_waiting_transition` | **FULLY EXERCISED** | no auto-retry; single dispatch; durable intent retained |
| 23 | execution deadline expiry | `item23_deadlines_are_durably_persisted_on_record`, `item23_expired_deadline_never_auto_resubmits_failclosed_observed`, `item23_expired_dir_does_not_mint_terminal_success` | **PARTIALLY EXERCISED / DEFERRED** | persistence + no-auto-retry asserted. **The contract's `EXHAUSTED` expired-window transition is NOT exercised because production has no such gate** (deadline stored but unenforced). See report §C. Must be remediated in M7 |
| 24 | catalog→disk→catalog stability race | `item24_*` (framed tamper, framed well-formed defect, unframed Case B, unstable-across-passes) | **PARTIALLY EXERCISED / DEFECT** | **M6 found a production defect**: `_query_catalog`'s framed check cannot `json.dumps` the frozen `mappingproxy` `known_jobs`, so ANY framed response (tampered OR well-formed) collapses to Case J. M6 asserts the SAFE fail-closed outcome (never adopted, no receipt) and does **NOT** claim the positive framing-verification path is exercised. Remediation required in M7. The stability behavior (unstable→not-finalize then retry) IS exercised in the unframed path |
| 25 | incompatible wire/capability version rejection | `item25_missing_recovery_capability_rejects_dispatch`, `item25_coordinator_engine_capability_unavailable_waits`, `item25_wire_schema_version_guarded_at_contract` | **FULLY EXERCISED** | capability gate blocks dispatch; capability-unavailable → WAITING_FOR_ENGINE; `schema_version=0` rejected at contract |

---

## §32 Required C++ Unreal Automation Tests — status per item

| §32 item | Automation (C++ AST) | Status |
|---|---|---|
| process-incarnation/session identity | `FAtlasUE56SessionIdentityPurityTest` | **preexisting**; compile-verified (module build). Not executed under editor in M6 |
| journal `ACCEPTED` before MRQ dispatch | `FAtlasUE56WitnessJournalAcceptedBeforeDispatchTest` | **preexisting**; compile-verified |
| journal `FINISHED` terminalization | `FAtlasUE56WitnessJournalFinishedWithHashAttestationTest` (+ `...RenderJobBoundaryTest` finalize invariants) | **preexisting**; compile-verified |
| per-file manifest/hash generation | `...RenderJobBoundaryTest` + `...FinishedWithHashAttestation` (manifest size/SHA non-empty) | **preexisting**; compile-verified |
| duplicate job identity handling | `...SubmitRenderDuplicateSuppression` + `...SubmitRenderConflictRejection` | **preexisting**; compile-verified |
| journal append/history retention | — | **CANT EXERCISE (contract/implementation gap)**. C++ `WriteJournalEntry` overwrites a single `<atlas>__<unreal>.json` per job-pair (`MOVEFILE_REPLACE_EXISTING`); there is no append-only `phase_history` array nor a monotonic `phase_sequence` as Contract §30/§37 requires. **No M6 test cements this divergence.** Requires C++ production remediation (M7) |
| malformed journal handling | `FAtlasUE56MalformedJournalHandlingTest` (**NEW**) | **PARTIALLY EXERCISED** — **compile-verified** (UBT build succeeded); asserts `journal_status==PARTIAL` on a malformed entry. Not executed under the editor in M6 |
| reconcile catalog completeness | `FAtlasUE56ReconcileCatalogReportingTest` (**preexisting**) + Python `item16`/`item24` | **PARTIALLY EXERCISED** — C++ compile-verified; Python asserts Case J/B paths deterministically |
| schema/capability reporting | `FAtlasUE56CapabilitySchemaReportingTest` (**NEW**) | **PARTIALLY EXERCISED** — **compile-verified**; asserts `schema_version==1` + `durable_journal`/`reconcile_render_jobs` capabilities present. Not executed under editor in M6 |

**C++ execution note:** no UE 5.6 editor automation test is RUN in M6 (that would be live
Unreal execution). The C++ additions are **compile-verified** via `UnrealBuildTool`
(module build succeeded) and their runtime assertions are **mirrored by the deterministic
Python suite**. Runtime execution of the C++ automation is an M7 build/validation gate.

---

## Verified test counts (this corrective pass)

- M6 suite: **79 passed** (no function-count change; several were strengthened/renamed).
- Existing M4/M5 Unreal suites: pass (re-run).
- Full `pytest -m "not integration"`: **1029 passed**.

## Production defects discovered by M6

1. **Framed-catalog integrity path is inert (mappingproxy).** `_query_catalog` in
   `planning/unreal_render_recovery_coordinator.py` cannot `json.dumps` the frozen
   `mappingproxy` `known_jobs`, so any framed reconcile response fails to Case J.
   Safety preserved; positive path unverified. → M7 production remediation.
2. **C++ journal is overwrite-only, not append-only.** `WriteJournalEntry` writes one
   `<atlas>__<unreal>.json` per pair with `MOVEFILE_REPLACE_EXISTING`; no
   `phase_history`/monotonic `phase_sequence` per Contract §30/§37. → M7 remediation.
3. **`execution_deadline` is stored but unenforced.** No `EXHAUSTED` expiry transition
   exists. → M7 remediation.

## M7 status

Live UE 5.6 restart/recovery **Scenarios 1–8 are NOT run** and require explicit
authorization. No workflow/action-runner tests are run.