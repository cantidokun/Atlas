# Atlas Current Development Handoff

**Updated:** September 3, 2026 — Stage 13 live verification checkpoint
**Blender continuation branch:** `feat/blender-stage11-mainline`
**Blender PR:** #49 — open, draft, unmerged
**Current Blender branch work:** Stage 13 multi-step autonomous task execution is proven; Stage 14 dependency-aware task composition is next

## Current state

Atlas is advancing on two independent execution-environment tracks: Blender and Unreal. The authority model remains unchanged:

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

Qwen never receives direct production execution authority.

Atlas development has standing authorization to run appropriate local tests, GitHub Actions workflows, action-runner tests, and relevant live validation required by the development task. Workflow execution no longer requires separate per-run user authorization.

## Blender — verified Stage 11 milestone

The first controlled real Blender mutation was proven locally through the Atlas execution boundary using Blender 4.4. `Goal_Left_post` was rotated from `[0.0, 0.0, 0.0]` to `[0.0, 0.0, 15.0]`, independently inspected after save, and restored to its original rotation.

## Blender — verified Stage 12 task-aware runtime and recovery

`planning/autonomous_task_runtime.py` provides the narrow adapter between declarative `AtlasTaskDefinition` contracts and the existing checkpointed autonomous future runtime. It reuses the existing task validation, target evaluator, immutable action authorization, deterministic future generator, continuation state, recovery gate, replan authorization, and supplied engine executor rather than introducing parallel control systems.

Stage 12 proved task-aware autonomous mutation, mandatory fresh verification, durable continuation after successful execution, and cross-process recovery after a durable action failure with fresh evidence and explicit replacement authorization.

During validation, continuation integrity correctly rejected a temporary harness defect in which Phase 2 supplied a different runtime-context identity. The harness was corrected; the integrity guard was not weakened.

## Blender — Stage 13: multi-step autonomous task execution with partial-progress recovery

Stage 13 is now **fully live-verified** against the real Blender 4.4 environment and the GitHub Actions regression suite.

The implementation first identified and corrected a real structural gap: `AutonomousTaskRuntime` previously overwrote multiple task evidence results instead of preserving them as a deterministic evidence bundle. Multiple evidence requests are now retained by stable request/tool keys, preserving backward compatibility for single-request tasks.

Regression coverage now proves that a later action failure does not replay an earlier successful action and that multi-request evidence remains available to target evaluation and verification.

### Live Phase 1

`scripts/run_live_autonomous_multistep_recovery_restart.py --phase failure` was executed successfully.

Observed:

```text
LIVE AUTONOMOUS MULTISTEP RECOVERY PHASE 1 VERIFIED
object=Goal_Left_post
original_location=[0.0, 5.302, 0.0]
original_rotation=[0.0, 0.0, 0.0]
action_1=completed
action_2=controlled_failure
partial_progress_checkpoint=verified
process_restart=ready
```

This proves that the first real Blender mutation completed, the second action failed in a controlled manner before its Blender write, and durable state recorded the partial-progress boundary.

### Live Phase 2

A fresh Python process then executed:

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

This is the completed Stage 13 proof. Atlas reconstructed the durable blocked state in a new process, recovered the original authorization, acquired fresh multi-source evidence, issued a new evidence-bound replan authorization, executed only the unfinished replacement action, independently verified both final properties, and restored the fixture.

The critical safety property is proven: **completed action 1 was not replayed after action 2 failed.**

## CI checkpoint

The exact Stage 13 branch head `361b97e685f815e54c22fcd65c29968a783ff73f` passed the GitHub Actions `Atlas Tests` workflow successfully (run `#1251`).

PR #49 remains **open, draft, and unmerged**.

## Architecture audit after Stage 13

The current execution path remains a single coherent authority chain:

```text
AtlasTaskDefinition
        ↓
Task-aware runtime adapter
        ↓
FutureExecutionController
        ↓
Atlas executor / engine adapter
        ↓
Independent evidence
        ↓
FutureRecoveryGate
        ↓
ReplanAuthorization
        ↓
Replacement future + new ActionAuthorization
```

The future controller already represents multiple ordered actions and durable continuation indexes. The next architectural gap is that ordering is currently encoded primarily by list position. `ActionSpec` has no explicit dependency semantics, while the deterministic future generator serializes the supplied action list into a linear path.

Do not replace the existing execution or authorization architecture. Extend it with explicit task-composition semantics while keeping execution deterministic and serial for the first Stage 14 increment.

## Next session — Stage 14: dependency-aware task composition

Begin with an audit of `ActionSpec`, `ActionPlan`, `ActionAuthorization`, `DeterministicFutureGenerator`, `FutureExecutionController`, `AtlasTaskDefinition`, and the task-aware runtime against a small soccer-field-related Blender task whose actions have explicit prerequisites.

The initial Stage 14 objective is **not** parallel execution. It is to make dependencies explicit and validated while preserving the current serial execution model.

A useful conceptual shape is:

```text
inspect authoritative state
        ↓
target evaluation
        ↓
authorized dependency graph
        ↓
prepare_geometry
        ↓
update_material
        ↓
configure_render
        ↓
fresh verification
        ↓
COMPLETE
```

Stage 14 acceptance criteria should include:

- dependencies are explicit rather than inferred only from list position;
- dependency references are validated and deterministic;
- cycles and unknown dependency IDs are rejected before execution;
- authorization remains bound to the exact dependency-aware plan;
- deterministic serial execution still produces one unambiguous next action;
- partial-progress recovery respects dependency completion state;
- replans cannot introduce actions outside the task contract;
- fresh verification remains mandatory;
- no second execution or authorization system is introduced.

Do not introduce parallel execution yet. Once dependency semantics are proven, a later stage can evaluate whether independent branches are safe to schedule concurrently.

## Unreal

The local Unreal Engine 5.6 production boundary remains proven through deterministic render configuration, render-state verification, Movie Render Queue submission, dynamic job-ID binding, asynchronous render-job inspection, semantic completion verification, MRQ artifact discovery, filesystem artifact validation, and evidence-bound persistent render receipts.

The Unreal runtime job registry remains in-memory. Cross-process Unreal render-job recovery is not implemented.

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
- partial-progress recovery -> completed prior actions are not blindly replayed;
- multi-request task evidence -> retained as deterministic evidence bundle;
- task target decision -> deterministic future binding;
- persisted task metadata -> future consistency;
- action authorization -> exact task action binding;
- cross-process continuation -> recovered authorization and fresh verification;
- cross-process blocked recovery -> recovered gate + authorization before replan;
- dependency graph -> unknown references rejected;
- dependency graph -> cycles rejected;
- dependency-aware authorization -> exact plan binding;
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
- Treat artifact existence as independently verified evidence, not an implication of job success.
- Do not claim cross-process Unreal render-job recovery unless it is separately implemented and verified.
- Preserve the canonical Digital Twin as distinct from Unreal, Blender, photogrammetry outputs, and temporary production artifacts.

## Resume point

**Next: begin Stage 14 — dependency-aware task composition.**

First inspect the current action/task primitives together, define the smallest explicit dependency representation that preserves serial determinism, add structural regression coverage, run the offline matrix, and only then extend to a live Blender proof.

PR #49 remains draft/unmerged.
