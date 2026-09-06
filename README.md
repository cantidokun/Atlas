# Atlas

## What Atlas is

Atlas is an **AI-assisted sports virtual-production and digital-twin platform** focused exclusively on soccer-field-related digital twins and production workflows.

Dedicated photogrammetry software is the upstream reconstruction stage. Blender analyzes, cleans, corrects, optimizes, and prepares the reconstruction. Unreal is a downstream controlled production environment around the canonical Atlas Digital Twin.

```text
Real-world soccer environment / captured soccer footage
                    ↓
          Dedicated photogrammetry
                    ↓
           Initial 3D reconstruction
                    ↓
               Blender Agent
        analyze / clean / correct / optimize
                    ↓
             Atlas Digital Twin
                    ↓
               Unreal Agent
          real-time production / VFX
```

Atlas supports source footage including 4K/UHD. Higher resolution changes processing, memory, storage, reconstruction, compositing, and render-throughput requirements; it does not change the core authority/orchestration model.

## Authority model

```text
Qwen / AI
  → reason and propose structured production intent

Python / Atlas
  → validate, resolve, authorize, execute, track, verify, recover

Blender / Unreal
  → controlled production execution

Independent verification
  → establish what actually happened
```

Qwen, Gemini, DeepSeek, Claude, Astra, Hermes, OpenHands, and other model/agent tooling are reasoning/development actors, not Atlas execution or authorization authorities.

---

# Current position — September 6, 2026 checkpoint

**Active branch:** `main`  
**Current milestone:** **M5 complete; M6 — deterministic fault-injection/concurrency suite IMPLEMENTED; M7 live restart/recovery validation PENDING**  
**Latest merged PR:** **#68**, merge commit `a9b6eb00e62f252cc3aa5b7ef81998797cb12f83`

Stage 13 multi-step partial-progress recovery is live-verified against Blender 4.4. Stage 14 dependency-aware serial execution and cross-process recovery are implemented and live-verified. Stage 15 semantic soccer-production workflows and versioned catalog compilation are established. Stage 16 Qwen integration is live-verified through proposal, Atlas authorization, real Blender mutation, cross-process recovery, and advisory-only Qwen recovery reasoning.

Stage 17 production-artifact lineage is live-verified for Blender. The real Unreal Engine 5.6 render/provenance path was also live-proven after the C++ render-state consistency defect was identified and fixed.

## Unreal autonomy architecture — MERGED TO MAIN

The Unreal autonomy subsystem is integrated as an execution adapter under Atlas's generic authority model:

```text
Qwen / model proposal
        ↓
Atlas planning / validation
        ↓
ActionAuthorization / TrustedUnrealContext
        ↓
AgentControllerHost
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
Unreal Engine 5.6 (AtlasTransportServer.cpp)
        ↓
observed Unreal state / witness evidence
        ↓
Atlas authoritative independent verification
        ↓
verified UnrealEvidence
        ↓
UnrealRenderReceipt
        ↓
ProductionArtifactManifest
```

Key architectural guarantees:
- Atlas owns authorization, execution progression, recovery, verification, and receipt authority.
- The model never authorizes execution or mints authorization IDs.
- The Unreal bridge never creates a second scheduler, authorization system, or recovery authority.
- Transport success is never treated as proof of production success.
- `UnrealEvidence` is unverified until the authoritative verifier proves the observed state and artifacts.
- Receipts are created only from independently verified evidence.
- Engine-specific behavior remains behind controlled adapters and transport boundaries.

## Stage 17 — Production artifact lineage

`planning/production_artifact.py` provides an immutable provenance-only `ProductionArtifactManifest` connecting a production representation to the canonical Atlas Digital Twin, source artifacts, workflow provenance, independent verification evidence, execution receipts, engine metadata, and a deterministic integrity digest.

The manifest does not execute, authorize, schedule, or recover work. Blender and Unreal use separate engine-specific construction and lineage-verification bridges.

### Blender Stage 17 — LIVE VERIFIED

The real Blender 4.4 production-artifact closed loop is user-verified: real mutation, fresh independent inspection, immutable receipt/evidence capture, durable manifest persistence, reload, and exact lineage verification.

### Unreal Stage 17 — LIVE VERIFIED

The real UE 5.6 Stage 17 proof completed successfully after the render-state race/terminal-state regression was fixed. The verified chain was:

```text
UE 5.6 render
  → inspect_render_job
  → authoritative Unreal evidence verification
  → verified UnrealEvidence
  → UnrealRenderReceipt
  → ProductionArtifactManifest
  → durable persistence
  → reload
  → exact lineage verification
```

The successful proof produced a verified render artifact and matching evidence, receipt, and manifest digests. The proof harness remains provenance-only and does not replace the execution/recovery runtime.

## Stage 18 / M4 — Cross-process Unreal render-job recovery

Milestone 4 is merged to `main`. The recovery system is now designed around durable Atlas job records, single-coordinator fencing, process/session identity, durable Unreal witness journaling, output isolation, engine-attested output manifests, artifact stability checks, and fail-closed reconciliation.

Authoritative recovery principles:

- Atlas generates the immutable `atlas_job_id` and owns the durable job record.
- A reauthorized rerender is a new attempt and a new Atlas job identity.
- Durable intent exists before transport submission.
- Uncertain transport acceptance is not silently retried.
- Unreal journal state is a witness, not the source of truth.
- Recovery can only adopt evidence that satisfies the full identity and artifact contracts.
- Contained Unreal processes can be supervised through the Windows Job Object boundary; uncontained attached sessions fail closed rather than pretending process death is proven.
- Attempt identity uses a persisted cryptographic nonce and HMAC-protected witness data.
- Render outputs are isolated per Atlas job/attempt.
- Rogue/unmanaged Unreal jobs are detectable during reconciliation and are never silently adopted.
- Receipt creation is create-if-absent and identity-bound.

Cross-process recovery is therefore implemented as an Atlas-owned recovery mechanism, not as an Unreal-side autonomous system.

## Milestone 5 — Independent evidence verification — COMPLETE

PR #68 is merged to `main`. The authoritative `verify_render_job_evidence(...)` boundary now fail-closes unless all required conditions are satisfied, including:

- supported evidence source class;
- complete identity binding to the durable `AtlasRenderJobRecord`;
- exact expected five-key output topology;
- unconditional frame-count enforcement;
- isolated output paths with traversal/ADS/device-namespace defenses;
- mandatory engine-attested output manifest;
- exact path, positive byte size, and lowercase 64-character SHA-256 validation;
- independent disk rehash and byte-size comparison;
- complete PNG structure/CRC/IHDR/IEND validation;
- IDAT zlib stream completion/integrity checks;
- no extra disk artifacts in the authorized output directory.

`verified=True` is produced only by this authoritative independent verification boundary. The transport layer never supplies verified evidence.

### M5 validation

The merged M5 head was `d7ce33194946fde5076871f8f13f2c5f6776d655` and was merged as `a9b6eb00e62f252cc3aa5b7ef81998797cb12f83`.

Verified before merge:
- targeted evidence verification: **39 passed**;
- recovery coordinator: **15 passed**;
- Unreal-focused suite: **302 passed, 648 deselected**;
- full repository suite: **950 passed**;
- GitHub Actions `Atlas Tests` for the M5 head: **completed successfully**.

No action-runner/workflow tests were used for the live recovery work.

## Milestone 6 — Deterministic fault-injection/concurrency test suite

An M6 test suite under `tests/m6/` implements the Contract V1 §31 failure matrix and §32 C++ automation boundary deterministically (controlled fakes, scripted transport responses, deterministic filesystem fixtures, explicit concurrency primitives — no live Unreal/Blender, no timing races, no workflow/action-runner tests). **Per-item honest status is in [`docs/UNREAL_M6_TEST_STATUS.md`](docs/UNREAL_M6_TEST_STATUS.md)** — some items are FULLY EXERCISED, others PARTIALLY EXERCISED or DEFERRED because the positive contract seam is missing.

M6 suite: **79 tests green**; full deterministic repository suite currently **1083 passed**. C++ automation additions (malformed-journal handling, capability/schema reporting, and — via M7 hardening — journal append/history retention) in `AtlasUE56RenderJobBoundaryTest.cpp` are compile-verified via UnrealBuildTool (module build succeeded) but not executed under the editor (no live UE in M6). M7 live UE 5.6 restart/recovery Scenarios 1–8 remain.

M7 **hardening/pre-flight** (see `docs/UNREAL_M7_HARDENING.md`) has repaired the three production gaps M6 surfaced and verified them deterministically: (1) framed-catalog integrity now deep-thaws and validates canonical `known_jobs` framing; (2) the C++ witness journal is append-only with monotonic `phase_sequence` per Contract §30/§37; (3) `execution_deadline`/`submission_deadline` expiry now transitions unresolved jobs to `RECOVERY_FAILED` + `EXHAUSTED`. M7 live Scenarios 1–8 are **not** run and require explicit human authorization.

## Current development workflow and model strategy

Atlas may use different reasoning models for development without changing Atlas authority. The current development architecture intentionally separates **implementation assistance** from **adversarial evaluation**:

```text
Hermes + development model
        ↓
implementation proposal / code changes
        ↓
Atlas contracts + deterministic tests
        ↓
independent review / red-team evaluation
        ↓
mainline merge only after evidence supports it
```

A model/provider switch is therefore an engineering experiment, not an architectural change. The current consideration is to compare Gemini with **DeepSeek V4 Flash** on token efficiency versus reasoning quality for Hermes-led development tasks. **Claude 5 and Astra remain reserved for red-team evaluation**, preserving independent adversarial review while the development model is evaluated.

ChatGPT can participate in the evaluation of Hermes-produced work as an additional review layer. This does not grant ChatGPT authority over Atlas execution; the repository contracts, tests, independent verification, and human merge decision remain authoritative.

The model comparison should be judged on concrete development outcomes such as useful reasoning per token, defect discovery, architectural fidelity, regression rate, test-fix efficiency, and amount of rework—not token consumption alone.

## Non-regression rules

- Qwen and other models remain proposal/reasoning-only.
- Never allow model-supplied authorization IDs, receipts, protected Unreal intent, or protected production flags to become Atlas authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from transport/write success alone.
- Preserve independent verification and the evidence ledger.
- Keep engine-specific behavior behind adapter/tool boundaries.
- Preserve canonical Digital Twin identity separately from production artifacts.
- Never weaken tests or contracts merely to make a model-produced change pass.
- Treat red-team models as evaluators, not alternate execution authorities.
- Do not run workflow/action-runner tests unless explicitly authorized.
- Do not rewrite historical dated handoffs merely to make them agree with the latest checkpoint.

## End-of-night resume point — September 6, 2026

1. Pull the latest `main`.
2. Treat M4 cross-process Unreal recovery and M5 evidence verification as the current merged baseline.
3. Preserve the live UE 5.6 Stage 17 proof as historical evidence of the working production/provenance chain.
4. Continue from the next unresolved Atlas milestone rather than reopening completed M4/M5 work unless a regression appears.
5. For Hermes development-model experiments, compare Gemini vs DeepSeek V4 Flash while keeping Astra and Claude 5 available for red-team evaluation.

Historical handoff snapshots remain archival records and should not be rewritten to reflect this checkpoint.