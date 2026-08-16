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
Target-state evaluation
 ↓
Conditional action decision
 ↓
Authorized action plan
 ↓
Python-controlled execution
 ↓
Independent verification
 ↓
Completion
```

Qwen can reason, but it does not get to decide that an action happened. Python owns execution state, authorization, mandatory ordering, target-state evaluation, verification, and completion.

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
- strict model-generated tool-argument validation
- generic target-state invariant evaluation
- live conditional no-op and write paths

The current test asset is `goalpost_test.blend`.

## Verified goalpost controller result

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

# Conditional execution

Atlas now has a generic target-state evaluation boundary. Required target properties are represented as named deterministic invariants over authoritative evidence. All invariants must pass before Atlas may decide that the target state already exists.

```text
Authoritative evidence
        ↓
TargetStateEvaluator
        ↓
All invariants pass?
   ↙              ↘
 YES              NO
  ↓                ↓
Skip write      Authorized action plan
  ↓                ↓
Finalize       Execute in Python
                 ↓
        Independent verification
```

Evaluation failures fail closed. The generic `ConditionalPlanningOrchestrator` now owns the deterministic phase boundary between evidence, target-state evaluation, and conditional action execution.

The live conditional workflow has passed both required cases:

- already-correct → no write
- incorrect → authorized write + independent verification

The goalpost scenario is a proving case; the target-state/evidence/action architecture is intended to be reusable across future Atlas production tasks.

---

# General planning architecture

### `action_plan.py`

Provides a generic ordered action state machine. Python exposes the next action, records successful results, blocks on required failures, and reports completion.

### `evidence_plan.py`

Tracks ordered evidence requests, completion, reuse, and blocking failures.

### `planning/target_state.py`

Provides `StateInvariant`, `TargetStateEvaluator`, and `TargetStateResult`. Evaluation is fail-closed and reports named invariants and failed invariants.

### `planning/planning_orchestrator.py`

Provides both the original evidence-to-action orchestrator and the generic `ConditionalPlanningOrchestrator`. Conditional execution cannot begin until evidence is complete and target-state evaluation has succeeded.

### Authorization boundary

A proposed action does not automatically become an executable action. The Python authorization layer must explicitly permit writes and restrict the available action tools.

### Recovery boundary

After a failed write, Atlas requires fresh evidence and a new validated, explicitly authorized plan. Automatic retry is refused because execution state may have changed.

### Audit trail

The live action workflow records the lifecycle from proposal through evidence, authorization, execution, and independent verification.

---

# Production-suite direction

Atlas is being designed as a suite of cooperating production agents rather than one monolithic model.

## Sports capture and understanding

Future agents can reason over captured sports footage to identify players, objects, field geometry, events, spatial relationships, and production opportunities. The resulting understanding can feed digital-twin and virtual-production workflows.

## Blender agents

Blender is the current proven environment for digital-twin construction, procedural geometry, scene inspection, spatial reasoning, environment manipulation, evidence collection, and controlled scene writes.

## Unreal Engine agents

Unreal Engine is a planned production environment for the next phase of Atlas. Future Unreal agents are expected to cover asset/scene organization, materials and look development, lighting and Lumen workflows, Nanite-enabled assets, CineCamera and cinematic setup, Sequencer and shot construction, Movie Render Queue workflows, and real-time virtual-production operations.

## Cinematic sports production

The wider repertoire includes impact frames, smear frames, cinematic bleed, match-cut transformations, environment-driven visual effects, temporary liquid/smoke/glass/metallic or other fluid-like environmental behavior, spatial overlays, digital-twin compositing, and cinematic environmental interactions.

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

**V1 PROVEN / CONTINUING**

## Stage 6 — Reliable Modification Control

**PROVEN FOR CURRENT CONTROLLER PATTERN**

## Stage 7 — General Action Planning

**V1 PROVEN / CONTINUING**

The generic action-plan primitive, evidence-plan primitive, planning orchestrator, controlled recovery boundary, audit trail, and Qwen structured planning bridge are proven.

## Stage 8 — Conditional Action Planning

**LIVE CASES PASSED / GENERAL ORCHESTRATION ACTIVE**

The already-correct and incorrect goalpost cases both passed on the self-hosted runner. Target-state evaluation and conditional execution are now represented as reusable Python architecture rather than only as a goalpost-specific boolean.

## Stage 9 — Broader Autonomous Task Control

**NEXT**

The next objective is to move from one conditional action sequence to broader task-level conditional planning while preserving strict argument validation, explicit authorization, evidence gates, and independent verification.

## Future — Unreal Production Agents

**PLANNED**

## Future — Sports Production Orchestration

**PLANNED**

---

# Offline tests

Latest previously documented local regression result:

```text
98 passed
```

The new conditional orchestration regression suite adds coverage for evidence-before-action ordering, target evaluation before action, satisfied-target no-op behavior, unsatisfied-target action execution, evaluation failure blocking, and duplicate target evaluation rejection. A new full-suite run is required before the next merge.

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
- Do not allow malformed tool arguments to cross the executor boundary.
- Keep production-environment-specific logic behind appropriate agent/tool boundaries.
- Preserve working components and improve incrementally.
- Keep `README.md`, `ATLAS_HANDOFF_CONTEXT.txt`, and `DEVELOPMENT_LOG.md` synchronized with verified milestones and test results.

For the detailed technical record, see `ATLAS_HANDOFF_CONTEXT.txt` and `DEVELOPMENT_LOG.md`.
