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

Atlas has now proven the core task-aware autonomous recovery loop against the real Blender 4.4 environment, including multi-step cross-process recovery after a durable later-action failure. The Unreal production/render boundary remains proven locally for the currently implemented capabilities.

The latest verified Blender sequence is:

```text
inspect authoritative state
        ↓
evaluate target
        ↓
issue immutable action authorization
        ↓
ACTION 1: real Blender mutation
        ↓
checkpoint partial progress
        ↓
ACTION 2: controlled failure
        ↓
BLOCKED durable checkpoint
        ↓
Python process restart
        ↓
reconstruct runtime + recovery gate + authorization
        ↓
acquire fresh multi-source evidence
        ↓
issue evidence-bound replan authorization
        ↓
execute only unfinished replacement action
        ↓
fresh independent verification
        ↓
COMPLETE / restore fixture
```

This proves that failed writes are not automatically retried, completed prior work is not blindly replayed, and recovery proceeds only from durable state, fresh evidence, and a separately bound replacement authorization.

## Latest regression / CI checkpoint

The exact Stage 13 branch head `361b97e685f815e54c22fcd65c29968a783ff73f` passed the GitHub Actions `Atlas Tests` workflow successfully (run `#1251`).

The development branch is:

`feat/blender-stage11-mainline`

The active PR is #49 and remains **open, draft, and unmerged**.

---

# Blender Agent status

The generic Atlas architecture remains centered on explicit intent, capability/schema validation, authorization, execution, independent verification, evidence, recovery, and replanning.

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

## Verified Blender Stage 12 capabilities

The task-aware autonomous runtime binds declarative `AtlasTaskDefinition` contracts to the existing checkpointed autonomous future runtime without introducing a second executor, authorization system, or engine-specific future controller.

Verified behaviors include:

- already-satisfied task → zero writes;
- unsatisfied task → deterministic authorized action sequence;
- successful action → fresh verification remains mandatory;
- failed action → durable `BLOCKED` checkpoint;
- fresh recovery evidence → required before recovery/replan;
- recovery replacement → explicit `ReplanAuthorization` bound to fresh evidence and replacement actions;
- replacement execution → a new task action authorization is created when writes remain necessary;
- continuation integrity → altered runtime identity is rejected rather than repaired implicitly;
- cross-process continuation after successful action → recovered authorization and fresh verification;
- cross-process recovery after failed action → reconstructed blocked gate, recovered authorization, fresh evidence, explicit replan, replacement execution, and fresh final verification.

## Verified Blender Stage 13 — multi-step partial-progress recovery

The first multi-step live proof uses `Goal_Left_post` and two ordered writes: move the object, then set its rotation.

Phase 1 completed the first mutation, intentionally failed the second action before its Blender write, and persisted the partial-progress checkpoint.

Phase 2 started as a fresh Python process, recovered the durable blocked state, acquired fresh evidence from multiple requests, issued a new replan authorization, executed only the unfinished second action, independently verified both target properties, and restored the fixture.

Observed live proof:

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

This is the completed Stage 13 proof. The critical property is explicit: **action 1 was not replayed after action 2 failed.**

---

# Unreal Agent status

Unreal production transport and rendering are proven locally for the current implemented capabilities.

The controlled render workflow supports:

- deterministic render configuration;
- render-state verification;
- Movie Render Queue submission;
- dynamic job-ID binding from submission evidence;
- asynchronous render-job inspection;
- completed-job semantic verification;
- actual output-artifact discovery from MRQ;
- filesystem existence and non-zero-size validation;
- evidence-bound deterministic `UnrealRenderReceipt` creation;
- atomic `UnrealRenderReceiptStore` persistence with fail-closed reload validation.

A controlled local render was previously proven at:

```text
resolution:       640x360
frame range:      1–2
output format:    PNG
output directory: Saved/AtlasRenderOutput
```

This 640x360 proof demonstrates the render boundary, not an imposed maximum source-footage resolution. Atlas's orchestration model is resolution-independent; 4K/UHD production will require appropriate decode, tracking, memory, storage, and render-throughput handling at the execution-environment level.

The Unreal runtime job registry remains in-memory. Durable render-receipt persistence is an Atlas/Python concern; cross-process Unreal render-job recovery has **not** been implemented.

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

### Stage 13 — Multi-step autonomous task execution
**COMPLETE FOR CURRENT CONTRACT**

Stage 13 proves multi-request evidence retention, deterministic ordered action execution, durable partial-progress checkpoints, cross-process reconstruction, recovery from actual observed partial state, non-replay of completed work, explicit replacement authorization, and mandatory fresh verification.

### Stage 14 — Dependency-aware task composition
**NEXT**

Stage 14 should make action prerequisites explicit rather than relying only on list position. The first implementation should remain deterministic and serial; parallel execution is not yet part of the scope.

### Stage 15 — Higher-level production tasks spanning multiple Blender operations
**PLANNED**

### Stage 16 — Qwen proposal integration into validated Atlas task planning
**PLANNED**

### Stage 17 — Shared autonomous production architecture across Blender and Unreal
**PLANNED**

---

# 4K / UHD footage support

Atlas should treat **4K/UHD as a normal supported production input**, not as a special architectural branch.

The important distinction is between **Atlas orchestration** and **execution workload**. Atlas's evidence, authorization, planning, checkpointing, recovery, and verification layers are fundamentally resolution-independent. The heavy work associated with 4K comes from the underlying media-processing and production tools: decoding high-resolution frames, tracking/reconstruction, photogrammetry, Blender processing, compositing, and Unreal rendering.

The intended pipeline remains:

```text
4K soccer footage
        ↓
photogrammetry / reconstruction as required
        ↓
Blender analysis + cleanup + correction
        ↓
canonical Digital Twin / prepared assets
        ↓
Unreal production + compositing / VFX
        ↓
4K deliverable
```

Atlas therefore does not need a separate “4K mode” in its core authority architecture. It does need execution-environment adapters and workload policies that can account for source resolution, frame count, codec, bit depth, memory pressure, GPU/CPU availability, temporary storage, proxy generation, and final-output requirements.

A future workload-planning stage should allow Atlas to choose when to use full-resolution frames versus proxies or intermediate representations while preserving authoritative source references and final-resolution verification.

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
- multi-request task evidence → retained as deterministic evidence bundle;
- task target decision → deterministic future binding;
- persisted task metadata → future consistency;
- action authorization → exact task action binding;
- cross-process continuation → recovered authorization and fresh verification;
- cross-process blocked recovery → recovered gate + authorization before replan;
- dependency graph → unknown references rejected;
- dependency graph → cycles rejected;
- dependency-aware authorization → exact plan binding;
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

## Resume point

For the next session, read `ATLAS_HANDOFF_CURRENT.md` and the relevant Unreal handoff, inspect the current branch/HEAD and newest regression result, and then begin **Stage 14 — dependency-aware task composition**.

Do not expand Qwen autonomy yet. First prove that explicit action prerequisites can be validated, authorized, checkpointed, and recovered without introducing a second execution or authorization system or changing the fail-closed control model.

Do not claim cross-process Unreal render-job recovery unless it is separately implemented and verified.
