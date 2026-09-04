# Atlas Current Development Handoff

**Updated:** September 4, 2026 — end-of-night checkpoint after restoration of the working Unreal 5.6 transport boundary and merge of PR #57.
**Active branch:** `main`
**Current stage:** Stage 17 — IN PROGRESS

## Current repository state

PR #57 (`Restore working Unreal render transport boundary`) has been merged into `main` as commit `3e2e78e654cab3db5f17ba9739ae5c609d82f386`. The restored branch was based on the last known working Unreal harness snapshot and reinstates the missing UE 5.6 project, render fixtures, transport server, transport headers/build module, render/world-save boundary tests, and supporting commandlets.

The restored Unreal tree was compile-verified locally with UE 5.6: **19/19 build actions succeeded**. `AtlasTransportServer.cpp`, `AtlasUnrealTransport.cpp`, the render boundary source, and the world-save boundary source all compiled and linked successfully.

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

The UE 5.6 render boundary has now been restored to `main` and compile-verified locally. The working boundary includes the controlled project and render fixtures plus the Unreal transport server needed for the render path.

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

The restored transport is an execution boundary only. The Python host remains the authority source for protected Unreal intent, authorization context, sequence path, and the production marker.

## Controller-to-Unreal trust boundary

The current mainline host remains intentionally narrow while PR #50 stays isolated. Protected Unreal production requests use the host-owned `TrustedUnrealContext` as the authority source for protected intent, authorization context, sequence path, and the production marker.

Model-supplied protected intent cannot replace the trusted intent. Conflicting model intent is retained only as diagnostic state. Model-supplied production flags cannot disable the host-owned production marker. The integration seam rejects missing required trusted context before execution.

The restored C++ transport does not create a second authorization layer; it validates the transport contract and executes only through the existing Atlas integration boundary.

## Important Unreal boundary

The Unreal runtime render-job registry remains in-memory. `UnrealRenderReceiptStore` provides durable receipt persistence, but cross-process Unreal render-job recovery is not implemented.

Do not represent receipt persistence as job persistence.

## Validation status

Verified in this checkpoint:

- UE 5.6 editor compilation of the restored Unreal harness: **19/19 actions succeeded**.
- `AtlasTransportServer.cpp` compiled and linked successfully.
- `AtlasUnrealTransport.cpp` compiled and linked successfully.
- Unreal render/world-save boundary sources compiled successfully.

Not yet verified in this checkpoint:

- a new deterministic Python test run for the September 4 controller trust-boundary changes;
- the human UE 5.6 Stage 17 provenance proof;
- live reconstruction of the verified Unreal evidence/receipt pair into a durable production-artifact manifest.

Do not represent the older deterministic test results as validation of the newest changes.

## Current next gate

At the next development session:

1. Pull the latest `main`.
2. Run focused deterministic tests for the newest Unreal/controller trust-boundary changes.
3. Run the human UE 5.6 Stage 17 provenance proof using the restored render boundary.
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
- PR #57 restored the working Unreal 5.6 transport/render boundary and was merged as `3e2e78e654cab3db5f17ba9739ae5c609d82f386`.

## Historical documentation

Older dated handoff snapshots are archival records and should not be rewritten. This document is the authoritative current development handoff.