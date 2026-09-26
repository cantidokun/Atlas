# Atlas

> **Current-state reconciliation — September 26, 2026.** M7 is complete/live-proven; State Extraction Fidelity v1 is complete/merged/live-gated; M12.5 v1 is implemented/merged; **M12.6 R2-A is paused at the R16 implementation-gate adjudication point.**
>
> **Functional implementation baseline:** `4897d9d4524df6cc2fa59caf0c86fa0b269f35a6`. **PR #142:** OPEN / DRAFT / BLOCKED / NOT MERGED.
>
> **R16 artifact:** `C:\Users\Gavin's PC\Desktop\ATLAS_M12_6_R1_NORMATIVE_DESIGN_REV16.md`
>
> **R16 exact SHA-256:** `6a4520ad417c85ce16239b7b7afc18bc9b1585720c550744e8025e9eef5a1eff`
>
> GLM returned **CLEAR** on fresh inspection of the exact R16 artifact. GPT-SOL-6 returned **BLOCKED** on one implementation-gate finding, **R16-1**, concerning Part XX case 8. The dispute is intentionally unresolved at this pause.
>
> Historical dated handoffs are archival. The authoritative restart surfaces are the current handoff files listed below.

## Active development checkpoint — September 24, 2026

### M12.6 — R2-A / R16 IMPLEMENTATION GATE PAUSED

- Normative artifact: **M12.6-R1-R16**.
- Exact external path: `C:\Users\Gavin's PC\Desktop\ATLAS_M12_6_R1_NORMATIVE_DESIGN_REV16.md`.
- Exact SHA-256: `6a4520ad417c85ce16239b7b7afc18bc9b1585720c550744e8025e9eef5a1eff`.
- R16 closes the two R15 implementation-gate blockers: the full nine-case Part XX matrix and the self-locating `ARTIFACT_DIGEST_RULE`.
- Artifact-local validation: **35 PASS / 0 FAIL**.
- **GLM: CLEAR.**
- **GPT-SOL-6: BLOCKED — R16-1.**
- R16-1 concerns whether Part XX case 8 can actually reach S4 with the mandated consumer-facing tuple when the matrix common base requires a supplied expectation and S3 validation precedes S4 lookup.
- Current status: **implementation paused pending targeted adjudication**.
- No R17 artifact exists; no production code has been changed; PR #142 remains historical blocked evidence only.
- Required next gate: literal case-8 execution-path adjudication. If invalid → preserve R16 byte-identically and proceed to human authorization. If valid → minimal R17 gate correction and fresh blind GLM + GPT-SOL-6 review.
- After the contract reaches the required CLEAR + human authorization state, implementation starts from a fresh branch on the functional main baseline `4897d9d4524df6cc2fa59caf0c86fa0b269f35a6`, never from PR #142.

### M12.5 — V1 IMPLEMENTED / MERGED

- PR #137 architecture: **MERGED**.
- PR #138 implementation: **MERGED**.
- Merge commit: `9b644d09a434ca97c21a15552383ff1268935a1f`.
- Dedicated M12.5 semantic live promotion remains separate from repository deterministic CI.

### Closed / frozen tracks

- Blender: **CLOSED** for the current declared contract.
- Temporal: **MERGED / LIVE-GATED / FROZEN**.
- M11: **FROZEN**.
- M12.1–M12.4: **IMPLEMENTED**.
- M13.8/token optimization: **PAUSED**.
- Older Unreal PR stack: **selective integration only; no blanket merge**.

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

# Current position — September 19, 2026

**Temporal Observation + State Delta v1**

- PR #109 is merged to `main` at `7c63c3190c4adacfddb8d8b6a35721234876669b`.
- Real Blender 4.4.3 L-1–L-5 validation: PASS.
- The Temporal v1 contract and implementation are now part of `main`; the older uncommitted-candidate/pause wording above is no longer current.

**Blender Wave 15 — W1/W1b/W2 live boundary closure — COMPLETE**

- Authoritative design merged in PR #114 → `b9a589c215f6d769fec9f340eb24f4f90d423a3b`.
- W1/W1b live gate merged in PR #115 → `dcb04f704644b7814bd9fd7eae314423dd528860`.
- W2 authorization-aware live gate merged in PR #116 → `4a27af868c418181c3363b939d585944599ac400`.
- Blender 4.4.3 / build `802179c51ccc` live evidence passed independently for both gate families.
- W1/W1b: 49 live gate assertions passed; W2: 34 live gate assertions passed.
- Exact-head CI remained green; the deterministic passed count remained **4,193**.
- Frozen asset SHA-256 remained `cf618bdc1123734bf49bf6f22677ded3f2e6c3fa2803b97f7a6cf7c7c66f11aa`.
- No production semantic changes were introduced by the Wave 15 live-closure PRs.
- W2 authorization semantics remain isolated from W1/W1b; W1/W1b remain isolated from W2.
- The remaining minor red-team findings are record-level/documentation refinements and do not block the merged implementation.

**Next Blender step**

- Wave 15 is closed across all three live correction families.
- Do not infer a new correction implementation from the Wave 15 completion alone.
- The next Blender milestone should begin with a **read-only discovery/design gate** against the current `main`; no new production semantic is authorized until that gate establishes the next bounded capability and its live evidence requirements.
- Preserve the existing separation between canonical contract authority, engine-specific adapters, deterministic validation, live evidence, and independent red-team review.

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

M6 suite: **79 tests green**; full deterministic repository suite at the M6 milestone: **1088 passed** (current counts are tracked in `ATLAS_HANDOFF_CURRENT.md`). C++ automation additions (malformed-journal handling, capability/schema reporting, and — via M7 hardening — journal append/history retention) in `AtlasUE56RenderJobBoundaryTest.cpp` are compile-verified via UnrealBuildTool (module build succeeded) but not executed under the editor (no live UE in M6).

M7 **hardening/pre-flight** (see `docs/UNREAL_M7_HARDENING.md`) has repaired the three production gaps M6 surfaced and verified them deterministically: (1) framed-catalog integrity now deep-thaws and validates canonical `known_jobs` framing; (2) the C++ witness journal is append-only with monotonic `phase_sequence` per Contract §30/§37; (3) `execution_deadline`/`submission_deadline` expiry now transitions unresolved jobs to `RECOVERY_FAILED` + `EXHAUSTED`.
M7 live status (September 22, 2026): **COMPLETE / MERGED / LIVE-PROVEN**. The first real UE 5.6.1 keeper-controlled execution rendered successfully, verified 24/24 artifacts, drained on the retained Job Object handle, and closed as **Case B with exactly one production receipt and zero adoption-path engine RPCs**. Four negative controls were independently refused. Exact-head CI was green and the independent post-live review returned **CLEAR / READY FOR INTEGRATION**. The frozen S1 rehearsal evidence is not the receipt source. The full S1-S8 scenario matrix is not being represented as complete by this rung.

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