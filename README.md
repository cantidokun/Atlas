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

Atlas has passed the core real-world controller test.

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

The final state was obtained from a separate Blender relationship inspection, not from the write result alone.

---

# What just happened in the live test

The latest live run exposed one important integration bug.

The controller successfully completed the two writes and the final Blender inspection succeeded. The final inspection reported the correct positions, a zero midpoint, and `symmetric_about_origin = true`. fileciteturn162file0L45-L93

However, Atlas still gave control back to Qwen after the controller reached its completed state. Qwen then tried to write the final answer itself. The validator rejected that answer because it did not include the full BEFORE, TARGET, and FINAL VERIFIED timeline. Qwen repeated the inspection and eventually reached the reasoning-step limit. fileciteturn162file0L99-L109

This was not a Blender failure.

It was not a write failure.

It was not a verification failure.

It was an **entrypoint control-flow bug**.

The deterministic finalizer already existed, but the entrypoint only checked for finalization when a controller action was being executed. After the final verification action, the controller returned `kind = complete`, so the finalizer was skipped and Qwen got another turn.

That has now been fixed.

The completion check now runs even when the controller says it is already complete. The live path is intended to be:

```text
final verification
      ↓
controller = COMPLETE
      ↓
Python finalizer
      ↓
complete final report
      ↓
clean exit
```

---

# Offline tests

The previous local baseline was:

```text
24 passed
```

The new entrypoint change adds a regression test that checks that completion is finalized before the model can run again.

A fresh local test is required before the next live run.

Run:

```powershell
python -m pytest -q
```

Expected result:

```text
25 passed
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

**LIVE CONTROLLER PROVEN; FINAL EXIT FIX IN TESTING**

The real Blender modification and independent verification passed. The remaining live gate is to prove that the new completion path exits cleanly.

## Stage 7 — General Action Planning

**NEXT AFTER LIVE GATE**

Generalize:

```text
Task
 ↓
Evidence
 ↓
Action plan
 ↓
Action 1
 ↓
Update state
 ↓
Action 2
 ↓
Verify
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

The next local test is the offline suite:

```powershell
python -m pytest -q
```

If it passes, the next live test is:

```powershell
python .\run_agent_with_controller.py
```

Start the live test from the clean BEFORE Blender file.

The expected final behavior is:

```text
Qwen / evidence
      ↓
Python controller
      ↓
Write A
      ↓
Write B
      ↓
Independent verification
      ↓
Deterministic Python final report
      ↓
CLEAN EXIT
```

If that succeeds, Atlas can move on to general action planning without another local test until a new Blender/Ollama integration boundary is reached.

For the full technical record, see `ATLAS_HANDOFF_CONTEXT.txt` and `DEVELOPMENT_LOG.md`.
