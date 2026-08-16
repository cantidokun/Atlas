# Atlas

## What Atlas is

Atlas is an agent that can inspect and change Blender files.

It uses two main parts:

- **Qwen**: thinks about the user's request and decides what information is needed.
- **Python**: controls tools, tracks what was proven, controls required actions, and checks the final answer.

The main idea is simple:

> **Qwen can reason, but Python controls what actually happened.**

---

# Where we are now

Atlas is past the basic proof-of-concept stage.

It can already:

- connect to Blender
- connect to the local Qwen model through Ollama
- inspect Blender scenes
- use approved Blender write tools
- handle tool errors
- keep an evidence ledger
- make Qwen use the evidence ledger when reasoning
- request missing evidence through the first version of the General Evidence Planner
- check final answers against measured evidence
- avoid unsupported recommendations
- track the state of an authorized modification
- calculate required target positions
- track required writes
- require a separate post-write verification
- run the controller inside the real Qwen/Ollama + Blender loop
- complete the tested two-write goalpost modification on a real Blender file

The most important recent change is that **mandatory modification steps are now controlled by Python instead of being left entirely to Qwen.**

A live test also found a final-answer problem. The Blender work succeeded, but Qwen kept trying to improve its final answer until the reasoning-step limit was reached. We have now added a deterministic Python recovery path that can build the final state-aware report directly from verified evidence when a controller-owned task is complete.

---

# The test we are using

Our main test file is:

`goalpost_test.blend`

Important objects:

- `Goal_Left_post`
- `Goal_Right_Post`

The live test measured this starting state:

```text
Goal_Left_post  = [0.0, 5.302, 0.0]
Goal_Right_Post = [0.0, -5.164, 0.0]
Midpoint        = [0.0, 0.069, 0.0]
```

The task required the midpoint to become:

```text
[0.0, 0.0, 0.0]
```

Atlas calculated:

```text
Goal_Left_post  → [0.0, 5.233, 0.0]
Goal_Right_Post → [0.0, -5.233, 0.0]
Adjustment      → [0.0, -0.069, 0.0]
```

The live post-write inspection then measured:

```text
Goal_Left_post  = [0.0, 5.233, 0.0]
Goal_Right_Post = [0.0, -5.233, 0.0]
Midpoint        = [0.0, 0.0, 0.0]
Distance        = 10.466 units
Symmetric       = true
```

This is important because the final state was checked by Blender again. Atlas did not trust the write result alone.

---

# What we recently built

## 1. Evidence ledger

Every successful tool result is saved in an evidence ledger.

Qwen receives that ledger when it reasons again. This gives the model a clear record of what Atlas has actually measured.

## 2. Final-answer validator

Python checks the proposed answer against the evidence.

For example, if the relationship tool says:

`symmetric_about_origin = false`

Atlas will reject an answer that says the objects are symmetric about the world origin.

The validator also checks whether an answer contains the information required by the current task.

For modification tasks, it can require the answer to separate:

- initial measured state
- calculated target state
- final verified state

## 3. General Evidence Planner V1

Qwen can now identify a specific evidence gap and request a tool.

The basic flow is:

```text
Qwen identifies missing evidence
        ↓
Python checks the ledger
        ↓
Already known?
   ↓           ↓
  YES          NO
   ↓           ↓
Reason      Run a tool
               ↓
          Save the result
               ↓
          Qwen reasons again
```

This is the first version of the General Evidence Planner from the roadmap.

It is **not finished yet**. It still needs broader testing and better integration with different task types.

## 4. Controller state machine

We built a deterministic controller for the current authorized midpoint task.

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

Python owns this sequence.

Qwen cannot make one successful write and then decide that the task is finished.

## 5. Controller runtime

The runtime can execute the next required controller action without asking Qwen to choose the order.

It tracks:

- the measured BEFORE state
- the TARGET state
- successful writes
- failed writes
- the AFTER inspection
- completion

## 6. Controller execution adapter

We added a small adapter that connects the controller to the existing Atlas architecture.

The adapter mirrors controller-owned results into the normal:

- tool execution history
- evidence ledger

It also hydrates the controller from BEFORE evidence that the main agent already collected. This prevents the controller from repeating the first inspection unnecessarily.

## 7. Live controller entrypoint

We added:

`run_agent_with_controller.py`

This is a thin entrypoint that uses the existing `agent.py` reasoning loop but inserts the controller immediately before the Ollama/Qwen request.

The result is:

```text
Existing Atlas agent
        ↓
Controller checks state
        ↓
Mandatory action?
   ↓             ↓
 YES             NO
  ↓               ↓
Python acts     Qwen reasons
  ↓               ↓
Evidence ledger ←─┘
```

The controller-generated tool result is added back into the same conversation and evidence state used by Atlas.

## 8. Deterministic controller finalization

The live test showed that the actual Blender work could succeed while Qwen still got stuck trying to produce the perfect final answer.

We added:

`controller_finalization.py`

When a controller-owned modification is complete and the final relationship inspection proves the required state, Python can build a complete report from the evidence.

The report includes:

- initial measured positions
- initial midpoint
- calculated target positions
- positional adjustment
- final verified positions
- final verified midpoint
- final relationship facts

This prevents a successful Blender operation from being lost only because Qwen uses too many final reasoning steps.

This is a recovery path for controller-owned tasks. Normal non-controller tasks still use the normal Qwen final-answer validation path.

## 9. Offline regression tests

The controller has an offline test suite.

The current local test result before the latest finalization change was:

```text
20 passed
```

New tests now cover the deterministic finalization path as well.

A GitHub Actions workflow was also added so the offline test suite can run automatically on pushes and pull requests.

---

# Roadmap status

## Stage 1 — Basic Blender Agent

**Status: COMPLETE**

Atlas can connect to Blender, inspect objects, use tools, and communicate with Qwen.

## Stage 2 — Reliable Evidence

**Status: COMPLETE**

Atlas records successful tool results and uses them as evidence. It also has factuality rules and a final-answer validator.

## Stage 3 — Mandatory Evidence Acquisition

**Status: COMPLETE**

We learned that prompt instructions alone were not enough. Python now controls mandatory evidence acquisition.

## Stage 4 — Evidence Validation and Recommendation Restraint

**Status: COMPLETE**

Atlas passed the recommendation-restraint test. It can measure a geometric offset without inventing an outside standard or automatically calling the offset an error.

## Stage 5 — General Evidence Planner

**Status: IN PROGRESS**

The first planner exists and can request specific missing evidence.

Still needed:

- more task types
- more evidence-gap tests
- stronger integration with different tasks
- clearer rules for when an existing tool is enough
- a clean path for deciding when a new tool is actually needed

## Stage 6 — Reliable Modification Control

**Status: LIVE TEST PASSED FOR THE CURRENT MIDPOINT CONTROLLER**

The controller system and live entrypoint now exist and have been run against the real local Ollama + Blender setup.

The tested workflow successfully completed:

```text
BEFORE
  ↓
TARGET
  ↓
WRITE A
  ↓
WRITE B
  ↓
AFTER VERIFICATION
  ↓
COMPLETE
```

The remaining work is to make this pattern general rather than tied to the current midpoint task.

## Stage 7 — General Action Planning

**Status: NEXT**

The next goal is to generalize the controller pattern so Atlas can keep track of multiple required actions without making Qwen rediscover the plan after every action.

The desired pattern is:

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

This should be built without adding goalpost-specific rules.

---

# What just happened

The recent development had one main goal: make Atlas control real Blender changes reliably.

First, we built and tested the controller state machine.

Then we connected it to the existing Atlas agent.

We checked the real local setup:

- Python 3.9.6
- Ollama 0.32.13
- `qwen3:8b`
- Blender 4.4

All of those connections worked.

We then inspected the real Blender test file. The live BEFORE state was:

```text
Goal_Left_post  = [0.0, 5.302, 0.0]
Goal_Right_Post = [0.0, -5.164, 0.0]
Midpoint        = [0.0, 0.069, 0.0]
```

Atlas calculated the required common movement and the controller performed both writes.

A separate Blender inspection then proved that the final midpoint was exactly `[0.0, 0.0, 0.0]`.

So the **core controller and Blender execution path passed a real end-to-end test**.

The failure came after the successful modification. Qwen's first final answer did not include all required before/target/after information. The validator rejected it. Qwen then requested another verification even though the needed final evidence was already present, and the run eventually reached the maximum reasoning-step limit.

That exposed a finalization problem, not a Blender modification problem.

We have now added a deterministic Python finalization path for completed controller tasks. It builds the required state-aware final report directly from verified evidence.

---

# What should happen next

## 1. Run the updated offline test suite locally

This is the next required local test after the new finalization code is pulled.

It should confirm that the new finalization module and controller entrypoint still pass all tests.

## 2. Re-run the live controller test

Once the offline tests pass, run the live controller entrypoint again.

The important new behavior is:

```text
Controller completes
        ↓
Final verification exists
        ↓
Python builds final report
        ↓
Atlas stops cleanly
```

Qwen should no longer consume extra reasoning steps after a completed controller task.

## 3. Test failure cases

After the normal live test is stable, we should deliberately test:

- first move fails
- second move fails
- verification fails
- Qwen tries to finish early
- Qwen asks for an unrelated write
- a tool returns an error
- the scene is already correct before any write

Atlas should fail safely or take the correct next action in each case.

## 4. Generalize the action controller

Once the current controller is stable, generalize the pattern beyond goalposts.

The long-term pattern is:

```text
BEFORE → TARGET → ACTIONS → AFTER → COMPLETE
```

The user's request and evidence should determine what those actions are.

## 5. Expand the General Evidence Planner

After action control is stable, continue testing the planner with different kinds of Blender questions.

The planner should answer:

1. **Do we already know this?**
2. **Can an existing tool find it?**
3. **If not, do we actually need a new tool?**

Only the third case should lead us to build a new Blender capability.

---

# The bigger goal

Atlas is not supposed to be a chatbot that only talks about Blender.

The goal is an agent that can:

**inspect → gather evidence → reason → act → verify → report**

The system is split on purpose:

- **Qwen is good at reasoning.**
- **Python is good at control and state.**
- **Blender tools provide the evidence.**

Together, they form Atlas.

---

## Current status in one sentence

**Atlas has now proven the controller can make and independently verify a real Blender modification; the next local test is to confirm the new deterministic finalization path, then we can move toward general multi-action planning and the General Evidence Planner.**

For the full technical handoff, see `ATLAS_HANDOFF_CONTEXT.txt`.
