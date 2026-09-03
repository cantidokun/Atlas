# Atlas Current Development Handoff

**Updated:** September 3, 2026 — Stage 14 live dependency proof + dependency-aware recovery implementation in progress
**Blender continuation branch:** `feat/blender-stage11-mainline`
**Blender PR:** #49 — open, draft, unmerged
**Current Blender branch work:** Stage 13 is complete; Stage 14 dependency-aware task composition has a successful live serial proof and is now being extended through cross-process dependency-aware recovery

## Current authority model

```text
Qwen / AI
  -> reason and propose

Python / Atlas
  -> validate, authorize, execute, track state, verify, recover

Blender / Unreal
  -> controlled production execution

Independent verification
  -> establish what actually happened
```

Qwen never receives direct production execution authority. Atlas development has standing authorization to run appropriate local tests, GitHub Actions workflows, action-runner tests, and relevant live validation required by the development task.

## Verified Blender — Stage 13

Stage 13 is fully live-verified against Blender 4.4 and GitHub Actions. The two-process harness used `Goal_Left_post` with two ordered writes: move the object, then set its rotation.

Phase 1 completed action 1, deliberately failed action 2 before its Blender write, and persisted the partial-progress checkpoint. Phase 2 started in a fresh Python process, reconstructed the blocked runtime and authorization, acquired fresh multi-request evidence, issued an evidence-bound replan authorization, executed only action 2, independently verified both target properties, and restored the fixture.

## Stage 14 — dependency-aware task composition

Stage 14 adds explicit prerequisite semantics without introducing parallel execution.

Implemented foundation:

- `ActionSpec.depends_on` declares prerequisite action names;
- dependency declarations are preserved in action-plan and deterministic-future state;
- dependency-bearing plans require unambiguous action names;
- unknown, later, self, duplicate, malformed, and unsafe optional-action dependencies are rejected;
- `ActionAuthorization` and `ReplanAuthorization` bind dependency declarations into their digests;
- `AtlasTaskDefinition`, `PlanningOrchestrator`, and `AutonomousTaskRuntime` preserve dependency information during reconstruction;
- structured task-plan validation accepts optional `depends_on` declarations without granting execution authority;
- `FutureExecutionController` derives dependency completion from successful future checkpoints rather than executor result payloads;
- inherited prerequisites proven complete by an earlier authorized continuation can be explicitly carried into a recovery replan;
- inherited dependency state is included in the deterministic future integrity digest and persisted snapshot.

The execution model remains serial and deterministic:

```text
explicit dependencies
        ↓
validated order
        ↓
exact authorization
        ↓
deterministic future
        ↓
one action at a time
        ↓
checkpoint
```

### Live Stage 14 serial proof — VERIFIED

`scripts/run_live_dependency_task.py` was successfully executed against the real Blender 4.4 environment.

Observed proof:

```text
LIVE AUTONOMOUS DEPENDENCY TASK VERIFIED
object=Goal_Left_post
original_location=[0.0, 5.302, 0.0]
target_location=[0.25, 5.302, 0.0]
target_rotation=[0.0, 0.0, 15.0]
explicit_dependency=prepare_rotation->prepare_location
dependency_validation=verified
dependency_authorization=verified
dependency_execution_order=verified
fresh_final_verification=verified
fixture_restored_location=[0.0, 5.302, 0.0]
fixture_restored_rotation=[0.0, 0.0, 0.0]
```

This proves that explicit dependency metadata reaches the real Blender task, authorization, execution order, independent verification, and fixture restoration.

### Stage 14 dependency-aware recovery — NEXT PROOF

A dedicated two-process harness is now present at:

`scripts/run_live_dependency_recovery.py`

Its purpose is to prove the harder case:

```text
prepare_location succeeds
        ↓
checkpoint
        ↓
prepare_rotation fails
        ↓
BLOCKED
        ↓
process restart
        ↓
fresh evidence
        ↓
recover the completed prerequisite
        ↓
explicit replan authorization
        ↓
execute dependent replacement action
        ↓
fresh independent verification
```

The recovery model explicitly carries `prepare_location` as an inherited prerequisite so the replacement action does not have to pretend that its prerequisite disappeared merely because the original action sequence was replaced.

## CI

The latest dependency implementation has generated a new `Atlas Tests` workflow run on the development branch. Do not mark Stage 14 complete until the current matrix is green and the dependency-aware recovery proof passes.

## Unreal

The local Unreal Engine 5.6 production boundary remains proven for the implemented capabilities: deterministic render configuration, render-state verification, Movie Render Queue submission, dynamic job-ID binding, asynchronous inspection, semantic completion verification, MRQ artifact discovery, filesystem validation, and evidence-bound persistent render receipts.

Cross-process Unreal render-job recovery is not implemented.

## Resolution / 4K direction

Atlas is intended to operate on source soccer footage including 4K/UHD. The existing 640x360 Unreal render is a controlled boundary test, not a source-footage maximum. Resolution affects decode, tracking, memory, storage, reconstruction, compositing, and render throughput, but does not change the core Atlas orchestration model.

Use resolution-aware workload/resource handling rather than a separate 4K architecture. Preserve the original high-resolution source as authoritative and use proxies/intermediates where appropriate without weakening provenance or evidence.

## Required regression philosophy

Preserve coverage for:

- already-satisfied state -> zero writes;
- unsatisfied state -> exact authorized action order;
- successful write -> verification remains mandatory;
- verification failure -> `BLOCKED`;
- action failure -> durable `BLOCKED` checkpoint;
- fresh recovery evidence -> required before recovery/replan;
- replacement plan -> explicit replan authorization required;
- replacement action tools -> remain within the task contract;
- partial-progress recovery -> completed prior steps are not blindly replayed;
- multi-request task evidence -> retained as a deterministic evidence bundle;
- dependency references -> validated before execution;
- dependency-aware authorization -> exact plan binding;
- dependency completion -> derived from successful future checkpoints;
- inherited dependency completion -> explicitly recorded and integrity-bound;
- cross-process continuation -> recovered authorization and fresh verification;
- cross-process blocked recovery -> recovered gate + authorization before replan;
- mutated arguments/result -> receipt mismatch;
- malformed executor result -> rejected;
- wrong result tool -> rejected;
- invalid continuation identity -> rejected;
- authorized fresh-evidence replan -> accepted;
- unauthorized replan -> rejected;
- malformed Qwen reasoning -> rejected;
- unknown/non-capability tool -> rejected;
- Blender write without independent persistence evidence -> incomplete;
- Blender expected/observed persistence mismatch -> rejected;
- render job completion without artifacts -> rejected;
- declared render artifacts that do not exist -> rejected;
- tampered persisted render receipt -> rejected.

## Non-regression rules

- Never give Qwen direct production execution authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from a transport/write response alone.
- Keep engine-specific behavior behind adapter/tool boundaries.
- Preserve independent verification and the evidence ledger.
- Do not introduce parallel execution until dependency semantics are independently proven safe.
- Preserve the canonical Digital Twin as distinct from Unreal, Blender, photogrammetry outputs, and temporary production artifacts.

## Resume point

**Next: complete the Stage 14 dependency-aware recovery proof.**

From the Atlas repository folder, run Phase 1:

```powershell
python -m scripts.run_live_dependency_recovery --phase failure --blender "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
```

Then, in the fresh process, run Phase 2:

```powershell
python -m scripts.run_live_dependency_recovery --phase recover --blender "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
```

Only after the recovery proof and current CI matrix are green should Atlas evaluate a later concurrency stage.

Do not expand Qwen autonomy yet.

Do not claim cross-process Unreal render-job recovery unless it is separately implemented and verified.

PR #49 remains draft/unmerged.
