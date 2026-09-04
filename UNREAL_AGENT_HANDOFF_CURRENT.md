# Atlas Unreal Agent — Current Handoff

**Updated:** September 4, 2026 — end-of-night checkpoint after PR #57 restored the working Unreal 5.6 transport/render boundary.
**Active Atlas branch:** `main`
**Current focus:** Stage 17 production-artifact lineage, with the UE 5.6 execution boundary restored and the final live provenance proof still pending.

## Architectural position

Atlas owns the canonical Digital Twin. Unreal is a controlled production representation/execution environment around that canonical state.

```text
Atlas intent
    ↓
Unreal Agent
    ↓
capability registry
    ↓
strict operation contract/schema
    ↓
Atlas authorization
    ↓
trusted controller context
    ↓
Unreal adapter / transport
    ↓
Unreal Engine 5.6
    ↓
independent evidence
    ↓
Atlas verification
    ↓
UnrealRenderReceipt
    ↓
ProductionArtifactManifest
```

Qwen remains a reasoning/proposal source. It does not authorize or directly execute Unreal operations.

## Restored and compile-verified Unreal execution baseline

PR #57 has restored the previously working Unreal 5.6 execution boundary to `main`. The recovered tree includes the controlled UE 5.6 project, render fixture assets, render/world-save boundary sources, Unreal transport module, and named-pipe transport server.

The local UE 5.6 editor build completed **19/19 actions successfully**. This included successful compilation and linking of `AtlasTransportServer.cpp` and `AtlasUnrealTransport.cpp`, plus the render and world-save boundary sources.

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

The restored boundary is compile-verified in this checkpoint; the next live step is to exercise the boundary again and produce fresh Stage 17 provenance evidence.

**Cross-process Unreal render-job recovery is not implemented.** The runtime render-job registry remains in-memory.

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

The current mainline `AgentControllerHost` remains intentionally narrow while the historical controller-host architecture in PR #50 remains isolated.

For protected Unreal production requests:

- `TrustedUnrealContext` supplies protected intent, authorization context, sequence path, and the production marker;
- model-supplied protected intent cannot replace the trusted intent;
- conflicting model intent becomes diagnostic mismatch state only;
- model-supplied production flags cannot disable the host-owned production marker;
- the Unreal production integration seam rejects missing required trusted context before execution.

The restored C++ transport is an engine execution/transport boundary, not a second authorization system. Its transport-level authorization field is part of the request contract, but authority remains owned by the trusted Atlas host boundary.

## Validation status

Verified in this checkpoint:

- UE 5.6 editor compilation of the restored Unreal harness: **19/19 actions succeeded**.
- `AtlasTransportServer.cpp` compiled and linked successfully.
- `AtlasUnrealTransport.cpp` compiled and linked successfully.
- render/world-save boundary sources compiled successfully.

Previously verified:

- deterministic Stage 17 provenance/snapshot coverage on Python 3.9 and 3.11;
- the original real UE 5.6 render/receipt path.

Still pending:

- a new deterministic Python test run for the September 4 controller trust-boundary changes;
- fresh execution of the restored UE 5.6 render path;
- the human UE 5.6 Stage 17 provenance proof using that fresh verified evidence/receipt pair.

## Resume point

1. Pull the latest `main`.
2. Run the focused controller trust-boundary tests.
3. Exercise the restored UE 5.6 render boundary and capture fresh verified evidence/receipt data.
4. Run `live_unreal_production_artifact_proof.py` against that verified evidence/receipt pair.
5. Confirm manifest persistence, reload, exact lineage, and digest identities.
6. Then continue selective integration of PR #50's stronger controller-host architecture.

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