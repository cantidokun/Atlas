# Atlas Unreal Agent — Current Handoff

**Updated:** September 5, 2026 — Clean Unreal autonomy bridge merged into main via PR #59.
**Active Atlas branch:** `main`
**Current focus:** Stage 17 production-artifact lineage, with the Unreal autonomy bridge and execution boundary merged to main and the live UE 5.6 provenance proof pending.

## Architectural position

Atlas owns the canonical Digital Twin. Unreal is a downstream controlled production representation/execution environment around that canonical state.

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
independent evidence (UnrealEvidence, verified=False)
        ↓
Atlas independent verification
        ↓
UnrealRenderReceipt -> ProductionArtifactManifest
```

Key authority invariants:
- `UnrealAutonomousExecutor` is an execution adapter, NOT an autonomous runtime.
- `UnrealExecutionBoundary` is a tool/operation validation boundary, NOT an authorization authority.
- `AutonomousTaskRuntime` / `AutonomousFutureRuntime` remains the single autonomous progression authority.
- `TrustedUnrealContext` remains the host-owned source of truth for protected production intent, sequence path, and production markers.
- Transport success != verification success: `UnrealEvidence` returns `verified=False` by default.
- Neither the bridge nor the adapter issues `UnrealRenderReceipt`. Independent verification downstream establishes verified evidence.

## Restored and compile-verified Unreal execution baseline

PR #57 restored the working Unreal 5.6 execution boundary to `main` (19/19 build actions succeeded on UE 5.6 editor build). PR #59 merged the clean autonomy bridge connecting `AutonomousTaskRuntime` to `UnrealAdapterProduction` and the C++ named-pipe server.

The working render workflow remains:

```text
render configuration
  → configuration verification
  → Movie Render Queue submission
  → dynamic job ID
  → asynchronous job inspection
  → semantic completion verification
  → actual output artifact discovery
  → filesystem validation
  → verified inspect_render_job evidence
  → evidence-bound UnrealRenderReceipt
  → durable receipt persistence
```

The previously proven controlled live render parameters were:

```text
resolution:       640x360
frame range:      1–2
output format:    PNG
output directory: Saved/AtlasRenderOutput
```

**Cross-process Unreal render-job recovery is not implemented.** The runtime render-job registry remains in-memory. Receipt persistence must not be described as job persistence.

## Stage 17 — production-artifact provenance

`ProductionArtifactManifest.from_unreal_render_receipt(...)` is a provenance-only bridge from an existing immutable `UnrealRenderReceipt` plus `UnrealEvidence`.

Required lineage invariants:

```text
engine                     == Unreal
operation_name             == inspect_render_job
verified                   == True
receipt.matches(evidence)  == True
artifact_path              ∈ independently observed output_files
```

`verify_unreal_render_lineage(...)` rechecks those bindings without executing Unreal, authorizing work, scheduling a render, or recovering a job.

`ProductionArtifactStore` provides durable versioned manifest persistence with fail-closed reload and integrity validation.

`UnrealEvidence.snapshot()` / `from_snapshot(...)` and `UnrealRenderReceipt.snapshot()` / `from_snapshot(...)` are canonical detached serialization boundaries with exact-field fail-closed validation.

The disposable `live_unreal_production_artifact_proof.py` harness consumes the already verified evidence/receipt pair, constructs the manifest, persists/reloads it, independently verifies exact lineage, and reports artifact/evidence/receipt digests. It does not submit or execute a render.

## Controller-to-Unreal trust boundary

For protected Unreal production requests:

- `TrustedUnrealContext` supplies protected intent, authorization context, sequence path, and the production marker;
- model-supplied protected intent cannot replace the trusted intent;
- conflicting model intent becomes diagnostic mismatch state only;
- model-supplied production flags cannot disable the host-owned production marker;
- the Unreal production integration seam rejects missing required trusted context before execution.

The C++ transport is an engine execution/transport boundary, not a second authorization system. Authority remains owned by the trusted Atlas host boundary.

## Validation status

Verified in this checkpoint:

- Clean Unreal autonomy bridge merged to `main` via PR #59;
- 842 deterministic repository tests pass (0 failures);
- CI passed on Python 3.9 and Python 3.11 for the clean PR;
- UE 5.6 editor compilation of the restored Unreal harness: **19/19 actions succeeded**;
- `AtlasTransportServer.cpp` compiled and linked successfully;
- `AtlasUnrealTransport.cpp` compiled and linked successfully;
- render/world-save boundary sources compiled successfully;
- Blender development and tests completely unaffected.

Previously verified:

- deterministic Stage 17 provenance/snapshot coverage on Python 3.9 and 3.11;
- the original real UE 5.6 render/receipt path.

Still pending:

- fresh execution of the restored UE 5.6 render path;
- the human UE 5.6 Stage 17 provenance proof using that fresh verified evidence/receipt pair (`live_unreal_production_artifact_proof.py`).

## Resume point

1. Pull the latest `main`.
2. Exercise the restored UE 5.6 render boundary and capture fresh verified evidence/receipt data.
3. Run `live_unreal_production_artifact_proof.py` against that verified evidence/receipt pair.
4. Confirm manifest persistence, reload, exact lineage, and digest identities.
5. Address remaining P1 items:
   - Durable render-job state across Unreal/editor process loss (`RenderJobRegistry` on-disk tracking).
   - Blueprint metadata evidence-shape alignment in `AtlasTransportServer.cpp`.

## Non-regression rules

- Never give Qwen direct production execution or authorization authority.
- Never accept model-supplied authorization IDs or receipts as authority.
- Never accept model-supplied protected Unreal intent or production flags as authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from a transport/write response alone.
- Preserve independent verification and the evidence ledger.
- Keep Unreal-specific behavior behind adapter/tool boundaries.
- Treat render artifacts as independently validated evidence.
- Preserve canonical Digital Twin identity separately from Unreal assets, levels, jobs, receipts, and files.
- Do not confuse durable receipt persistence with runtime job persistence.
- Do not claim cross-process Unreal job recovery until implemented and verified.
- Do not run workflow/action-runner tests unless explicitly authorized.

## Historical documentation

Older dated handoff snapshots are archival records and should not be rewritten. This document is the authoritative current Unreal handoff.