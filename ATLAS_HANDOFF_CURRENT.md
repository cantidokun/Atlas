# Atlas Current Development Handoff

**Updated:** September 2, 2026 — active Atlas development
**Blender continuation branch:** `feat/blender-stage11-mainline`
**Blender Stage 11 PR:** #49 — controlled live mutation harness / Stage 12 continuation
**Current Blender branch work:** task-aware autonomous runtime, restart recovery, and task recovery/replan seam

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

The reusable closed-loop Blender execution boundary remains unchanged. The architectural gap was the missing task-level binding between declarative `AtlasTaskDefinition` contracts and the existing checkpointed autonomous future runtime.

`planning/autonomous_task_runtime.py` now provides that narrow binding. It reuses the existing task validation, target-state evaluator, immutable action authorization, deterministic future generator, autonomous continuation state, and supplied engine executor.

The adapter:

1. validates and prepares the declarative task;
2. acquires authoritative pre-action evidence;
3. evaluates the target state;
4. issues the existing immutable `ActionAuthorization` when writes are required;
5. generates the existing deterministic future from that resolved decision;
6. persists the task target evaluation and write authorization as task-level continuation metadata;
7. binds each autonomous write to the authorized task action and current deterministic future step;
8. executes through the supplied executor;
9. acquires fresh authoritative evidence after the action or zero-write decision; and
10. completes only when verification succeeds, otherwise remaining blocked.

The runtime explicitly keeps action authorization digests distinct from deterministic future-plan digests. It rejects inconsistent persisted task/future bindings instead of attempting to repair them implicitly.

## Blender — verified Stage 12 live autonomous mutation

The controlled live task-aware rotation proof was established locally against Blender 4.4. The proof demonstrated real evidence acquisition, target-state evaluation, explicit action authorization, deterministic autonomous execution, real Blender mutation, fresh independent verification, and fixture restoration through the existing closed-loop persistence boundary.

## Blender — verified Stage 12 cross-process restart recovery

The restart harness `scripts/run_live_autonomous_rotation_restart.py` was successfully executed locally on the development PC across two separate Python processes.

Verified sequence:

```text
phase 1 preflight evidence
        ↓
target evaluated unsatisfied
        ↓
write authorization persisted
        ↓
action executed in real Blender
        ↓
fresh verification checkpoint persisted
        ↓
Python process terminated
        ↓
fresh Python process reconstructed runtime
        ↓
exact authorization recovered from durable state
        ↓
fresh Blender verification
        ↓
COMPLETE
        ↓
fixture restored and independently verified
```

Observed live proof included:

```text
LIVE AUTONOMOUS RESTART PHASE 1 VERIFIED
checkpoint=verification
process_restart=ready
LIVE AUTONOMOUS RESTART VERIFIED
durable_checkpoint=verified
authorization_recovered=verified
fresh_verification=verified
fixture_restored=[0.0, 0.0, 15.0]
```

The fixture was originally at `[0.0, 0.0, 15.0]`; the harness normalized it to `[0.0, 0.0, 0.0]` for phase 1 so the task necessarily exercised the write path, then restored the original `[0.0, 0.0, 15.0]` state after completion.

## Blender — task recovery/replan seam implemented, live validation pending

The task-aware runtime now binds the existing generic recovery protocol without creating a second execution or authorization boundary.

Implemented behavior:

- a failed autonomous write is durably checkpointed as `BLOCKED`;
- `FutureRecoveryGate` classifies the failure and prohibits automatic retry;
- fresh task evidence is required before recovery can proceed;
- replacement actions are limited to the task's allowed action tools;
- `ReplanAuthorization` binds replacement actions to the fresh recovery evidence;
- a replacement future is generated only after explicit replan authorization;
- a new `ActionAuthorization` is issued for the replacement future when writes remain necessary;
- resumed task adapters retain the reconstructed runtime object so subsequent verification/recovery operates on the active continuation.

The existing generic recovery gate already enforces fresh evidence and rejects automatic retry. fileciteturn631file0

Regression coverage has been added for the autonomous task recovery path, including failed-write recovery, fresh-evidence gating, explicit replacement authorization, and unauthorized recovery tools. The current CI run is the validation gate for this increment.

## Unreal

The local Unreal Engine 5.6 production boundary remains proven through deterministic render configuration, render-state verification, Movie Render Queue submission, dynamic job-ID binding, asynchronous job inspection, semantic completion verification, MRQ artifact discovery, filesystem artifact validation, and evidence-bound persistent render receipts.

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
- task target decision -> deterministic future binding;
- persisted task metadata -> future consistency;
- action authorization -> exact task action binding;
- cross-process continuation -> recovered authorization and fresh verification;
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

Stage 11 live mutation is proven. Stage 12 task-aware autonomous runtime integration and cross-process Blender continuation are proven locally. The task recovery/replan seam is now implemented and covered by regression tests, with live failure/replan validation still required. Do not expand task autonomy further until the recovery/replan path is exercised against real Blender failure and the resulting replacement action is independently verified.
