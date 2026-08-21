# Atlas

## What Atlas is

Atlas is an **AI-assisted sports virtual production and digital-twin platform** designed to turn captured sports footage and real-world environments into richer, controllable production experiences.

Blender is the first execution environment being brought to full agent operation. Unreal Engine is a planned complementary production environment.

```text
Real-world environment / captured sports footage
                 ↓
       Dedicated photogrammetry
                 ↓
        Initial 3D reconstruction
                 ↓
            Blender Agent
       analyze / clean / correct
              / optimize
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

Blender
  → production execution

Independent verification
  → establish what actually happened
```

Qwen never receives direct execution authority.

---

# Current Blender Agent status

**Latest verified CI baseline: 687 passed.** The corresponding GitHub Actions run is green on both Python 3.9 and Python 3.11.

The major pre-integration architecture is now in place:

```text
Qwen reasoning
      ↓
structured Blender intent
      ↓
capability/schema validation
      ↓
authorized ActionPlan
      ↓
controlled execution boundary
      ↓
verification
      ↓
immutable execution evidence / agent state
      ↓
replanning when required
```

Recent work established the structured Qwen → Atlas reasoning boundary. Model output is parsed into a constrained `BlenderTaskIntent`; malformed confidence, empty objectives/actions/evidence, non-object arguments, and invalid structured output are rejected before planning. Unknown Blender tools remain blocked by the canonical capability planner.

Agent-state and evidence-driven replanning are also part of the current architecture. Replanning consumes verified observations and produces a new task intent rather than mutating an already-authorized plan.

**Testing is part of development, not a final step.** Every meaningful architectural increment must have focused regression coverage and a fresh green CI result before it is treated as complete.

---

# Blender development roadmap

## Stage 1 — Basic Blender Agent
**COMPLETE**

## Stage 2 — Reliable Evidence
**COMPLETE**

## Stage 3 — Mandatory Evidence Acquisition
**COMPLETE**

## Stage 4 — Evidence Validation and Recommendation Restraint
**COMPLETE**

## Stage 5 — General Evidence Planner
**COMPLETE**

## Stage 6 — Reliable Modification Control
**COMPLETE**

## Stage 7 — General Action Planning
**COMPLETE**

## Stage 8 — Conditional Action Planning
**COMPLETE**

The generic architecture has been proven across conditional write/no-write behavior, authorization, independent verification, recovery/replanning boundaries, continuation integrity, and immutable execution receipts.

## Stage 9 — Qwen/Atlas Agent Reasoning Boundary
**COMPLETE FOR CURRENT CONTRACT**

Qwen can propose structured reasoning that Atlas converts into a constrained `BlenderTaskIntent`. Atlas remains responsible for capability validation, authorization, execution ordering, verification, and recovery.

Latest regression milestone: **687 passed**.

## Stage 10 — Blender Adapter / Real Execution Bridge
**CURRENT DEVELOPMENT STAGE**

The next objective is the adapter between Atlas's already-authorized action model and a real Blender runtime.

The adapter must preserve capability restrictions, exact validated arguments, authorization scope, deterministic execution, structured execution results, evidence capture, independent verification, fail-closed errors, and compatibility with the existing state/replanning system.

It must not become an unrestricted Python escape hatch for Qwen.

## Stage 11 — First Controlled Live Blender Operation
**NOT STARTED**

The first live connection should be deliberately small: inspect a controlled Blender scene, perform one constrained operation, and independently verify the result.

## Stage 12 — Closed-loop Blender Agent
**FUTURE**

```text
Blender scene
    ↓
inspection/evidence
    ↓
Qwen reasoning
    ↓
Atlas intent + plan
    ↓
authorization
    ↓
Blender execution
    ↓
independent verification
    ↓
reassessment / replan
```

This is the milestone at which Atlas can be considered a functioning autonomous Blender Agent rather than a collection of validated planning primitives.

---

# Digital Twin direction

Atlas owns the canonical Digital Twin. Blender, Unreal, photogrammetry software, and future tools are adapters/executors around that canonical model.

A `.blend` file is a representation/production state, not the canonical identity of the environment. Identity, provenance, revisions, production variants, and shot-specific changes must remain explicit.

The future photogrammetry intake contract will define how a dedicated reconstruction system hands its initial 3D output to the Blender Agent for analysis, cleanup, correction, and optimization.

# Unreal direction

Unreal Engine is planned for real-time production, materials, lighting, Nanite, CineCamera, Sequencer, Movie Render Queue, and cinematic virtual-production workflows.

Atlas remains broader than any one DCC or game engine.

# Production repertoire

The wider Atlas production system may include impact frames, smear frames, cinematic bleed, match-cut transformations, spatial overlays, digital-twin compositing, and environment-driven effects including temporary liquid, smoke, glass, metallic, or other fluid-like behavior.

These are production modules, not the definition of Atlas.

---

# Required regression philosophy

Preserve coverage for:

- already-satisfied state → zero writes;
- unsatisfied state → exact authorized action order;
- successful write → verification remains mandatory;
- verification failure → `BLOCKED`;
- action failure → recovery gate;
- mutated arguments/result → receipt mismatch;
- malformed executor result → rejected;
- wrong result tool → rejected;
- invalid continuation identity → rejected;
- authorized fresh-evidence replan → accepted;
- unauthorized replan → rejected;
- malformed Qwen reasoning → rejected;
- unknown/non-capability Blender tool → rejected.

# Development rules

- Preserve the evidence ledger and independent verification.
- Do not make goalpost behavior the generic architecture.
- Do not add tools without proving a capability gap.
- Do not allow a production-tool success response alone to establish completion.
- Do not allow action plans to execute without explicit authorization.
- Do not allow Qwen to bypass Python-owned execution state.
- Do not allow automatic retry after failed writes.
- Keep Blender/Unreal-specific behavior behind adapter/tool boundaries.
- Treat photogrammetry as an upstream reconstruction capability.
- Preserve provenance and canonical Digital Twin identity.
- Test every meaningful increment.
- Keep `README.md`, `ATLAS_HANDOFF_CURRENT.md`, `ATLAS_HANDOFF_CONTEXT.txt`, and `DEVELOPMENT_LOG.md` synchronized with verified milestones.

## Resume point

For the next session: read `ATLAS_HANDOFF_CURRENT.md`, inspect the current branch/HEAD, inspect the newest CI result, then continue **Stage 10 — Blender Adapter / Real Execution Bridge**. Do not claim readiness for live Blender connection until the adapter contract and its focused tests are green.
