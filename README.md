# Atlas

## What Atlas is

Atlas is an **AI-assisted sports virtual production and digital-twin platform** designed to turn captured sports footage and real-world environments into richer, more controllable production experiences.

Blender is the first proven execution environment. Unreal Engine is a planned complementary production environment. Atlas is intentionally broader than any one DCC or game engine.

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
                 ↓
        Finished production state
                 ↓
      Independent Atlas verification
```

**Photogrammetry is an upstream reconstruction capability, not a Blender responsibility.** The Blender Agent receives and processes the initial reconstruction; photogrammetry intake is a future contract.

## Core operating principle

Atlas separates reasoning from execution:

```text
Qwen / AI agents
    → understand, reason, propose

Python / Atlas control layer
    → validate, authorize, execute, track state

Production tools
    → Blender now; future specialized tools

Independent verification
    → confirm what actually happened
```

Qwen never gets direct execution authority. Python owns execution state, authorization, mandatory ordering, verification, completion, and recovery.

---

# Current development status — Blender Agent

**Current roadmap milestone: Stage 9 — Broader Autonomous Blender Task Control, substantially advanced.**

Atlas has moved beyond a single goalpost proof. The same generic control architecture has now been exercised across multiple materially different Blender task shapes, while the task/runtime boundary is being hardened for production-facing use.

The current execution-integrity loop is:

```text
Qwen proposal
    ↓
Blender/tool schema validation
    ↓
authoritative evidence
    ↓
target-state evaluation
    ↓
authorization
    ↓
deterministic future
    ↓
Blender execution
    ↓
fresh independent verification
    ↓
immutable execution receipt
    ↓
completion / conservative recovery
```

### Current verified architectural components

- `planning/blender_tool_schema.py`
  - validates admitted Blender tools and required arguments;
  - rejects unknown tools, missing arguments, invalid types, and invalid coordinates;
  - snapshots mutable supported arguments before execution.

- `planning/blender_execution_boundary.py`
  - validates every call before Blender receives it;
  - preserves the backward-compatible raw `execute()` API;
  - provides `execute_verified()` for normalized verification-aware execution;
  - provides receipt-bound execution after successful verification;
  - rejects malformed executor responses.

- `planning/blender_result_contract.py`
  - immutable `BlenderExecutionResult`;
  - requires a valid tool, boolean success state, non-empty execution state, and object-shaped details.

- `planning/blender_verification.py`
  - requires the result to belong to the requested tool;
  - requires `ok=True` before the verified path succeeds;
  - fails closed on unsuccessful or mismatched results.

- `planning/blender_execution_receipt.py`
  - binds the exact tool, validated arguments, and verified execution result;
  - uses deterministic digests to detect request/result mutation;
  - cannot be produced from a failed execution.

- `planning/task_definition.py` + `planning/task_runtime.py`
  - separate declarative task data from runtime execution policy;
  - write-capable tasks are now checked for required verification at runtime rather than being rejected merely while constructing the task definition;
  - keeps orchestration logic generic and task data declarative.

- Runtime/session integrity
  - continuation identity is bound to stable instructions, authorized plan/future identity, and authoritative persisted state;
  - session lifecycle, replay, and close-state coverage has been expanded through focused regression work;
  - invalid or tampered continuation remains fail-closed.

### Live capabilities previously proven

The generic architecture has been exercised against these live Blender task paths using the local Windows runner and dedicated Atlas Ollama:

- object rotation — already-correct and incorrect paths;
- object rename;
- object delete;
- collection membership;
- parent relationship;
- generic collection;
- conditional goalpost task — already-correct and incorrect paths;
- Blender continuation — correct, incorrect, and tampered-context rejection;
- adversarial verification — executor claims success while authoritative state disagrees → `BLOCKED`.

These are capability proofs, not claims that arbitrary Blender production tasks are solved. The important milestone is that the same Python-owned validation → authorization → execution → verification architecture is reusable across different task shapes.

### Recent hardening

Recent development has tightened the boundary around `AtlasTaskDefinition` and runtime policy. A write-capable task may exist as declarative data, but `prepare_task_runtime()` is now the enforcement point for the requirement that writes receive post-action verification. This preserves a clean separation between task description and execution policy.

`AtlasTaskDefinition.snapshot()` also has deep-copy protection for nested mutable action/evidence arguments and metadata, preventing callers from mutating the live task through a snapshot.

Transient Ollama planning timeouts were previously observed in live testing. Ollama is now treated as **dedicated Atlas infrastructure**, so no workflow-level compensation for unrelated projects is required. The collection harness also contains bounded retry handling for transient planning timeouts.

### Current test state

The latest reported full local gate immediately before the runtime-boundary test correction was:

```text
444 passed, 1 failed
```

The remaining failure was the expected write-verification assertion living at the wrong boundary. The implementation was corrected and commit `353740a` removed the constructor-level enforcement; commit `554c6d` moved the regression assertion to `prepare_task_runtime()`.

A fresh fully green local gate after `554c6d` has **not yet been recorded**, so this documentation deliberately does not claim the newer code is fully validated.

Previously verified live regressions remain the historical live baseline until each newer change is freshly validated.

---

# Verified live Blender proof

The conditional goalpost harness remains an important reference proof, but it is no longer the definition of the architecture.

Fixtures:

- `goalpost_test_CONDITIONAL_CORRECT.blend`
- `goalpost_test_CONDITIONAL_INCORRECT.blend`

Target state:

```text
Goal_Left_post  = [0.0, 5.233, 0.0]
Goal_Right_Post = [0.0, -5.233, 0.0]
Midpoint        = [0.0, 0.0, 0.0]
Distance        = 10.466
Symmetric       = true
```

The proven conditional behavior is:

```text
already correct
  → target satisfied
  → skip writes
  → fresh independent verification
  → complete

incorrect
  → target unsatisfied
  → authorized writes
  → fresh independent verification
  → complete
```

The final state is established through independent Blender evidence rather than trusting a write response alone.

The goalpost fixture is a proof fixture, **not the generic architecture**.

---

# General planning architecture

Atlas already contains generic primitives for:

- ordered action plans;
- ordered evidence plans;
- target-state evaluation;
- generic post-action verification;
- planning/orchestration state machines;
- action authorization;
- replan authorization;
- deterministic future generation;
- deterministic future execution and resume;
- fail-closed recovery and replanning;
- runtime-context fingerprinting;
- runtime integrity / continuation identity;
- audit-trail ordering;
- immutable Blender execution receipts;
- declarative task definitions and runtime task preparation.

The intended lifecycle is:

```text
structured proposal
 ↓
authoritative evidence
 ↓
target-state evaluation
 ↓
authorization
 ↓
deterministic future
 ↓
execution
 ↓
independent verification
 ↓
receipt / completion
```

Failure lifecycle:

```text
action or verification failure
 ↓
BLOCKED
 ↓
fresh authoritative evidence
 ↓
explicit recovery decision
 ↓
new authorized plan
 ↓
new deterministic future
```

Automatic retry is prohibited for failed writes. Transient **planning-service** failures may be retried only within an explicit bounded planning budget and must not silently mutate an authorized execution future.

---

# Runtime integrity

Atlas separates stable instructions from authoritative dynamic state. Runtime continuation is bound to identities including stable instruction fingerprint, authorized plan identity, and authoritative persisted-state identity.

A continuation must fail closed if any required identity changes or is missing.

Blender receipts bind the exact validated request to the verified result from one execution and detect later mutation.

The remaining milestone is to demonstrate this integrity boundary as part of a broader production-facing continuation/resume flow across multiple materially different Blender tasks, rather than only as isolated primitives or a single fixture.

---

# Digital Twin architecture

Atlas owns the canonical Digital Twin. Blender, Unreal, photogrammetry software, and future production tools are adapters/executors around that canonical model.

A `.blend` file, Unreal project, render, or shot-specific modification is a representation or production state, not the canonical identity of the environment.

Atlas must distinguish between:

- canonical Digital Twin state;
- cleaned/corrected canonical revisions;
- downstream tool representations;
- production variants;
- shot-specific overrides;
- temporary cinematic effects;
- deliberately altered VFX states.

Identity must not be inferred from filenames, Blender object names, Unreal asset names, or timestamps. Stable physical/site identity anchors and provenance are the intended safety boundary. Ambiguous identity becomes an evidence problem rather than a Qwen guess.

The first identity primitive is `planning/digital_twin_identity.py`.

---

# Production-suite direction

## Blender Agent — current focus

Blender is the current proven environment for:

- digital-twin construction;
- scene inspection and spatial reasoning;
- procedural geometry;
- environment manipulation;
- cleanup and correction;
- optimization;
- evidence collection;
- controlled scene writes;
- independent verification.

The Blender Agent remains behind an adapter/tool boundary so Blender-specific behavior does not become the generic Atlas architecture.

## Photogrammetry intake — planned

Dedicated photogrammetry software will create the initial 3D reconstruction. Atlas will eventually define an intake/output contract covering assets, metadata, identity evidence, provenance, validation, cleanup/optimization, canonical revision creation, and downstream handoff.

## Unreal Agent — planned

Unreal Engine is a planned production environment for real-time virtual production, materials, lighting, Nanite, CineCamera, Sequencer, Movie Render Queue, and related workflows.

## Cinematic sports production

The wider Atlas repertoire can include:

- impact frames;
- smear frames;
- cinematic bleed;
- match-cut transformations;
- environment-driven effects;
- temporary liquid, smoke, glass, metallic, or other fluid-like environmental behavior;
- spatial overlays and field intelligence;
- digital-twin compositing;
- cinematic environmental interactions.

These are production modules, not the definition of Atlas.

---

# Roadmap

## Stage 1 — Basic Blender Agent

**COMPLETE**

## Stage 2 — Reliable Evidence

**COMPLETE**

## Stage 3 — Mandatory Evidence Acquisition

**COMPLETE**

## Stage 4 — Evidence Validation and Recommendation Restraint

**COMPLETE**

## Stage 5 — General Evidence Planner

**COMPLETE FOR CURRENT GENERIC PRIMITIVE**

## Stage 6 — Reliable Modification Control

**COMPLETE FOR CURRENT CONTROLLER PATTERN**

## Stage 7 — General Action Planning

**COMPLETE FOR CURRENT GENERIC PRIMITIVES**

## Stage 8 — Conditional Action Planning

**COMPLETE FOR CURRENT LIVE GOALPOST HARNESS**

The conditional architecture proves both no-write and write-required paths with independent verification and fail-closed recovery boundaries.

## Stage 9 — Broader Autonomous Blender Task Control

**IN PROGRESS — SUBSTANTIALLY ADVANCED**

This stage has progressed from a single goalpost proof to a multi-capability Blender control layer. Live proofs now cover materially different action/evidence shapes including rotation, rename, delete, collection membership, parent relationships, generic collection behavior, continuation, and adversarial verification.

The remaining work is not to invent a new architecture for each Blender operation. It is to finish hardening and prove that the same architecture can support production-facing continuation/resume across multiple tasks, including the marker task, while preserving:

```text
structured proposal
 ↓
authoritative evidence
 ↓
explicit target-state evaluation
 ↓
conditional decision
 ↓
authorization
 ↓
deterministic future
 ↓
Blender execution
 ↓
independent verification
 ↓
execution receipt
 ↓
completion / conservative recovery
```

## Future — Digital Twin Identity and Revision Model

**FOUNDATION IMPLEMENTED / BROADER MODEL PLANNED**

## Future — Photogrammetry Intake and Reconstruction Contract

**PLANNED**

## Future — Unreal Production Agents

**PLANNED**

## Future — Sports Production Orchestration

**PLANNED**

---

# Required Blender regression coverage

The Blender test suite should continue to cover:

- already-satisfied state → zero writes;
- unsatisfied state → exact authorized action order;
- authorization mandatory before writes;
- successful write → verification mandatory;
- verification failure → blocked;
- action failure → recovery gate;
- mutated arguments → receipt mismatch;
- mutated execution result → receipt mismatch;
- malformed executor result → rejected;
- wrong result tool → rejected;
- invalid continuation identity → rejected;
- authorized replan based on fresh evidence → accepted;
- unauthorized replan → rejected;
- one receipt-bound execution cannot cause duplicate writes;
- write-verification policy is enforced at task-runtime preparation rather than only at task-definition construction.

For each new stage, the development process is:

1. inspect current `main`;
2. implement the smallest coherent Blender increment;
3. add focused offline tests;
4. run the local test gate;
5. inspect the newest GitHub Actions workflows;
6. approve `local-testing` only when GitHub explicitly requests that deployment review;
7. diagnose failures from actual logs;
8. fix and retest without requiring a separate user instruction for routine failures;
9. update the README and handoff after verified milestones;
10. continue to the next coherent Blender stage.

---

# Local environment

```text
Python 3.9.6
Ollama 0.32.13
qwen3:8b
Blender 4.4.3
```

Ollama endpoint:

```text
http://localhost:11434/api/chat
```

Ollama is treated as dedicated Atlas infrastructure for this development track.

---

# Development rules

- Do not rewrite the entire agent.
- Preserve the evidence ledger.
- Preserve independent post-write verification.
- Do not make goalpost behavior the generic architecture.
- Do not add tools without proving a real capability gap.
- Do not let a successful production-tool response alone establish completion.
- Do not allow action plans to execute without explicit authorization.
- Do not allow Qwen to bypass Python-owned execution state.
- Do not allow automatic retry after failed writes.
- Keep Blender/Unreal-specific behavior behind adapter/tool boundaries.
- Treat photogrammetry as an upstream reconstruction capability.
- Atlas owns canonical Digital Twin identity and state.
- Do not merge Digital Twin captures on weak or missing identity evidence.
- Keep canonical state separate from shot-specific/cinematic variants.
- Preserve provenance.
- Improve incrementally and preserve working components.
- Keep `README.md`, `ATLAS_HANDOFF_CURRENT.md`, and `DEVELOPMENT_LOG.md` synchronized with verified milestones.

## Resume point

For the next development session, read `ATLAS_HANDOFF_CURRENT.md`, inspect the current `main` HEAD, and check the latest workflow state before changing code.

**Immediate next stage:** finish the current task-runtime/test hardening, obtain a fresh green offline gate, then live-prove `create_empty_marker` and expand the broader production-facing continuation/resume proof across the already-demonstrated multi-capability Blender control layer.
