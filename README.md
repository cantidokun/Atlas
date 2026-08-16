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

Atlas has passed the first full real-world controller test and the first live Qwen structured-planning bridge test.

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
- track a generic ordered evidence plan with Python
- coordinate evidence completion before authorized action execution
- accept a structured Qwen evidence/action proposal without allowing that proposal to execute writes automatically

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

# What the live controller proved

The real local end-to-end controller workflow completed:

```text
BEFORE
 ↓
TARGET
 ↓
WRITE 1
 ↓
WRITE 2
 ↓
INDEPENDENT VERIFICATION
 ↓
PYTHON FINAL REPORT
 ↓
CLEAN EXIT
```

The first final-answer attempt from Qwen was incomplete. Atlas rejected it, acquired the missing final verification, and Python built the complete final report from authoritative evidence.

This proved that completion no longer depends on Qwen producing a perfect final answer after the Blender state is already verified.

---

# Offline tests

The latest local regression suite has passed:

```text
98 passed
```

The suite covers controller state transitions, required write ordering, post-write verification, final-answer validation, deterministic finalization, generic ordered action plans, generic ordered evidence plans, evidence-to-action orchestration, authorization boundaries, recovery behavior, and audit-trail ordering.

---

# General Action Planning V1

`action_plan.py` provides a generic action-plan state machine.

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

The plan can expose its current state for logging and evidence.

This module is deliberately separate from the goalpost controller. The goal is to avoid replacing one special-case controller with another special-case controller.

---

# Evidence Planning V1

`evidence_plan.py` provides a state machine for evidence requests.

An evidence plan can contain requests such as:

```text
Need scene information
        ↓
Need relationship information
        ↓
Evidence complete
```

Python tracks whether each request has been satisfied.

Evidence that is already known can be marked as `reused`, so Atlas can avoid running the same inspection again.

A failed required evidence request blocks the plan instead of letting the system pretend the evidence exists.

---

# Planning Orchestrator V1

`planning_orchestrator.py` connects the evidence plan and action plan:

```text
Evidence plan
     ↓
Evidence complete?
     ↓
Yes
     ↓
Authorized action plan
     ↓
Expose next action
```

The orchestrator blocks action execution until evidence is complete.

It can reuse evidence that is already known instead of running another tool.

If evidence acquisition fails, the orchestrator stays blocked.

If an authorized action fails, the action plan stays blocked.

---

# Qwen Structured Planning Bridge — PASS

`live_qwen_planning_loop.py` is the first live boundary between Qwen task planning and the generic Python planning primitives.

The verified flow is:

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
- authoritative read-only Blender evidence
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

This proves Qwen can now participate in structured planning without gaining direct control over execution.

---

# Controlled failure and recovery — PASS

The controlled failure harness proves that a failed write does not trigger an unsafe automatic retry.

The recovery decision requires:

```text
FAILED WRITE
 ↓
FRESH EVIDENCE REQUIRED
 ↓
NEW VALIDATED PLAN
 ↓
NEW EXPLICIT AUTHORIZATION
 ↓
RETRY
```

Automatic retry is refused after a failed write because execution state may have changed.

---

# Audit trail — PASS

The live action workflow records the lifecycle in order:

```text
Qwen proposal
 ↓
Evidence
 ↓
Authorization
 ↓
Execution 1
 ↓
Execution 2
 ↓
Verification
```

The final live test completed with an audit trail and independent verification.

---

# Architecture

Atlas separates three different questions:

```text
1. What do I need to know?
          ↓
   Evidence planning

2. What should I do?
          ↓
   Action planning

3. How do I know it worked?
          ↓
   Verification
```

That gives us the target loop:

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
 ↓
Final response
```

The evidence must support the action, the action must be authorized, and the resulting state must be verified.

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

The evidence-plan primitive and live evidence loop are working. The next step is deeper conditional evidence/action reasoning.

## Stage 6 — Reliable Modification Control

**COMPLETE FOR CURRENT CONTROLLER PATTERN**

The real Blender modification, independent verification, and deterministic completion path all passed.

## Stage 7 — General Action Planning

**IN PROGRESS**

The generic action-plan primitive, evidence-plan primitive, planning orchestrator, controlled recovery boundary, audit trail, and Qwen structured planning bridge are now proven.

The next goal is conditional action planning: determine from authoritative evidence whether the requested state is already satisfied before executing a proposed write.

## Stage 8 — Broader Autonomous Task Control

**NOT STARTED**

This comes only after the generic planner is stable.

---

# Next development target

The next test should prove that Atlas avoids an unnecessary write when authoritative evidence already shows the requested state is satisfied.

Desired behavior:

```text
Task
 ↓
Structured evidence requirements
 ↓
Evidence ledger
 ↓
Determine whether target already holds
 ↓
Already satisfied? → skip write
 ↓
Not satisfied? → retain authorized action plan
 ↓
Python-controlled execution
 ↓
Independent verification
 ↓
Completion
```

After that boundary is stable, test a case where a write is genuinely required.

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

# Development rules

- Do not rewrite the entire agent.
- Do not remove the evidence ledger.
- Do not remove independent post-write verification.
- Do not make goalpost behavior the generic architecture.
- Do not add tools without proving a real capability gap.
- Do not let a successful Blender state depend on a perfect Qwen final answer.
- Do not allow an action plan to execute without explicit authorization.
- Preserve working components and improve incrementally.
- Keep `README.md`, `ATLAS_HANDOFF_CONTEXT.txt`, and `DEVELOPMENT_LOG.md` synchronized with verified milestones and test results.

For the full technical record, see `ATLAS_HANDOFF_CONTEXT.txt` and `DEVELOPMENT_LOG.md`.
