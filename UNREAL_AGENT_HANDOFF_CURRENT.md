# Atlas Unreal Agent — Current Handoff

**Updated:** September 4, 2026 — Unreal Engine 5.6 render/receipt execution remains live-proven, and Stage 17 production-artifact provenance is now implemented and regression-hardened on main.
**Focus:** Unreal Agent and supporting architecture only.
**Active Atlas branch:** `main`

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

## Verified Unreal execution baseline

The Unreal production transport and render boundary has been exercised through a real Unreal Engine 5.6 runtime.

Verified path:

```text
render configuration
  → configuration verification
  → Movie Render Queue submission
  → dynamic job ID
  → asynchronous job inspection
  → semantic completion verification
  → actual output artifact discovery
  → filesystem existence/non-zero-size validation
  → verified evidence
  → evidence-bound UnrealRenderReceipt
  → durable receipt persistence
```

Controlled live render:

```text
resolution:       640x360
frame range:      1–2
output format:    PNG
output directory: Saved/AtlasRenderOutput
```

The completed live render produced a real PNG artifact. The receipt was derived from verified render evidence.

## Stage 17 production-artifact provenance

`ProductionArtifactManifest.from_unreal_render_receipt(...)` is a provenance-only bridge from an existing immutable `UnrealRenderReceipt` plus its immutable `UnrealEvidence` to a production artifact.

Construction now requires:

```text
engine                     == Unreal
operation_name             == inspect_render_job
verified                   == True
receipt.matches(evidence)  == True
artifact_path              ∈ independently observed output_files
```

`verify_unreal_render_lineage(...)` rechecks the same bindings without executing Unreal, authorizing work, scheduling a render, or recovering a job.

The manifest is durably persisted through `ProductionArtifactStore`, with deterministic serialization, atomic replacement, file flushing, fail-closed reload validation, and manifest-integrity checking.

Offline regression coverage now spans:

```text
verified evidence
→ UnrealRenderReceipt
→ ProductionArtifactManifest
→ durable manifest store
→ reload
→ exact receipt/evidence lineage verification
```

Substitution of evidence, receipts, engine identity, artifact output path, or persisted envelope content is rejected.

### Current validation status

The underlying real Unreal render/receipt path is live verified. The new Stage 17 production-artifact manifest bridge has **not yet been live verified in Unreal**.

The next human gate is therefore not another render implementation. It is a disposable proof that consumes the already-proven real Unreal receipt/evidence boundary, constructs the manifest, persists and reloads it, and independently verifies exact lineage.

## Important boundary

The Unreal runtime render-job registry remains in-memory.

`UnrealRenderReceiptStore` provides durable receipt persistence, but **cross-process recovery of Unreal runtime render jobs is not implemented**.

Do not represent receipt persistence as job persistence.

## Non-regression rules

- Never give Qwen direct production execution or authorization authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from a transport/write response alone.
- Preserve independent verification and the evidence ledger.
- Keep Unreal-specific behavior behind adapter/tool boundaries.
- Treat render artifacts as independently validated evidence.
- Preserve canonical Digital Twin identity separately from Unreal assets, levels, jobs, and files.
- Do not confuse durable receipt persistence with runtime job persistence.
- Do not claim cross-process Unreal job recovery until implemented and verified.
- Do not run workflow/action-runner tests for the live gate unless explicitly authorized.

## Resume point

For Unreal-only work: read this handoff plus `ATLAS_HANDOFF_CURRENT.md`, inspect `main`, and continue from the Stage 17 live production-artifact proof gate. Do not rework the proven render/receipt execution boundary without identifying a concrete capability gap.
