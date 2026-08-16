# Atlas

## What Atlas is

Atlas is a local agent for inspecting and changing Blender files.

It has two main parts:

- **Qwen** thinks, reasons, and helps choose what evidence is needed.
- **Python** runs tools, tracks state, controls required actions, checks evidence, and controls completion.

The key rule is:

> **Qwen can reason, but Python controls what actually happened.**

---

# Where Atlas is now

Atlas is past the basic proof-of-concept stage.

It can now:

- connect to Blender
- connect to local Qwen through Ollama
- inspect Blender scenes
- run approved Blender write tools
- handle tool errors
- keep an evidence ledger
- ask for missing evidence
- validate factual claims in final answers
- avoid unsupported recommendations
- control a required multi-step modification
- verify the Blender state after a modification
- build a final report from verified evidence

The current controller has been run against the real local Blender and Qwen setup.

The real modification worked.

The first live run found one problem: Qwen kept trying to improve the final answer after the Blender work was already complete. Atlas now has a Python finalization path for controller-owned tasks so that verified work can finish without wasting more reasoning steps.

---

# Current test

The main test file is:

`goalpost_test.blend`

The test uses:

- `Goal_Left_post`
- `Goal_Right_Post`

The live BEFORE state was:

```text
Goal_Left_post  = [0.0, 5.302, 0.0]
Goal_Right_Post = [0.0, -5.164, 0.0]
Midpoint        = [0.0, 0.069, 0.0]
```

Atlas calculated the required movement:

```text
Adjustment      = [0.0, -0.069, 0.0]
Goal_Left_post  = [0.0, 5.233, 0.0]
Goal_Right_Post = [0.0, -5.233, 0.0]
```

The final Blender inspection proved:

```text
Goal_Left_post  = [0.0, 5.233, 0.0]
Goal_Right_Post = [0.0, -5.233, 0.0]
Midpoint        = [0.0, 0.0, 0.0]
Distance        = 10.466 units
Symmetric       = true
```

So the real controller sequence passed:

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
CORRECT FINAL STATE
```

---

# What we have built

## Evidence ledger

Atlas saves successful tool results as evidence.

Qwen receives this evidence when it reasons again. This helps prevent the model from guessing facts that Atlas has already measured.

## Final-answer validator

Python checks the proposed answer against the evidence.

It can reject things such as:

- unsupported measurements
- false symmetry claims
- unsupported soccer classifications
- missing required task information
- missing BEFORE, TARGET, or FINAL information

## General Evidence Planner V1

The first version can find a specific evidence gap and request an existing tool when that evidence is missing.

It is still being expanded.

## Controller state machine

The current controller follows:

```text
BEFORE
  ↓
TARGET
  ↓
WRITE A
  ↓
WRITE B
  ↓
AFTER
  ↓
COMPLETE
```

Python owns this order.

Qwen does not get to declare the task finished after only one required write.

## Live controller entrypoint

`run_agent_with_controller.py` connects the controller to the existing Atlas reasoning loop.

It lets Python take over when a mandatory controller action is required, while normal reasoning still goes through Qwen.

## Deterministic finalization

`controller_finalization.py` builds a complete final report when:

- BEFORE evidence exists
- the required writes succeeded
- a separate FINAL inspection exists
- the required final state is proven

The report separates:

```text
INITIAL MEASURED STATE
CALCULATED TARGET STATE
FINAL VERIFIED STATE
```

The vector formatter also prevents values such as `-0.000` from appearing in final reports.

---

# Test status

The local offline suite now passes:

```text
24 passed
```

The tests cover the controller, integration, runtime, entrypoint, and finalization behavior.

A regression test also makes sure negative zero cannot return to the final report.

GitHub Actions has been added to run the offline tests on pushes and pull requests.

---

# Roadmap

## Stage 1 — Basic Blender Agent

**COMPLETE**

Atlas can connect to Blender, inspect it, use tools, and communicate with Qwen.

## Stage 2 — Reliable Evidence

**COMPLETE**

Atlas has an evidence ledger, factuality rules, and final-answer validation.

## Stage 3 — Mandatory Evidence Acquisition

**COMPLETE**

Python can require evidence instead of trusting Qwen to remember to request it.

## Stage 4 — Evidence Validation and Recommendation Restraint

**COMPLETE**

Atlas can separate a measured fact from an unsupported recommendation.

## Stage 5 — General Evidence Planner

**IN PROGRESS**

The first planner exists.

Next work includes:

- more task types
- more evidence-gap tests
- stronger integration
- better rules for deciding whether existing evidence is enough

## Stage 6 — Reliable Modification Control

**CONTROLLER PROVEN ON THE LIVE GOALPOST TEST**

The real Blender modification and independent verification passed.

The final-answer recovery path has also passed the local offline suite.

The remaining local gate is to rerun the complete live controller entrypoint with the new finalization code.

## Stage 7 — General Action Planning

**NEXT AFTER LIVE REGRESSION**

The controller must become task-neutral.

The target design is:

```text
Task
 ↓
Required evidence
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

# What happens next

The next local test is:

```powershell
python -m pytest -q
```

This has already passed with 24 tests on the current local checkout.

The next required live test is:

```powershell
python .\run_agent_with_controller.py
```

The test should start from a restored `goalpost_test.blend` so the BEFORE state is known.

The expected flow is:

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
Python final report
      ↓
Clean exit
```

If that passes, development can continue toward general action planning without another local test until we reach another Blender or Ollama integration boundary.

---

# Current local environment

The verified local setup is:

```text
Python 3.9.6
Ollama 0.32.13
qwen3:8b
Blender 4.4
```

Atlas uses:

```text
http://localhost:11434/api/chat
```

The Blender executable is:

```text
C:\Program Files\Blender Foundation\Blender 4.4\blender.exe
```

---

# The bigger goal

Atlas is being built to follow this loop:

**inspect → gather evidence → reason → act → verify → report**

Qwen provides flexible reasoning.

Python provides control and state.

Blender provides the real environment and measured evidence.

The goal is a system that can perform useful Blender work without guessing what happened.

For the full technical handoff, see `ATLAS_HANDOFF_CONTEXT.txt`.
