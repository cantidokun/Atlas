# Atlas Current Development Handoff

**Updated:** September 3, 2026 — Stage 13 live verification + Stage 14 dependency foundation
**Blender continuation branch:** `feat/blender-stage11-mainline`
**Blender PR:** #49 — open, draft, unmerged
**Current Blender branch work:** Stage 13 multi-step autonomous recovery is proven; Stage 14 dependency-aware task composition is in progress

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

Qwen never receives direct production execution authority.

Atlas development has standing authorization to run appropriate local tests, GitHub Actions workflows, action-runner tests, and relevant live validation required by the development task.

## Blender — verified Stage 13

Stage 13 is fully live-verified against Blender 4.4. The two-process proof used `Goal_Left_post` with two ordered writes: move the object, then set its rotation.

Phase 1 completed action 1, deliberately failed action 2 before its Blender write, and persisted the partial-progress checkpoint. Phase 2 started in a fresh Python process, reconstructed the blocked runtime and authorization, acquired fresh multi-request evidence, issued an evidence-bound replan authorization, executed only the unfinished action 2, independently verified the final location and rotation, and restored the fixture.

Observed proof:

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

The critical safety property is proven: completed action 1 is not blindly replayed after action 2 fails.

The exact Stage 13 head `361b97e685f815e54c22fcd65c29968a783ff73f` also passed GitHub Actions `Atlas Tests` run `#1251`.

## Stage 14 — dependency-aware task composition

Stage 14 has now started from the proven Stage 13 architecture. The initial design deliberately does **not** introduce parallel execution.

Implemented foundation:

- `ActionSpec` now supports declarative `depends_on` action names;
- dependency metadata is included in action-plan execution state;
- `ActionAuthorization` binds its digest to dependency declarations, so authorized dependencies cannot be silently changed;
- `planning/action_dependencies.py` validates dependency-bearing plans before execution;
- `AtlasTaskDefinition` validates dependency declarations;
- `DeterministicFutureGenerator` preserves the authorized serial action order and carries dependency metadata into future steps;
- `PlanningOrchestrator` and `AutonomousTaskRuntime` preserve dependency metadata when reconstructing action specifications;
- dependency regression coverage checks valid serial dependencies, later-action dependencies, unknown/self/duplicate dependencies, and authorization mismatch after dependency mutation.

The design rule is intentional: dependency semantics constrain the exact authorized order, but the current executor remains serial and deterministic. No scheduler or second execution system has been introduced.

### Current dependency model

```text
authorized action list
        ↓
explicit prerequisite declarations
        ↓
validated topological order
        ↓
serial deterministic future
        ↓
checkpoint after each completed action
        ↓
fresh verification
```

Dependency-free legacy action lists remain valid. Dependency-bearing plans must use unambiguous action names; references to later, unknown, self, or duplicated dependencies are rejected.

## Stage 14 next validation

GitHub Actions `Atlas Tests` run `#1263` is currently queued on the latest dependency-validation change (`d650029...`). Do not treat Stage 14 as complete until the new matrix passes.

After CI is green, add a deliberately small soccer-field-related Blender task with explicit prerequisites and prove the dependency metadata survives authorization, checkpointing, and process reconstruction. Keep execution serial for this increment.

## Unreal

The local Unreal Engine 5.6 production boundary remains proven for the current implemented capabilities: deterministic render configuration, render-state verification, Movie Render Queue submission, dynamic job-ID binding, asynchronous job inspection, semantic completion verification, MRQ artifact discovery, filesystem artifact validation, and evidence-bound persistent render receipts.

Cross-process Unreal render-job recovery is not implemented.

## Resolution / 4K direction

Atlas is intended to work with source footage including 4K/UHD. The 640x360 Unreal render proof is a controlled boundary test, not a source-footage limit. Resolution affects decode, tracking, memory, storage, reconstruction, compositing, and render throughput, but it does not change the core Atlas authority/orchestration model.

Plan resolution-aware workload/resource handling rather than a separate 4K architecture. Preserve the original high-resolution source as authoritative and use proxies/intermediates where appropriate without weakening evidence or provenance.

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
- dependency graph -> unknown references rejected;
- dependency graph -> cycles/later references rejected;
- dependency-aware authorization -> exact plan binding;
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
- Treat artifact existence as independently verified evidence, not an implication of job success.
- Preserve the canonical Digital Twin as distinct from Unreal, Blender, photogrammetry outputs, and temporary production artifacts.
- Do not introduce parallel execution until dependency semantics are independently proven safe.

## Resume point

**Next: complete Stage 14 dependency validation.**

First obtain a green CI result for the dependency foundation. Then construct and live-verify the smallest soccer-field-related Blender task whose actions declare explicit prerequisites. Confirm dependency metadata survives authorization, deterministic future generation, checkpoints, and cross-process reconstruction. Only after that should Atlas evaluate safe scheduling of independent branches.

PR #49 remains draft/unmerged.
