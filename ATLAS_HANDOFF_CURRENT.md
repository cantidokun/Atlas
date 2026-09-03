# Atlas Current Development Handoff

**Updated:** September 3, 2026 — Stage 15 higher-level production-task composition live-verified
**Blender continuation branch:** `feat/blender-stage11-mainline`
**Blender PR:** #49 — open, draft, unmerged
**Current Blender branch work:** Stage 14 dependency-aware task composition is fully live-verified; Stage 15 adds semantic soccer-production goals and reusable composition fragments compiled into the existing autonomous task runtime

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

### Stage 15 live proof — VERIFIED

`scripts/run_live_production_task.py` has now been successfully executed against the real Blender 4.4 environment using the composed fragment path. The proof verified:

- higher-level soccer production objective;
- reusable fragment composition;
- explicit fragment dependency handling;
- multi-operation canonical task compilation;
- existing autonomous task runtime execution;
- independent final verification;
- fixture restoration.

The confirmed live target was `Goal_Left_post`, moved by `+0.25` on X and rotated by `+15` degrees on Z, then restored to its original transform.

CI run #1318 passed on the verified branch state before the subsequent semantic-fragment extension. Re-verify the exact branch head before describing the latest commit as CI-green.

## CI

The dependency-recovery implementation previously produced a matrix run with `521 passed, 2 failed`; those failures were confined to the new inherited-dependency regression tests and were subsequently corrected. The corrected Stage 15 composition milestone passed GitHub Actions run #1318 on commit `c070ed0`. New commits after that run require their own CI verification.

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
