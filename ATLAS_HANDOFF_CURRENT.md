# Atlas Current Development Handoff

**Updated:** September 4, 2026 — Stage 17 production artifact lineage is implemented and hardened across Blender and Unreal, with durable persistence and focused integration regression coverage. Blender Stage 17 remains user-verified against real Blender 4.4; Unreal Stage 17 has the offline provenance/persistence contract in place, while live production-artifact proof remains the next human validation gate.
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

The proven live path establishes real Blender mutation, fresh independent scene inspection, immutable receipt/evidence capture, durable manifest persistence, reload integrity, and exact provenance binding.

### Unreal Stage 17 — IMPLEMENTED / HUMAN LIVE PROOF PENDING

The existing Unreal render boundary already produces verified `inspect_render_job` evidence and an evidence-bound immutable `UnrealRenderReceipt` for semantically completed successful renders. `ProductionArtifactManifest.from_unreal_render_receipt(...)` now requires:

- `engine == "Unreal"`;
- evidence operation `inspect_render_job`;
- `verified == True`;
- receipt/evidence identity to match exactly;
- the manifest artifact path to appear in independently observed `output_files`.

`verify_unreal_render_lineage(...)` re-checks those same bindings without executing Unreal, authorizing work, scheduling, or recovering a render job. `ProductionArtifactStore` provides durable versioned manifest persistence with atomic replacement, flushing, and fail-closed reload validation.

Focused integration coverage exercises Unreal receipt → manifest → durable store → reload → exact lineage verification and rejects evidence, receipt, engine, output-path, and persisted-envelope substitutions. This remains an offline contract gate; no claim of live Unreal production-artifact manifest proof is made yet.

The previously proven real Unreal Engine 5.6 render path remains intact:

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
```

Cross-process Unreal render-job recovery remains unimplemented and must not be implied by receipt persistence or by Stage 17 provenance.

## Current next gate

The next substantive Stage 17 milestone is a disposable, human-run Unreal proof equivalent to the Blender proof: consume an already verified real Unreal render receipt/evidence pair, construct the production artifact manifest, persist and reload it through `ProductionArtifactStore`, independently verify exact lineage, and report the resulting digest identities. The proof must remain non-authorizing and must not add a second Unreal execution path.

No action-runner test should be run for this gate unless explicitly authorized. The human live Unreal validation should use the existing proven Unreal render boundary rather than inventing a parallel transport or runtime.

## Non-regression rules

- Qwen remains proposal-only.
- Never accept model-supplied authorization IDs or receipts as authority.
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
