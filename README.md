

---

## REV46-M1 — M1 IMPLEMENTATION GATE CLOSED — 2026-10-08

**Design status:** **R12 = CLEAR / FROZEN.** Fresh independent review by **GPT 6.1 Sol** returned **REV46-M1-R12 — CLEAR**.

- R12 artifact: `REV46_M1_R12_FINAL_CLOSURE.txt`
- R12 SHA-256: `75b32f8681a8e1b02110412ea68e0829bca0ae7a4a05208844088af02f8b7b18`
- Authorized implementation baseline: `3dc2fca3d1f26cadd45a6c4d773bcb2e24f7cad7`

**Implementation branch:** `feat/rev46-m1-duplicate-occurrence`

**Implementation commit:** `90e4d0a862cedb0b79b33b703ba716a327230847` (parent `1717c0b8f1633abda9bae51cc9b53eea1f7e033b`).

**Independent implementation review:** **Claude Sonnet — CLEAR WITH MINOR FINDINGS.** The review confirmed: executor-authoritative duplicate-occurrence selection (`face_ids[1]`); exact integer validation with no coercion; no min/max/search/fallback target reconstruction; `expected_face_tuple` taken from the selected occurrence; `params["mesh_id"]` as a consistency check only, with `corr.mesh_id` the authoritative target identity; exact-index mutation; the ordered postcondition; harness-side invocation evidence distinguishing identical `[A,X,A,A]` occurrences; passing W1/W1b live gates; no A-REF implementation; no authority/persistence/recovery/receipt/Unreal scope leakage.

**M1 implementation gate: CLOSED.** Minor findings are non-blocking and do not trigger another R12 revision.

**Documented limitation (non-blocking):** the identical-occurrence mutant (identical `[A,X,A,A]` tuples — the two removal candidates yield the same canonical child) is a documented R12 limitation, not a blocker.

**No R13 is authorized or required.** A-REF implementation has **NOT** started.

**Next gate: A-REF design red-team** — a fresh independent review of the A-REF design artifact is required before any A-REF implementation.


> **CURRENT PAUSE OVERRIDE — Approval Authority Architecture / September 30, 2026 local / October 1 UTC.**
>
> The active engineering focus is the **Blender Approval Authority Architecture**. The Blender capability itself remains stable/frozen for its declared contract, but full production agent readiness remains **NOT ESTABLISHED**.
>
> Rev 8 received an independent **B — PARTIALLY CLOSED / REVISION REQUIRED** verdict. Rev 9 is the architecture-only remediation at SHA `4071ad52bccc02055a26c599827f116925ab878679cea9c9d1cc7db3ea0a23f9`.
>
> **Current gate:** a fresh SHA-bound independent red-team of Rev 9. Hermes' NEW-1…NEW-8 closure claims remain provisional until that review.
>
> No implementation, agent exposure, feasibility implementation, key/TPM/service provisioning, correction-bridge/executor work, or Unreal implementation is authorized before that gate.
>
> Open feasibility prerequisites remain OPEN: A-ENUM, A-INJ, A-TDM-PARSE, A-REF, A-MAT, A-TPM-POLICY, A-NV, A-TOKEN, A-PROF, A-H2.
>
> The Rev 8 independent review confirmed the Rev 4 provenance-laundering defense remained intact. Rev 9 must independently preserve that closure.
>
> **Next single gate: FRESH SHA-BOUND INDEPENDENT RED-TEAM OF REV 9.**
>
> **CURRENT PAUSE OVERRIDE — September 29, 2026 local / September 30 UTC.**
>
> The current engineering focus is **Blender Agent Readiness / authority design**, with Unreal intentionally paused.
>
> Main authority is `2f972a582f9c3288fa2e40f94616c108c3b4976a`.
>
> The Blender capability track is stable/frozen for its declared contract, but the **Blender agent is not yet production-ready** for the original Atlas mission: the real soccer-asset gate is blocked, canonical-agent integration is not established, and no legitimate production approval issuer exists for canonical Winding/Merge corrections.
>
> W1/W1b remain agent-blocked. Winding/Merge remain agent-blocked pending a new approval-authority design. No implementation is authorized from this pause.
>
> **Next single gate: DESIGN NEW APPROVAL AUTHORITY.**

> CURRENT PAUSE — September 29, 2026 UTC / September 28 local.
>
> MOCK TWIN VALIDATED / FROZEN. The synthetic U1 validation project completed its final isolated evidence pass and independent review. The portable read-only extraction plugin is merged in PR #146 at 8f601184e62da2362ec38c948e61b7ff8058f95b.
>
> Final review bundle: eacdeba5cfec9e8fa4af486e8ea0aaaa8f617bfbf7c43f5da92bd17067cc0079; GLM CLEAR; GPT-SOL-6 CLEAR WITH MINOR FINDINGS, blockers none. The mock is a validation fixture only: U1 PRODUCTION AUTHORITY IS NOT ESTABLISHED, and mock observations must not populate planning/m12/expectation.py.
>
> The next task is real production U1 intake/evidence collection against the actual .uproject and reviewed target/expectation population. Do not create another mock project and do not begin R2-B implementation.
>
> R2-B REV10 remains the frozen external normative baseline (SHA-256 5d2409cf2ee0c15e35f73ecbae59ab2e03ddbd70abdb3f8c5e4dfc1d9b0d452f); fresh GLM + GPT-SOL-6 reviews are CLEAR, but implementation remains unauthorized pending U1/U7 and the human gate.
>
> Full restart details: ATLAS_HANDOFF_2026-09-29_U1_MOCK_VALIDATION_CLOSEOUT.md.

# Atlas

> **Current-state reconciliation — September 27, 2026.** M7 is complete/live-proven; State Extraction Fidelity v1 is complete/merged/live-gated; M12.5 v1 is implemented/merged; **M12.6 R2-A is landed and M12.6 R2-B is now paused at the REV4 independent-review gate.**
>
> **Documentation checkpoint base:** main @ 2b39acb005e406f4f992531257b6ff3d82852ee8. This pause adds documentation only; production implementation state is unchanged.
>
> **Landed M12.6 R2-A:** 7b591445d1a11e0ae181330fafaf0956d6cebdbb via PR #143; merge commit e9a572c2104153285b1139d7dc09d1e9acd479ac.
>
> **R2-A contract:** ATLAS_M12_6_R1_NORMATIVE_DESIGN_REV25.md, SHA-256 8f9cccc6c59635a554cc63f200c719d80c09dce0372e13715c83aee1809ae1c8.
>
> **Current R2-B normative artifact:** C:\Users\Gavin's PC\Desktop\ATLAS_M12_6_R2B_NORMATIVE_DESIGN_REV4.md
>
> **REV4 exact SHA-256:** 6fc8027cd79908be0b8a551cf94f9ceafd6ada6f2237a372bca4fbb739c5fc7d
>
> **REV4 declaration self-digest:** 7e2a2012b019300ef58e8514ebf2f67bb064b21aa1b003930a3e3c1798158581
>
> REV4 is the current external design candidate. Hermes' artifact-local self-audit is complete, but the required fresh blind GLM + GPT-SOL-6 review has **not yet been completed**. **Implementation remains NOT AUTHORIZED.**
>
> Previous REV3 dual review remains historical evidence: GLM **CLEAR**; GPT-SOL-6 **BLOCKED** on three surgical blockers. REV4 was authored to close those findings.
>
> **R2-B current gate:** fresh exact-SHA dual review of REV4, with special adversarial attention to the positive-claim authority (PCA), mutation + recomputed-digest attack, and evidence_source_class derivation.
>
> Historical dated handoffs are archival. The authoritative restart surfaces are the current handoff files listed below.

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