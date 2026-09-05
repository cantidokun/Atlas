# Atlas Current Development Handoff

**Updated:** September 5, 2026 — Clean Unreal autonomy bridge merged into main via PR #59.
**Active branch:** `main`
**Current stage:** Stage 17 — IN PROGRESS

## Current repository state

PR #59 (`feat: port Unreal autonomy to mainline`) has been merged into `main`. This integrates the clean, selective Unreal autonomy execution bridge directly above current `main` without importing historical or deprecated subsystem bloat.

The repository now possesses:
- `planning/unreal_execution_boundary.py`: Narrow, fail-closed execution boundary mapping validated tool calls to typed `UnrealOperation` primitives.
- `planning/unreal_autonomous_executor.py`: Pure `ToolExecutor`-compatible adapter (`(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]`) directly consumable by `AutonomousFutureRuntime` and `AutonomousTaskRuntime`.
- `controller/agent_controller_host.py`: Wired with `build_unreal_autonomous_executor()`, safely binding host-owned trusted context and real Unreal integration without creating duplicate authorization or execution authorities.
- `planning/unreal_transport_contract.py`, `planning/unreal_transport_serialization.py`, `planning/unreal_transport_named_pipe.py`, `planning/unreal_adapter_production.py`: Verified production transport layer.

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

### Unreal Stage 17 — IMPLEMENTED / LIVE UNVERIFIED (REAL UE PROOF PENDING)

The UE 5.6 render boundary is compile-verified locally (19/19 build actions succeeded on `AtlasTransportServer.cpp`, `AtlasUnrealTransport.cpp`, and boundary tests). The execution bridge to Atlas's generic autonomous runtime is implemented and deterministic-test verified.

The Stage 17 production-artifact manifest bridge and its proof harness are regression-verified, and the authoritative independent verification boundary `verify_render_job_evidence(...)` (`planning/unreal_evidence_contract.py`) has been implemented to convert raw `inspect_render_job` state into verified `UnrealEvidence` only after validating semantic completion, canonical identities, and filesystem presence/non-zero size. However, the system has **not yet received live UE 5.6 Stage 17 provenance verification**. Live UE 5.6 proof is the next major validation gate.

```text
render configuration
  -> configuration verification
  -> Movie Render Queue submission
  -> dynamic job ID
  -> asynchronous job inspection
  -> semantic completion verification
  -> actual output artifact discovery
  -> filesystem validation
  -> verify_render_job_evidence
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

For protected Unreal production requests:
- `TrustedUnrealContext` supplies protected intent, authorization context, sequence path, and the production marker;
- model-supplied protected intent cannot replace the trusted intent;
- conflicting model intent is retained only as diagnostic mismatch state;
- model-supplied production flags cannot disable the host-owned production marker;
- the Unreal production integration seam rejects missing required trusted context before execution.

The Unreal transport remains an engine execution boundary, not a second authorization system. Authority remains owned by the trusted Atlas host boundary.

## Important Unreal boundary

The Unreal runtime render-job registry remains in-memory. `UnrealRenderReceiptStore` provides durable receipt persistence, but cross-process Unreal render-job recovery is not implemented.

**Receipt persistence is not equivalent to durable render-job persistence.**

## Validation status

Verified in this checkpoint:

- Clean Unreal autonomy bridge merged to `main` via PR #59;
- 842 deterministic repository tests pass (0 failures);
- CI passed on Python 3.9 and Python 3.11 for the clean PR;
- UE 5.6 editor compilation of the restored Unreal harness: **19/19 actions succeeded**;
- `AtlasTransportServer.cpp` compiled and linked successfully;
- `AtlasUnrealTransport.cpp` compiled and linked successfully;
- Unreal render/world-save boundary sources compiled successfully;
- Blender development and tests completely unaffected.

Not yet verified in this checkpoint:

- the human UE 5.6 Stage 17 provenance proof (`live_unreal_production_artifact_proof.py`);
- live reconstruction of the verified Unreal evidence/receipt pair into a durable production-artifact manifest from real UE 5.6 render output.

Do not represent the older deterministic test results as validation of live execution.

## Current next gate

At the next development session:

1. Pull the latest `main`.
2. Run the human UE 5.6 Stage 17 provenance proof using evidence emitted by the restored render boundary.
3. Confirm manifest persistence, reload, exact lineage, and digest identities via `live_unreal_production_artifact_proof.py`.
4. Address remaining P1 items:
   - Durable render-job state across Unreal/editor process loss (`RenderJobRegistry` on-disk tracking).
   - Blueprint metadata evidence-shape alignment in `AtlasTransportServer.cpp`.

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
- PR #57 restored the working Unreal 5.6 transport/render boundary.
- PR #59 merged the clean Unreal autonomy execution bridge into `main`.

## Historical documentation

Older dated handoff snapshots are archival records and should not be rewritten. This document is the authoritative current development handoff.