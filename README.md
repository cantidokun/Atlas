# Atlas

## What Atlas is

Atlas is an **AI-assisted sports virtual production and digital-twin platform** designed to turn captured sports footage and real-world environments into richer, more controllable production experiences.

It is not intended to be only a Blender agent. Blender is the first proven execution environment; Unreal Engine is a planned complementary production environment. The long-term goal is a production suite in which specialized AI agents can understand sports footage, reason about environments and assets, plan changes, execute production operations, and verify the resulting state.

Atlas sits at the intersection of:

- sports capture and analysis
- digital twins and spatial understanding
- AI-assisted virtual production
- procedural scene construction and manipulation
- cinematic rendering and compositing
- production automation and orchestration

For sports, this can support workflows such as field and stadium reconstruction, player/environment interaction, spatial visualization, cinematic effects, environmental transformations, impact and smear treatments, match-cut transformations, and other production-level visualizations around real athletes.

The architecture is intentionally broader than any one DCC or game engine:

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

**Photogrammetry is an upstream reconstruction capability, not a Blender responsibility.** Dedicated photogrammetry software is expected to create the initial 3D reconstruction. The Blender Agent then analyzes that reconstruction, cleans it up, corrects problems, optimizes it, and prepares it for downstream production. This is an architectural direction; the photogrammetry integration is not yet implemented.

Atlas task orchestration sits above these specialized tools:

```text
Captured sports footage / production task
                 ↓
        Atlas task understanding
                 ↓
       Evidence and scene reasoning
                 ↓
       Specialized production agents
          ↙                 ↘
      Blender              Unreal Engine
          ↘                 ↙
          Production state
                 ↓
      Independent verification
                 ↓
        Finished production result
```

## Core operating principle

Atlas separates reasoning from execution:

```text
Qwen / AI agents
    → understand, reason, propose

Python / Atlas control layer
    → validate, authorize, execute, track state

Production tools
    → photogrammetry, Blender, Unreal Engine, and future specialized tools

Verification
    → independently confirm what actually happened
```

The target control loop is:

```text
Task
 ↓
Task understanding
 ↓
Evidence plan
 ↓
Evidence ledger
 ↓
Authorized action plan
 ↓
Python-controlled execution
 ↓
Independent verification
 ↓
Completion
```

Qwen can reason, but it does not get to decide that an action happened. Python owns execution state, authorization, mandatory ordering, verification, and completion.

---

# Current status

The current implementation is concentrated on the Blender side because Blender provides a controlled environment in which the agent architecture can be proven incrementally.

Atlas has already proven:

- local Qwen/Ollama integration
- Blender scene inspection
- read-only evidence acquisition
- evidence tracking and reuse
- authorized Blender writes
- ordered multi-step action execution
- independent post-write verification
- deterministic finalization from verified evidence
- controlled write-failure recovery
- audit-trail ordering
- generic ordered action plans
- generic ordered evidence plans
- evidence-to-action orchestration
- structured Qwen planning without automatic write execution
- conditional no-write and write branches
- generic post-action verification
- deterministic future generation and execution gating
- fail-closed recovery and replan authorization
- runtime-context fingerprinting and cache invalidation boundaries
- an explicit authoritative model-request boundary

The current test asset is `goalpost_test.blend`.

## Verified goalpost controller result

The original live controller measured:

```text
BEFORE
Goal_Left_post  = [0.0, 5.302, 0.0]
Goal_Right_Post = [0.0, -5.164, 0.0]
Midpoint        = [0.0, 0.069, 0.0]
```

Target:

```text
Goal_Left_post  = [0.0, 5.233, 0.0]
Goal_Right_Post = [0.0, -5.233, 0.0]
```

Final independently verified state:

```text
Goal_Left_post  = [0.0, 5.233, 0.0]
Goal_Right_Post = [0.0, -5.233, 0.0]
Midpoint        = [0.0, 0.0, 0.0]
Distance        = 10.466 units
Symmetric       = true
```

The final state came from a separate Blender relationship inspection rather than trusting the write result alone.

---

# Qwen Structured Planning Bridge — PASS

`live_qwen_planning_loop.py` proves the first live boundary between Qwen task planning and generic Python planning primitives:

```text
Qwen structured plan
 ↓
Python plan validation
 ↓
Read-only Blender evidence
 ↓
Planning orchestrator
 ↓
Structured action plan
 ↓
WRITE EXECUTION NOT PERFORMED
```

The successful live run produced:

- 1 structured evidence request
- 2 structured actions
- validated plan
- authoritative read-only evidence
- completed evidence plan
- structured action plan with the next action exposed
- zero write execution

Result:

```text
QWEN PLAN ACCEPTED
EVIDENCE VERIFIED READ-ONLY
ACTION PLAN STRUCTURED
WRITE EXECUTION NOT PERFORMED
ATLAS QWEN PLANNING BRIDGE TEST: PASS
```

---

# General planning architecture

### `action_plan.py`

Provides a generic ordered action state machine. Python exposes the next action, records successful results, blocks on required failures, and reports completion.

### `evidence_plan.py`

Tracks ordered evidence requests, completion, reuse, and blocking failures.

### `planning/planning_orchestrator.py`

Connects evidence and action plans. Actions remain blocked until required evidence is complete.

### Authorization boundary

A proposed action does not automatically become an executable action. The Python authorization layer must explicitly permit writes and restrict the available action tools.

### Recovery boundary

After a failed write, Atlas requires fresh evidence and a new validated, explicitly authorized plan. Automatic retry is refused because execution state may have changed.

### Audit trail

The live action workflow records:

```text
Qwen proposal
 ↓
Evidence
 ↓
Authorization
 ↓
Execution
 ↓
Verification
```

### Runtime context boundary

Stable instructions and dynamic runtime state are treated as different classes of information. Atlas fingerprints the stable instruction context so stale cached context can be detected when the stable instructions change, while dynamic observations and execution cursor state do not alter that stable fingerprint.

The model-request boundary is explicit: authoritative runtime requests must be formed from the current validated Atlas context rather than allowing stale or unvalidated context to become an execution authority.

---

# Digital Twin architecture

## Canonical ownership

Atlas owns the **canonical Digital Twin**.

Blender, Unreal Engine, photogrammetry software, and future production tools are adapters/executors around that canonical model. None of those environments is the ultimate source of truth for Atlas identity or canonical state.

The intended ownership model is:

```text
Real-world environment / captured sports footage
                 ↓
       Dedicated photogrammetry
                 ↓
        Initial reconstruction
                 ↓
          Atlas intake layer
                 ↓
       Canonical Digital Twin
                 ↙          ↘
            Blender       Unreal
          adapter/tool    adapter/tool
                 ↘          ↙
              production variants
                 ↓
          Atlas verification
```

A `.blend` file, Unreal project, render, or shot-specific modification is therefore a **representation or production state**, not the canonical identity of the environment.

## Canonical state vs. production variants

Atlas must distinguish between:

- canonical Digital Twin state
- cleaned/corrected canonical revisions
- downstream tool representations
- production variants
- shot-specific overrides
- temporary cinematic effects
- deliberately altered VFX states

A cinematic modification must not silently overwrite the canonical environment. Production changes should be represented as explicit variants, overrides, or derived states so Atlas can always recover the canonical twin.

## Digital Twin identity

Atlas must be able to recognize that two captures may represent the **same real-world environment at different times**.

For example:

```text
2026 capture
    ↓
photogrammetry
    ↓
reconstruction A
    ↓
Blender cleanup
    ↓
Atlas Twin FIELD_001

2027 capture
    ↓
photogrammetry
    ↓
reconstruction B
    ↓
Blender cleanup
    ↓
Atlas identity evaluation
    ↓
FIELD_001 new capture/version
```

Identity is not based on a file name, Blender object name, Unreal asset name, or capture timestamp.

Atlas uses explicit **stable identity anchors** as the safety boundary. Examples can include an external site identifier, geographic reference, survey/control reference, or another durable physical identifier. Capture-specific metadata such as capture date is deliberately not part of canonical identity.

The identity decision is conservative:

```text
Observed identity evidence
          ↓
     Compare stable anchors
          ↓
   ┌──────┼───────────────┐
   ↓      ↓               ↓
 MATCH  NO MATCH   INSUFFICIENT EVIDENCE
   ↓      ↓               ↓
 reuse   separate       do not merge
 identity candidate    automatically
```

Atlas must **not silently merge** a new capture into an existing Digital Twin when required identity evidence is missing. Ambiguous identity becomes an evidence problem requiring additional authoritative information, not a guess by Qwen.

The first implementation primitive is `planning/digital_twin_identity.py`. It provides deterministic identity anchors, a stable identity fingerprint, and conservative match states: `MATCH`, `NO_MATCH`, and `INSUFFICIENT_EVIDENCE`.

## Identity is separate from geometry

Geometry is important evidence for identity, but geometry alone should not become an implicit identity key. Real environments change, reconstructions contain noise, and production modifications can intentionally alter geometry.

Atlas should therefore treat identity as a separate semantic layer that can use geometry as supporting evidence while retaining explicit stable anchors and provenance.

## Provenance

The eventual Digital Twin model should distinguish at minimum:

- captured information
- reconstructed information
- inferred information
- Atlas-corrected information
- production-authored information
- shot-specific temporary state

This provenance is necessary so Atlas can reason about what is known, what was inferred, what was deliberately changed, and what should survive into future revisions.

## Validation ownership

Validation remains an Atlas responsibility. Blender and Unreal can report authoritative evidence from their respective environments, but completion is not established merely because a production tool reports success.

The same principle used by the current conditional architecture therefore extends to the Digital Twin:

```text
Tool operation
    ↓
independent evidence
    ↓
Atlas invariant evaluation
    ↓
canonical/variant state update
```

---

# Production-suite direction

Atlas is being designed as a suite of cooperating production agents rather than one monolithic model.

## Photogrammetry intake

Dedicated photogrammetry software is intended to create the **initial 3D reconstruction** from real-world captures. Atlas does not currently treat photogrammetry reconstruction itself as a Blender responsibility.

The intended boundary is:

```text
Photogrammetry software
        ↓
Initial reconstruction
        ↓
Atlas intake / validation
        ↓
Blender Agent
        ↓
Analysis / cleanup / correction / optimization
        ↓
Prepared canonical Digital Twin revision
```

The photogrammetry stage is an upstream capability that will eventually need a defined intake/output contract so Blender can reliably inspect and process the resulting reconstruction. This integration is planned, not implemented.

## Sports capture and understanding

Future agents can reason over captured sports footage to identify players, objects, field geometry, events, spatial relationships, and production opportunities. The resulting understanding can feed digital-twin and virtual-production workflows.

## Blender agents

Blender is the current proven environment for:

- receiving initial 3D reconstructions from upstream photogrammetry
- digital-twin construction
- analyzing reconstructed geometry and scene structure
- procedural geometry
- scene inspection
- spatial reasoning
- environment manipulation
- cleanup and correction
- optimization for downstream production
- evidence collection
- controlled scene writes

Atlas should remain environment-agnostic at the orchestration level so Blender-specific behavior does not become the generic architecture.

## Unreal Engine agents

Unreal Engine is a planned production environment for the next phase of Atlas. Future Unreal agents are expected to cover capabilities such as:

- asset and scene organization
- materials and look development
- lighting and Lumen workflows
- Nanite-enabled assets
- CineCamera and cinematic setup
- Sequencer and shot construction
- Movie Render Queue workflows
- real-time virtual-production operations

The Unreal layer will plug into the same broader control philosophy: AI proposes and reasons; Atlas validates and authorizes; the production environment executes; independent checks verify the resulting state.

## Cinematic sports production

Atlas is intended to support visual treatments around real athletes without requiring the final experience to be a conventional game or conventional VFX pipeline.

The wider repertoire includes:

- impact frames
- smear frames
- cinematic bleed
- match-cut transformations
- environment-driven visual effects
- temporary liquid, smoke, glass, metallic, or other fluid-like environmental behavior
- spatial overlays and field intelligence
- digital-twin compositing
- cinematic environmental interactions

The exact effects are production modules, not the definition of Atlas itself.

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

The conditional architecture now proves both no-write and write-required paths, with independent verification and fail-closed recovery boundaries.

## Stage 9 — Broader Autonomous Task Control

**IN PROGRESS**

The current work is strengthening the autonomous runtime boundary rather than allowing Qwen direct authority. Runtime context fingerprinting, cache invalidation, authoritative model-request formation, and related execution-safety boundaries are being proven incrementally.

The next production-facing objective is to generalize the verified control loop across a second non-goalpost production task while preserving:

```text
Task
 ↓
structured evidence requirements
 ↓
authoritative evidence
 ↓
explicit target-state evaluation
 ↓
conditional decision
 ↓
deterministic future
 ↓
authorized action sequence if needed
 ↓
independent verification
 ↓
completion / conservative recovery
```

## Future — Digital Twin Identity and Revision Model

**FOUNDATION IMPLEMENTED / BROADER MODEL PLANNED**

The first conservative identity primitive is now implemented. The broader Digital Twin model still needs explicit versioning, provenance, canonical-vs-variant state management, identity evidence aggregation, and intake contracts.

## Future — Unreal Production Agents

**PLANNED**

Unreal Engine agents will extend Atlas into a broader real-time virtual-production environment.

## Future — Photogrammetry Intake and Reconstruction Contract

**PLANNED**

Define how dedicated photogrammetry software hands an initial reconstruction to the Atlas intake layer and Blender Agent, including the expected assets, scene metadata, identity evidence, validation requirements, cleanup/optimization boundary, canonical revision creation, and downstream handoff.

## Future — Sports Production Orchestration

**PLANNED**

The long-term system should be able to coordinate capture analysis, photogrammetry reconstruction, Digital Twins, Blender/Unreal production operations, cinematic treatments, and final verification as one production workflow.

---

# Regression status

The latest previously verified GitHub Actions regression matrix passed on both supported CI Python versions:

```text
Run #172: 133 tests passed on Python 3.11 and Python 3.9
Run #173: 133 tests passed on Python 3.11 and Python 3.9
```

Subsequent runtime-context work has added further regression coverage. The Digital Twin identity changes on the current development branch add dedicated tests for conservative matching, missing evidence, conflicting anchors, and identity fingerprint stability; the branch CI run is the validation gate for these changes.

---

# Local environment

```text
Python 3.9.6
Ollama 0.32.13
qwen3:8b
Blender 4.4
```

Ollama endpoint:

```text
http://localhost:11434/api/chat
```

---

# Development rules

- Do not rewrite the entire agent.
- Do not remove the evidence ledger.
- Do not remove independent post-write verification.
- Do not make goalpost behavior the generic architecture.
- Do not add tools without proving a real capability gap.
- Do not let a successful production state depend on a perfect Qwen final answer.
- Do not allow an action plan to execute without explicit authorization.
- Do not allow Qwen to bypass Python-owned execution state.
- Do not allow automatic retry after failed writes.
- Keep Blender/Unreal-specific behavior behind appropriate adapter/tool boundaries.
- Treat photogrammetry as an upstream reconstruction capability rather than making Blender responsible for the initial reconstruction.
- Atlas owns canonical Digital Twin identity and state; production tools do not become the source of truth.
- Do not merge Digital Twin captures on weak or missing identity evidence.
- Keep canonical state separate from shot-specific or cinematic production variants.
- Preserve provenance for captured, inferred, corrected, and production-authored state.
- Preserve working components and improve incrementally.
- Keep `README.md`, `ATLAS_HANDOFF_CONTEXT.txt`, and `DEVELOPMENT_LOG.md` synchronized with verified milestones and test results.

For the detailed technical record, see `ATLAS_HANDOFF_CONTEXT.txt` and `DEVELOPMENT_LOG.md`.
