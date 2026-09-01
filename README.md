# Atlas

## What Atlas is

Atlas is an **AI-assisted sports virtual production and digital-twin platform** designed to turn captured sports footage and real-world environments into richer, controllable production experiences.

Blender and Unreal Engine are execution environments around Atlas's canonical Digital Twin. Dedicated photogrammetry software is an upstream reconstruction stage.

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

Blender / Unreal
  → controlled production execution

Independent verification
  → establish what actually happened
```

Qwen never receives direct production execution authority.

---

# Current Atlas status — September 1, 2026

Atlas has now proven a real Unreal Engine 5.6 production-render boundary locally, in addition to the established Blender planning and execution architecture.

Latest local Python regression reported during the September 1 development session:

**1033 passed, 5 skipped**

`git diff --check` was clean at the same checkpoint.

The Unreal render boundary has been exercised through the real UE 5.6 editor/runtime and now covers render configuration, configuration verification, render submission, dynamic render-job identity, asynchronous job inspection, output artifact discovery, artifact verification, and deterministic render receipts.

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
reassessment / replan
```

Blender remains an independent development track. Its process/adapter boundaries preserve capability restrictions, validated arguments, authorization scope, deterministic execution, independent verification, and fail-closed behavior.

---

# Unreal Agent status

Unreal production transport and rendering are no longer merely planned or unverified. The local UE 5.6 boundary has been exercised end to end.

The controlled render workflow now supports:

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

A real controlled render was executed using:

```text
resolution:       640x360
frame range:      1–2
output format:    PNG
output directory: Saved/AtlasRenderOutput
```

The completed live job returned a real PNG artifact through `inspect_render_job`, and Atlas marked the completed inspection `verified=True`.

A live `UnrealRenderReceipt` was then issued from that verified evidence. The verified session produced these deterministic identities:

```text
evidence_digest:
f5014c719628478f7223ed3a8c4173d9230f13f4957e786ef99e20cd4b1b6cd0

receipt_digest:
f053d427fde579637225fa350b5204f6a001bfb041041802d06542c8e8114dcb

SELF MATCH: True
```

The receipt store has focused regression coverage for round-tripping, deterministic persistence, extra-field rejection, and digest tampering.

The Unreal runtime job registry itself remains in-memory. Durable render-receipt persistence is an Atlas/Python concern; cross-process Unreal job recovery has **not** been implemented.

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
**IN PROGRESS**

### Stage 11 — First Controlled Live Blender Operation
**NEXT BLENDER LIVE GATE**

### Stage 12 — Closed-loop Blender Agent
**FUTURE**

## Unreal

### Unreal Engine Boundary
**PROVEN LOCALLY**

### Unreal Production Transport
**PROVEN LOCALLY FOR CURRENT IMPLEMENTED CAPABILITIES**

### Unreal Render / MRQ Boundary
**PROVEN LOCALLY**

### Render Artifact Verification
**PROVEN LOCALLY**

### Unreal Render Receipt
**PROVEN LOCALLY**

### Render Receipt Persistence
**PROVEN LOCALLY**

### Next Unreal increment
Integrate receipt creation/persistence into the higher-level Atlas render execution workflow, then expand Unreal capabilities only where a real capability gap justifies them.

---

# Digital Twin direction

Atlas owns the canonical Digital Twin. Blender, Unreal, photogrammetry software, and future tools are adapters/executors around that canonical model.

A `.blend` file, Unreal project, level, render configuration, or other DCC artifact is a representation/production state, not the canonical identity of the environment. Identity, provenance, revisions, production variants, and shot-specific changes remain explicit.

Photogrammetry creates the initial reconstruction. Blender analyzes, cleans, corrects, optimizes, and prepares it for downstream production.

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
- action failure → recovery gate;
- mutated arguments/result → receipt mismatch;
- malformed executor result → rejected;
- wrong result tool → rejected;
- invalid continuation identity → rejected;
- authorized fresh-evidence replan → accepted;
- unauthorized replan → rejected;
- malformed Qwen reasoning → rejected;
- unknown/non-capability tool → rejected;
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
- Keep Blender/Unreal-specific behavior behind adapter/tool boundaries.
- Treat photogrammetry as an upstream reconstruction capability.
- Preserve provenance and canonical Digital Twin identity.
- Test every meaningful increment.
- Keep the project handoffs synchronized with verified milestones.

## Resume point

For the next session: read `ATLAS_HANDOFF_CURRENT.md` and `UNREAL_AGENT_HANDOFF_CURRENT.md`, inspect the current branch/HEAD and newest regression result, then continue from the **Unreal render receipt integration** checkpoint or the independently tracked Blender adapter/live-operation track. Do not claim cross-process Unreal job recovery unless it is separately implemented and verified.
