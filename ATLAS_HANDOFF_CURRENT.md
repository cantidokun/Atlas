# Atlas Current Development Handoff

**Updated:** September 3, 2026 — Stage 13 complete; Stage 14 dependency-aware task composition in progress
**Blender continuation branch:** `feat/blender-stage11-mainline`
**Blender PR:** #49 — open, draft, unmerged
**Current Blender branch work:** Stage 13 multi-step autonomous recovery is proven; Stage 14 dependency-aware task composition is implemented at the validation/authorization/runtime layer and awaiting live proof

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

```text
LIVE AUTONOMOUS MULTISTEP RECOVERY VERIFIED
object=Goal_Left_post
original_location=[0.0, 5.302, 0.0]
original_rotation=[0.0, 0.0, 0.0]
recovered_location=[0.25, 5.302, 0.0]
recovered_rotation=[0.0, 0.0, 15.0]
initial_authorization=atlas-stage13-multistep-initial
replan_authorization=atlas-stage13-multistep-replan
multi_request_evidence=verified
action_1_not_replayed=verified
durable_partial_progress=verified
process_restart=verified
fresh_recovery_evidence=verified
replacement_execution=verified
fresh_final_verification=verified
fixture_restored_location=[0.0, 5.302, 0.0]
fixture_restored_rotation=[0.0, 0.0, 0.0]
```

The exact Stage 13 head `361b97e685f815e54c22fcd65c29968a783ff73f` passed GitHub Actions `Atlas Tests` run `#1251`.

## Stage 14 — dependency-aware task composition

The first Stage 14 increment adds explicit prerequisite semantics without adding a scheduler or parallel execution engine.

Implemented:

- `ActionSpec.depends_on` declares prerequisite action names;
- dependency declarations are preserved in action-plan and future-step state;
- dependency-bearing plans require unambiguous action names;
- unknown, later, self, duplicate, malformed, and unsafe optional-action dependencies are rejected;
- `ActionAuthorization` includes dependency declarations in its digest;
- `ReplanAuthorization` also includes and validates dependency declarations;
- `AtlasTaskDefinition`, `PlanningOrchestrator`, and `AutonomousTaskRuntime` preserve dependencies during reconstruction;
- the structured task-plan JSON schema accepts optional `depends_on` declarations;
- structured task-plan validation carries dependencies into `ActionSpec` and rejects invalid dependency graphs;
- `FutureExecutionController` derives dependency completion from its own successful execution checkpoints rather than executor result payloads;
- regression coverage covers dependency validation, authorization binding, structured-plan propagation, and fail-closed dependency execution.

The execution model remains deliberately serial:

```text
explicit dependencies
        ↓
validated action order
        ↓
exact authorization digest
        ↓
deterministic future
        ↓
one next action at a time
        ↓
checkpoint
```

Dependency-free legacy plans remain valid.

## Stage 14 — current live proof

A dedicated real-Blender harness is now present at:

`scripts/run_live_dependency_task.py`

It performs a small soccer-field-related task against the real Blender fixture with:

```text
prepare_location
      ↓
prepare_rotation
      depends_on = prepare_location
```

The harness routes writes through the existing persistence boundary, performs independent evidence acquisition, verifies the final state, and restores the fixture. Stage 14 is not complete until this live proof passes.

## CI

The latest Stage 14 regression run is currently in progress on branch `feat/blender-stage11-mainline`. Do not mark Stage 14 complete until the current matrix is green and the live dependency proof has passed.

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

**Next: complete Stage 14 with the real Blender dependency proof.**

After CI is green, run:

```powershell
python -m scripts.run_live_dependency_task --blender "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
```

Do not expand Qwen autonomy yet. After the live dependency proof passes, audit whether dependency-aware checkpoint/recovery semantics justify a later concurrency stage; do not implement concurrency merely because the graph permits it.

PR #49 remains draft/unmerged.
