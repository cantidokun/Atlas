# Atlas Current Development Handoff

**Updated:** September 3, 2026 — end-of-night freeze. Stage 15 complete for current contract; Stage 16 Qwen provider, Atlas authorization handoff, runtime boundary, and first end-to-end mutation harness implemented but not yet live-verified.
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

### Verified

The local proposal-only Qwen smoke was user-verified:

```text
LIVE QWEN PRODUCTION PROPOSAL VERIFIED
workflow=broadcast-goal-preparation
workflow_version=1
workflow_parameter_contract=verified
proposal_validation=verified
catalog_resolution=verified
semantic_task_compilation=verified
execution_authorization=not_requested
execution=not_attempted
blender_mutation=not_attempted
```

This proves live Qwen communication, structured extraction, provider/catalog validation, and semantic task compilation without Blender mutation.

### Implemented but not yet user-verified

`qwen/production_handoff.py` provides a provenance-bound handoff from validated Qwen intent into the existing Atlas authorization mechanism.

It rechecks proposal, semantic-task, and compiled-task integrity and independently recompiles the proposal before authorizing. Model-supplied authorization fields are rejected. No executor or recovery authority is exposed.

`planning/authorized_task_runtime.py` provides a generic bootstrap for an already-issued Atlas `ActionAuthorization`. It verifies the exact action-plan binding, acquires authoritative initial evidence, evaluates the target, and constructs the existing `AutonomousTaskRuntime`. It is not a second execution or authorization system.

Live harnesses now exist for:

```text
scripts/run_live_qwen_production_handoff.py
scripts/run_live_qwen_production_runtime_boundary.py
scripts/run_live_qwen_production_runtime.py
```

The intended full chain is:

```text
Qwen
  ↓
structured proposal
  ↓
provider + trusted catalog validation
  ↓
QwenProductionProposal
  ↓
ProductionTaskDefinition
  ↓
AtlasTaskDefinition
  ↓
QwenProductionTaskHandoff
  ↓
existing Atlas ActionAuthorization
  ↓
existing AutonomousTaskRuntime
  ↓
controlled Blender execution
  ↓
fresh independent verification
  ↓
fixture restoration
```

The **first full Qwen-authorized Blender mutation harness is implemented but has not yet been user-verified**.

## Next session — exact resume point

Run the following from the Atlas repository on the Windows development machine:

```powershell
cd "C:\Users\Gavin's PC\Desktop\Atlas"
git pull
python -m scripts.run_live_qwen_production_runtime_boundary --blender "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
python -m scripts.run_live_qwen_production_runtime --blender "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
```

The boundary proof must establish that Qwen-driven semantic intent reaches Atlas authorization and the existing runtime without a write before the `ACTION` phase.

The full proof must establish real Blender mutation, fresh independent verification, and exact fixture restoration.

After that proof succeeds, extend the same Qwen proposal/handoff contract into the **existing Atlas failure/recovery machinery**. Recovery must remain Atlas-owned, require fresh authoritative evidence, require explicit replan authorization, preserve completed prerequisites, and never automatically retry failed writes.

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

## Documentation state

The root `README.md`, `docs/ATLAS_ARCHITECTURE_CONTRACT.md`, `ATLAS_HANDOFF_CONTEXT.txt`, `UNREAL_AGENT_HANDOFF_CURRENT.md`, `docs/OPENHANDS_TRANSITION_GUIDE.md`, and `DEVELOPMENT_LOG.md` were synchronized to this checkpoint before development was stopped for the night.

## PR status

PR #49 remains open, draft, and unmerged. **Do not merge unless explicitly requested.**
