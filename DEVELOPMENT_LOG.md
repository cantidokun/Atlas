# Atlas Development Log

## September 3, 2026 — Qwen Proposal, Atlas Authorization, Runtime, and Cross-Process Recovery

Atlas advanced through the full Stage 16 Qwen integration boundary and live-verified Qwen-originated recovery across a Python process restart.

### Stage 16 provider milestone

The local Qwen/Ollama provider produces an intent-only `QwenProductionProposal` containing the canonical workflow, optional version, and typed workflow parameters. Provider output is treated as untrusted and is validated against the trusted soccer-production catalog before release.

The current canonical catalog contract is:

```text
broadcast-goal-preparation@1

file_name       -> string
object_name     -> string
target_location -> vector3
target_rotation -> vector3
```

The live proposal-only smoke test was user-verified locally.

### Atlas authorization handoff

`qwen/production_handoff.py` establishes a provenance-bound seam between the validated Qwen proposal and Atlas authority. The handoff validates proposal/catalog provenance, records digests, independently recompiles before authorization, rejects model-supplied authorization fields, and delegates to the existing Atlas authorization path.

The handoff is also durably reconstructable through `QwenProductionTaskHandoff.from_snapshot(...)`. Persisted proposal, semantic-task, compiled-task, and digest fields are revalidated and recompiled fail-closed before they can re-enter Atlas recovery.

### Full Qwen-authorized production runtime — LIVE VERIFIED

`scripts/run_live_qwen_production_runtime.py` was user-verified against Blender 4.4.

Verified live chain:

```text
Qwen proposal
  ↓
trusted catalog validation
  ↓
semantic ProductionTaskDefinition
  ↓
Atlas ActionAuthorization
  ↓
existing AutonomousTaskRuntime
  ↓
real Blender mutation
  ↓
fresh independent verification
  ↓
fixture restoration
```

Observed live verification:

```text
workflow=broadcast-goal-preparation
workflow_version=1
qwen_proposal=verified
catalog_validation=verified
semantic_task=verified
atlas_authorization=verified
existing_task_runtime=verified
blender_execution=verified
independent_final_verification=verified
```

The live mutation targeted `Goal_Left_post` at `[0.5, 5.302, 0.0]` with rotation `[0.0, 0.0, 15.0]`, then restored the observed fixture state to location `[0.25, 5.302, 0.0]` and rotation `[0.0, 0.0, 0.0]`.

### Qwen-originated cross-process recovery — LIVE VERIFIED

`scripts/run_live_qwen_production_recovery_restart.py` now exercises the established Atlas recovery path with persisted Qwen provenance.

Phase 1:
- obtains a live Qwen proposal;
- validates and compiles it through the trusted catalog;
- obtains Atlas authorization;
- executes the first real action in Blender;
- intentionally fails the later action before Blender is invoked;
- persists the blocked continuation plus Qwen provenance.

Phase 2:
- starts a fresh Python process;
- reconstructs the persisted Qwen handoff through canonical validation/recompilation;
- reconstructs the existing Atlas runtime and original authorization;
- acquires fresh authoritative evidence;
- derives only the unfinished action from the persisted authorized workflow;
- explicitly issues a new Atlas replan authorization;
- executes the replacement action;
- independently verifies the complete target state;
- restores the fixture.

User-verified output:

```text
LIVE QWEN PRODUCTION RECOVERY VERIFIED
object=Goal_Left_post
workflow=broadcast-goal-preparation
workflow_version=1
qwen_provenance_recovered=verified
initial_authorization_recovered=verified
process_restart=verified
fresh_recovery_evidence=verified
qwen_workflow_target_revalidated=verified
completed_prerequisite_not_replayed=verified
replacement_execution=verified
independent_final_verification=verified
```

This establishes that Qwen-originated work can cross a process boundary without giving Qwen recovery authority. Atlas still owns recovery classification, evidence acquisition, replan authorization, execution, and final verification.

### Recovery architecture rule

Do not add a Qwen-specific executor, authorization system, scheduler, or recovery controller. Qwen remains an intent/proposal source; Atlas remains the sole production authority and recovery owner.

### CI note

A CI run after the initial recovery changes exposed one assertion-message mismatch (`615 passed, 1 failed`). The test expectation was corrected. A subsequent CI result for the newest correction commit has not yet been reported, so CI should not be described as green until a fresh run confirms it.

## Stage 15 — Semantic Soccer Production Tasks

Stage 15 established `ProductionTaskDefinition`, reusable production-task fragments, target-state evaluators, canonical soccer-production templates, and the versioned workflow catalog.

The semantic task layer compiles directly into the existing `AtlasTaskDefinition` and therefore reuses the existing execution/authorization/recovery runtime.

The real Blender 4.4 environment live-verified the versioned workflow path, including semantic provenance, dependency validation, multi-operation execution, independent verification, recovery, and exact fixture restoration.

## Stage 14 — Dependency-aware task composition

Stage 14 added explicit action prerequisites through `ActionSpec.depends_on` while keeping execution serial and deterministic.

Dependency declarations participate in authorization and integrity digests, and completed prerequisites are recovered from trusted successful checkpoints.

The live dependency task and cross-process dependency-recovery paths were verified against Blender 4.4.

## Stage 13 — Multi-step partial-progress recovery

Stage 13 demonstrated that a completed action is not blindly replayed after a later action fails. Durable checkpointing, process restart, fresh evidence, explicit replan authorization, replacement execution, independent verification, and fixture restoration were all verified.

## Unreal — Current baseline

Unreal Engine 5.6 render configuration, MRQ submission, dynamic job IDs, asynchronous inspection, artifact verification, evidence-bound render receipts, and durable receipt persistence are proven locally for the implemented boundary.

Cross-process Unreal render-job recovery remains unimplemented.

## Development rules

- Qwen proposes; Atlas validates and authorizes; Blender/Unreal execute through controlled adapters.
- Never give Qwen direct execution or authorization authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from a transport/write response alone.
- Preserve independent verification and the evidence ledger.
- Keep engine-specific execution behind adapter/tool boundaries.
- Preserve canonical Digital Twin identity separately from DCC/engine artifacts.
- Keep dependency-aware execution serial until concurrency is independently justified.
- Keep project handoffs and readmes synchronized with verified milestones.
