# Atlas Current Development Handoff

**Updated:** September 4, 2026 — end-of-night checkpoint. Stage 17 production-artifact lineage is implemented and hardened across Blender and Unreal, with durable persistence, canonical Unreal evidence/receipt snapshot boundaries, focused regression coverage, and a disposable Unreal live-proof harness on `main`. Blender Stage 17 is user-verified against real Blender 4.4. Unreal Stage 17 provenance is implemented and regression-verified; the real UE 5.6 provenance proof remains the final human validation gate.
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

The manifest has separate engine-specific bridges for Blender and Unreal. Both bridges enforce engine identity at construction time and during lineage verification. Unreal lineage additionally requires verified `inspect_render_job` evidence and an artifact path independently observed in the render output files.

### Blender Stage 17 — LIVE VERIFIED

The user verified the real Blender 4.4 production-artifact path: real mutation, fresh independent inspection, immutable receipt/evidence capture, durable manifest persistence, reload, and exact lineage verification.

### Unreal Stage 17 — IMPLEMENTED / REAL UE PROOF PENDING

The proven Unreal render boundary is:

```text
render configuration
  -> configuration verification
  -> Movie Render Queue submission
  -> dynamic job ID
  -> asynchronous job inspection
  -> semantic completion verification
  -> actual output artifact discovery
  -> filesystem validation
  -> verified inspect_render_job evidence
  -> UnrealRenderReceipt
  -> durable receipt persistence
```

Stage 17 extends this into a provenance-only continuation:

```text
verified UnrealEvidence snapshot
  -> immutable receipt reconstruction
  -> ProductionArtifactManifest
  -> durable ProductionArtifactStore
  -> reload
  -> exact lineage verification
```

`UnrealEvidence.snapshot()` / `from_snapshot(...)` and `UnrealRenderReceipt.snapshot()` / `from_snapshot(...)` are canonical detached serialization boundaries with fail-closed exact-field validation. The receipt store preserves its separate versioned storage envelope.

The disposable `live_unreal_production_artifact_proof.py` harness consumes an already verified evidence/receipt pair, constructs the manifest, persists/reloads it, independently verifies exact lineage, and reports artifact/evidence/receipt/manifest digest identities. It does not submit or execute a render and does not implement Unreal job recovery.

Focused regression coverage for the harness and snapshot boundaries passed on Python 3.9 and 3.11. The latest controller trust-boundary increments have **not** yet been validated by a new local test run in this session.

The remaining Stage 17 gate is a human-run proof using evidence emitted by the existing proven Unreal Engine 5.6 render boundary. `docs/STAGE17_UNREAL_PROOF.md` records the exact procedure.

## Controller-to-Unreal trust boundary

The current mainline host remains intentionally narrow while PR #50 stays isolated. Protected Unreal production requests now use the host-owned `TrustedUnrealContext` as the authority source for protected intent, authorization context, sequence path, and the production marker.

Model-supplied protected intent cannot replace the trusted intent. Conflicting model intent is retained only as diagnostic state. Model-supplied production flags cannot disable the host-owned production marker. The integration seam rejects missing required trusted context before execution.

This work adds no second authorization system, scheduler, recovery engine, or Unreal execution path.

## Important Unreal boundary

The Unreal runtime render-job registry remains in-memory. `UnrealRenderReceiptStore` provides durable receipt persistence, but cross-process Unreal render-job recovery is not implemented.

Do not represent receipt persistence as job persistence.

## Current next gate

At the next development session:

1. Pull the latest `main`.
2. Run focused deterministic tests for the newest Unreal/controller trust-boundary changes.
3. Run the human UE 5.6 Stage 17 provenance proof using the existing verified render evidence/receipt pair.
4. Confirm manifest persistence, reload, exact lineage, and digest identities.
5. Then resume selective integration of the stronger historical controller-host architecture from PR #50.

No action-runner/workflow test should be run for the live gate unless explicitly authorized.

## Non-regression rules

- Qwen remains proposal-only.
- Never accept model-supplied authorization IDs or receipts as authority.
- Never accept model-supplied protected Unreal intent or production flags as authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from transport/write success alone.
- Preserve independent verification and the evidence ledger.
- Keep engine-specific behavior behind adapter/tool boundaries.
- Keep dependency-aware execution serial until concurrency is independently justified.
- Preserve canonical Digital Twin identity separately from production artifacts.
- Do not claim cross-process Unreal job recovery unless separately implemented and verified.
- Do not run workflow/action-runner tests unless explicitly authorized.

## Recent mainline work

- PR #49 merged the task-aware autonomous recovery continuation.
- PR #52 restored and locked engine-specific production-artifact factory binding.
- PR #53 hardened Blender lineage verification.
- PR #54 hardened Unreal lineage verification to require verified `inspect_render_job` evidence.
- PR #55 added the disposable Unreal production-artifact proof harness.
- PR #56 added canonical Unreal evidence/receipt snapshots.
- Subsequent mainline commits hardened the protected Unreal controller host against model-controlled intent/production-state substitution and added deterministic regression coverage.

## Historical documentation

Older dated handoff snapshots are archival records and should not be rewritten. This document is the authoritative current development handoff.