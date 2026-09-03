# Atlas Current Development Handoff

**Updated:** September 3, 2026 — Qwen Stage 16 runtime and cross-process recovery live-verified.
**Active branch:** `feat/blender-stage11-mainline`
**PR #49:** open, draft, unmerged
**Current stage:** Stage 16 — IN PROGRESS

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

## Stage 16 — Qwen integration

### Verified: proposal, authorization, runtime, and real Blender mutation

The local proposal-only Qwen smoke was user-verified, and the full Qwen-authorized production runtime was subsequently verified against Blender 4.4.

```text
LIVE QWEN-AUTHORIZED SOCCER PRODUCTION RUNTIME VERIFIED
object=Goal_Left_post
workflow=broadcast-goal-preparation
workflow_version=1
qwen_proposal=verified
catalog_validation=verified
semantic_task=verified
atlas_authorization=verified
authorization_id=atlas-qwen-production-runtime-live
existing_task_runtime=verified
blender_execution=verified
independent_final_verification=verified
```

The live mutation targeted the verified Qwen workflow parameters and the harness restored the fixture afterward.

### Verified: durable Qwen recovery across Python restart

`qwen/production_handoff.py` supports `QwenProductionTaskHandoff.from_snapshot(...)` for cross-process continuation. The persisted proposal is revalidated and recompiled through the trusted catalog/compiler, and persisted semantic/compiled snapshots plus digests must match exactly. Persisted handoffs remain inert until Atlas explicitly authorizes work.

`scripts/run_live_qwen_production_recovery_restart.py` was user-verified in two phases:

```text
Phase 1
Qwen proposal
  ↓
trusted catalog validation
  ↓
Atlas authorization
  ↓
existing AutonomousTaskRuntime
  ↓
first Blender action succeeds
  ↓
later action deliberately fails before Blender invocation
  ↓
durable continuation + Qwen provenance checkpoint

Phase 2 — fresh Python process
persisted Qwen handoff reconstruction
  ↓
existing Atlas continuation recovery
  ↓
fresh authoritative evidence
  ↓
explicit replan authorization
  ↓
unfinished action replacement
  ↓
fresh independent verification
  ↓
fixture restoration
```

User-verified recovery signals:

```text
LIVE QWEN PRODUCTION RECOVERY VERIFIED
object=Goal_Left_post
workflow=broadcast-goal-preparation
workflow_version=1
qwen_provenance_recovered=verified
initial_authorization_recovered=verified
process_restart=verified
fresh_recovery_evidence=verified
qwen_workflow_target_revalidated=verified
completed_prerequisite_not_replayed=verified
replacement_execution=verified
independent_final_verification=verified
fixture_restored_location=[0.25, 5.302, 0.0]
fixture_restored_rotation=[0.0, 0.0, 0.0]
```

This is the current highest verified Qwen milestone. Qwen-originated work now survives a process boundary while Atlas retains sole authority over recovery classification, evidence, replan authorization, execution, and final verification.

## Current architectural direction

The next useful increment is not a new Qwen executor or recovery engine. The existing proven Qwen workflow proposal contract should be used to express recovery intent where appropriate, while Atlas derives the executable unfinished action from the persisted authorized task, validates dependency constraints, issues the explicit replan authorization, and performs the write through the existing runtime.

Do not create a Qwen-specific execution engine, authorization system, scheduler, or recovery system.
Do not introduce parallel execution until dependency semantics justify it independently.

## Next verification gate

The newest recovery-related code has not yet received a fresh reported CI result after the latest correction commit. Obtain a fresh offline CI result before treating the branch as regression-clean.

Then continue by hardening the Qwen-to-recovery proposal boundary and add tests proving that a model cannot expand a recovery replan beyond the unfinished authorized scope or alter inherited prerequisites.

Recovery must remain Atlas-owned, require fresh authoritative evidence, require explicit replan authorization, preserve completed prerequisites, and never automatically retry failed writes.

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
