# Atlas Unreal Agent — Current Handoff

**Updated:** September 3, 2026 — Unreal boundary remains proven; Atlas overall development has advanced through Stage 15 and into Stage 16 Qwen integration.
**Focus:** Unreal Agent and supporting architecture only.
**Active Atlas branch:** `feat/blender-stage11-mainline`
**PR #49:** open, draft, unmerged.

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

Qwen remains a reasoning/proposal source. It does not authorize or directly execute Unreal operations.

## Verified Unreal milestone

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

The completed live render produced a real PNG artifact. A receipt was derived from verified render evidence.

Known receipt identities from the proven milestone:

```text
evidence_digest:
f5014c719628478f7223ed3a8c4173d9230f13f4957e786ef99e20cd4b1b6cd0

receipt_digest:
f053d427fde579637225fa350b5204f6a001bfb041041802d06542c8e8114dcb

SELF MATCH: True
```

## Important boundary

The Unreal runtime render-job registry remains in-memory.

`UnrealRenderReceiptStore` provides durable receipt persistence, but **cross-process recovery of Unreal runtime render jobs is not implemented**.

Do not represent receipt persistence as job persistence.

## Current broader Atlas position

The Blender side has completed Stage 13 dependency-aware recovery and Stage 15 semantic production-task work. Stage 16 is integrating live Qwen proposals into Atlas-owned validation, authorization, and the existing autonomous runtime.

The current Qwen authority chain is:

```text
Qwen proposal
  → trusted catalog validation
  → semantic production task
  → provenance-bound handoff
  → existing Atlas authorization
  → existing runtime
```

This does not change the Unreal authority model. Any future Qwen-to-Unreal production integration must cross the same Atlas-owned authorization boundary and use the existing Unreal capability/transport contracts.

## Next Unreal work

Resume the Unreal track from the **higher-level render receipt integration** checkpoint only if that work is being actively resumed. The live UE 5.6 render/artifact/verification/receipt path is already proven and should not be reworked without a concrete capability gap.

The next Unreal capability must preserve:

- evidence-driven completion;
- engine-neutral receipt identity;
- durable receipt persistence;
- explicit Atlas authorization;
- independent artifact verification;
- no automatic retry after failed writes.

Cross-process Unreal render-job recovery remains a future capability and must not be claimed until separately implemented and verified.

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

## Resume point

For Unreal-only work: read this handoff plus `ATLAS_HANDOFF_CURRENT.md`, inspect the active branch/HEAD and `origin/main`, then continue only from an established Unreal capability gap.

For overall Atlas development: the authoritative resume point is the Stage 16 Qwen runtime boundary in `ATLAS_HANDOFF_CURRENT.md`.

This handoff supersedes the September 1 Unreal-only checkpoint as the current Unreal reference while preserving the proven render/receipt baseline.
