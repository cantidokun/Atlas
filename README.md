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

We have now added a small adapter that connects the controller to the existing Atlas architecture.

The adapter is designed to mirror controller-owned tool results into the normal:

- tool execution history
- evidence ledger

This lets us keep the existing reasoning loop and final-answer validator instead of rewriting them.

The adapter has its own tests.

**Important:** the adapter exists and is tested, but the live `agent.py` tool boundary has **not yet been wired to call it**. That is the next implementation step.

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
- stronger integration with the main agent loop
- clearer rules for when an existing tool is enough
- a clean path for deciding when a new tool is actually needed

## Stage 6 — Reliable Modification Control

**Status: CORE SYSTEM BUILT / LIVE AGENT INTEGRATION NEXT**

The core controller pieces now exist:

- state machine
- target calculation
- required-write tracking
- write-result tracking
- post-write verification
- completion gates
- controller runtime
- execution adapter
- adapter tests

What is still missing is the final connection from the adapter into the live `agent.py` tool-execution boundary.

We should **not** call Stage 6 complete until the live agent passes the full Blender test.

---

# What just happened

The recent development had one main goal: make Atlas control real Blender changes more reliably.

First, we built the controller state machine.

Then we built the runtime that can execute the next required action.

Then we added an adapter between that controller and the rest of Atlas.

The adapter is intentionally small. It does not replace Qwen, the evidence ledger, or the final validator.

The next step is to put that adapter directly into the existing tool-execution path in `agent.py`.

This is the point where the controller stops being an isolated subsystem and becomes part of the actual agent.

---

# What should happen next

## 1. Wire the adapter into `agent.py`

This is the immediate next step.

The current flow is roughly:

```text
Qwen requests tool
        ↓
agent.py executes tool
        ↓
result goes to ledger
        ↓
Qwen reasons again
```

We want:

```text
Qwen requests tool
        ↓
Python controller checks state
        ↓
Mandatory controller action?
      ↙        ↘
    YES         NO
     ↓           ↓
Controller    Normal tool
chooses it     execution
     ↓           ↓
     └─────┬─────┘
           ↓
     Evidence ledger
           ↓
          Qwen
```

The controller should only take control when the current task actually requires its workflow.

## 2. Run the full midpoint test

The live agent must prove that it can:

- collect the BEFORE relationship
- calculate the TARGET
- move `Goal_Left_post`
- move `Goal_Right_Post`
- perform the AFTER relationship inspection
- confirm the midpoint is exactly `[0.0, 0.0, 0.0]`
- produce a final answer supported by the evidence

## 3. Test failure cases

We should deliberately test:

- first move fails
- second move fails
- verification fails
- Qwen tries to finish early
- Qwen asks for an unrelated write
- a tool returns an error
- the scene is already correct before any write

Atlas should fail safely or take the correct next action in each case.

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

**Atlas can already inspect Blender scenes, gather and validate evidence, reason without inventing facts, and has the core system for controlled modifications; the next major step is wiring that controller into the live agent and proving the complete modification loop.**

For the full technical handoff, see `ATLAS_HANDOFF_CONTEXT.txt`.
