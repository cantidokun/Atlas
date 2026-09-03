# Atlas Current Development Handoff

**Updated:** September 3, 2026 — Qwen Stage 16 runtime and cross-process recovery live-verified, including a fresh Qwen recovery recommendation; Stage 17 production-artifact lineage foundation added.
**Active branch:** `feat/blender-stage11-mainline`
**PR #49:** open, draft, unmerged
**Current stage:** Stage 17 — production artifact lineage, IN PROGRESS

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

## Stage 13–15 baseline

Stage 13 multi-step partial-progress recovery is complete for the current contract and live verified against Blender 4.4.

Stage 14 dependency-aware task composition is complete for the current contract. Dependency validation, exact authorization binding, serial deterministic execution, inherited prerequisite handling, and cross-process dependency-aware recovery have been implemented and live verified.

Stage 15 semantic soccer-production tasks are complete for the current contract. `ProductionTaskDefinition`, reusable fragments, target-state evaluation, canonical soccer-production templates, the versioned catalog, and semantic provenance persistence are established and live verified.

Current catalog contract:

```text
broadcast-goal-preparation@1

file_name       -> string
object_name     -> string
target_location -> vector3
target_rotation -> vector3
```

## Stage 16 — Qwen integration — VERIFIED FOR CURRENT CONTRACT

The local proposal-only Qwen smoke, full Qwen-authorized Blender mutation, and two-process recovery were user-verified against Blender 4.4.

The recovery proof additionally makes a fresh Phase 2 Qwen recommendation after process restart. Atlas validates that recommendation against the persisted canonical task, treats it as advisory only, derives the unfinished executable action from the persisted authorized task, and uses the existing Atlas replan/recovery path.

User-verified output includes:

```text
LIVE QWEN PRODUCTION RECOVERY VERIFIED
object=Goal_Left_post
workflow=broadcast-goal-preparation
workflow_version=1
qwen_provenance_recovered=verified
initial_authorization_recovered=verified
process_restart=verified
qwen_recovery_recommendation=verified
qwen_recovery_recommendation_advisory_only=verified
fresh_recovery_evidence=verified
qwen_workflow_target_revalidated=verified
completed_prerequisite_not_replayed=verified
replan_authorization=atlas-qwen-recovery-replan
replacement_execution=verified
independent_final_verification=verified
fixture_restored_location=[0.25, 5.302, 0.0]
fixture_restored_rotation=[0.0, 0.0, 0.0]
```

GitHub Actions Atlas Tests **#1439 passed** after this live-verification increment.

## Stage 17 — Production artifact lineage

A new non-executable foundation is now present in `planning/production_artifact.py`:

`ProductionArtifactManifest` binds a production representation to a canonical Digital Twin identifier while preserving upstream source-artifact relationships, workflow provenance, evidence digests, receipt digests, and engine/version metadata.

The manifest is immutable, deterministic, independently digestable, reconstructable from persisted snapshots, and fail-closed on tampering or malformed fields. It intentionally exposes no execution, authorization, scheduling, or recovery behavior.

Regression coverage is in `tests/test_production_artifact.py`.

This establishes lineage as a cross-engine provenance contract rather than conflating `.blend` files, Unreal projects, render outputs, or receipts with canonical Digital Twin identity.

## Next work

Integrate `ProductionArtifactManifest` into the existing evidence/receipt paths, beginning with a narrow Blender production-artifact lineage proof and then the corresponding Unreal boundary.

The first integration should link the canonical Digital Twin identifier, input artifact lineage, workflow provenance, and independently verified output artifact without changing execution authority or introducing another runtime.

Do not create a second execution, authorization, scheduler, or recovery system for lineage tracking.
Do not introduce parallel execution until dependency semantics independently justify it.

## Unreal status

The Unreal Engine 5.6 render boundary remains locally proven for the implemented capabilities: deterministic configuration, render-state verification, MRQ submission, dynamic job IDs, asynchronous inspection, semantic completion verification, artifact discovery/validation, evidence-bound `UnrealRenderReceipt`, and durable receipt persistence.

Cross-process Unreal render-job recovery is **not implemented**. Receipt persistence must not be described as runtime job persistence.

## Resolution / Digital Twin

Atlas is intended for soccer source footage including 4K/UHD. Resolution changes execution-resource requirements, not the orchestration contract. Preserve high-resolution provenance while using appropriate intermediates/proxies.

Atlas owns the canonical Digital Twin. Photogrammetry is upstream reconstruction; Blender analyzes/cleans/corrects/prepares; Unreal is downstream production execution. DCC/engine files remain representations or production state, not canonical identity.

## Non-regression rules

- Qwen remains proposal-only until Atlas validates and authorizes.
- Never accept model-supplied authorization IDs or receipts as authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from transport/write success alone.
- Preserve independent verification and the evidence ledger.
- Keep engine-specific behavior behind adapter/tool boundaries.
- Keep dependency-aware execution serial.
- Preserve canonical Digital Twin identity separately from production artifacts.
- Do not claim cross-process Unreal job recovery unless separately implemented and verified.

## PR status

PR #49 remains open, draft, and unmerged. **Do not merge unless explicitly requested.**
