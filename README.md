# Atlas

> **Current-state reconciliation — September 22, 2026.** M7 Case-B durable-witness + containment-keeper is complete, merged, and live-proven. Current main is `89ca71180cebd00619d7f839819549cf4ede4be9` (PR #136 merge). The M7 implementation merge is `526b267d1b30b7c0547d2ee0bbd9e936a7c4dff3` (PR #132). Historical dated handoffs remain archival and are not rewritten.

## Active development checkpoint — September 22, 2026

The September 20-21 checkpoint is now superseded by the completed M7 live rung.

### M7 — COMPLETE / MERGED / LIVE-PROVEN

- PR #132 merged the repository-owned containment keeper and M7 provenance hardening.
- The first real UE 5.6.1 keeper-controlled execution closed as **Case B with exactly 1 production receipt and 0 adoption-path engine RPCs**.
- **24/24 artifacts** were independently verified and **4/4 negative controls** refused.
- Exact-head CI for the M7 documentation follow-up was green on Python 3.9 and 3.11.
- Independent post-live review returned **CLEAR / READY FOR INTEGRATION**.
- The frozen S1 rehearsal evidence remains rehearsal/render evidence only; it is not the production receipt source.
- M7 closure does **not** claim that the full Contract V1 §33 S1-S8 scenario matrix was live-executed.

### Unreal State Extraction Fidelity v1 — COMPLETE / MERGED / LIVE-GATED

State Extraction Fidelity v1 is already implemented and merged:

- PR #106 froze Revision 3.3 of the read-only extraction contract and merged the design.
- PR #107 implemented Revision 3.3 and merged the implementation.
- The implementation was independently reviewed **CLEAR**.
- UE 5.6.1 build succeeded, fixture automation passed **8/8**, and the live transport gate passed.
- Positive baseline digest: `5160b6fa11c95d594b6d7262d00ffe742fbf51e996fdef27abc4e793613cc3a` over 1862 canonical bytes.
- Residual cases remain explicitly classified as live-covered, refusal-verified, blocked by engine/API limitation, or not-yet-live-covered; no false live pass is claimed.

The extraction layer is now the factual, read-only Unreal-state source that M12 can consume. It remains distinct from semantic verification and does not itself produce a semantic success claim.

### M12.5 — ACTIVE ARCHITECTURE GATE / NIGHT PAUSE

M12.5 is the active Unreal architecture/reconciliation gate. The work is **paused for the night** at PR #137; implementation remains unauthorized.

Current PR #137 head: `73e1b5d8c159122f14ec93a5a00e8996cd46c169` (draft, documentation/design only).

The independent-review sequence is: GLM exact-head review → final architecture CLEAR → implementation authorization → deterministic implementation. Hermes's latest review found two blockers and two major findings at an earlier remediated head; those design issues were incorporated into the current head. Hermes disclosed that this was not a third-party gate because it was the same agent family that authored related work.

After the final handoff commits, GitHub Actions `Atlas Tests` run **#2242** is still **IN PROGRESS** on the current documentation head; no CI pass is claimed.

M12.5 will consume the frozen semantic task/plan contracts plus authoritative Unreal state extraction and existing verified render evidence where applicable. It will evaluate target-state invariants fail-closed, bind the result to task/plan/source digests and observation identities, and produce a deterministic semantic verification result.

M12.5 will **not** create a second executor, authorization authority, scheduler, recovery authority, render verifier, or receipt issuer. Render-bearing completion remains dependent on the existing M4–M10 render submission/recovery/evidence/receipt path.

### Other current tracks

- Blender: **CLOSED** for the current declared contract.
- M11: **FROZEN**.
- M12.1-M12.4: **implemented**.
- M12.5: **architecture/reconciliation gate paused at PR #137; final independent review pending; implementation not authorized**.
- M13.8/token optimization: **paused**.
- Older Unreal PR stack: **do not blanket-merge**; retain selective-integration discipline.

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