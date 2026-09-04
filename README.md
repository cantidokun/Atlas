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

Atlas is designed for source footage including 4K/UHD. Higher resolution changes processing, memory, storage, reconstruction, compositing, and render throughput requirements, not the core orchestration model.

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

# Current position — September 4, 2026

**Active branch:** `main`  
**Current development stage:** **Stage 17 — production artifact lineage, IN PROGRESS**

Stage 13 multi-step partial-progress recovery is live-verified against Blender 4.4. Stage 14 dependency-aware serial execution and cross-process recovery are implemented and live-verified. Stage 15 semantic soccer-production workflows and versioned catalog compilation are complete for the current contract.

Stage 16 Qwen integration is live-verified through proposal, Atlas authorization, real Blender mutation, cross-process recovery, and an advisory-only Qwen recovery recommendation.

## Stage 17 — Production artifact lineage

`planning/production_artifact.py` provides an immutable provenance-only `ProductionArtifactManifest` connecting a production representation to the canonical Atlas Digital Twin, source artifacts, workflow provenance, independent verification evidence, execution receipts, engine metadata, and a deterministic integrity digest.

The manifest does not execute, authorize, schedule, or recover work. Blender and Unreal use separate engine-specific construction and lineage-verification bridges.

### Blender Stage 17 — LIVE VERIFIED

The existing Blender write/inspection closed loop can be associated with the production artifact manifest, durably persisted, reloaded, and independently lineage-verified without causing another Blender operation. The user has already completed the real Blender 4.4 proof.

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

Stage 17 adds the provenance-only continuation:

```text
verified UnrealEvidence snapshot
  → immutable receipt reconstruction
  → ProductionArtifactManifest
  → durable ProductionArtifactStore
  → reload
  → exact lineage verification
```

`UnrealEvidence.snapshot()` / `from_snapshot(...)` and `UnrealRenderReceipt.snapshot()` / `from_snapshot(...)` are now the canonical detached serialization boundaries, with fail-closed exact-field validation. The receipt store preserves its separate versioned storage envelope.

The disposable `live_unreal_production_artifact_proof.py` harness consumes the verified receipt/evidence pair and reports artifact, evidence, receipt, and manifest digests. It does not submit or execute a render and does not implement Unreal job recovery.

See `docs/STAGE17_UNREAL_PROOF.md` for the human validation procedure. The only remaining Stage 17 gate is the real UE 5.6 proof using evidence emitted by the existing proven render boundary.

**Cross-process Unreal render-job recovery is not implemented.** Receipt persistence must not be described as job persistence.

## Digital Twin and production direction

Atlas owns the canonical Digital Twin. `.blend` files, Unreal projects, levels, render jobs, receipts, and output artifacts are production representations/state, not canonical identity.

The wider production repertoire may include impact frames, smear frames, chromatic aberration, cinematic bleed, match-cut transformations, spatial overlays, digital-twin compositing, and temporary liquid/smoke/glass/metallic environment effects.

These are production modules, not the definition of Atlas.

## Non-regression rules

- Qwen never receives direct execution or authorization authority.
- Model output remains untrusted until Atlas validates it.
- Never allow model-supplied authorization IDs, receipts, or protected Unreal intent to become Atlas authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from a transport/write response alone.
- Preserve independent verification and the evidence ledger.
- Keep engine-specific behavior behind adapter/tool boundaries.
- Keep dependency-aware execution serial until concurrency is independently justified.
