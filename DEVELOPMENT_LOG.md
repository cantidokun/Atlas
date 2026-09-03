# Atlas Development Log

## September 3, 2026 — Qwen Proposal, Atlas Authorization Handoff, and Runtime Boundary

Atlas advanced from the Stage 15 semantic production-task layer into Stage 16 Qwen integration.

### Stage 16 provider milestone

The local Qwen/Ollama provider now produces an intent-only `QwenProductionProposal` containing the canonical workflow, optional version, and typed workflow parameters. Provider output is treated as untrusted and is validated against the trusted soccer-production catalog before release.

The current canonical catalog contract is:

```text
broadcast-goal-preparation@1

file_name       -> string
object_name     -> string
target_location -> vector3
target_rotation -> vector3
```

The live proposal-only smoke test was user-verified locally:

```text
LIVE QWEN PRODUCTION PROPOSAL VERIFIED
workflow=broadcast-goal-preparation
workflow_version=1
workflow_parameter_contract=verified
proposal_validation=verified
catalog_resolution=verified
semantic_task_compilation=verified
execution_authorization=not_requested
execution=not_attempted
blender_mutation=not_attempted
```

This established live model communication, structured extraction, provider-side semantic validation, trusted catalog resolution, and semantic task compilation without mutating Blender.

### Atlas authorization handoff

`qwen/production_handoff.py` establishes a provenance-bound seam between the validated Qwen proposal and Atlas authority.

The handoff:

- validates the proposal;
- compiles through the trusted catalog;
- records proposal, semantic-task, and compiled-task digests;
- rechecks those bindings before authorization;
- independently recompiles the proposal to detect provenance drift;
- rejects model-supplied authorization fields;
- delegates authorization to the existing Atlas `TaskPlanProposal` / `instantiate_authorized_plans(...)` / `ActionAuthorization` path;
- exposes no execution API and no Qwen-specific recovery authority.

### Existing runtime bridge

`planning/authorized_task_runtime.py` provides a generic bootstrap for an already-issued Atlas `ActionAuthorization`.

It does not mint a new authorization mechanism or create a second executor. It verifies the exact action-plan binding, acquires authoritative initial evidence, evaluates the target state, and constructs the existing `AutonomousTaskRuntime`.

The dedicated boundary harness stops before the action phase and is intended to prove that Qwen-driven semantic intent can safely enter the existing runtime without prematurely mutating Blender.

### Full mutation harness

`scripts/run_live_qwen_production_runtime.py` implements the complete intended live chain:

```text
Qwen proposal
  ↓
trusted catalog validation
  ↓
semantic ProductionTaskDefinition
  ↓
Atlas authorization
  ↓
existing AutonomousTaskRuntime
  ↓
Blender mutation
  ↓
fresh independent verification
  ↓
fixture restoration
```

The harness has been implemented but has **not yet been user-verified**.

### Next work

The next development session should run the no-write runtime boundary proof and then the full Qwen-authorized Blender mutation proof. If those pass, extend the same Qwen proposal/handoff boundary into the established Atlas failure/recovery machinery.

Recovery must remain Atlas-owned, explicitly authorized, fresh-evidence-driven, independently verified, and free of automatic write retries.

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
