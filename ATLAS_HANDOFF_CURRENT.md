# Atlas Current Development Handoff

**Updated:** September 3, 2026 — Stage 15 complete for current contract; Stage 16 Qwen provider, Atlas authorization handoff, and runtime-boundary integration implemented
**Blender continuation branch:** `feat/blender-stage11-mainline`
**Blender PR:** #49 — open, draft, unmerged
**Stage status:** Stage 15 COMPLETE FOR CURRENT CONTRACT; Stage 16 IN PROGRESS

## Current authority model

```text
Qwen / AI
  -> reason and propose structured production intent

Python / Atlas
  -> validate, resolve, authorize, execute, track state, verify, recover

Blender / Unreal
  -> controlled production execution

Independent verification
  -> establish what actually happened
```

Qwen never receives direct production execution authority. Atlas remains the authority layer.

## Stage 15 — COMPLETE FOR CURRENT CONTRACT

Stage 15 introduced a semantic production-goal layer without introducing a second execution engine. `ProductionTaskDefinition` represents meaningful soccer-production objectives with objective, domain, deliverables, constraints, evidence, ordered actions, target evaluation, and an action-tool allowlist. It compiles directly into the existing `AtlasTaskDefinition`, preserving the single canonical autonomous runtime.

Reusable `ProductionTaskFragment` composition supports named fragment ordering, semantic fragment dependencies, fragment-level evidence/actions, deliverables, constraints, and descriptive metadata. Executable ordering remains governed by `ActionSpec.depends_on` and the existing deterministic future controller.

Canonical soccer-production templates currently include `GoalPositionTemplate`, `GoalOrientationTemplate`, and `BroadcastGoalPreparationTemplate`.

`planning/soccer_production_catalog.py` provides the canonical versioned workflow catalog. Current contract:

```text
broadcast-goal-preparation@1

file_name       -> string
object_name     -> string
target_location -> vector3
target_rotation -> vector3
```

The catalog validates exact identity/version, required and unexpected parameters, declared parameter kinds, vector shape, and finite numeric values before template construction. Compilation records the exact catalog descriptor and normalized parameters as semantic provenance.

`AutonomousTaskRuntime` persists task metadata at start and authorized replan, and resume/reconstruction requires semantic metadata to match the task definition. Tampered semantic provenance fails closed.

The real Blender 4.4 environment live-verified the catalog -> semantic task -> existing autonomous runtime path and a two-process failure/recovery path. The recovery proof verified version identity, typed parameter contract, semantic provenance recovery, no replay of the completed prerequisite, fresh recovery evidence, explicit replan authorization, replacement execution, independent final verification, and fixture restoration.

Stage 15 therefore closes for the current contract.

## CI checkpoint

GitHub Actions `Atlas Tests` run **#1370** passed for the Stage 15 recovery-harness stabilization commit `a8d81196b3bccc1c674d6038ff6fee115b24d8ec`. Stage 16 provider tests passed run **#1383** for commit `bcbf3c76be2b4737783233b681f0b7f47113318d`. Run **#1384** passed for the subsequent provider-to-catalog revision. Run **#1394** exposed three stale provider-test expectations while the live smoke test also exposed model-generated invalid parameter values; both classes of issues have since been corrected. The live Qwen proposal-only smoke was subsequently user-verified successfully. Qwen handoff/runtime-boundary commits are awaiting current CI results.

## Stage 16 — Qwen proposal integration IN PROGRESS

Stage 16 begins at the proposal-resolution boundary rather than the execution layer.

Implemented:

- `qwen/production_proposal.py` defines `QwenProductionProposal` as an intent-only envelope containing `workflow`, optional `version`, and `parameters`;
- proposal values are defensively isolated so caller mutation cannot silently alter the semantic request after validation;
- `validate_qwen_production_proposal(...)` rejects malformed proposal shapes and unknown top-level fields before catalog resolution;
- `compile_qwen_production_proposal(...)` resolves the proposal exclusively through the trusted Stage 15 soccer-production catalog and returns one canonical `ProductionTaskDefinition`;
- catalog validation remains responsible for workflow identity, version, required parameters, parameter kinds, vector shape, and finite numeric values;
- Qwen proposal input cannot specify an executor, authorization ID, scheduling instruction, recovery operation, or arbitrary tool invocation;
- `qwen/provider_output.py` is the strict decoded-provider-output adapter and never exposes execution capabilities;
- `qwen/ollama_provider.py` provides the actual local Ollama/Qwen provider boundary at `http://localhost:11434/api/chat` with `qwen3:8b` defaults;
- the provider requests structured output with a schema derived from the trusted live catalog, including exact workflow/version enums and required parameter names/types;
- provider history accepts only `user`/`assistant` turns and cannot inject a system or tool role;
- after parsing, provider output is semantically validated against the trusted catalog before the proposal is released from the provider boundary;
- invalid model values such as empty required strings, missing parameters, unknown workflow names, and combined name/version identifiers fail closed as `QwenProviderError`;
- `scripts/run_live_qwen_production_proposal.py` provides a proposal-only live smoke test and is confirmed by the user to work locally without Blender mutation;
- provider-to-catalog regression coverage proves the proposal path remains canonical and inert;
- `qwen/production_handoff.py` creates an explicit provenance-bound handoff from validated Qwen proposal to canonical semantic and compiled Atlas task definitions;
- handoff integrity checks re-hash proposal, semantic task, and compiled task snapshots and independently recompile the proposal before Atlas authorization;
- the handoff rejects model-supplied authorization fields and contains no executor or recovery API;
- handoff authorization delegates to the existing `TaskPlanProposal` / `instantiate_authorized_plans(...)` / `ActionAuthorization` path;
- `tests/test_qwen_production_handoff.py` covers inert construction, existing-path reuse, model-authorization rejection, no-execution surface, provenance tampering, and fail-closed authorization;
- `scripts/run_live_qwen_production_handoff.py` provides the live Qwen -> semantic task -> explicit Atlas authorization proof, stopping before tool execution;
- `planning/authorized_task_runtime.py` adds a generic bootstrap seam that accepts only an already-issued Atlas `ActionAuthorization`, verifies exact action-plan binding, acquires authoritative initial evidence, evaluates the target, and constructs the existing `AutonomousTaskRuntime` without minting a second receipt;
- the bootstrap fails closed for invalid authorization type, action-plan mismatch, or an already-satisfied target with write authorization;
- `tests/test_authorized_task_runtime.py` covers reuse of the exact pre-issued receipt, exact-plan binding, satisfied-target rejection, and validation before evidence acquisition;
- `scripts/run_live_qwen_production_runtime_boundary.py` provides the next live proof: local Qwen proposal, trusted compilation, existing Atlas authorization, authoritative Blender inspection, and construction of the existing autonomous runtime, stopping before the first ACTION write and explicitly checking the Blender fixture remains unchanged.

### Live Stage 16 proposal-only smoke test — VERIFIED

The user successfully verified the local Qwen proposal-only smoke:

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

### Stage 16 controlled authorization handoff

The live provider result can now be converted into an explicit Atlas authorization through `QwenProductionTaskHandoff`. Atlas, not Qwen, issues the `ActionAuthorization`; authorization is detached from model output and bound to the canonical compiled action plan. Integrity is rechecked before this boundary is crossed.

### Stage 16 existing-runtime boundary

The runtime boundary is now implemented without creating a Qwen-specific runtime. The generic `planning.authorized_task_runtime.start_authorized_task_runtime(...)` function consumes an Atlas-issued authorization receipt and creates the existing `AutonomousTaskRuntime`. Initial Blender evidence is read through the established `BlenderExecutionBoundary`; no write occurs during bootstrap. The live boundary harness verifies the fixture state before and after bootstrap and stops before `ACTION`.

The intended authority flow is now:

```text
Qwen
  ↓
structured proposal
  ↓
provider + trusted catalog validation
  ↓
QwenProductionProposal
  ↓
trusted catalog compilation
  ↓
ProductionTaskDefinition / AtlasTaskDefinition
  ↓
QwenProductionTaskHandoff
  ↓
existing Atlas ActionAuthorization
  ↓
generic pre-authorized runtime bootstrap
  ↓
existing AutonomousTaskRuntime
  ↓
existing Blender execution / verification / recovery
```

There is still no Qwen execution engine, Qwen authorization receipt, parallel scheduler, or alternate recovery path.

### Stage 16 next work

Run and validate `scripts/run_live_qwen_production_runtime_boundary.py` against the local Blender 4.4 installation. A successful proof establishes the complete live boundary through runtime construction while stopping before the first write. After that, the next checkpoint is a real Qwen-authorized Blender mutation using the existing runtime, with fresh independent verification and exact fixture restoration; failure/recovery should then reuse the already-proven recovery machinery rather than adding Qwen-specific recovery logic.

## Unreal

The local Unreal Engine 5.6 production boundary remains proven for the implemented capabilities: deterministic render configuration, render-state verification, Movie Render Queue submission, dynamic job-ID binding, asynchronous inspection, semantic completion verification, MRQ artifact discovery, filesystem validation, and evidence-bound persistent render receipts.

Cross-process Unreal render-job recovery is not implemented.

## Resolution / 4K direction

Atlas is intended to operate on source soccer footage including 4K/UHD. The existing 640x360 Unreal render is a controlled boundary test, not a source-footage maximum. Resolution affects decode, tracking, memory, storage, reconstruction, compositing, and render throughput, but does not change the core Atlas orchestration model.

Use resolution-aware workload/resource handling rather than a separate 4K architecture. Preserve the original high-resolution source as authoritative and use proxies/intermediates where appropriate without weakening provenance or evidence.

## Non-regression rules

- Never give Qwen direct production execution authority.
- Never allow model-supplied authorization IDs or receipts to become Atlas authority.
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

**Continue Stage 16 by live-validating `scripts/run_live_qwen_production_runtime_boundary.py`. The proof must stop after construction of the existing Atlas autonomous runtime and demonstrate that Qwen's proposal and Atlas authorization have crossed the boundary without any Blender write. Once verified, perform the first Qwen-authorized Blender mutation through the existing runtime, then independently verify and restore the fixture.**
