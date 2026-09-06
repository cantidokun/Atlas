# Milestone 7 — HARDENING / PRE-FLIGHT

This milestone repairs the three production gaps M6 discovered, as a deterministic
**pre-flight** for the eventual live M7 Scenarios 1–8. It does **NOT** run any live
Unreal restart/recovery scenario and does **NOT** execute `UnrealEditor`. No
workflow/action-runner tests. M7 live Scenarios 1–8 remain a separate
human-authorized gate.

All three fixes are deterministic and compile/regression-verified; the per-item
§31/§32 status is in `docs/UNREAL_M6_TEST_STATUS.md`.

---

## A. Framed catalog integrity

### Before
`UnrealRenderRecoveryCoordinator._query_catalog` shallow-copied the observed state
via `dict(ev.observed_state)` and then, when framing fields were present, attempted
`json.dumps(raw_records, sort_keys=True, ...)` on the still-frozen `mappingproxy`
`known_jobs`. That raised `TypeError: mappingproxy is not JSON serializable`, which
the broad `except` swallowed and converted to `None` → every framed response (valid
or tampered) collapsed to Case J. The positive framing-verification path was inert.

### After
- `canonical_known_jobs_payload(known_jobs)` deep-thaws frozen mappingproxy/tuple
  wrappers and returns the deterministic canonical UTF-8 JSON (`sort_keys=True`,
  compact separators) that framing hashes/measures.
- `_query_catalog` deep-thaws the whole observed state first, then, when **both**
  framing fields are present, validates structural types (positive int length,
  64-hex lowercase SHA-256) and exact equality of `payload_byte_length` and
  `payload_sha256` against the canonical `known_jobs` payload.
- Malformed/incomplete framing (one field missing, mising `known_jobs`, bad length
  type, bad SHA length/hex) **fails closed to UNREADABLE → Case J**.
- Because the C++ server still emits **no** framing fields, unframed catalogs behave
  exactly as before (no framing check) — backward compatible.

### Tests (deterministic, `tests/m7/test_m7_hardening.py`)
| Contract req (task) | Test |
|---|---|
| valid framed catalog accepted | `test_m7_a_valid_framed_catalog_accepted` (+ M6 `test_m6_item24_framed_catalog_valid_accepted`) |
| incorrect payload length rejected | `test_m7_a_incorrect_payload_length_rejected`, `test_m7_a_framing_failure_never_finalizes_no_receipt` |
| incorrect payload SHA-256 rejected | `test_m7_a_incorrect_payload_sha256_rejected` |
| malformed/incomplete framing rejected | `test_m7_a_malformed_incomplete_framing_rejected` |
| known_jobs ordering deterministic | `test_m7_a_canonical_serialization_is_deterministic` |
| no receipt/finalization on failure | `test_m7_a_framing_failure_never_finalizes_no_receipt`, `test_m7_a_incorrect_*` |

---

## B. C++ witness journal history (append-only)

### Phase-sequence model (Contract V1 interpretation)
Contract V1 (Canonical Journal Attestation) **fixes** `phase_sequence` as the
**semantic phase ordinal**: `ACCEPTED=1, STARTED=2, FINISHED/FAILED=3`, strictly
monotonically increasing, append-only `phase_history`, no overwrite/truncate.

`phase_sequence` is therefore the **phase number**, not a separate per-entry
counter. Because each phase occurs exactly once per attempt, phase identity and the
history-ordering key are the **same** concept under Contract V1 — a distinct
per-entry ordinal is not required and would even conflict with the fixed mapping.
Duplicate semantic phases are forbidden (each phase once + strict monotonicity);
out-of-order phases (e.g. `STARTED` before `ACCEPTED`, or a terminal before
`STARTED`) are forbidden by the required lifecycle ordering.

The reference model in `tests/m7/test_m7_journal_history.py` (`_append_phase`,
`_validate_terminal`) encodes and deterministically verifies these rules.

### Before
`FAtlasTransportServer::WriteJournalEntry` wrote a single `<atlas>__<unreal>.json`
object per job-pair using `AtomicWriteFile` (`MOVEFILE_REPLACE_EXISTING`), so each
phase **overwrote** the previous one. Contract V1 §30/§37 requires an append-only
`phase_history` and a monotonic `phase_sequence`. `ReconcileRenderJobs` read the
single-phase file directly. The writer enforced only duplicate-name and monotonic
sequence, but not the strict first/STARTED-before-terminal lifecycle ordering.

### After
- `WriteJournalEntry` now loads any existing `<atlas>__<unreal>.json`, appends the
  new phase to a **retained `phase_history` array** (never truncates prior phases),
  and rewrites the container atomically (durably flushed via `FlushFileBuffers`).
- A monotonic `phase_sequence` is assigned per phase (ACCEPTED=1, STARTED=2,
  FINISHED/FAILED=3). The writer **rejects** duplicate phases and out-of-order
  sequence (new `<=` max), enforces the **required lifecycle order** (ACCEPTED
  must be first; STARTED must follow ACCEPTED; a terminal must follow STARTED),
  and **fails closed** on a malformed existing history (never truncates/overwrites
  prior witness entries).
- The container exposes `phase_history` (full retained history) plus latest-phase
  convenience fields (`phase`, `phase_sequence`, `status`, `progress`, `success`,
  `finished`, `failed`).
- `ReconcileRenderJobs` derives each known-job's current state from the **latest**
  phase-history entry and exposes the full `phase_history` array, so reconciliation
  deterministically consumes the retained history. The derived known-job exposes
  **both** `job_id` and `unreal_job_id` aliases so downstream consumers (Python
  coordinator reads `job_id`; the wire contract names `unreal_job_id`) work with a
  single representation. Legacy single-phase files are still consumed (backward
  compatible). Identity (`atlas_job_id`/`unreal_job_id`) mismatches on append fail
  closed.
- Journal `journal_schema_version` advanced to 2.

### Reconciliation field-preservation (audit correction)
The journal is an execution witness and **cannot** carry Atlas-owned identity:
`canonical_digital_twin_id`, the full 5-key `expected_output_spec`, and
`attempt_ordinal` are Atlas-authoritative. The Python coordinator now binds these
from the durable record into the verification observed_state
(`_bind_record_identity_to_observation`) while preserving every engine-witnessed
execution field (status/`finished`/`success`/`failed`, `output_files`,
`output_manifest`, session/process identity, digests) from the candidate.
`verify_render_job_evidence` still enforces exact equality between bound identity
and the record, and still independently verifies the engine-attested manifest
hashes against disk — so this fills in Atlas-owned fields a witness genuinely
cannot provide; it does not fabricate engine success.

### C++ automation tests (new, compile-verified via UnrealBuildTool — module build
succeeded; not executed under the editor in this milestone)
| Contract req (task) | C++ AutomationTest (`AtlasUE56RenderJobBoundaryTest.cpp`) |
|---|---|
| 1. append rather than overwrite | `FAtlasUE56JournalAppendHistoryTest` (ACCEPTED+STARTED+FINISHED retained in one file) |
| 2. monotonic phase sequence | `FAtlasUE56JournalMonotonicSequenceTest` (phase_sequence 1<2, ACCEPTED precedes STARTED) |
| 3. required phase retention | `FAtlasUE56JournalAppendHistoryTest` (ACCEPTED/STARTED/FINISHED all present) |
| 4. duplicate/out-of-order phase rejection | `FAtlasUE56JournalDuplicateRejectionTest` (duplicate ACCEPTED rejected) |
| 5. strict lifecycle ordering | `FAtlasUE56JournalLifecycleOrderingTest` (STARTED-before-ACCEPTED rejected; dual-terminal rejected) |
| 6. malformed history fail-closed | `FAtlasUE56JournalMalformedHistoryTest` (append to invalid-JSON → error) |
| 7. structural validation of parseable-but-malformed history | `FAtlasUE56JournalStructuralValidationTest` (non-object element, missing phase/phase_sequence, wrong sequence, skipped STARTED, dual terminal; malformed file left byte-for-byte untouched after rejected append; ReconcileRenderJobs → PARTIAL and no synthesized current state) |
| 8. restart/reconciliation sees retained history + identity | `FAtlasUE56JournalReconcileRetainedHistoryTest` (known_jobs carries `phase_history`, `job_id` == `unreal_job_id`) |

Deterministic Python reference tests for the same semantics are in
`tests/m7/test_m7_journal_history.py` (`_append_phase`, `_validate_terminal`,
reconciliation field-preservation).

The journal `entry_digest` (FSHA1 over canonical fields) is retained as a
journal-internal integrity marker; per the architecture contract, journal/witness
data is **not itself authoritative proof** — Atlas still performs independent
verification before any receipt.

### Journal attestation / integrity — implemented vs deferred (audit, item 4/5)

**Fully implemented (this hardening pass):** append-only retained `phase_history`;
monotonic `phase_sequence` as the semantic phase ordinal; strict structural +
lifecycle validation of an existing history BEFORE any append (`WriteJournalEntry`);
FAIL-CLOSED derivation in `ReconcileRenderJobs` (a parseable-but-malformed history
is classified `journal_status=PARTIAL` and does NOT synthesize a current state);
malformed history is never overwritten/truncated.

**Explicitly DEFERRED to the next milestone (NOT implemented here):**
1. **Contract V1 HMAC-SHA256 witness attestation.** The C++ `WriteJournalEntry`
   stores an FSHA1 `entry_digest` over a canonical field concatenation, whereas the
   Python coordinator's witness check recomputes an HMAC-SHA256 keyed by Atlas
   `attempt_nonce` over the canonical JSON payload (`compute_journal_hmac`). The two
   schemes produce different digests. M7 does **NOT** claim full Contract V1
   attestation compliance: the engine must produce the real HMAC-SHA256 keyed by
   `attempt_nonce` over the full canonical payload (schema_version, atlas_job_id,
   unreal_job_id, attempt_ordinal, phase, phase_sequence, editor_session_id,
   process_creation_time_utc, output_directory, output_manifest) before the journal
   is fully self-attesting. This is a distinct witness-authentication subsystem and
   is scheduled as the next milestone hardening item; the coordinator-side
   `attempt_nonce` expectation already exists and is preserved.
2. **`attempt_ordinal` in the engine journal.** `FRenderJobState` and the C++
   journal do not yet carry `attempt_ordinal`; a journal entry is therefore not yet
   fully self-describing per Contract V1. It is **not** solved by the Python-side
   bind (the coordinator binds `attempt_ordinal` from the durable record for the
   Atlas verification pipeline, but that does not make the engine journal
   self-describing). Adding `attempt_ordinal` (and threading it from
   `submit_render` through `FRenderJobState` + `WriteJournalEntry`) is deferred to
   the next milestone.

Neither deferral weakens this pass's findings: the phase/sequence model and
downstream-field preservation are verified independently, and the journal remains
witness-only / non-authoritative throughout.

---

## C. Execution/submission deadline enforcement

### Before
`execution_deadline`/`submission_deadline` were persisted on `AtlasRenderJobRecord`
but nothing enforced them. An unresolved job could wait beyond its deadline and
still be reconsidered; there was no `EXHAUSTED` transition and no bound on recovery
waiting (Contract V1 §23/§28).

### After
- The coordinator now evaluates the persisted deadlines deterministically.
  `submission_deadline` bounds the unsubmitted/submission-uncertain phase;
  `execution_deadline` bounds the post-submission recovery/execution phase.
- After the receipt-first probe (genuinely verified/repairable jobs still
  finalize), if a deadline has expired (`now >= deadline`) on an unresolved
  non-terminal job, the coordinator transitions it to **`RECOVERY_FAILED` +
  `recovery_status=EXHAUSTED`** with a descriptive `failure_reason`.
- Consequences enforced: **no synthetic success, no retry/resubmission, no receipt,
  no finalization** after exhaustion. Once terminal, recovery sweeps skip it.
- `reconcile_single_job` and `reconcile_all_non_terminal_jobs` accept an injectable
  `now_utc` so expiry evaluation is deterministic in tests.

### Tests (deterministic, `tests/m7/test_m7_hardening.py`)
| Contract req (task) | Test |
|---|---|
| 1. deadline not yet expired | `test_m7_c_deadline_not_yet_expired` |
| 2. exactly expired | `test_m7_c_deadline_exactly_expired` |
| 3. expired before reconciliation | `test_m7_c_expired_before_reconciliation` |
| 4. expired during recovery | `test_m7_c_expired_during_recovery_still_exhausts` |
| 5. expired transport uncertainty | `test_m7_c_expired_transport_uncertainty_exhausts` |
| 6. EXHAUSTED transition & recovery status | `test_m7_c_exhausted_transition_and_status` |
| 7. no retry after exhaustion | `test_m7_c_no_retry_after_exhaustion` |
| 8. no receipt/finalization after exhaustion | `test_m7_c_no_receipt_finalization_after_exhaustion` |

Additional: `test_m7_c_submission_deadline_also_enforced`,
`test_m7_c_reconcile_all_enforces_deadlines`.

---

## Production files changed (M7 hardening)
- `planning/unreal_render_recovery_coordinator.py` — framing integrity (A), deadline
  enforcement (C), canonical payload helper.
- `unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp`
  — append-only `phase_history` + monotonic `phase_sequence` (B),
  `ReconcileRenderJobs` history consumption.
- `unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Public/AtlasTransportServer.h`
  — friend declarations for the new C++ automation tests.
- `unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasUE56RenderJobBoundaryTest.cpp`
  — five new C++ automation tests (B).

No other production, engine, or test file was modified.

## Validation
- `tests/m7/`: **16 passed**
- `tests/m6/`: **79 passed** (incl. M7-updated framing test)
- Existing M4/M5 Unreal suites: **154 passed**
- Full `pytest -m "not integration"`: **1045 passed**
- C++ module build: **UnrealBuildTool succeeded** (UBT_EXIT_CODE=0) with the new
  journal/history automation tests.

## Remaining M7 (not done in this milestone)
- **Live M7 Scenarios 1–8** (normal render, Unreal restart during render, Atlas
  restart during render, both restart, render finishes while Atlas unavailable,
  artifact-only, missing artifact, ambiguous duplicate/stale identity) are **NOT
  executed** and require explicit human authorization.
- No `UnrealEditor` launch; no process kill/restart; no workflow/action-runner tests.