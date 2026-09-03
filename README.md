# Atlas

## What Atlas is

Atlas is an **AI-assisted sports virtual production and digital-twin platform** focused exclusively on soccer-field-related digital twins and production workflows.

Dedicated photogrammetry software is the upstream reconstruction stage. Blender analyzes, cleans, corrects, optimizes, and prepares the reconstruction. Unreal is a downstream controlled production environment around the canonical Atlas Digital Twin.

```text
Real-world soccer environment / captured soccer footage
                    ↓
          Dedicated photogrammetry
                    ↓
           Initial 3D reconstruction
                    ↓
               Blender Agent
        analyze / clean / correct / optimize
                    ↓
             Atlas Digital Twin
                    ↓
               Unreal Agent
          real-time production / VFX
```

Atlas is designed for source footage including 4K/UHD. Higher resolution changes processing, memory, storage, reconstruction, compositing, and render throughput requirements, not the core orchestration model.

## Authority model

```text
Qwen / AI
  → reason and propose structured production intent

Python / Atlas
  → validate, resolve, authorize, execute, track, verify, recover

Blender / Unreal
  → controlled production execution

Independent verification
  → establish what actually happened
```

Qwen is never the execution or authorization authority.

---

# Current position — September 3, 2026

**Active branch:** `feat/blender-stage11-mainline`  
**PR #49:** open, draft, unmerged  
**Current development stage:** **Stage 16 — Qwen proposal integration, IN PROGRESS**

Stage 13 multi-step partial-progress recovery is live-verified against Blender 4.4 and passed GitHub Actions. Stage 14 dependency-aware serial execution and cross-process recovery are implemented and live-verified. Stage 15 semantic soccer-production workflows and versioned catalog compilation are complete for the current contract.

Stage 16 now has a live-proven Qwen proposal boundary and an implemented Atlas-owned authorization/runtime handoff. The full Qwen-authorized Blender mutation path has been implemented as a live harness but has **not yet been user-verified**.

## Stage 16 current flow

```text
Qwen
  ↓
Ollama structured proposal
  ↓
strict provider-output validation
  ↓
trusted soccer-production catalog
  ↓
QwenProductionProposal
  ↓
ProductionTaskDefinition
  ↓
AtlasTaskDefinition
  ↓
QwenProductionTaskHandoff
  ↓
existing Atlas ActionAuthorization
  ↓
existing AutonomousTaskRuntime
  ↓
Blender execution boundary
  ↓
fresh independent verification
```

Implemented Stage 16 components include:

- `qwen/production_proposal.py` — intent-only model proposal envelope;
- `qwen/provider_output.py` — strict provider-output adapter;
- `qwen/ollama_provider.py` — local Ollama/Qwen provider boundary with catalog-bound structured output;
- `qwen/production_handoff.py` — provenance-bound proposal-to-Atlas handoff;
- `planning/authorized_task_runtime.py` — generic bootstrap for an already-issued Atlas authorization;
- `scripts/run_live_qwen_production_proposal.py` — proposal-only live smoke test;
- `scripts/run_live_qwen_production_handoff.py` — proposal-to-explicit-authorization proof;
- `scripts/run_live_qwen_production_runtime_boundary.py` — no-write runtime-boundary proof;
- `scripts/run_live_qwen_production_runtime.py` — first complete Qwen-authorized Blender mutation harness.

The provider and handoff boundaries reject model-supplied executors, authorization IDs, arbitrary tools, combined workflow/version identifiers, malformed parameters, and provenance drift. The handoff re-checks proposal/task integrity and delegates authorization to the established Atlas authorization mechanism rather than creating a second one.

## Live Qwen milestone — VERIFIED

The user successfully ran the proposal-only local Qwen smoke test:

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

This proves live Qwen communication, structured proposal extraction, catalog validation, and semantic task compilation. It deliberately performed no Blender mutation.

## Next verification checkpoint

Run from the Atlas repository:

```powershell
cd "C:\Users\Gavin's PC\Desktop\Atlas"
git pull
python -m scripts.run_live_qwen_production_runtime_boundary --blender "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
python -m scripts.run_live_qwen_production_runtime --blender "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
```

The boundary harness must prove that Qwen intent reaches Atlas authorization and the existing runtime without executing a write before the action phase. The full harness must prove real Blender mutation, independent final verification, and exact fixture restoration.

After that proof, extend the same boundary into the already-proven failure/recovery machinery. Recovery must remain Atlas-owned, explicitly authorized, fresh-evidence-driven, independently verified, and free of automatic write retries.

---

# Earlier proven architecture

### Stage 12 — task-aware autonomous execution and recovery
**COMPLETE FOR CURRENT CONTRACT**

### Stage 13 — multi-step partial-progress recovery
**COMPLETE FOR CURRENT CONTRACT**

### Stage 14 — dependency-aware task composition
**COMPLETE FOR CURRENT CONTRACT**

Explicit dependencies are validated, included in authorization/integrity digests, persisted through continuation, and recovered using checkpoint-derived completed prerequisites. Execution remains serial; parallel scheduling has not been introduced.

### Stage 15 — semantic soccer-production tasks
**COMPLETE FOR CURRENT CONTRACT**

`ProductionTaskDefinition`, reusable production fragments, target-state evaluation, soccer-production templates, and the versioned catalog are established. Current catalog workflow:

```text
broadcast-goal-preparation@1

file_name       -> string
object_name     -> string
target_location -> vector3
target_rotation -> vector3
```

---

# Unreal Agent status

The Unreal Engine 5.6 boundary is proven locally for the implemented render workflow:

- deterministic render configuration and verification;
- Movie Render Queue submission;
- dynamic job-ID binding;
- asynchronous render-job inspection;
- semantic completion verification;
- output artifact discovery;
- filesystem existence and non-zero-size validation;
- evidence-bound `UnrealRenderReceipt` creation;
- durable receipt persistence with fail-closed reload validation.

Controlled proof was 640x360, frames 1–2, PNG. This is a boundary test, not a source-footage resolution limit.

**Cross-process Unreal render-job recovery is not implemented.** Receipt persistence must not be described as job persistence.

---

# Digital Twin and production direction

Atlas owns the canonical Digital Twin. `.blend` files, Unreal projects, levels, render jobs, receipts, and output artifacts are production representations/state, not canonical identity.

The wider production repertoire may include impact frames, smear frames, chromatic aberration, cinematic bleed, match-cut transformations, spatial overlays, digital-twin compositing, and temporary liquid/smoke/glass/metallic environment effects.

These are production modules, not the definition of Atlas.

---

# Non-regression rules

- Qwen never receives direct execution or authorization authority.
- Model output remains untrusted until Atlas validates it.
- Never allow model-supplied authorization IDs or receipts to become Atlas authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from a transport/write response alone.
- Preserve independent verification and the evidence ledger.
- Keep engine-specific behavior behind adapter/tool boundaries.
- Preserve canonical Digital Twin identity separately from production artifacts.
- Do not introduce parallel execution until dependency semantics justify it independently.
- Do not claim cross-process Unreal job recovery unless implemented and verified.

## PR status

PR #49 remains open, draft, and unmerged. **Do not merge unless explicitly requested.**

## Resume point

**Stage 16:** execute the two Qwen runtime proofs above. If the full mutation proof succeeds, continue by integrating Qwen-driven proposals into the existing Atlas failure/recovery path without creating a second execution, authorization, or recovery system.