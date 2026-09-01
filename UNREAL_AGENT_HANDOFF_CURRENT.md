# Atlas Unreal Agent — Current Handoff

**Updated:** September 1, 2026
**Focus:** Unreal Agent and supporting architecture only
**GitHub documentation branch:** `docs/sep1-2026-unreal-render-handoff`
**GitHub main baseline at documentation start:** `b56aada`
**Local development checkpoint reported by user:** `f658e16` — `feat: establish Unreal render artifact receipt pipeline`
**Latest local regression reported by user:** **1033 passed, 5 skipped**
**Latest local `git diff --check`:** clean

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
render receipt / persisted receipt when applicable
```

The Unreal Agent proposes and decomposes operations. It does not authorize or directly execute them. Qwen likewise remains a reasoning/proposal source only.

## Verified September 1 Unreal milestone

The disposable Unreal harness and the production Unreal transport boundary have now been exercised through a real Unreal Engine 5.6 runtime.

The verified render path includes:

- deterministic render configuration;
- render-state verification;
- Movie Render Queue submission;
- dynamic job-ID binding from submission evidence;
- asynchronous render-job inspection;
- completed-job semantic verification;
- MRQ output artifact discovery;
- filesystem artifact existence and non-zero-size validation;
- evidence-bound deterministic `UnrealRenderReceipt` creation;
- atomic `UnrealRenderReceiptStore` persistence with fail-closed reload validation.

Controlled live proof:

```text
resolution:       640x360
frame range:      1–2
output format:    PNG
output directory: Saved/AtlasRenderOutput
```

The completed live render produced a real PNG artifact. `inspect_render_job` returned that artifact and was marked `verified=True` after the executor routed the inspection through render-job semantic verification.

A real receipt was issued from that verified evidence:

```text
evidence_digest:
f5014c719628478f7223ed3a8c4173d9230f13f4957e786ef99e20cd4b1b6cd0

receipt_digest:
f053d427fde579637225fa350b5204f6a001bfb041041802d06542c8e8114dcb

SELF MATCH: True
```

Focused render/receipt coverage was expanded and the latest full local regression reached **1033 passed, 5 skipped**.

## Important implementation boundary

The Unreal runtime render-job registry remains in-memory. The Atlas-side `UnrealRenderReceiptStore` provides durable receipt persistence, but **cross-process recovery of Unreal runtime render jobs is not implemented**.

Do not represent receipt persistence as job persistence.

## Proven render flow

```text
render configuration
      ↓
configuration verification
      ↓
MRQ submission
      ↓
dynamic Unreal job ID
      ↓
async job inspection
      ↓
finished + successful state
      ↓
actual output_files[]
      ↓
filesystem artifact validation
      ↓
verified Unreal evidence
      ↓
deterministic evidence digest
      ↓
UnrealRenderReceipt
      ↓
atomic receipt persistence
```

The boundary is intentionally evidence-driven: a render-job success flag alone is insufficient to establish a completed production artifact.

## Current Unreal files / concepts

The current implementation includes the Unreal capability registry, task planner, production adapter/transport, render contract, render-job verifier, render receipt, and render receipt store, together with the Unreal 5.6 harness and focused tests.

The render receipt remains engine-neutral and is derived from verified `inspect_render_job` evidence. The persisted receipt contains the receipt identity and evidence digest rather than duplicating the entire evidence ledger.

## Next development increment

The next Unreal task is **render receipt integration into the higher-level Atlas render execution workflow**:

1. issue/persist receipts automatically after verified completion;
2. add focused tests for that service boundary;
3. preserve the engine-neutral receipt/store separation;
4. only then expand Unreal capabilities where a real capability gap justifies them.

Blender remains an independent development track and should not be blocked by this Unreal receipt work.

## Regression and safety rules

- Never give Qwen direct production execution authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from a transport/write response alone.
- Preserve independent verification and the evidence ledger.
- Keep Unreal-specific behavior behind adapter/tool boundaries.
- Treat output artifacts as evidence that must be independently validated.
- Preserve canonical Digital Twin identity separately from Unreal assets, levels, render jobs, and output files.
- Do not claim cross-process Unreal job recovery until separately implemented and verified.
- Do not confuse local regression results with GitHub CI results.
- Keep the disposable harness as a regression fixture rather than turning it into unrestricted production logic.

## Resume point

Read this handoff and `ATLAS_HANDOFF_CURRENT.md`, inspect the local branch/HEAD and `origin/main`, then continue from the **Unreal render receipt integration** checkpoint. The live UE 5.6 render/artifact/verification/receipt path is already proven locally and should not be reworked without a concrete capability gap.

This handoff is the authoritative Unreal continuation point until superseded.
