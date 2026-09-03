# Atlas Current Development Handoff

**Updated:** September 3, 2026 — Stage 15 semantic workflow catalog, provenance, and live cross-process recovery fully verified
**Blender continuation branch:** `feat/blender-stage11-mainline`
**Blender PR:** #49 — open, draft, unmerged
**Stage status:** Stage 15 COMPLETE FOR CURRENT CONTRACT; Stage 16 Qwen proposal integration is now the next development stage

## Current authority model

```text
Qwen / AI
  -> reason and propose structured production tasks

Python / Atlas
  -> validate, authorize, execute, track state, verify, recover

Blender / Unreal
  -> controlled production execution

Independent verification
  -> establish what actually happened
```

Qwen never receives direct production execution authority. Atlas remains the authority layer.

## Stage 15 — COMPLETE FOR CURRENT CONTRACT

Stage 15 introduced a semantic production-goal layer without introducing a second execution engine. `ProductionTaskDefinition` represents meaningful soccer-production objectives with objective, domain, deliverables, constraints, evidence, ordered actions, target evaluation, and an action-tool allowlist. It compiles directly into the existing `AtlasTaskDefinition`, preserving the single canonical autonomous runtime.

Reusable `ProductionTaskFragment` composition supports named fragment ordering, semantic fragment dependencies, fragment-level evidence/actions, deliverables, constraints, and descriptive metadata. Executable ordering remains governed by `ActionSpec.depends_on` and the existing deterministic future controller.

Canonical soccer-production templates currently include:

- `GoalPositionTemplate`
- `GoalOrientationTemplate`
- `BroadcastGoalPreparationTemplate`

The reusable broadcast workflow owns its target-state evaluator and composes the position and orientation operations into the existing Atlas task contract.

### Canonical workflow catalog

`planning/soccer_production_catalog.py` now provides a declarative, versioned catalog for reusable soccer-production workflows. Current contract:

```text
broadcast-goal-preparation@1

file_name       -> string
object_name     -> string
target_location -> vector3
target_rotation -> vector3
```

The catalog validates exact workflow identity, version, required parameters, unexpected parameters, parameter kinds, vector shape, and finite numeric values before template construction.

`compile_soccer_production_workflow(...)` resolves the versioned catalog entry, constructs the canonical semantic production task, and records the exact workflow descriptor plus normalized parameters as semantic provenance. The catalog does not execute, authorize, schedule, or recover work.

### Autonomous semantic provenance

`AutonomousTaskRuntime` now persists task metadata into continuation state at task start and authorized replan. Resume/reconstruction verifies that persisted semantic metadata matches the supplied task definition. Authorized replans retain the original semantic task metadata. Tampered semantic provenance fails closed.

This preserves workflow identity across normal continuation and recovery without creating a second recovery mechanism.

### Live reusable workflow — VERIFIED

The real Blender 4.4 environment successfully executed the catalog-defined workflow through the existing autonomous runtime:

```text
LIVE VERSIONED SOCCER PRODUCTION WORKFLOW VERIFIED
workflow=broadcast-goal-preparation
workflow_version=1
workflow_parameter_contract=verified
workflow_catalog=verified
workflow_template=verified
fragment_composition=verified
fragment_dependencies=verified
multi_operation_composition=verified
dependency_validation=verified
existing_task_runtime=verified
independent_final_verification=verified
```

The target object was `Goal_Left_post`, moved to `[0.25, 5.302, 0.0]`, rotated to `[0.0, 0.0, 15.0]`, independently verified, and restored.

### Live cross-process versioned workflow recovery — VERIFIED

The recovery proof was executed against real Blender 4.4 across two Python processes.

Phase 1 deliberately failed the second production operation after the first prerequisite action completed. The durable checkpoint preserved workflow version, typed parameter contract, and semantic provenance.

Phase 2 reconstructed the workflow from persisted catalog provenance in a fresh process and verified:

- `broadcast-goal-preparation@1` identity recovered;
- workflow parameter contract recovered;
- semantic provenance recovered;
- completed prerequisite was not replayed;
- process restart recovery succeeded;
- fresh authoritative evidence was required;
- explicit replan authorization was required;
- replacement execution succeeded;
- fresh final verification succeeded;
- fixture restoration succeeded.

User-confirmed live output:

```text
LIVE VERSIONED WORKFLOW RECOVERY VERIFIED
workflow=broadcast-goal-preparation
workflow_version=1
workflow_parameter_contract=verified
semantic_provenance_recovered=verified
completed_prerequisite_not_replayed=verified
process_restart=verified
fresh_recovery_evidence=verified
replan_authorization=verified
replacement_execution=verified
fresh_final_verification=verified
fixture_restored_location=[0.25, 5.302, 0.0]
fixture_restored_rotation=[0.0, 0.0, 0.0]
```

The restored location value `[0.25, 5.302, 0.0]` reflects the fixture's pre-test state at the time of this run; the verified recovery path restored that observed original state exactly.

## CI

GitHub Actions `Atlas Tests` passed after the Stage 15 repair series, including run **#1370** for commit `a8d81196b3bccc1c674d6038ff6fee115b24d8ec`. Earlier Stage 15 commits also passed runs #1365, #1366, #1367, and #1368. The earlier run #1362 failed because older catalog tests had not yet been updated for the typed parameter contract; those regressions were corrected.

The latest Stage 15 live-recovery harness fix is included in the green #1370 validation checkpoint.

## Stage 16 — NEXT

Stage 16 begins Qwen proposal integration.

The intended boundary is:

```text
Qwen
  ↓
reason about a soccer-production objective
  ↓
propose structured workflow/task
  ↓
Atlas parses and validates proposal
  ↓
Atlas resolves allowed catalog/template/task contract
  ↓
Atlas derives evidence + actions + dependencies
  ↓
Atlas authorizes
  ↓
existing autonomous runtime executes
  ↓
independent verification
  ↓
existing recovery/replan protocol
```

Qwen is a proposal/reasoning layer only. It must not receive direct tool execution, authorization, persistence, recovery, or scheduler authority.

Stage 16 should therefore begin with a proposal adapter/validator around the existing structured Qwen contract and the Stage 15 workflow catalog, not with a new executor.

## Unreal

The local Unreal Engine 5.6 production boundary remains proven for the implemented capabilities: deterministic render configuration, render-state verification, Movie Render Queue submission, dynamic job-ID binding, asynchronous inspection, semantic completion verification, MRQ artifact discovery, filesystem validation, and evidence-bound persistent render receipts.

Cross-process Unreal render-job recovery is not implemented.

## Resolution / 4K direction

Atlas is intended to operate on source soccer footage including 4K/UHD. The existing 640x360 Unreal render is a controlled boundary test, not a source-footage maximum. Resolution affects decode, tracking, memory, storage, reconstruction, compositing, and render throughput, but does not change the core Atlas orchestration model.

Use resolution-aware workload/resource handling rather than a separate 4K architecture. Preserve the original high-resolution source as authoritative and use proxies/intermediates where appropriate without weakening provenance or evidence.

## Non-regression rules

- Never give Qwen direct production execution authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from a transport/write response alone.
- Keep engine-specific behavior behind adapter/tool boundaries.
- Preserve independent verification and the evidence ledger.
- Do not introduce parallel execution until dependency semantics are independently proven safe.
- Preserve the canonical Digital Twin as distinct from Unreal, Blender, photogrammetry outputs, and temporary production artifacts.

## PR status

PR #49 remains open, draft, and unmerged. **Do not merge unless explicitly requested.**

## Resume point

**Begin Stage 16: Qwen proposal integration into the validated Stage 15 workflow/task planning boundary.** Preserve Qwen as proposal-only and route all resulting work through Atlas validation, authorization, the existing autonomous runtime, and independent verification. No new execution engine or parallel path should be introduced.
