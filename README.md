# Atlas

## What Atlas is

Atlas is an **AI-assisted sports virtual production and digital-twin platform** designed to turn captured soccer footage and soccer-field-related real-world environments into richer, controllable production experiences.

Blender and Unreal Engine are execution environments around Atlas's canonical Digital Twin. Dedicated photogrammetry software is an upstream reconstruction stage.

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
            Prepared digital twin
                    ↓
               Unreal Agent
          real-time production / VFX
```

Photogrammetry is an upstream reconstruction capability, not a Blender responsibility.

Atlas is designed to operate on source footage across production resolutions, including **4K/UHD footage**. Resolution affects processing cost, memory, storage, and render throughput; it does not change the core Atlas orchestration model.

## Core control principle

```text
Qwen / AI
  → understand, reason, propose

Python / Atlas
  → validate, authorize, execute, track state, verify, recover

Blender / Unreal
  → controlled production execution

Independent verification
  → establish what actually happened
```

Qwen never receives direct production execution authority.

---

# Current Atlas status — September 3, 2026

Stage 13 multi-step autonomous partial-progress recovery is now fully live-verified against Blender 4.4 and passed GitHub Actions. Stage 14 dependency-aware task composition is in progress.

The Stage 13 proof established:

```text
ACTION 1 succeeds
      ↓
checkpoint
      ↓
ACTION 2 fails
      ↓
BLOCKED durable checkpoint
      ↓
Python process restart
      ↓
fresh multi-source evidence
      ↓
explicit replan authorization
      ↓
execute only unfinished action
      ↓
fresh independent verification
      ↓
fixture restored
```

This proved that completed work is not blindly replayed during recovery.

## Latest regression / CI checkpoint

The exact Stage 13 branch head `361b97e685f815e54c22fcd65c29968a783ff73f` passed the GitHub Actions `Atlas Tests` workflow successfully (run `#1251`). A newer Stage 14 dependency-validation series is now running on the same development branch.

The development branch is:

`feat/blender-stage11-mainline`

The active PR is #49 and remains **open, draft, and unmerged**.

---

# Blender Agent status

The generic Atlas architecture is centered on explicit intent, capability/schema validation, authorization, execution, independent verification, evidence, recovery, and replanning.

```text
Qwen reasoning
      ↓
structured task intent
      ↓
capability/schema validation
      ↓
authorized plan
      ↓
controlled execution boundary
      ↓
independent verification
      ↓
immutable evidence / receipt
      ↓
reassessment / recovery / replan
```

## Verified Blender capabilities

Task-aware autonomous execution binds declarative `AtlasTaskDefinition` contracts to the existing checkpointed autonomous future runtime without introducing a second executor, authorization system, or engine-specific future controller.

Verified behaviors include:

- already-satisfied task → zero writes;
- unsatisfied task → deterministic authorized action sequence;
- successful action → fresh verification remains mandatory;
- failed action → durable `BLOCKED` checkpoint;
- fresh recovery evidence → required before recovery/replan;
- replacement recovery → explicit `ReplanAuthorization` bound to fresh evidence and replacement actions;
- continuation integrity → altered runtime identity is rejected rather than repaired implicitly;
- cross-process continuation → authorization and fresh verification are recovered;
- cross-process blocked recovery → the blocked gate, fresh evidence, replan authorization, replacement execution, and final verification are reconstructed explicitly;
- multi-request task evidence → preserved as a deterministic evidence bundle;
- multi-step partial-progress recovery → completed earlier actions are not blindly replayed.

## Stage 14 — dependency-aware task composition

Stage 14 extends the proven linear action model with explicit prerequisites while keeping execution serial and deterministic.

Implemented foundation:

- `ActionSpec.depends_on` declares prerequisite action names;
- dependency metadata is carried into deterministic future steps and action-plan state;
- `ActionAuthorization` includes dependency declarations in its plan digest;
- `planning/action_dependencies.py` validates dependency references and ordering;
- `AtlasTaskDefinition`, `PlanningOrchestrator`, and `AutonomousTaskRuntime` preserve dependency information through reconstruction;
- regression tests cover valid dependencies and invalid references/order/self/duplicate dependency declarations.

The current rule is deliberate:

```text
explicit dependencies
        ↓
validated serial order
        ↓
authorized future
        ↓
one deterministic next action
```

Atlas is **not** scheduling independent branches in parallel yet. That decision remains deferred until dependency semantics, checkpointing, recovery, and evidence handling are proven safe.

## Live Stage 13 proof

The real Blender 4.4 multi-step harness used `Goal_Left_post` with a location mutation followed by a rotation mutation.

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

---

# Unreal Agent status

Unreal production transport and rendering are proven locally for the current implemented capabilities:

- deterministic render configuration;
- render-state verification;
- Movie Render Queue submission;
- dynamic job-ID binding;
- asynchronous render-job inspection;
- semantic completion verification;
- MRQ artifact discovery;
- filesystem existence and non-zero-size validation;
- evidence-bound persistent `UnrealRenderReceipt` creation.

A controlled local render was previously proven at 640x360, frames 1–2, PNG output. This is a boundary test, not a source-footage resolution limit.

Atlas's orchestration model is resolution-independent. 4K/UHD workflows will require appropriate decode, tracking, memory, storage, reconstruction, compositing, and render-throughput handling at the execution-environment level.

Cross-process Unreal render-job recovery has **not** been implemented.

---

# Development roadmap

## Blender

### Stage 1 — Basic Blender Agent
**COMPLETE**

### Stage 2 — Reliable Evidence
**COMPLETE**

### Stage 3 — Mandatory Evidence Acquisition
**COMPLETE**

### Stage 4 — Evidence Validation and Recommendation Restraint
**COMPLETE**

### Stage 5 — General Evidence Planner
**COMPLETE**

### Stage 6 — Reliable Modification Control
**COMPLETE**

### Stage 7 — General Action Planning
**COMPLETE**

### Stage 8 — Conditional Action Planning
**COMPLETE**

### Stage 9 — Qwen/Atlas Agent Reasoning Boundary
**COMPLETE FOR CURRENT CONTRACT**

### Stage 10 — Blender Adapter / Real Execution Bridge
**COMPLETE FOR CURRENT IMPLEMENTED BOUNDARY**

### Stage 11 — First Controlled Live Blender Operation
**COMPLETE**

### Stage 12 — Task-aware closed-loop autonomous Blender execution and recovery
**COMPLETE FOR CURRENT CONTRACT**

### Stage 13 — Multi-step autonomous task execution and partial-progress recovery
**COMPLETE FOR CURRENT CONTRACT**

### Stage 14 — Dependency-aware task composition
**IN PROGRESS**

### Stage 15 — Higher-level production tasks spanning multiple Blender operations
**PLANNED**

### Stage 16 — Qwen proposal integration into validated Atlas task planning
**PLANNED**

### Stage 17 — Shared autonomous production architecture across Blender and Unreal
**PLANNED**

---

# Digital Twin direction

Atlas owns the canonical Digital Twin. Blender, Unreal, photogrammetry software, and future tools are adapters/executors around that canonical model.

A `.blend` file, Unreal project, level, render configuration, or other DCC artifact is a representation/production state, not the canonical identity of the environment. Identity, provenance, revisions, production variants, and shot-specific changes remain explicit.

Photogrammetry creates the initial reconstruction. Blender analyzes, cleans, corrects, optimizes, and prepares it for downstream production.

Atlas remains exclusively focused on soccer-field-related digital twins and their production pipeline.

---

# Production repertoire

The wider Atlas production system may include impact frames, smear frames, chromatic aberration, cinematic bleed, match-cut transformations, spatial overlays, digital-twin compositing, and environment-driven effects including temporary liquid, smoke, glass, metallic, or other fluid-like behavior.

These are production modules, not the definition of Atlas.

---

# Required regression philosophy

Preserve coverage for:

- already-satisfied state → zero writes;
- unsatisfied state → exact authorized action order;
- successful write → verification remains mandatory;
- verification failure → `BLOCKED`;
- action failure → durable `BLOCKED` checkpoint;
- fresh recovery evidence → required before recovery/replan;
- replacement plan → explicit replan authorization required;
- replacement action tools → remain within the task contract;
- partial-progress recovery → completed prior steps are not blindly replayed;
- multi-request task evidence → retained as a deterministic evidence bundle;
- dependency graph → unknown references rejected;
- dependency graph → later/self/duplicate dependencies rejected;
- dependency-aware authorization → exact plan binding;
- deterministic continuation → exact checkpoint position preserved;
- cross-process continuation → recovered authorization and fresh verification;
- cross-process blocked recovery → recovered gate + authorization before replan;
- mutated arguments/result → receipt mismatch;
- malformed executor result → rejected;
- wrong result tool → rejected;
- invalid continuation identity → rejected;
- authorized fresh-evidence replan → accepted;
- unauthorized replan → rejected;
- malformed Qwen reasoning → rejected;
- unknown/non-capability tool → rejected;
- Blender write without independent persistence evidence → incomplete;
- Blender expected/observed persistence mismatch → rejected;
- render job completion without artifacts → rejected;
- declared render artifacts that do not exist → rejected;
- tampered persisted render receipt → rejected.

# Development rules

- Preserve the evidence ledger and independent verification.
- Do not make goalpost behavior the generic architecture.
- Do not add tools without proving a capability gap.
- Do not allow a production-tool success response alone to establish completion.
- Do not allow action plans to execute without explicit authorization.
- Do not allow Qwen to bypass Python-owned execution state.
- Do not allow automatic retry after failed writes.
- Never silently rewrite an authorized plan.
- Keep Blender/Unreal-specific behavior behind adapter/tool boundaries.
- Treat photogrammetry as an upstream reconstruction capability.
- Preserve provenance and canonical Digital Twin identity.
- Test every meaningful increment.
- Keep project handoffs synchronized with verified milestones.
- Keep dependency-aware execution serial until concurrency is independently justified.

## Resume point

Complete **Stage 14 — dependency-aware task composition**.

First obtain a green CI result for the current dependency foundation. Then create the smallest soccer-field-related Blender task with explicit prerequisites and prove dependency metadata survives authorization, deterministic future generation, checkpointing, and cross-process reconstruction. Only after that should Atlas evaluate safe scheduling of independent branches.

Do not expand Qwen autonomy yet.

Do not claim cross-process Unreal render-job recovery unless it is separately implemented and verified.
