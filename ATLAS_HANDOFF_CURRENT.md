# Atlas Current Development Handoff

**Updated:** September 3, 2026 — Stage 15 complete for current contract; Stage 16 Qwen provider integration and controlled Atlas authorization handoff implemented
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

GitHub Actions `Atlas Tests` run **#1370** passed for the Stage 15 recovery-harness stabilization commit `a8d81196b3bccc1c674d6038ff6fee115b24d8ec`. Stage 16 provider tests passed run **#1383** for commit `bcbf3c76be2b4737783233b681f0b7f47113318d`. Run **#1382** failed for an intermediate provider revision and was superseded. Run **#1384** passed for the subsequent provider-to-catalog revision. Run **#1394** exposed three stale provider-test expectations while the live smoke test also exposed model-generated invalid parameter values; both classes of issues have since been corrected. The Qwen proposal-only live smoke was subsequently user-verified successfully. The latest authorization-handoff commits are now awaiting their own CI results.

The Stage 15 live recovery itself was user-verified against Blender 4.4.

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
- the provider system prompt enumerates the exact canonical workflow contract and explicitly requires every required parameter to be populated from the supplied objective or verified context;
- provider history accepts only `user`/`assistant` turns and cannot inject a system or tool role;
- after parsing, provider output is semantically validated against the trusted catalog before the proposal is released from the provider boundary;
- invalid model values such as empty required strings, missing parameters, unknown workflow names, and combined name/version identifiers fail closed as `QwenProviderError`;
- `scripts/run_live_qwen_production_proposal.py` provides a proposal-only live smoke test using an explicit, deterministic soccer-production objective and verified parameter context, and it stops before authorization, persistence, execution, recovery, or Blender mutation;
- provider-to-catalog regression coverage proves the complete offline handoff remains inert and canonical;
- `qwen/production_handoff.py` introduces one explicit handoff record containing the validated Qwen proposal, canonical `ProductionTaskDefinition`, compiled `AtlasTaskDefinition`, and integrity digests;
- the handoff re-verifies proposal, semantic-task, compiled-task, and canonical-recompilation equivalence before authorization, so tampered catalog/semantic provenance fails closed;
- the handoff creates a standard `TaskPlanProposal` and delegates authorization to the existing `planning.task_planner.instantiate_authorized_plans(...)` path, which issues the existing `ActionAuthorization` receipt;
- the handoff contains no executor, scheduler, recovery, or alternate authorization mechanism and remains inert until its explicit `authorize(...)` method is called;
- `scripts/run_live_qwen_production_handoff.py` provides a live Qwen -> validated proposal -> semantic task -> explicit Atlas authorization proof and deliberately stops before any tool execution or Blender mutation;
- `tests/test_qwen_production_handoff.py` covers inert construction, reuse of the existing authorization path, rejection of model-supplied authorization data, absence of execution APIs, provenance tampering, and fail-closed authorization.

### Live smoke failures and corrections

The first user-run live smoke test returned `soccer_goal_broadcast`, which the catalog correctly rejected as an unknown workflow. Atlas did not add an alias. The provider was strengthened to enumerate the canonical catalog and reject invented identifiers.

The next live run returned `broadcast-goal-preparation@1`. That represented a model interpretation of the displayed identity, not a valid Atlas field value. Atlas retains separate `workflow` and `version` fields and explicitly instructs the model never to combine them.

The following live run reached semantic parameter validation but returned an empty `file_name`. Atlas correctly rejected that output. The provider is now stricter: the Ollama structured-output schema requires every catalog parameter and semantic catalog validation executes before a proposal leaves the provider boundary. The smoke test also supplies concrete verified values for the current workflow so the live proof tests model-to-contract translation rather than asking the model to invent operational inputs.

The correct Stage 16 flow is now:

```text
Qwen
  ↓
reason about soccer-production objective
  ↓
Ollama structured-output provider
  ↓
provider-owned canonical catalog/schema
  ↓
strict provider-output parser
  ↓
Atlas catalog semantic validation
  ↓
QwenProductionProposal
  ↓
trusted catalog compilation
  ↓
ProductionTaskDefinition
  ↓
QwenProductionTaskHandoff
  ↓
existing Atlas TaskPlanProposal / ActionAuthorization path
  ↓
existing Atlas runtime / verification / recovery
```

Ollama's chat API supports supplying a JSON schema through the `format` field for structured output. Atlas uses that to shape provider output, but it remains untrusted input and is independently checked against the canonical catalog before any execution path is reachable.

### Live Stage 16 proposal-only smoke test — VERIFIED

From the Atlas repository on the local Windows machine:

```powershell
cd "C:\Users\Gavin's PC\Desktop\Atlas"
git pull
python -m scripts.run_live_qwen_production_proposal
```

The user successfully verified:

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

This is a real local Qwen provider milestone: model communication, structured proposal extraction, semantic validation, exact catalog resolution, and canonical semantic task construction are live-verified while Blender remains untouched.

### Stage 16 controlled authorization handoff

The next boundary is implemented and intentionally separate from Qwen itself. `QwenProductionTaskHandoff.from_proposal(...)` accepts only a validated proposal shape, compiles it through the trusted catalog, and binds detached proposal/task snapshots to integrity digests. `verify_integrity()` independently recompiles the proposal and compares the semantic and compiled snapshots before crossing into the authorization boundary.

`QwenProductionTaskHandoff.authorize(...)` then delegates to the existing Atlas `TaskPlanProposal` / `instantiate_authorized_plans(...)` path. The resulting `ActionAuthorization` is issued by Atlas from the compiled action list; Qwen does not construct, provide, or control that authorization receipt.

This boundary does not execute tools. It establishes that a live Qwen proposal can be transformed into a canonical Atlas task and then explicitly authorized by Atlas without giving the model execution authority.

### Live Stage 16 authorization handoff proof

From the Atlas repository on the local Windows machine:

```powershell
cd "C:\Users\Gavin's PC\Desktop\Atlas"
git pull
python -m scripts.run_live_qwen_production_handoff
```

A successful proof must show `proposal_validation=verified`, `handoff_integrity=verified`, `catalog_provenance=verified`, `atlas_authorization_path=existing`, an Atlas-issued `authorization_id`/digest, `action_plan_authorized=True`, and `execution=not_attempted` / `blender_mutation=not_attempted`.

### Stage 16 next work

After the live authorization handoff is verified, the next meaningful checkpoint is to feed that explicitly authorized canonical task into the **existing Atlas runtime** while preserving the same authority model: Qwen proposes, Atlas validates/authorizes, and the existing runtime executes and verifies. The live proof should initially exercise the existing runtime boundary with the controlled soccer-goal fixture and retain independent final verification; no new Qwen executor or Qwen-owned runtime is permitted.

Do not expand Qwen autonomy beyond proposal generation, proposal parsing, validated catalog resolution, and handoff into Atlas's existing authority path until this runtime-boundary proof is complete.

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

**Continue Stage 16 by live-validating `QwenProductionTaskHandoff` with the local Ollama/Qwen provider using `scripts/run_live_qwen_production_handoff.py`. The proof must stop after explicit Atlas authorization: no tool execution and no Blender mutation. Once that is verified, integrate the authorized canonical task with the existing Atlas runtime as the next controlled boundary.**
