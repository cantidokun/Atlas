# Atlas Current Development Handoff

**Updated:** September 3, 2026 — Stage 15 reusable soccer-production workflow live-verified and target-state regression coverage extended
**Blender continuation branch:** `feat/blender-stage11-mainline`
**Blender PR:** #49 — open, draft, unmerged
**Current Blender branch work:** Stage 14 dependency-aware task composition is fully live-verified; Stage 15 adds semantic soccer-production goals, reusable composition fragments, and self-contained workflow templates compiled into the existing autonomous task runtime

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
- inherited dependency state is included in the deterministic future integrity digest and persisted snapshot;
- legacy dependency-free authorization digest compatibility is preserved for existing durable receipts;
- future-controller snapshot calls fail closed when inherited dependency state is mutated after authorization.

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

### Live Stage 14 dependency-aware recovery — VERIFIED

`scripts/run_live_dependency_recovery.py` was successfully executed across two separate Python processes against the real Blender 4.4 environment. The completed `prepare_location` prerequisite was inherited by the replacement rotation action without replaying the completed write.

## Stage 15 — higher-level production tasks

Stage 15 introduces a semantic production-goal layer rather than another execution layer. `ProductionTaskDefinition` represents a meaningful soccer-production objective with:

- human-readable `objective`;
- production `domain`;
- explicit `deliverables`;
- explicit `constraints`;
- evidence requests and multi-operation `ActionSpec` sequences;
- existing target evaluator and action-tool allowlist.

A production task compiles directly to one existing `AtlasTaskDefinition`. Execution, authorization, checkpointing, recovery, and independent verification remain owned by the already-proven generic runtime.

Reusable `ProductionTaskFragment` composition now supports:

- named fragments with preserved order;
- fragment-level evidence and action groups;
- explicit semantic fragment dependencies validated at composition time;
- fragment-level deliverables and constraints;
- durable fragment metadata and snapshots;
- task-level metadata retaining the composed fragment specifications.

Fragment dependencies are semantic composition constraints. Executable ordering remains governed by the canonical `ActionSpec.depends_on` graph and the existing future controller.

### Reusable soccer-production workflow templates — VERIFIED

`planning/soccer_production_templates.py` is the canonical reusable workflow-template module. It currently provides:

- `GoalPositionTemplate` — atomic goal-position fragment;
- `GoalOrientationTemplate` — atomic goal-orientation fragment with a fixed semantic dependency on `position-goal` and an executable dependency on `position_goal`;
- `BroadcastGoalPreparationTemplate` — composed two-phase workflow for preparing a soccer goal for a broadcast shot.

The templates validate transform shape and finite numeric values before composition. The broadcast template now owns construction of its semantic `ProductionTaskDefinition`, including its target-state evaluator, deliverables, constraints, metadata, and allowlisted action tools, while still compiling into the existing Atlas task contract rather than creating a second runtime.

### Live Stage 15 reusable workflow proof — VERIFIED

`scripts/run_live_production_task.py` was successfully executed against the real Blender 4.4 environment using the self-contained `BroadcastGoalPreparationTemplate.production_task()` path.

The proof verified:

- reusable workflow-template identity;
- semantic soccer-production objective;
- reusable fragment composition;
- explicit semantic fragment dependencies;
- canonical executable action dependencies;
- multi-operation production-task compilation;
- existing autonomous task runtime execution;
- independent final verification;
- fixture restoration.

The confirmed live target was `Goal_Left_post`, moved to `[0.25, 5.302, 0.0]` and rotated to `[0.0, 0.0, 15.0]`, then restored to `[0.0, 5.302, 0.0]` and `[0.0, 0.0, 0.0]`.

### Target-state evaluator coverage — EXTENDED

The reusable workflow test suite now directly exercises the evaluator attached by `BroadcastGoalPreparationTemplate.production_task()`:

- matching authoritative evidence satisfies both position and orientation invariants;
- a position mismatch fails the overall target state while preserving the independently passing orientation invariant.

This strengthens the semantic workflow boundary without altering execution or authorization semantics.

## CI

GitHub Actions `Atlas Tests` run **#1337** completed successfully for commit `2f84e10123501eb64146bd5ae1ca53659185b774`, which contains the live-verified reusable workflow implementation and live harness alignment.

The current branch head is `cb9716eee847b7cbf1080325908b25b91ec22016`, a test-only follow-up extending target-state evaluator coverage. At the time of this handoff update, no workflow run or combined status is yet associated with that exact commit, so the current head must not be described as CI-green until its own run appears.

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
- production-task semantics -> compile to the existing task contract;
- production-task dependencies -> remain authorization-bound;
- production-task metadata -> remain descriptive, never executable;
- fragment semantics -> retained through composition without creating execution authority;
- reusable workflow target-state evaluation -> authoritative matching and fail-closed mismatch behavior;
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

**Next: continue Stage 15 by expanding reusable soccer-production workflow composition and recovery semantics while preserving the single canonical Atlas task/runtime path. Stage 16 remains deferred until the production-task abstraction is structurally mature.**

Do not expand Qwen autonomy yet.

Do not claim cross-process Unreal render-job recovery unless it is separately implemented and verified.

PR #49 remains draft/unmerged.
