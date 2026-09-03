# Atlas Current Development Handoff

**Updated:** September 3, 2026 — Qwen Stage 16 runtime and cross-process recovery live-verified; Qwen-guided recovery recommendation binding implemented but not yet live-verified.
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

### Verified: proposal, authorization, runtime, real Blender mutation, and cross-process recovery

The local proposal-only Qwen smoke and full Qwen-authorized production runtime were user-verified against Blender 4.4.

The two-process Qwen-originated recovery proof was also user-verified:

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
replan_authorization=atlas-qwen-recovery-replan
replacement_execution=verified
independent_final_verification=verified
fixture_restored_location=[0.25, 5.302, 0.0]
fixture_restored_rotation=[0.0, 0.0, 0.0]
```

This proves that Qwen-originated work can cross a Python restart while Atlas retains sole authority over recovery classification, fresh evidence, replan authorization, execution, and final verification.

### Implemented: Qwen-guided recovery recommendation binding

`QwenProductionTaskHandoff.validate_recovery_recommendation(...)` now validates a fresh Qwen production recommendation against the exact persisted canonical task. A changed workflow, version, object, target, dependency-bearing task contract, or other compiled-task difference is rejected before replan authorization.

The model therefore cannot expand recovery scope simply by proposing a new action or target. Atlas derives the executable unfinished action from the persisted authorized task and continues to use the existing recovery authorization/runtime path.

Targeted regression coverage verifies matching recommendations and fail-closed target/object changes.

## Next verification gate

The latest local suite before this guided-recovery increment was **616 passed in 1.43s**. Pull the newest branch and rerun:

```powershell
cd "C:\Users\Gavin's PC\Desktop\Atlas"
git pull
python -m pytest -q -m "not integration"
```

After the suite is green, the next live proof should make a fresh Qwen recommendation during Phase 2 recovery, validate it through `validate_recovery_recommendation(...)`, then let Atlas derive and explicitly authorize only the unfinished replacement action.

Do not create a Qwen-specific execution engine, authorization system, scheduler, or recovery system.
Do not introduce parallel execution until dependency semantics justify it independently.

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
