# Atlas Unreal Agent — Current Handoff

**Updated:** September 6, 2026 — M4/M5 merged (PR #68); M6 deterministic fault-injection/concurrency suite merged (PR #70); **M7 hardening/pre-flight implemented** (framed-catalog integrity, C++ append-only witness history, execution-deadline enforcement — production + deterministic tests, docs/UNREAL_M7_HARDENING.md). Per-item §31/§32 status: docs/UNREAL_M6_TEST_STATUS.md.
**Active Atlas branch:** `main`
**Current focus:** M5/M6 + M7 hardening complete. **M7 live UE 5.6 restart/recovery Scenarios 1–8 is the next authoritative gate and requires explicit human authorization** (live Unreal execution). Not run.
**Latest M5 merge commit:** `a9b6eb00e62f252cc3aa5b7ef81998797cb12f83`

## Architectural position

Atlas owns the canonical Digital Twin. Unreal is a downstream controlled production representation/execution environment around that canonical state.

```text
Qwen / model proposal
        ↓
Atlas planning / validation / authorization
        ↓
AgentControllerHost / TrustedUnrealContext
        ↓
AutonomousTaskRuntime / AutonomousFutureRuntime
        ↓
UnrealAutonomousExecutor
        ↓
UnrealExecutionBoundary
        ↓
UnrealAdapterProduction
        ↓
Windows Named Pipe transport
        ↓
Unreal Engine 5.6
        ↓
observed state / witness data
        ↓
Atlas recovery + authoritative independent verification
        ↓
verified UnrealEvidence
        ↓
UnrealRenderReceipt
        ↓
ProductionArtifactManifest
```

Key authority invariants:
- `UnrealAutonomousExecutor` is an execution adapter, NOT an autonomous runtime.
- `UnrealExecutionBoundary` is a tool/operation validation boundary, NOT an authorization authority.
- `AutonomousTaskRuntime` / `AutonomousFutureRuntime` remains the single autonomous progression authority.
- `TrustedUnrealContext` remains the host-owned source of truth for protected production intent, sequence path, authorization context, and production markers.
- Transport success != verification success.
- Unreal witness/journal information is not itself authoritative proof.
- Neither the bridge nor the adapter issues a render receipt.
- Independent Atlas verification establishes verified evidence; the receipt/provenance layers consume that evidence downstream.

## Restored and compile-verified Unreal execution baseline

PR #57 restored the working Unreal 5.6 execution boundary to `main`. PR #59 merged the clean autonomy bridge connecting the generic Atlas runtime to the production Unreal adapter and named-pipe transport.

The working render path is:

```text
render configuration
  → configuration verification
  → Movie Render Queue submission
  → dynamic job ID
  → asynchronous job inspection
  → semantic completion verification
  → artifact discovery
  → Atlas recovery/identity checks where required
  → authoritative evidence verification
  → verified UnrealEvidence
  → evidence-bound UnrealRenderReceipt
  → ProductionArtifactManifest / provenance
```

## Stage 17 — production-artifact provenance — LIVE VERIFIED

The real UE 5.6 production/provenance proof completed successfully after the server-side state-consistency defect from the first proof attempt was corrected.

The C++ hardening included callback identity filtering, terminal-state anti-regression, fail-closed finalization, and locked snapshot construction so that inspection cannot observe incoherent terminal state.

The successful chain was:

```text
UE 5.6 render
  → inspect_render_job
  → verify_render_job_evidence
  → verified UnrealEvidence
  → UnrealRenderReceipt
  → ProductionArtifactManifest
  → durable persistence
  → reload
  → exact lineage verification
```

The successful proof established real artifact/evidence/receipt/manifest lineage and deterministic digest identities.

## M4 — Cross-process Unreal render-job recovery — COMPLETE

The durable recovery design is now merged to `main` and follows Contract V1.

### Atlas authority

Atlas creates and owns the immutable `atlas_job_id`, authoritative job record, attempt identity, lifecycle, recovery status, authorization binding, output isolation, and final verification/receipt decisions.

### Durable job record

`AtlasRenderJobRecord` is frozen and acts as the durable authority boundary. Construction/deserialization validates the versioned schema, canonical IDs, attempt ordinal, authorization/configuration values, output isolation, expected output specification, lifecycle/recovery state, and recomputed `authoritative_digest`.

State transitions construct new records rather than mutating existing records.

### Submission/recovery invariants

- Durable intent is written before render submission.
- A new authorized rerender is a new attempt and new Atlas job identity.
- Uncertain transport acceptance is not silently retried.
- Single-coordinator lease/fencing prevents competing recovery writers.
- Per-job locking and atomic durable writes protect record integrity.
- Process identity includes editor/session and process-creation identity.
- Contained Unreal execution can use a Windows Job Object supervision boundary.
- Unsupported uncontained attached recovery fails closed rather than treating parent PID death as proof of engine quiescence.
- Unreal witness journaling occurs outside `Saved` and records durable accepted/start/finish/failure phases.
- Attempt identity uses a CSPRNG nonce with HMAC-protected witness information and the nonce is not persisted in plaintext proof artifacts.
- Outputs are isolated per Atlas job/attempt.
- Engine-attested output manifests bind path, size, and SHA-256 to actual files.
- Reconciliation covers the full engine catalog and detects unmanaged/rogue jobs without silently adopting them.
- Orphaned artifacts and conclusive ambiguity fail through explicit recovery states rather than synthetic success.
- Receipt issuance is identity-bound, create-if-absent, and gated by coordinator lease/revision state.

The Unreal process is a controlled production worker/witness. It is not the Atlas recovery authority.

## M5 — Independent evidence verification — COMPLETE

PR #68 is merged to `main`. `verify_render_job_evidence(...)` in `planning/unreal_evidence_contract.py` is the authoritative boundary that may produce `UnrealEvidence(verified=True)` from raw observed render-job state.

The verifier strictly requires:

- an allowed evidence source class (`ENGINE_LIVE` or `ENGINE_JOURNAL_ATTESTED`);
- a concrete `AtlasRenderJobRecord` with intact constructor/deserialization invariants;
- complete evidence identity binding to the durable record;
- exact output-directory isolation;
- complete expected topology: PNG format, width, height, start frame, end frame;
- unconditional frame-count enforcement;
- mandatory engine-attested output manifest;
- exact path-set equality between the manifest and declared output files;
- positive integer sizes and canonical lowercase 64-character SHA-256 values;
- independent disk size/hash verification;
- complete PNG structural, CRC, IHDR/IEND, and trailing-byte validation;
- IDAT zlib stream completion/integrity checks;
- rejection of unexpected extra disk artifacts.

`verified=True` is never transported from Unreal. It exists only after Atlas independently proves the evidence and filesystem artifacts.

### M5 validation evidence

M5 head: `d7ce33194946fde5076871f8f13f2c5f6776d655`
Merged: `a9b6eb00e62f252cc3aa5b7ef81998797cb12f83`

Validated before merge:
- evidence verification tests: **39 passed**;
- recovery coordinator tests: **15 passed**;
- Unreal-focused suite: **302 passed, 648 deselected**;
- full repository suite: **950 passed**;
- GitHub Actions `Atlas Tests`: completed successfully for the M5 head.

No action-runner/workflow tests were run.

## Receipt / provenance boundary

`UnrealRenderReceipt` may only be issued from verified evidence and binds the full render identity. `ProductionArtifactManifest` is downstream provenance only.

`ProductionArtifactStore` persists provenance manifests. Receipt persistence is not a substitute for durable render-job state.

`UnrealEvidence.snapshot()` / `from_snapshot(...)` and `UnrealRenderReceipt.snapshot()` / `from_snapshot(...)` are canonical detached, fail-closed serialization boundaries.

## Model/agent development boundary

Hermes and its selected reasoning model may assist implementation, diagnosis, and code generation. They do not gain Unreal authority through model selection.

The next-session experiment under consideration is **Gemini vs DeepSeek V4 Flash** for Hermes-led development, specifically the tradeoff between token usage and reasoning quality. **Astra and Claude 5 remain reserved for red-team evaluation**, preserving a separate adversarial layer. ChatGPT can independently inspect Hermes-produced changes as an additional evaluator.

No model substitution changes the Atlas authority chain, evidence rules, recovery contract, or merge gate.

## Resume point

1. Pull the latest `main`.
2. Treat M4 and M5 as complete unless a concrete regression is found.
3. Continue with the next unresolved Unreal/Atlas milestone from the authoritative current handoff and architecture contract — the next gate is **M7 live UE 5.6 restart/recovery Scenarios 1–8** (Contract V1 §33–§35); do not run without explicit authorization (live Unreal execution).
4. Preserve the M4 recovery and M5 verification invariants during all future Unreal changes.
5. Evaluate Gemini vs DeepSeek V4 Flash on real Hermes development tasks using engineering outcomes rather than tokens alone.

## Non-regression rules

- Never give any model direct production execution or authorization authority.
- Never accept model-supplied authorization IDs or receipts as authority.
- Never accept model-supplied protected Unreal intent or production flags as authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from transport/write success alone.
- Preserve independent verification and the evidence ledger.
- Keep Unreal-specific behavior behind adapter/tool boundaries.
- Treat render artifacts as independently validated evidence.
- Preserve canonical Digital Twin identity separately from Unreal assets, levels, jobs, receipts, and files.
- Do not confuse durable receipt/provenance persistence with job-state persistence.
- Never treat Unreal journal/witness state as sufficient authoritative proof.
- Preserve contained/uncontained recovery distinctions and fail closed when quiescence is not proven.
- Do not run workflow/action-runner tests unless explicitly authorized.
- M9 (pre-flight): deterministic Scenario 1-8 harness + live pre-flight checks + LIVE_EXECUTION_CHECKLIST added; NO live scenario executed. S1/S5/S6/S7 READY_FOR_LIVE, S2/S4/S8 BLOCKED, S3 NOT_PROVEN until a real UE restart is run. Remaining live dependencies: real UE 5.6 process + MRQ render, real durable journal, real GetProcessTimes identity, real contained Job Object quiescence.
- M10 (live): corrected S1 render PASSED (real UE 5.6 MRQ render, FINISHED journal, HMAC verified, 23 artifacts independently verified); reconciliation blocked by two production defects (A: coordinator used apply_authorized/WRITE for the reconcile READ; B: in-memory reconcile overlay dropped M8 attestation/session fields). Both fixed in the remediation PR (reconcile read now uses inspect; C++ overlay now lets the durable journal-derived attested entry win and relays attempt_ordinal). tests/m10 added; full suite 1158 passed. Live S1 must rerun after merge before S2-S8; S2-S8 NOT executed.
- M10 (live, Defect C): S1 verification rerun proved live A & B RESOLVED; new block = Defect C. Root cause: adapter _build_request did not relay operation entity_ids into nested arguments.entity_ids (C++ requires it for every op). Fixed at adapter boundary (generic, fail-closed). tests/m10 Defect C (7); full suite 1165 passed. S1 must rerun after merge before S2-S8; S2-S8 NOT executed.
- M10 (live, Defect D): S1 final run proved A/B/C RESOLVED live; last blocker = Defect D (declared 24, MRQ rendered 23). Fix: submission now sends start_frame/end_frame; C++ SubmitRender applies inclusive [start,end] to MRQ. Verifier NOT weakened (23 still fails). tests/m10 (7 D); full suite 1172; UBT_EXIT_CODE=0. One final S1 rerun required post-merge; S2-S8 NOT executed.
- M10 (live, Defect D v2): fresh S1 Run B proved A/B/C + D-transmit resolved; v1 (output-setting range) insufficient because MRQ enumerates shots from the SEQUENCE playback range. Fix: SubmitRender duplicates the source sequence into a transient (isolation-safe, shared asset unmutated), SetPlaybackRange(start, end-start+1) inclusive, Job->SetSequence(transient); also fixed SetSequencerPlaybackRange off-by-one. Verifier strict (23 still fails). tests/m10 (8 D2); full suite 1180; UBT_EXIT_CODE=0. Another fresh S1 rerun required; S2-S8 NOT executed.
- M10 (live, Defect D v3): s1_final3 proved A/B/C + D-transmit + D-v2 sequence range active ([1,25)) STILL 23 files. UE-source root cause: MRQ output enumeration uses GetEffectivePlaybackRange (OUTPUT SETTING [CustomStart,CustomEnd) half-open), NOT the sequence playback range (D-v1 end=24 ->23; D-v2 wrong lever). Fix: CustomEndFrame=end+1 -> end-start+1 frames (24). Verifier strict (23 fails). tests/m10 (9 D3); full suite 1189; UBT_EXIT_CODE=0. Another fresh S1 rerun required; S2-S8 NOT executed.
- M8: engine `attempt_ordinal` + real HMAC-SHA256 witness attestation implemented; journals without attempt_ordinal/HMAC are legacy/unsupported witnesses that fail closed (never treated as ENGINE_JOURNAL_ATTESTED; no success/receipt/finalization/retry). Python/C++ canonicalization conformance verified. Live M7 Scenarios 1–8 NOT run.

## Historical documentation

Older dated handoff snapshots are archival records and should not be rewritten. This document is the authoritative current Unreal handoff.