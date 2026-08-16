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

The most important recent change is that **mandatory modification steps are moving out of Qwen's control and into Python**.

---

# The test we are using

Our main test file is:

`goalpost_test.blend`

Important objects:

- `Goal_Left_post`
- `Goal_Right_Post`

The measured starting midpoint is:

`[0.0, 0.138, 0.0]`

The task requires the midpoint to become:

`[0.0, 0.0, 0.0]`

This is a useful test because Atlas must:

1. inspect the file
2. measure the relationship
3. calculate the required change
4. perform the required writes
5. inspect the file again
6. prove the final result
7. report only what the evidence supports

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

The validator also handles negative wording correctly, so phrases such as **"not confirmed"** are not mistaken for positive confirmation.

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

It also hydrates the controller from BEFORE evidence that the main agent already collected. This prevents the controller from repeating an inspection unnecessarily.

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

This gives us a real live integration path without copying the whole agent loop into a second implementation.

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

**Status: INTEGRATION BUILT / REAL BLENDER TEST NEXT**

The controller system and live entrypoint now exist.

Built pieces include:

- state machine
- target calculation
- required-write tracking
- write-result tracking
- post-write verification
- completion gates
- controller runtime
- execution adapter
- live-agent integration entrypoint
- integration tests

We still need to run the live entrypoint against the real local Ollama + Blender setup. Until that passes, Stage 6 is not complete.

---

# What just happened

The recent development had one main goal: make Atlas control real Blender changes more reliably.

First, we built the controller state machine.

Then we built the runtime that can execute the next required action.

Then we added an adapter between that controller and the rest of Atlas.

Then we added a live entrypoint that places the controller into the existing Qwen reasoning loop without rewriting the whole agent.

We also fixed an important evidence problem: the controller can now start from BEFORE evidence already collected by Atlas instead of repeating the first inspection.

The remaining proof is now an actual run against the user's local environment.

---

# What should happen next

## 1. Run the live controller entrypoint

Run `run_agent_with_controller.py` in the local Atlas environment.

The expected flow is:

```text
Qwen gathers BEFORE evidence
        ↓
Python controller takes over
        ↓
Move Goal_Left_post
        ↓
Move Goal_Right_Post
        ↓
Inspect relationship again
        ↓
Verify midpoint = [0.0, 0.0, 0.0]
        ↓
Qwen produces final report
```

## 2. Test failure cases

We should deliberately test:

- first move fails
- second move fails
- verification fails
- Qwen tries to finish early
- Qwen asks for an unrelated write
- a tool returns an error
- the scene is already correct before any write

Atlas should fail safely or take the correct next action in each case.

## 3. Promote the hook into `agent.py`

Once the live entrypoint passes, move the controller hook into the permanent `agent.py` loop.

This removes the temporary compatibility entrypoint and makes controller support part of the normal Atlas agent.

## 4. Generalize the controller

Once the live midpoint test passes, generalize the controller beyond goalposts.

The long-term pattern is:

```text
BEFORE → TARGET → ACTIONS → AFTER → COMPLETE
```

The user's request and evidence should determine what those actions are.

## 5. Expand the General Evidence Planner

After the controller is stable, test the planner with different kinds of Blender questions.

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

**Atlas now has a live controller integration path; the next major step is to run it against the real local Ollama + Blender environment and prove the complete modification loop.**

For the full technical handoff, see `ATLAS_HANDOFF_CONTEXT.txt`.
