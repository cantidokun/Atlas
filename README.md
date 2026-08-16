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
    → Blender, Unreal Engine, and future specialized tools

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

### `planning_orchestrator.py`

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

---

# Production-suite direction

Atlas is being designed as a suite of cooperating production agents rather than one monolithic model.

## Sports capture and understanding

Future agents can reason over captured sports footage to identify players, objects, field geometry, events, spatial relationships, and production opportunities. The resulting understanding can feed digital-twin and virtual-production workflows.

## Blender agents

Blender is the current proven environment for:

- digital-twin construction
- procedural geometry
- scene inspection
- spatial reasoning
- environment manipulation
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

**IN PROGRESS**

## Stage 6 — Reliable Modification Control

**COMPLETE FOR CURRENT CONTROLLER PATTERN**

## Stage 7 — General Action Planning

**IN PROGRESS**

The generic action-plan primitive, evidence-plan primitive, planning orchestrator, controlled recovery boundary, audit trail, and Qwen structured planning bridge are proven.

## Stage 8 — Conditional Action Planning

**NEXT**

Atlas must determine from authoritative evidence whether the requested state is already satisfied before executing a proposed write.

Desired behavior:

```text
Task
 ↓
Evidence
 ↓
Target already satisfied?
   ↙          ↘
 YES           NO
  ↓             ↓
skip write    authorized action plan
                ↓
          controlled execution
                ↓
        independent verification
```

The first test should use an already-correct state and prove that Atlas does not write unnecessarily. A second test should use a genuinely incorrect state and prove that the necessary write path remains available.

## Stage 9 — Broader Autonomous Task Control

**NOT STARTED**

This comes after the generic planner and conditional execution boundary are stable.

## Future — Unreal Production Agents

**PLANNED**

Unreal Engine agents will extend Atlas into a broader real-time virtual-production environment.

## Future — Sports Production Orchestration

**PLANNED**

The long-term system should be able to coordinate capture analysis, digital twins, Blender/Unreal production operations, cinematic treatments, and final verification as one production workflow.

---

# Offline tests

Latest local regression result:

```text
98 passed
```

The suite covers controller state transitions, required write ordering, post-write verification, final-answer validation, deterministic finalization, generic ordered action plans, generic ordered evidence plans, evidence-to-action orchestration, authorization boundaries, recovery behavior, and audit-trail ordering.

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
- Keep production-environment-specific logic behind appropriate agent/tool boundaries.
- Preserve working components and improve incrementally.
- Keep `README.md`, `ATLAS_HANDOFF_CONTEXT.txt`, and `DEVELOPMENT_LOG.md` synchronized with verified milestones and test results.

For the detailed technical record, see `ATLAS_HANDOFF_CONTEXT.txt` and `DEVELOPMENT_LOG.md`.
