# Atlas Current Development Handoff

**Updated:** September 3, 2026 — Qwen Stage 16 runtime and cross-process recovery live-verified; Qwen-guided recovery recommendation binding is implemented and CI-verified, with the new live recommendation call awaiting user-side Blender/Ollama verification.
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

### Implemented and CI-verified: Qwen-guided recovery recommendation binding

`QwenProductionTaskHandoff.validate_recovery_recommendation(...)` validates a fresh Qwen production recommendation against the exact persisted canonical task. A changed workflow, version, object, target, dependency-bearing task contract, or other compiled-task difference is rejected before replan authorization.

The live restart harness now makes a fresh Phase 2 call to Qwen after process restart. The recommendation is validated as advisory intent only. Atlas does not consume model-supplied actions, authorization, tools, or recovery instructions; it derives the executable unfinished `ActionSpec` from the persisted canonical task and continues through the existing `recover_with_fresh_evidence(...)` → `authorize_replan(...)` → `install_authorized_replan(...)` path.

GitHub Actions **Atlas Tests #1438 is green** on the implementing commit. The pre-change local baseline was **619 passed in 1.57s**. The new Phase 2 Qwen recommendation call itself still requires the next user-side live verification with Ollama + Blender.

## Next verification gate

Pull the latest branch and rerun the existing local suite:

```powershell
cd "C:\Users\Gavin's PC\Desktop\Atlas"
git pull
python -m pytest -q -m "not integration"
```

Then perform the two-process live recovery proof. Phase 1 remains unchanged; Phase 2 now requires the local Ollama service and will ask Qwen for a recovery recommendation before Atlas derives the unfinished action.

```powershell
python -m scripts.run_live_qwen_production_recovery_restart --phase failure --blender "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"

python -m scripts.run_live_qwen_production_recovery_restart --phase recover --blender "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
```

Expected new Phase 2 markers include:

```text
qwen_recovery_recommendation=verified
qwen_recovery_recommendation_advisory_only=verified
```

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
