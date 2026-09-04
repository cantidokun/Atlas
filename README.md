# Atlas

## What Atlas is

Atlas is an **AI-assisted sports virtual production and digital-twin platform** focused exclusively on soccer-field-related digital twins and production workflows.

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

Qwen is never the execution or authorization authority.

---

# Current position — September 4, 2026 end-of-night checkpoint

**Active branch:** `main`  
**Current development stage:** **Stage 17 — production artifact lineage, IN PROGRESS**

Stage 13 multi-step partial-progress recovery is live-verified against Blender 4.4. Stage 14 dependency-aware serial execution and cross-process recovery are implemented and live-verified. Stage 15 semantic soccer-production workflows and versioned catalog compilation are established. Stage 16 Qwen integration is live-verified through proposal, Atlas authorization, real Blender mutation, cross-process recovery, and advisory-only Qwen recovery reasoning.

## Stage 17 — Production artifact lineage

`planning/production_artifact.py` provides an immutable provenance-only `ProductionArtifactManifest` connecting a production representation to the canonical Atlas Digital Twin, source artifacts, workflow provenance, independent verification evidence, execution receipts, engine metadata, and a deterministic integrity digest.

The manifest does not execute, authorize, schedule, or recover work. Blender and Unreal use separate engine-specific construction and lineage-verification bridges.

### Blender Stage 17 — LIVE VERIFIED

The real Blender 4.4 production-artifact closed loop has been user-verified: real mutation, fresh independent inspection, immutable receipt/evidence capture, durable manifest persistence, reload, and exact lineage verification.

### Unreal Stage 17 — IMPLEMENTED / REAL UE PROOF PENDING

The proven Unreal Engine 5.6 render boundary is:

```text
render configuration
  → configuration verification
  → Movie Render Queue submission
  → dynamic job ID
  → asynchronous job inspection
  → semantic completion verification
  → output artifact discovery
  → filesystem validation
  → verified UnrealEvidence
  → UnrealRenderReceipt
  → durable receipt persistence
```

The Stage 17 provenance continuation is:

```text
verified UnrealEvidence snapshot
  → immutable receipt reconstruction
  → ProductionArtifactManifest
  → durable ProductionArtifactStore
  → reload
  → exact lineage verification
```

`UnrealEvidence.snapshot()` / `from_snapshot(...)` and `UnrealRenderReceipt.snapshot()` / `from_snapshot(...)` are canonical detached serialization boundaries with fail-closed validation. The receipt store retains its separate versioned storage envelope.

The disposable `live_unreal_production_artifact_proof.py` harness consumes an already verified Unreal evidence/receipt pair, reconstructs the immutable provenance chain, persists and reloads the manifest, independently verifies exact lineage, and reports digest identities. It does not submit or execute a render and does not implement Unreal job recovery.

The remaining Stage 17 gate is a human-run proof using evidence emitted by the existing proven UE 5.6 render boundary. The exact procedure is documented in `docs/STAGE17_UNREAL_PROOF.md`.

**Cross-process Unreal render-job recovery is not implemented.** Receipt persistence must not be described as job persistence.

## Controller-to-Unreal trust boundary

The current mainline `AgentControllerHost` is deliberately narrower than the historical controller-host branch that remains isolated in PR #50.

For protected Unreal production requests:

```text
model response
      ↓
host classifier
      ↓
TrustedUnrealContext
      ↓
protected intent + production marker + authorization + sequence path
      ↓
Unreal production integration seam
```

Model-supplied protected intent is never promoted to authority. A conflicting model intent is retained only as diagnostic mismatch state. Model-supplied production flags cannot disable the host-owned production marker. The integration seam rejects missing required trusted context before execution.

This boundary adds no second authorization, scheduler, recovery engine, or Unreal execution path.

## Digital Twin and production direction

Atlas owns the canonical Digital Twin. `.blend` files, Unreal projects, levels, render jobs, receipts, and output artifacts are production representations/state, not canonical identity.

The wider production repertoire may include impact frames, smear frames, chromatic aberration, cinematic bleed, match-cut transformations, spatial overlays, digital-twin compositing, and temporary liquid/smoke/glass/metallic environment effects.

These are production modules, not the definition of Atlas.

## Non-regression rules

- Qwen never receives direct execution or authorization authority.
- Model output remains untrusted until Atlas validates it.
- Never allow model-supplied authorization IDs, receipts, protected Unreal intent, or protected production flags to become Atlas authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from a transport/write response alone.
- Preserve independent verification and the evidence ledger.
- Keep engine-specific behavior behind adapter/tool boundaries.
- Keep dependency-aware execution serial until concurrency is independently justified.
- Preserve canonical Digital Twin identity separately from production artifacts.
- Do not claim cross-process Unreal job recovery unless separately implemented and verified.
- Do not run workflow/action-runner tests unless explicitly authorized.

## End-of-night resume point

1. Pull the latest `main`.
2. Run the focused deterministic tests covering the latest Unreal/controller trust-boundary changes.
3. Do not run the live Unreal proof until the Windows/UE 5.6 environment is ready for the human validation gate.
4. Execute the existing UE 5.6 render boundary, capture its verified evidence/receipt pair, then run `live_unreal_production_artifact_proof.py` against that pair.
5. Only after that proof succeeds, resume selective integration of the stronger historical controller-host architecture from PR #50.

Historical handoff snapshots remain archival records and should not be rewritten to reflect this checkpoint.