# Milestone 8 — Witness Attestation + Engine Attempt Identity

Closes the two attestation gaps explicitly deferred at the end of Milestone 7:
engine-side `attempt_ordinal` in the witness journal and real HMAC-SHA256 journal
attestation keyed by the Atlas `attempt_nonce`. This is a DETERMINISTIC milestone:
it does not run live Unreal. The live M7 Scenarios 1–8 remain a separate
human-authorized gate (never executed here).

Authoritative spec: `docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md`
(attempt identity §4.2, engine journal, canonical journal attestation).

## M8 status

- **Implemented:** engine-side `attempt_ordinal`; real HMAC-SHA256 witness
  attestation; shared Python/C++ canonical serialization; coordinator fail-closed
  attestation gates for reconciliation.
- **Deterministic-test verified:** M8 suite (conformance + witness gates), plus the
  full `pytest -m "not integration"` suite.
- **Python/C++ canonicalization conformance verified:** a fixed conformance vector
  produces identical canonical bytes and the same HMAC-SHA256 digest in both
  languages (Python stdlib `hmac` == C++ RFC-2104 manual implementation).
- **Live M7 Scenarios 1–8 have NOT been run.** No `UnrealEditor` launch, no
  workflow/action-runner tests, no Blender. Live restart/recovery remains pending.

## Authority boundary (unchanged)

- Atlas (Python/controller) remains authoritative for: authorization,
  `atlas_job_id`, `attempt_ordinal`, `attempt_nonce`, lifecycle, recovery, evidence
  verification, and receipt issuance.
- Unreal remains an execution worker and **witness only** — never an
  authorization/recovery/scheduler authority.
- `attempt_ordinal` is carried verbatim from the durable Atlas record; Unreal MUST
  NOT invent, increment, or reinterpret it. It never becomes an authorization
  mechanism or retry permission.
- `attempt_nonce` is an Atlas-generated 256-bit secret used ONLY as the HMAC key;
  it MUST NEVER be written in plaintext to journal/receipt/manifest/logs.

## Exact HMAC-SHA256 definition

```
entry_digest = HMAC-SHA256(key = UTF8(attempt_nonce), message = canonical_bytes)
```

Implemented natively in C++ as RFC-2104 HMAC over the BCrypt SHA-256 provider
(ipad/opad key blocks), which is byte-identical to Python's stdlib `hmac`.

## Canonical serialization definition

message = `field(\x1f field)*\x1e`  (fields joined by U+001F, trailing U+001E)

Signed fields, in this exact order:
`schema_version`, `atlas_job_id`, `unreal_job_id`, `attempt_ordinal`, `phase`,
`phase_sequence`, `editor_session_id`, `process_creation_time_utc`,
`output_directory`, `output_manifest`.

- Integers (`schema_version`, `attempt_ordinal`, `phase_sequence`) are decimal ASCII.
- Strings are UTF-8, verbatim.
- `output_manifest` is 0..N entries; each entry serializes as
  `path \x1c size \x1c sha256 \x1d`; empty manifest is the empty string.
- The result is UTF-8-encoded. Locale- and platform-independent by construction
  (control separators never appear in the field serializations, so the encoding is
  unambiguous).
- `output_manifest` is REQUIRED-significant on `FINISHED` (the FINISHED witness
  must carry the output attestation); for non-terminal phases it is empty/absent and
  canonicalizes to the empty string, so the same field-order rule applies uniformly.

Python reference: `planning/unreal_journal_attestation.py`.
C++ reference: `FAtlasTransportServer::ComputeJournalAttestationCanonical` +
`ComputeJournalAttestationDigest` in `AtlasTransportServer.cpp`.

## attempt_ordinal data path

```
AtlasRenderJobRecord.attempt_ordinal
  -> submit_render request arguments (attempt_ordinal, attempt_nonce)
  -> FRenderJobState.AttemptOrdinal (in-memory; AttemptNonce = HMAC key only)
  -> WriteJournalEntry -> journal phase entry (attempt_ordinal) + HMAC input
  -> reconcile_render_jobs -> latest-phase copy exposes attempt_ordinal
  -> Atlas reconciliation binding: compare observed vs durable record
  -> mismatch FAILS CLOSED (UNTRUSTED_WITNESS / RECOVERY_FAILED)
```

## Legacy journal contract (no attempt_ordinal / no HMAC)

- Journals lacking `attempt_ordinal` and/or HMAC attestation (`entry_digest`) are
  **legacy/unsupported witnesses**.
- They MUST NOT be treated as `ENGINE_JOURNAL_ATTESTED`.
- They **fail closed as untrusted witness evidence** (`UNTRUSTED_WITNESS` →
  `RECOVERY_FAILED`). No success, receipt, finalization, or retry may result.
- This behavior is **intentional** and does not weaken the M7 fail-closed
  guarantees. Existing legacy journals are NOT silently migrated into attested
  evidence — a legacy witness cannot become attested without the Atlas-supplied
  attempt_nonce and attempt_ordinal that it never carried.

## Replay/tampering behavior

Any alteration of a signed field changes the canonical bytes and therefore the
HMAC. The coordinator verifies the digest against the persisted record's
`attempt_nonce` and the observed `attempt_ordinal`:

- missing `attempt_ordinal` → fail closed (legacy witness)
- non-int/mismatched `attempt_ordinal` → fail closed
- missing/empty `entry_digest` → fail closed
- non-64-hex / malformed `entry_digest` → fail closed
- HMAC verification failure (wrong/replayed nonce, tampered field) → fail closed
- malformed canonical payload (reconstruction raises) → fail closed

A bad/missing HMAC can never synthesize execution success, create a receipt,
finalize a job, or authorize a retry. It is classified untrusted. No code path
treats a bad HMAC as ordinary evidence.

## Deterministic test counts (final tree)

- `tests/m8/`: 19 tests (4 conformance + 15 witness/secret-handling gates).
- Full `pytest -m "not integration"`: 1107 passed.
- UBT: module build `UBT_EXIT_CODE=0` (C++ automation compile-verified only; the
  automation tests are NOT executed under the editor).

## C++ change summary

- `FRenderJobState` gains `AttemptOrdinal` (int32) and `AttemptNonce` (FString,
  in-memory HMAC key only; never serialized).
- `SubmitRender` parses `attempt_ordinal`/`attempt_nonce` from arguments.
- `WriteJournalEntry` emits `attempt_ordinal` into each phase entry and computes
  the real HMAC-SHA256 attestation digest over the canonical payload (manifest
  built first since the HMAC covers it). Journals written without a nonce carry an
  empty `entry_digest` (legacy/unsupported).
- New helpers: `ComputeSha256Buffer`, `ComputeJournalAttestationCanonical`,
  `ComputeJournalAttestationDigest`.
- New C++ automation test `FAtlasUE56JournalAttestationVectorTest` reproduces the
  exact conformance vector (canonical bytes + pinned digest + modified-field and
  wrong-nonce divergence).

## Remaining deferred items

- **Live M7 Scenarios 1–8**: require explicit human authorization; not run.
- C++ automation tests are **compile-verified only**, not executed under the
  Unreal editor runtime.
- Engine `FRenderJobState` completeness beyond attestation (e.g. full
  `expected_output_spec`) — not part of this milestone.