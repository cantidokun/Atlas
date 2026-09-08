# Atlas Current Development Handoff

> **Authoritative current-state reconciliation (supersedes the legacy milestone line below).**

## Current status (authoritative reconciliation — supersedes stale milestone headers)

- **M10 — COMPLETE. All eight live Unreal scenarios (S1–S8) were executed and PASSED against the real Unreal 5.6 boundary.** Each is backed by a per-scenario live PASS report in `live_run_state/{s1_final4,s2,s3,s4r,s5,s6,s7,s8}/M10_S*_PASS_REPORT.md`. This is live validation, not merely deterministic preparation.
  - S1 — normal live render, 24/24 frames, Case B → FINALIZED, one verified receipt.
  - S2 — Unreal process/session restart; durable Atlas state remained authoritative; FINALIZED/RESOLVED; one verified receipt.
  - S3 — Atlas restart; durable authority preserved; no resubmission; FINALIZED/RESOLVED.
  - S4 — dual-restart torn witness; Case J → RECOVERY_PENDING (after remediation PR #79); no receipt, no retry.
  - S5 — Unreal finished while Atlas was down; Atlas recovered and finalized correctly; one verified receipt.
  - S6 — artifact present without trustworthy evidence → ORPHANED_ARTIFACTS_PRESENT; no synthetic success, no receipt.
  - S7 — terminal engine evidence with missing artifact → Case G/FAILED fail-closed; no receipt/retry.
  - S8 — duplicate/stale execution identities → real engine CONFLICT → Case H/RECOVERY_FAILED; no adoption/retry/synthetic success.
- **M11 (development model-router) is FROZEN / paused.** M11.1–M11.4 are merged (PRs #82/#83/#84/#85) as development-tooling infrastructure that coexists with the Unreal roadmap but is not required for it. No further M11 benchmarking/calibration/provider work is ongoing.
- **M12 (Unreal Semantic Soccer Production Layer) is the next Unreal development milestone.** Design (PR #86) merged; **M12.1** (semantic task contract + normalize/compile), **M12.2** (catalog + fragments + composition), **M12.3** (semantic execution-plan boundary), **M12.4** (semantic → runtime adapter) implemented — `planning/m12/`; docs `UNREAL_M12_1_SEMANTIC_TASK_CONTRACT.md` / `UNREAL_M12_2_CATALOG_FRAGMENTS_COMPOSITION.md` / `UNREAL_M12_3_EXECUTION_PLAN.md` / `UNREAL_M12_4_RUNTIME_ADAPTER.md`. M12.4 is an adapter, not a new authority: it maps non-render semantic plans onto the existing `AtlasTaskDefinition` runtime and fails closed for render-bearing intent. Render-bearing execution remains deferred; M12.5 (independent verification) next.

> The "Current milestone" line under this block is an older snapshot that predates the final M10 live validation. It is preserved verbatim as historical context; it does NOT reflect current state.

**Active branch:** (see HEAD — M10/M11 merged into `main`; M12 design branch follows)

<sup>Note: the original snapshot below the divider is retained verbatim for provenance. The authoritative current state is the block above.</sup>

### Legacy dated snapshot (preserved verbatim — historical context, not current state)

```
**Updated:** September 6, 2026 — M4/M5 merged (PR #68); M6 deterministic fault-injection/concurrency suite merged (PR #70); **M7 hardening/pre-flight implemented** (framed-catalog integrity, C++ append-only witness history, execution-deadline enforcement — production + deterministic tests, docs/UNREAL_M7_HARDENING.md). Per-item §31/§32 status: docs/UNREAL_M6_TEST_STATUS.md.
**Active branch:** `main`
**Current milestone:** M5/M6 + M7 hardening complete. **M7 live UE 5.6 restart/recovery Scenarios 1–8 is the next authoritative gate and requires explicit human authorization** (Contract V1 §35). Not run.
```

> The three lines above are the ORIGINAL dated snapshot header, preserved verbatim. They predate the final M10 live validation and state "Not run", which has since been superseded — M10 S1–S8 were completed and PASSED live (see the authoritative block above). They are retained only as dated provenance.

**Latest M5 merge commit:** `a9b6eb00e62f252cc3aa5b7ef81998797cb12f83`

## Current repository state

The clean Unreal autonomy bridge from PR #59 is merged to `main`. Milestone 4 established durable cross-process Unreal render-job recovery. Milestone 5 established the authoritative independent evidence-verification boundary. PR #68 merged the M5 implementation after deterministic and CI validation.

Current Unreal execution path:

```text
Qwen / development model proposal
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
observed engine state / witness data
        ↓
Atlas recovery + authoritative independent verification
        ↓
verified UnrealEvidence
        ↓
UnrealRenderReceipt
        ↓
ProductionArtifactManifest
```

## Authority model

```text
Qwen / AI / Gemini / DeepSeek / other models
    -> reason and propose structured production intent

Python / Atlas
    -> validate, resolve, authorize, execute, track, verify, recover

Blender / Unreal
    -> controlled production execution

Independent verification
    -> establish what actually happened
```

External models and agent wrappers are never execution or authorization authorities.

## Stage 13–16 baseline

Stage 13 multi-step partial-progress recovery is complete for the current contract and live verified against Blender 4.4.

Stage 14 dependency-aware task composition is complete for the current contract, including deterministic serial execution, inherited prerequisite handling, and cross-process recovery.

Stage 15 semantic soccer-production tasks are complete for the current contract. `ProductionTaskDefinition`, reusable fragments, target-state evaluation, canonical soccer-production templates, the versioned catalog, and semantic provenance persistence are established.

Stage 16 Qwen integration is live verified through proposal, Atlas authorization, real Blender mutation, cross-process recovery, and advisory-only Qwen recovery reasoning.

## Stage 17 — Production artifact lineage

`planning/production_artifact.py` defines `ProductionArtifactManifest`, a provenance-only contract connecting a production representation to the canonical Atlas Digital Twin, source artifacts, workflow provenance, verification evidence, execution receipts, engine metadata, and a deterministic integrity digest.

### Blender Stage 17 — LIVE VERIFIED

The real Blender 4.4 production-artifact path is live verified: real mutation, fresh independent inspection, immutable receipt/evidence capture, durable manifest persistence, reload, and exact lineage verification.

### Unreal Stage 17 — LIVE VERIFIED

The real UE 5.6 production/provenance proof completed successfully. The chain was:

```text
UE 5.6 render
  -> inspect_render_job
  -> authoritative evidence verification
  -> verified UnrealEvidence
  -> UnrealRenderReceipt
  -> ProductionArtifactManifest
  -> durable persistence
  -> reload
  -> exact lineage verification
```

A real state-consistency bug discovered during the first proof was fixed in the C++ Unreal server before the successful proof. Terminal state anti-regression, callback identity filtering, locked snapshot serialization, and fail-closed finalization were added so the authoritative verifier can rely on coherent observed state.

The live proof produced real artifact/evidence/receipt/manifest digests and reported successful completion.

## M4 — Cross-process Unreal render-job recovery — COMPLETE

Milestone 4 is merged to `main` under Contract V1.

The recovery architecture now includes:

- durable Atlas-owned `AtlasRenderJobRecord` state;
- atomic record replacement and stale-writer rejection;
- single coordinator lease/fencing plus per-job ownership;
- durable intent before transport submission;
- Atlas-generated immutable `atlas_job_id` and attempt ordinal;
- cryptographic attempt nonce with HMAC-protected witness payloads;
- editor/session/process identity, including process creation identity;
- contained `CONTAINED_JOB_OBJECT` supervision with Windows Job Object quiescence proof;
- fail-closed `UNCONTAINED_ATTACHED` handling when cross-process adoption is not supportable;
- Unreal witness journal outside `Saved`, with durable `ACCEPTED`, `STARTED`, `FINISHED`, and `FAILED` phases;
- Unreal deduplication plus Atlas-side exclusive claim;
- per-attempt output isolation;
- engine-attested output manifests with path, size, and SHA-256;
- full-catalog reconciliation with framed payload integrity and stability checks;
- explicit rogue/unmanaged job detection without silent adoption;
- nonmutating handling of orphaned artifacts and conclusive ambiguity;
- receipt identity binding, create-if-absent semantics, lease/revision gating;
- unified lifecycle and separate recovery-status state;
- fail-closed recovery for uncertain execution instead of automatic resubmission.

The Unreal engine remains a witness/execution environment. Atlas remains the recovery authority.

## M5 — Independent evidence verification — COMPLETE

PR #68 expanded `verify_render_job_evidence(...)` into the authoritative conversion boundary from raw observed Unreal state to `UnrealEvidence(verified=True)`.

The verifier now requires, among other invariants:

- supported evidence source class;
- a concrete `AtlasRenderJobRecord` with its constructor/deserialization invariants intact;
- complete identity binding across Atlas/Unreal authorization, twin, sequence, configuration, session/process, and output directory;
- exact five-key expected output topology (`format`, `width`, `height`, `start_frame`, `end_frame`);
- unconditional expected frame-count enforcement;
- output path isolation and traversal/ADS/device-namespace defenses;
- mandatory engine-attested output manifest;
- exact output path-set matching;
- positive integer manifest sizes and lowercase 64-character SHA-256 digests;
- independent disk size and SHA-256 verification;
- PNG signature/chunk/CRC/IHDR/IEND validation;
- IDAT zlib stream completion/integrity checks;
- rejection of unexpected extra disk artifacts.

`verified=True` is never transported from Unreal. It is produced only after independent Atlas verification succeeds.

### M5 validation evidence

M5 head: `d7ce33194946fde5076871f8f13f2c5f6776d655`

Merged as: `a9b6eb00e62f252cc3aa5b7ef81998797cb12f83`

Verified before merge:
- evidence-verification tests: **39 passed**;
- recovery-coordinator tests: **15 passed**;
- `pytest -k unreal`: **302 passed, 648 deselected**;
- full `pytest`: **950 passed**;
- GitHub Actions `Atlas Tests` for the M5 head: **completed successfully**.

No action-runner/workflow tests were run for this milestone.

## Concrete record boundary

`AtlasRenderJobRecord` is the durable authority boundary for an Unreal render job. It is frozen and validates schema, canonical identity, attempt ordinal, authorization/configuration fields, output isolation, lifecycle/recovery enums, expected output specification, and recomputed `authoritative_digest` during construction/deserialization. State transitions create new records rather than mutating the existing record.

This record is not inferred from a model response, Unreal transport response, receipt, or historical journal text.

## Evidence and receipt boundaries

The transport contract returns observed state only. `UnrealEvidence` defaults to unverified. `verify_render_job_evidence(...)` is the sole authoritative verifier for raw `inspect_render_job` evidence.

`UnrealRenderReceipt` can only be issued from verified evidence and binds the complete receipt identity. `ProductionArtifactManifest` is downstream provenance only. Receipt persistence is separate from job-state persistence.

## Model strategy / Hermes development

The development workflow permits experimentation with the reasoning model used by Hermes without changing Atlas authority boundaries.

The current consideration for the next session is a controlled comparison of **Gemini vs DeepSeek V4 Flash**, focusing on the token-to-reasoning tradeoff in Hermes-led implementation work. **Astra and Claude 5 remain reserved for red-team evaluation** so a development-model change does not remove an important independent adversarial review layer.

ChatGPT may also independently inspect/evaluate Hermes-produced work. This is an additional review layer, not an execution authority or replacement for deterministic tests, evidence verification, CI, or the human merge decision.

The comparison should measure practical engineering outcomes: reasoning quality per token, architectural fidelity, defect rate, test-fix efficiency, red-team findings, rework, and time-to-merge.

## Current resume point

At the beginning of the next session:

1. Pull the latest `main`.
2. Treat M4 and M5 as merged, completed baseline work; do not reopen them without evidence of regression.
3. Continue from the next unresolved milestone in the architecture contract — the next authoritative gate is **M7 live UE 5.6 restart/recovery Scenarios 1–8** (Contract V1 §33–§35), which must NOT be run without explicit authorization (live Unreal execution; no workflow/action-runner tests).
4. For Hermes, run the Gemini vs DeepSeek V4 Flash comparison as a development-model experiment while preserving Astra/Claude 5 red-team capacity.
5. Keep implementation, deterministic validation, independent verification, and red-team evaluation clearly separated.

Do not run workflow/action-runner tests unless explicitly authorized.

## Non-regression rules

- Qwen and other models remain proposal/reasoning-only.
- Never accept model-supplied authorization IDs, receipts, protected Unreal intent, or protected production flags as Atlas authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from transport/write success alone.
- Preserve independent verification and the evidence ledger.
- Preserve Atlas-owned recovery authority.
- Keep engine-specific behavior behind adapter/tool boundaries.
- Preserve canonical Digital Twin identity separately from production artifacts.
- Never treat journal/witness data as authoritative proof by itself.
- Never weaken tests or contracts to make model-produced changes pass.
- Do not run workflow/action-runner tests unless explicitly authorized.
- Historical dated handoffs remain archival and must not be rewritten.

## Recent mainline work

- PR #59 — clean Unreal autonomy execution bridge.
- PR #61 — authoritative Unreal render-job evidence verifier.
- PR #62 — C++ terminal-state/callback race hardening discovered by live proof.
- PR #63 — required C++/test access fix for the hardened render state.
- PR #64 — M1 durable process identity, wire schema/capabilities, witness journal, output manifest, reconciliation foundations.
- PR #65 — M2 normative lifecycle/recovery state, durable render-job record/store, locking/quarantine.
- PR #66 — M3 durable intent, exclusive Atlas submission orchestration, capability gate, acceptance-unknown semantics.
- PR #67 — M4 cross-process Unreal recovery coordinator and Contract V1 recovery hardening.
- PR #68 — M5 authoritative independent render-evidence verification.
- PR #69 — docs-only M4/M5 recovery-status correction.
- PR #70 — M6 deterministic fault-injection / concurrency suite.
- PR #71 — M7 deterministic hardening of the three M6-discovered production gaps (framed-catalog integrity, append-only C++ witness journal, deadline enforcement) + journal-history structural fail-closed corrections.
- M8 — witness attestation (real HMAC-SHA256 keyed by Atlas attempt_nonce) + engine attempt_ordinal threading; canonical Python/C++ conformance verified.
- PR #72 — M8 witness attestation (real HMAC-SHA256 keyed by Atlas attempt_nonce) + engine attempt_ordinal threading; canonical Python/C++ conformance verified.
- M9 (pre-flight) — deterministic Scenario 1-8 harness + live-execution pre-flight checks + LIVE_EXECUTION_CHECKLIST. NO live scenario executed; S1/S5/S6/S7 READY_FOR_LIVE, S2/S4/S8 BLOCKED, S3 NOT_PROVEN until live UE restart.
- **M10 attempt-by-attempt forensics log (historical, preserved verbatim).** Each bullet below documents the STATE AT THE TIME each live attempt was made, including the defect-stops. They are NOT the current state. The final live outcome is M10 S1–S8 ALL PASSED (see the authoritative "Current status" block at the top of this file, and the per-scenario PASS reports in `live_run_state/`). The earlier "S2-S8 NOT executed" clauses below reflect the moment each attempt stopped; they were superseded as S2–S8 were subsequently executed and passed live.
- M10 (live) — first authorized live execution attempted. Corrected S1 render PASSED (real MRQ render, FINISHED journal, HMAC verified, 23 artifacts independently verified). Reconciliation found + stopped at two production defects (Defect A: coordinator used WRITE-only apply_authorized for the reconcile READ; Defect B: in-memory reconcile overlay dropped the M8 attestation/session fields). Both fixed in a remediation PR; new tests/m10 + full suite. S1 must rerun after merge before S2-S8. S2-S8 NOT executed.
- M10 (live, Defect C) — S1 verification rerun proved live: Defects A & B RESOLVED (reconcile READ via inspect; catalog preserves journal-derived attestation fields). Reconciliation still blocked by NEW Defect C: adapter `_build_request` did not relay operation entity_ids into nested `arguments.entity_ids`, which the C++ engine requires. Fixed at the adapter transport boundary (generic, fail-closed on any arguments.entity_ids conflict); tests/m10 + full suite. S1 must rerun again after merge before S2-S8. S2-S8 NOT executed.
- M10 (live, Defect D) — S1 final run proved live: A/B/C RESOLVED; only blocker left was Defect D (declared 24 frames, MRQ rendered 23). ROOT CAUSE: submit_render never transmitted start_frame/end_frame to Unreal, and SubmitRender never applied the authorized inclusive range to MRQ -> half-open end dropped frame 24. Fixed: submission now sends start/end; C++ SubmitRender applies bUseCustomPlaybackRange + CustomStart/End (inclusive). Verifier NOT weakened (23 still fails). tests/m10 + full suite; UBT_EXIT_CODE=0. S1 requires ONE final live rerun after merge; S2-S8 NOT executed.
- M10 (live, Defect D v2) — A further fresh live S1 (Run B) proved: A/B/C and D-transmit resolved; D-v1 (applying range to the MRQ output setting) remained INSUFFICIENT. Forensic log: MRQ "Registering range: [800,19200)" = SEQUENCE playback range (80-tick), the source MRQ enumerates shots from. Fix: SubmitRender now duplicates the source ULevelSequence into the transient package (isolation-safe, never mutating the shared asset), SetPlaybackRange(start, end-start+1) inclusive, and points Job->SetSequence at the transient copy; also fixed the same exclusive-upper-bound off-by-one in SetSequencerPlaybackRange. Verifier strict (23 still fails). tests/m10 + full suite; UBT_EXIT_CODE=0. S1 requires ANOTHER fresh live rerun after merge; S2-S8 NOT executed.
- M10 (live, Defect D v3) — Final fresh S1 (s1_final3) proved A/B/C + D-transmit + D-v2 active ([1,25) registered) but still 23 files. UE-source root cause: MRQ output-frame enumeration uses GetEffectivePlaybackRange = OUTPUT SETTING's [CustomStart, CustomEnd) half-open, NOT the sequence playback range (D-v1 set end=24 -> 23; D-v2 changed the wrong lever). Fix: CustomEndFrame = end+1 (exclusive upper) -> end-start+1 frames (1..24 -> 24). Verifier strict (23 fails). tests/m10 (9 D3) + full suite; UBT_EXIT_CODE=0. S1 requires ANOTHER fresh live rerun after merge; S2-S8 NOT executed.

## Historical documentation

Older dated handoff snapshots are archival records and should not be rewritten. This document is the authoritative current development handoff.

## M10 - S4 Case J remediation (latest)
- Genuine S4 s4b dual-restart produced a torn non-terminal journal (job 899e6a81, ACCEPTED-only).
- Recovery misclassified it Case G -> terminal FAILED ("Engine claims FINISHED...").
- Contract requires Case J -> RECOVERY_PENDING (non-terminal, no receipt). Fixed:
  coordinator now checks `_candidate_is_terminal` before the finished-candidate path;
  torn/interrupted (finished=False / phase ACCEPTED/STARTED) -> Case J (RECOVERY_PENDING,
  ambiguity++, no receipt, no retry). Genuine terminal Case G still fails closed.
- New tests/m10/test_m10_case_j_torn_journal.py (9 tests). Full suite 1198 passed.

## M11 - Adaptive model routing + engineering control plane (DESIGN, no implementation)
- Investigation + design only. docs/ATLAS_M11_ADAPTIVE_MODEL_ROUTING_DESIGN.md created.
- No production code changed, no live scenario, no Unreal launch, no PR merge.
- Boundary: M11 is dev-tooling only; Atlas remains sole production authority (Contract V1 §2 forbids model-controlled authorization).
- Design covers task/risk taxonomy (L0-L3 tiers), deterministic routing (cheapest tier meeting risk), hard escalation triggers,
  evidence-based confidence (no self-report), adaptive token budgets, escalation packet, privacy-safe telemetry schema,
  benchmark corpus from real Atlas tasks, authority safeguards, and phased implementation plan.
- Current-state findings recorded: no explicit model-tier router; multi-model review done manually (astra/deepseek/opus/sonnet);
  model/provider names are DESIGN PARAMETERS (not hard-coded).
- HARDENED (before implementation): frozen deterministic risk->tier mapping (R1-R7: per-dimension 0-3 scoring, worst-dim
  max drives tier, hard-selector floors L2/L3, unknown-data fails closed to L3, combined selectors take max; model
  self-confidence never affects selection). Model capability is validated static config (tier/provider/model_id/
  capability_floor/supported_classes/token_budget/timeout). Finite escalation budget MAX_ESCALATIONS_PER_TASK=3, terminal
  NEEDS_HUMAN_REVIEW on exhaustion/L3-fail/insufficient-evidence (no blind rerun). Telemetry is append-only with task_id/
  attempt_id/escalation_id; immutable risk/tier fields; never stores secret/nonce/key. Explicit router failure modes
  (missing profile, unavailable provider, timeout, malformed response, invalid tool, failing gate, exhausted budget,
  telemetry-write-fail, config ambiguity) all fail closed. 9 objective acceptance criteria added.

## M11.1 - adaptive model router core (implemented)
- implemented planning/m11_router/ (model_profile, risk R1-R7, routing, escalation, telemetry,
  evidence_gate, escalation_packet, router facade, benchmark skeleton). 136 deterministic tests.
- Full suite 1348 passed (1212 + 136). Non-negotiable boundary: router never imports production
  authority; no submit/reconcile/apply_authorized/receipt/schedule path (tests enforce).
- Docs: docs/UNREAL_M11_1_MODEL_ROUTER_CORE.md. Deferred: model execution orchestration, provider
  invocation, full benchmark corpus, Hermes runtime integration (M11.2+).

## M11.2 - model/provider execution + adaptive routing (shadow mode)
- Provider-execution layer for the M11 router in SAFE SHADOW/ADVISORY mode.
- planning/m11_router/provider/: providers_config (fail-closed config + token/cost accounting),
  invocation (ProviderAdapter/ModelResult/invoke_model, error-classified, no uncontrolled retry),
  shadow (ShadowAdvisor.advise: resolve provider -> invoke -> evidence -> telemetry, advisory only).
- benchmark.run_benchmark_task(advisor=...) now executes corpus w/ useful-output metrics.
- Tests: tests/m11 177 (136 M11.1 + 41 M11.2, mocked adapters). Full suite 1389 passed.
- Authority: no production imports/calls (docstring prohibitions + enum names only); tests enforce.
- Telemetry: extends existing append-only ledger; privacy allow-list preserved.
- Deferred: real vendor adapter (credentials in secure config), endpoint resolution, Hermes auto-wiring.

## M11.3 - real OpenRouter adapter + controlled Hermes integration (shadow)
- planning/m11_router/provider/secure_config.py: SecureConfigResolver (endpoint_config_ref -> live key+endpoint; fail-closed).
- planning/m11_router/provider/openrouter_adapter.py: real OpenRouterAdapter (requests/session) -> immutable ModelResult;
  malformed/auth/rate-limit classified; never uncontrolled retry; credentials never persist/return.
- planning/m11_router/hermes_integration.py: M11FeatureConfig + ShadowRoutedExecutor behind ATLAS_M11_ROUTING_ENABLED/MODE;
  default off preserves current behavior; shadow invokes routed model, advisory only.
- Tests: tests/m11 204 (177 + 27 M11.3). Full suite 1416 passed. No workflow tests / live Unreal / Blender.
- Pre-PR scans: no credential leakage; no production-authority import/call; sector boundary enforced.

## M11.4 - live provider validation + adaptive routing measurement
- planning/m11_router/live_validation.py: ControlledLiveValidator (operator gate, one call, no retry, safe telemetry)
  + run_live_smoke. live_operator.py: operator CLI (python -m planning.m11_router.live_operator --live --smoke|--benchmark --out X).
- benchmark.run_benchmark_corpus: machine-readable JSON (first-pass/useful-output, tokens, cost, latency, provider_errors,
  evidence_failures, honest UNKNOWN). live_operator.run_offline_baseline_report / run_live_baseline_report.
- Telemetry sensitivity hardened: key-vs-value split + safe-canonical-name whitelist; rejects Authorization/API-key/nonce/HMAC/credential prompts.
- Tests: tests/m11 229 (204 + 25 M11.4). Full suite 1441 passed. No workflow tests / live Unreal / Blender.
- Live provider calls are operator-gated (--live) and excluded from deterministic CI; no real creds in repo.
- LIVE run NOT executed (no credentials provisioned); smoke path verified fail-closed (AUTH_ERROR, honest UNKNOWN).
