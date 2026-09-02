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

# Current Atlas status — September 2, 2026

Atlas has now proven the core task-aware autonomous recovery loop against the real Blender 4.4 environment, including cross-process recovery after a durable action failure. The Unreal production/render boundary remains proven locally for the currently implemented capabilities.

The latest verified Blender sequence is:

```text
inspect authoritative state
        ↓
evaluate target
        ↓
issue immutable action authorization
        ↓
execute deterministic future
        ↓
controlled action failure
        ↓
BLOCKED durable checkpoint
        ↓
Python process restart
        ↓
reconstruct runtime + recovery gate + authorization
        ↓
acquire fresh authoritative evidence
        ↓
issue evidence-bound replan authorization
        ↓
execute replacement action
        ↓
fresh independent verification
        ↓
COMPLETE / restore fixture
```

This proves that failed writes are not automatically retried and that recovery proceeds only from durable state, fresh evidence, and a separately bound replacement authorization.

## Latest local regression / CI checkpoint

The corrected Stage 12 recovery implementation has passed the GitHub Actions offline test matrix on Python 3.9 and Python 3.11.

The development branch is:

`feat/blender-stage11-mainline`

The active PR is #49 and remains draft/unmerged.

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

The task-aware autonomous runtime now binds declarative `AtlasTaskDefinition` contracts to the existing checkpointed autonomous future runtime without introducing a second executor, authorization system, or engine-specific future controller.

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

### Live Blender recovery proof

The real Blender 4.4 environment has now successfully completed the cross-process failure/recovery harness:

```text
LIVE AUTONOMOUS RECOVERY RESTART VERIFIED
object=Goal_Left_post
original=[0.0, 0.0, 0.0]
recovered=[0.0, 0.0, 15.0]
initial_authorization=atlas-stage12-autonomous-recovery-restart-initial
replan_authorization=atlas-stage12-autonomous-recovery-restart-replan
durable_failure_checkpoint=verified
process_restart=verified
authorization_recovered=verified
fresh_recovery_evidence=verified
replan_authorization=verified
replacement_execution=verified
fresh_final_verification=verified
fixture_restored=[0.0, 0.0, 0.0]
```

The harness uses two separate Python processes. Phase 1 intentionally fails the first write before Blender is invoked and persists the `BLOCKED` state. Phase 2 reconstructs the runtime from disk, recovers the original action authorization, obtains fresh Blender evidence, authorizes a replacement action, executes it, independently verifies the result, and restores the original fixture state.

The continuation-integrity layer is deliberately fail-closed. An earlier harness defect that changed the runtime context across the process boundary was rejected by the integrity check and was fixed at the harness level rather than weakening the guard.

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
**NEXT**

Stage 13 should extend the proven single-action task contract into deterministic multi-step execution while preserving per-plan authorization, exact sequencing, checkpoints, fresh verification, and fail-closed recovery.

The first Stage 13 target should deliberately be small but genuinely multi-step, so the architecture can prove:

```text
ACTION 1 succeeds
      ↓
checkpoint
      ↓
ACTION 2 succeeds/fails
      ↓
if failure: recover from actual partial-progress state
      ↓
fresh evidence
      ↓
explicit replan
      ↓
continue without blindly replaying completed work
```

The Stage 13 audit must specifically test:

1. per-step authorization remains bound to the intended plan;
2. partial progress survives failure and process restart;
3. recovery replans against current observed state rather than original assumptions;
4. deterministic continuation reconstructs the exact multi-step position;
5. no second execution or authorization system is introduced.

### Stage 14 — Richer task composition and action dependencies
**PLANNED**

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
- task target decision → deterministic future binding;
- persisted task metadata → future consistency;
- action authorization → exact task action binding;
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

## Resume point

For the next session, read `ATLAS_HANDOFF_CURRENT.md` and the relevant Unreal handoff, inspect the current branch/HEAD and newest regression result, and then begin **Stage 13 — multi-step autonomous task execution with partial-progress recovery**.

Do not expand Qwen autonomy yet. First prove that the existing Atlas-owned execution/recovery machinery scales from one action to several ordered actions without losing authorization boundaries, deterministic continuation, fresh verification, or fail-closed recovery.

Do not claim cross-process Unreal render-job recovery unless it is separately implemented and verified.
