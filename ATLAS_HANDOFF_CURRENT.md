# Atlas Current Development Handoff

**Updated:** September 4, 2026 — Stage 17 production artifact lineage is implemented and hardened across Blender and Unreal, with durable persistence, focused integration regression coverage, a disposable Unreal live-proof harness, and canonical Unreal evidence/receipt snapshot boundaries on mainline. Blender Stage 17 remains user-verified against real Blender 4.4; Unreal Stage 17 provenance is implemented and regression-verified while the real UE 5.6 proof remains the final human validation gate.
**Active branch:** `main`
**Current stage:** Stage 17 — IN PROGRESS

## Authority model

```text
Qwen / AI
  -> reason and propose structured production intent

Python / Atlas
  -> validate, resolve, authorize, execute, track state, verify, recover

Blender / Unreal
  -> controlled production execution

Independent verification
  -> establish what actually happened
```

Qwen never receives direct production execution or authorization authority.

## Stage 13–16 baseline

Stage 13 multi-step partial-progress recovery is complete for the current contract and live verified against Blender 4.4.

Stage 14 dependency-aware task composition is complete for the current contract. Dependency validation, exact authorization binding, serial deterministic execution, inherited prerequisite handling, and cross-process dependency-aware recovery have been implemented and live verified.

Stage 15 semantic soccer-production tasks are complete for the current contract. `ProductionTaskDefinition`, reusable fragments, target-state evaluation, canonical soccer-production templates, the versioned catalog, and semantic provenance persistence are established and live verified.

Stage 16 Qwen integration is live verified through proposal, Atlas authorization, real Blender mutation, cross-process recovery, and a fresh Qwen-guided recovery recommendation that remains advisory-only.

## Stage 17 — Production artifact lineage

`planning/production_artifact.py` defines `ProductionArtifactManifest`, a provenance-only contract connecting a production representation to the canonical Atlas Digital Twin, source artifacts, workflow provenance, verification evidence, execution receipts, engine metadata, and a deterministic integrity digest.

The manifest has separate engine-specific bridges for Blender and Unreal. Both bridges enforce their engine identity at construction time, and the corresponding lineage-verification helpers enforce the same identity on persisted/tampered manifests.

### Blender Stage 17 — LIVE VERIFIED

The Blender bridge accepts only existing immutable `BlenderExecutionReceipt` and `BlenderPersistenceEvidence` objects. A focused integration regression exercises the existing `BlenderExecutionBoundary.execute_with_persistence(...)` closed loop, constructs the immutable manifest, durably persists and reloads it, and independently verifies the exact receipt/evidence lineage without causing another Blender operation.

The user executed `python live_blender_production_artifact_proof.py` locally against real Blender 4.4 after pulling commit `5306a6b` and received:

```text
ATLAS LIVE BLENDER PRODUCTION ARTIFACT PROOF: PASS
REAL BLENDER WRITE -> FRESH SCENE INSPECTION -> IMMUTABLE RECEIPT/EVIDENCE -> DURABLE MANIFEST -> RELOAD -> EXACT LINEAGE VERIFIED
```

### Unreal Stage 17 — IMPLEMENTED / REAL UE PROOF PENDING

The existing Unreal render boundary already produces verified `inspect_render_job` evidence and an evidence-bound immutable `UnrealRenderReceipt` for semantically completed successful renders. `ProductionArtifactManifest.from_unreal_render_receipt(...)` requires:

- `engine == "Unreal"`;
- evidence operation `inspect_render_job`;
- `verified == True`;
- receipt/evidence identity to match exactly;
- the manifest artifact path to appear in independently observed `output_files`.

`verify_unreal_render_lineage(...)` re-checks those bindings without executing Unreal, authorizing work, scheduling, or recovering a render job. `ProductionArtifactStore` provides durable versioned manifest persistence with atomic replacement, flushing, and fail-closed reload validation.

`UnrealEvidence` and `UnrealRenderReceipt` now expose canonical detached `snapshot()` / `from_snapshot(...)` boundaries with exact-field fail-closed validation. `UnrealRenderReceiptStore` uses the canonical receipt snapshot boundary while preserving its versioned storage envelope.

The disposable `live_unreal_production_artifact_proof.py` harness consumes an already verified Unreal evidence snapshot plus matching render receipt, constructs the manifest, persists/reloads it, independently verifies exact lineage, and reports the resulting digest identities. It does not submit or execute a render and does not introduce a second Unreal execution path.

Focused regression coverage for the harness and canonical snapshot boundaries passes on Python 3.9 and 3.11. The corrected mainline test run after the receipt-store compatibility fix passed completely.

The remaining gate is a human-run proof using evidence emitted by the existing proven Unreal Engine 5.6 render boundary. `docs/STAGE17_UNREAL_PROOF.md` records the exact proof procedure and the expected evidence boundary.

### Controller boundary hardening

The current `AgentControllerHost` now takes the protected Unreal production `intent` from the host-owned `TrustedUnrealContext` rather than accepting a model-supplied intent as authority. When a model response carries a different intent, the host preserves the trusted intent and records the mismatch as diagnostic context rather than allowing the model value to become the protected request identity.

A deterministic regression covers both explicit model-intent substitution and the no-model-intent case. This increment does not add execution, scheduling, recovery, or a second authorization system.

### Proven Unreal render boundary

```text
render configuration
  → configuration verification
  → Movie Render Queue submission
  → dynamic job ID
  → asynchronous job inspection
  → semantic completion verification
  → actual output artifact discovery
  → filesystem validation
  → verified evidence
  → UnrealRenderReceipt
  → durable receipt persistence
  → Stage 17 ProductionArtifactManifest proof harness
```

Cross-process Unreal render-job recovery remains unimplemented and must not be implied by receipt persistence or Stage 17 provenance.

## Current next gate

Run the disposable human Unreal proof against a real completed UE 5.6 render using the existing verified receipt/evidence output. The proof must construct and reload the production-artifact manifest, verify exact lineage, and preserve the non-authorizing boundary.

No action-runner test should be run for this gate unless explicitly authorized.

## Non-regression rules

- Qwen remains proposal-only.
- Never accept model-supplied authorization IDs or receipts as authority.
- Never accept model-supplied protected Unreal intent as authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from transport/write success alone.
- Preserve independent verification and the evidence ledger.
- Keep engine-specific behavior behind adapter/tool boundaries.
- Keep dependency-aware execution serial until concurrency is independently justified.
- Preserve canonical Digital Twin identity separately from production artifacts.
- Do not claim cross-process Unreal job recovery unless separately implemented and verified.
- Do not run workflow/action-runner tests unless explicitly authorized.

## Recent mainline merges

- PR #49 merged the Stage 12 task-aware autonomous recovery continuation.
- PR #52 restored and locked engine-specific production-artifact factory binding after the PR #49 merge-resolution regression.
- PR #54 hardened Unreal artifact lineage to require verified `inspect_render_job` evidence.
- PR #53 hardened Blender lineage verification to enforce `engine == "Blender"` symmetrically with Unreal.
- PR #55 added the disposable Unreal production-artifact proof harness and focused regression coverage.
- PR #56 added canonical Unreal evidence/receipt snapshots and integrated them into the proof harness/store boundary.
