# Atlas

## What Atlas is

Atlas is a local Blender agent.

It follows this basic loop:

```text
inspect → gather evidence → reason → act → verify → report
```

Atlas uses two main parts:

- **Qwen** reasons about the task.
- **Python** controls tools, state, required actions, and verification.

The goal is simple: Qwen can reason, but Python keeps track of what really happened.

---

# Current status

Atlas has passed the first full real-world controller test.

It can now:

- connect to Blender
- connect to local Qwen through Ollama
- inspect Blender scenes
- record evidence
- use Blender write tools
- control a required multi-step modification
- require independent verification after writes
- validate final answers
- build a final report from verified evidence
- finish a completed controller task without giving control back to Qwen
- track a generic ordered action plan with Python

The current test asset is `goalpost_test.blend`.

The tested modification moved two objects so their midpoint became the world origin.

### Measured BEFORE state

```text
Goal_Left_post  = [0.0, 5.302, 0.0]
Goal_Right_Post = [0.0, -5.164, 0.0]
Midpoint        = [0.0, 0.069, 0.0]
```

### Calculated TARGET

```text
Goal_Left_post  = [0.0, 5.233, 0.0]
Goal_Right_Post = [0.0, -5.233, 0.0]
Adjustment      = [0.0, -0.069, 0.0]
```

### FINAL VERIFIED state

```text
Goal_Left_post  = [0.0, 5.233, 0.0]
Goal_Right_Post = [0.0, -5.233, 0.0]
Midpoint        = [0.0, 0.0, 0.0]
Distance        = 10.466 units
Symmetric       = true
```

The final state came from a separate Blender relationship inspection, not from the write result alone.

---

# What just happened

The latest live run completed the entire controller workflow on the real local setup.

The first final-answer attempt was rejected because Qwen did not include the full BEFORE, TARGET, and FINAL VERIFIED timeline. Atlas then obtained the missing final verification and Python built the final answer directly from the evidence.

The final report was:

```text
INITIAL MEASURED STATE
Goal_Left_post  = [0.000, 5.302, 0.000]
Goal_Right_Post = [0.000, -5.164, 0.000]
Midpoint        = [0.000, 0.069, 0.000]

CALCULATED TARGET STATE
Goal_Left_post  = [0.000, 5.233, 0.000]
Goal_Right_Post = [0.000, -5.233, 0.000]
Positional adjustment = [0.000, -0.069, 0.000]

FINAL VERIFIED STATE
Goal_Left_post  = [0.000, 5.233, 0.000]
Goal_Right_Post = [0.000, -5.233, 0.000]
Midpoint        = [0.000, 0.000, 0.000]
```

This proved that Python can take control of a mandatory modification, perform every required write, require an independent verification, and then finish the task without another Qwen reasoning cycle.

---

# Offline tests

The current local regression suite has passed:

```text
26 passed
```

The suite now includes tests for:

- controller state transitions
- required write ordering
- required post-write verification
- final-answer validation
- deterministic finalization
- controller completion before another model call
- negative-zero formatting
- generic ordered action plans

---

# New: General Action Planning V1

The goalpost controller proved that Python should own execution state for a multi-step task.

We are now generalizing that idea.

A new module is:

`action_plan.py`

It provides a small generic action-plan state machine.

An action plan contains ordered actions such as:

```text
Action 1
   ↓
Action 2
   ↓
Action 3
```

Python records each result and advances only after success.

If a required action fails, the plan becomes blocked instead of silently moving on.

The plan can also expose its current state for logging and evidence.

This module is deliberately separate from the goalpost controller. The goal is to avoid replacing one special-case controller with another special-case controller.

### Important limitation

General Action Planning V1 is currently a **primitive**, not yet the full Atlas planner.

It does not yet decide what actions a task needs.

That decision still requires task reasoning and evidence.

The next architecture work is to connect:

```text
Task understanding
      ↓
Evidence requirements
      ↓
Action plan
      ↓
Python-controlled execution
      ↓
Verification
```

---

# Roadmap

## Stage 1 — Basic Blender Agent

**COMPLETE**

Blender, tools, and Qwen/Ollama are connected.

## Stage 2 — Reliable Evidence

**COMPLETE**

Atlas keeps an evidence ledger and validates factual claims.

## Stage 3 — Mandatory Evidence Acquisition

**COMPLETE**

Python can require missing evidence instead of trusting Qwen to remember it.

## Stage 4 — Evidence Validation and Recommendation Restraint

**COMPLETE**

Atlas distinguishes measured facts from guesses and recommendations.

## Stage 5 — General Evidence Planner

**IN PROGRESS**

The first version exists. More task types and evidence-gap cases are still needed.

## Stage 6 — Reliable Modification Control

**COMPLETE FOR THE CURRENT CONTROLLER PATTERN**

The real Blender modification passed.

The final state was independently verified.

The deterministic finalizer completed the task cleanly.

The controller no longer depends on Qwen to decide when mandatory writes or final verification are finished.

## Stage 7 — General Action Planning

**IN PROGRESS**

The first generic action-plan primitive now exists.

The next goal is to make the action plan come from the task and evidence instead of hard-coding goalpost behavior.

Desired flow:

```text
Task
 ↓
Evidence needed
 ↓
Evidence ledger
 ↓
Action plan
 ↓
Action 1
 ↓
Update state
 ↓
Action 2
 ↓
...
 ↓
Independent verification
 ↓
Complete
```

This must not become another goalpost-specific rule.

---

# Local environment

The verified local setup is:

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

# Next step

The next development step is to connect the generic action-plan primitive to Atlas's existing evidence and authorization model without changing the proven live controller.

The current design should remain:

```text
Qwen = reasoning and interpretation
Python = execution state and safety gates
Blender tools = measured evidence and actions
```

We will first test this connection offline. No local Blender/Ollama test is needed until the new architecture reaches another live integration boundary.

For the full technical record, see `ATLAS_HANDOFF_CONTEXT.txt` and `DEVELOPMENT_LOG.md`.
