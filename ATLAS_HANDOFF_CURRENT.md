# Atlas Current Development Handoff

**Updated:** September 2, 2026 — active Atlas development
**Blender continuation branch:** `feat/blender-stage11-mainline`
**Blender Stage 11 PR:** #49 — controlled live mutation harness / Stage 12 continuation
**Current Blender branch work:** task-aware autonomous runtime seam

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

## Blender — Stage 12 task-aware runtime

The reusable closed-loop Blender execution boundary already existed and remains unchanged. The actual architectural gap was the missing task-level binding between:

- declarative `AtlasTaskDefinition` contracts;
- the existing target evaluator and action authorization;
- the existing deterministic future generator;
- the existing checkpointed `AutonomousFutureRuntime`; and
- fresh task evidence at the verification checkpoint.

`planning/autonomous_task_runtime.py` now provides that narrow binding. It does not introduce another mutation boundary, receipt model, authorization system, or engine-specific future controller.

The adapter:

1. validates and prepares the declarative task;
2. acquires authoritative pre-action evidence;
3. evaluates the target state;
4. issues the existing immutable `ActionAuthorization` when writes are required;
5. generates the existing deterministic future;
6. executes the authorized future through the supplied executor;
7. acquires fresh authoritative evidence after the action or zero-write decision;
8. evaluates the fresh evidence; and
9. completes only when verification succeeds, otherwise remaining blocked.

The action executor path is bound back to the immutable task authorization and deterministic future before a write is dispatched.

The Blender rotation task contract is parameterized for live use while preserving its existing defaults and now accepts the canonical Blender result shape in its evaluator.

Focused tests cover:

- authorized mutation;
- already-satisfied zero-write behavior;
- failed fresh verification -> `BLOCKED`;
- canonical Blender inspection result normalization.

## Blender live proof next gate

`scripts/run_live_autonomous_rotation.py` provides the next controlled proof. It uses the declarative rotation task, `AutonomousTaskRuntime`, the production Blender process executor, and the existing persistence boundary for fixture restoration.

The intended proof is:

```text
fresh Blender evidence
        ↓
task target evaluation
        ↓
explicit action authorization
        ↓
deterministic autonomous future
        ↓
real Blender mutation
        ↓
fresh independent Blender evidence
        ↓
target verification
        ↓
COMPLETE
```

The fixture is restored afterward through the existing closed-loop persistence boundary and independently verified.

## Unreal

The local Unreal Engine 5.6 production boundary remains proven through deterministic render configuration, render-state verification, Movie Render Queue submission, dynamic job-ID binding, asynchronous job inspection, semantic completion verification, MRQ artifact discovery, filesystem artifact validation, and evidence-bound persistent render receipts.

The Unreal runtime job registry remains in-memory. Cross-process Unreal render-job recovery is not implemented.

## Required regression philosophy

Preserve coverage for:

- already-satisfied state -> zero writes;
- unsatisfied state -> exact authorized action order;
- successful write -> verification remains mandatory;
- verification failure -> `BLOCKED`;
- action failure -> recovery gate;
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

Stage 11 live mutation is proven. Stage 12 task-aware autonomous runtime integration is implemented and under validation. The immediate next gate is real Blender execution through `AutonomousTaskRuntime`; after that, continue expanding the autonomous path only where the existing architecture has a demonstrable gap.
