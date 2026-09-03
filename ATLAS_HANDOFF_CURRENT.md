# Atlas Current Development Handoff

**Updated:** September 3, 2026 — Stage 15 complete for current contract; Stage 16 proposal-only Qwen provider integration implemented
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

GitHub Actions `Atlas Tests` run **#1370** passed for the Stage 15 recovery-harness stabilization commit `a8d81196b3bccc1c674d6038ff6fee115b24d8ec`. Stage 16 provider tests subsequently passed run **#1383** for commit `bcbf3c76be2b4737783233b681f0b7f47113318d`; run **#1382** failed for an intermediate provider revision and was superseded by #1383. Run **#1384** is the current validation run for the latest provider-to-catalog test revision.

The Stage 15 live recovery itself was user-verified against Blender 4.4.

## Stage 16 — Qwen proposal integration IN PROGRESS

Stage 16 now begins at the proposal-resolution boundary rather than the execution layer.

Implemented:

- `qwen/production_proposal.py` defines `QwenProductionProposal` as an intent-only envelope containing `workflow`, optional `version`, and `parameters`;
- proposal values are defensively copied so caller mutation cannot silently alter the semantic request after validation;
- `validate_qwen_production_proposal(...)` rejects malformed proposal shapes and unknown top-level fields before catalog resolution;
- `compile_qwen_production_proposal(...)` resolves the proposal exclusively through the trusted Stage 15 soccer-production catalog and returns one canonical `ProductionTaskDefinition`;
- catalog validation remains responsible for workflow identity, version, required parameters, parameter kinds, vector shape, and finite numeric values;
- Qwen proposal input cannot specify an executor, authorization ID, scheduling instruction, recovery operation, or arbitrary tool invocation;
- regression coverage proves malformed Qwen envelopes, unknown workflows, bad parameter kinds, attempted execution fields, malformed JSON, invalid UTF-8, and detached proposal snapshots are rejected or safely isolated;
- `qwen/provider_output.py` is the strict decoded-provider-output adapter and never exposes execution capabilities;
- `qwen/ollama_provider.py` now provides the actual local Ollama/Qwen provider boundary at `http://localhost:11434/api/chat` with `qwen3:8b` defaults;
- the Ollama boundary requests a structured response using `PRODUCTION_PROPOSAL_JSON_SCHEMA`, disables streaming, uses deterministic temperature `0`, and sends no Atlas tools to the model;
- provider history accepts only `user`/`assistant` messages and cannot replace or inject a system message, so the Atlas proposal-only system contract remains provider-owned;
- provider responses are accepted only after strict proposal parsing; malformed provider responses and transport failures become `QwenProviderError`;
- `scripts/run_live_qwen_production_proposal.py` provides a live local smoke test that contacts Qwen, validates the proposal, resolves the trusted catalog, and compiles a semantic task while explicitly stopping before authorization, persistence, execution, recovery, or Blender mutation;
- provider-to-catalog regression coverage proves the complete offline handoff remains inert and canonical.

The intended Stage 16 flow is:

```text
Qwen
  ↓
reason about soccer-production objective
  ↓
Ollama structured-output provider
  ↓
strict provider-output parser
  ↓
QwenProductionProposal
  ↓
Atlas validates proposal envelope
  ↓
Atlas resolves trusted catalog contract
  ↓
Atlas constructs one ProductionTaskDefinition
  ↓
existing Atlas authorization/runtime/verification/recovery
```

Ollama's current API supports passing a JSON schema in the chat `format` field and returning a non-streaming response, which is the mechanism used by the provider boundary. This constrains model output shape but does not make the model trusted; Atlas catalog validation remains the authority boundary. urlOllama API documentationhttps://docs.ollama.com/api/chat

### Live Stage 16 smoke test

From the Atlas repository on the local Windows machine:

```powershell
cd "C:\Users\Gavin's PC\Desktop\Atlas"
git pull
python -m scripts.run_live_qwen_production_proposal
```

This test is intentionally proposal-only. A successful result proves live model/provider communication, structured proposal extraction, Atlas proposal validation, catalog resolution, and semantic task construction. It must not perform a Blender write.

### Stage 16 next work

The next meaningful proof is a live local Qwen proposal against the real installed `qwen3:8b` endpoint using the new smoke harness. After that, Stage 16 can extend the proposal contract to multiple trusted soccer-production workflows while preserving the same catalog authority and execution boundary.

Do not expand Qwen autonomy beyond proposal generation and proposal parsing at this point.

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

**Continue Stage 16 by running and validating the live local Qwen proposal-only smoke test. Preserve the rule that model output is untrusted and inert until Atlas validates it against the Stage 15 catalog; no Qwen execution or authorization autonomy yet.**
