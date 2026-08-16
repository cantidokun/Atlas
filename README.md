# Atlas

## What Atlas is

Atlas is an agent that can inspect and change Blender files.

It uses two main parts:

- **Qwen**: thinks about the user's request and decides what information is needed.
- **Python**: controls the tools, keeps track of what was proven, and checks whether the final answer is allowed.

The main idea is simple: **Qwen can reason, but Python controls what actually happened.**

---

## Where we are now

Atlas is past the first major proof-of-concept stage.

The agent can already:

- connect to Blender
- connect to the local Qwen model through Ollama
- call Blender inspection tools
- call approved write tools
- handle tool errors
- keep an evidence ledger of successful tool results
- make Qwen use that evidence when reasoning
- check final answers for claims that disagree with the evidence
- ask for more evidence when an answer needs information that is not known yet
- avoid making recommendations when the evidence does not show that a change is needed

The most important recent progress is that we started moving **execution control out of Qwen and into Python**.

This matters because a language model can say that it wants to do something without actually doing it. Atlas now has a separate controller that can track the real steps of a modification task.

---

## The test we have been using

Our main test file is:

`goalpost_test.blend`

It contains two important objects:

- `Goal_Left_post`
- `Goal_Right_Post`

The current measured midpoint between them is:

`[0.0, 0.138, 0.0]`

The test requirement says the midpoint must be:

`[0.0, 0.0, 0.0]`

So the file gives us a good test for whether Atlas can:

1. inspect a Blender scene
2. understand a measured relationship
3. calculate a required change
4. make the change
5. check the result again
6. report only what was actually proven

---

## What we recently built

### 1. Evidence tracking

Atlas keeps an **evidence ledger**.

Every successful tool result is recorded there.

This means Qwen does not have to rely on memory alone. It receives the measured information that Atlas has already collected.

For example, if a relationship tool says the midpoint is `[0.0, 0.138, 0.0]`, that becomes verified evidence.

Atlas also knows not to call the same inspection again just because the model forgot that the result was already available.

### 2. Final-answer checking

We added a Python validator that checks Qwen's proposed answer against the evidence.

For example, if the tool says:

`symmetric_about_origin = false`

Atlas will reject an answer that says the objects are symmetric about the world origin.

The validator was also fixed so it does not mistake phrases such as **"not confirmed"** for a positive confirmation.

### 3. Evidence planning

Atlas now gives Qwen a way to request a specific piece of missing evidence.

The basic idea is:

```text
Qwen identifies an evidence gap
        ↓
Python checks the evidence ledger
        ↓
Is the evidence already known?
        ↓
   YES        NO
    ↓          ↓
Reason     Run an available tool
               ↓
          Add result to ledger
               ↓
          Qwen reasons again
```

This is the first version of the **General Evidence Planner** from the roadmap.

It is still limited and needs more testing.

### 4. A real controller state machine

We also built a separate controller for authorized modification tasks.

It tracks this sequence:

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

For the current midpoint task, that means Atlas must:

1. measure the starting relationship
2. calculate where each object needs to go
3. move the first authorized object
4. move the second authorized object
5. inspect the relationship again
6. only then report success

A successful first move is **not** enough to mark the task complete.

A failed write also does not count as a completed step.

This is an important change because Python, not Qwen, now owns the required sequence.

---

# Roadmap status

## Stage 1 — Basic Blender Agent

**Status: COMPLETE**

Atlas can connect to Blender, inspect objects, use tools, and communicate with the local reasoning model.

---

## Stage 2 — Reliable Evidence

**Status: COMPLETE**

Atlas now records successful tool results and uses them as the evidence base for its answers.

It also has factuality rules and a final-answer validator.

---

## Stage 3 — Mandatory Evidence Acquisition

**Status: COMPLETE**

We learned an important lesson here: prompt instructions alone were not enough.

Qwen could say, "I need to inspect this," and then answer without actually doing it.

We solved this by putting mandatory acquisition in Python.

This established one of Atlas's main design rules:

> **Qwen reasons. Python executes and controls state.**

---

## Stage 4 — Evidence Validation and Recommendation Restraint

**Status: COMPLETE**

Atlas passed the recommendation-restraint test.

The test showed that Atlas could measure an offset without automatically calling it an error.

It did not invent soccer rules or standard dimensions. It did not recommend moving the objects when the available evidence did not show that a move was required.

This is important because the goal is not for Atlas to change things just because it can.

---

## Stage 5 — General Evidence Planner

**Status: IN PROGRESS**

This is the current roadmap stage.

The goal is to remove task-specific logic such as:

```text
if two_goalposts:
    inspect_object_relationship()
```

and replace it with a general process:

```text
User request
    ↓
Qwen identifies needed evidence
    ↓
Python checks what is already known
    ↓
Python finds an existing tool that can get missing evidence
    ↓
Tool runs
    ↓
Evidence is saved
    ↓
Qwen reasons again
```

The first version of this planner now exists, but it needs to be connected more deeply to the main agent loop and tested with more than the current goalpost example.

---

## Stage 6 — Reliable Modification Control

**Status: PARTLY BUILT / NEXT INTEGRATION STEP**

We have built the controller pieces needed for this stage, including:

- controller state
- target calculation
- required-write tracking
- write-result tracking
- post-write verification
- completion gates
- tests for incomplete and complete states

What is still needed is to connect this controller cleanly to the main `agent.py` execution loop.

The goal is:

```text
Qwen asks for a tool
        ↓
Python checks the controller
        ↓
Is this an authorized task?
        ↓
YES → controller decides the next required action
        ↓
Python executes it
        ↓
State is updated
        ↓
Qwen gets the new evidence
```

This prevents Qwen from skipping a required write or claiming that a task is complete too early.

---

# What just happened

The latest development work focused on making Atlas more reliable when it changes a Blender file.

We first added a state machine. Then we added tests. Then we tightened the completion rules.

The controller now understands that **AFTER verification cannot happen while required writes are still missing**.

We also created a controller runtime that can execute the next required action instead of asking Qwen to decide the order of every mandatory step.

The next job is to connect that runtime to the existing agent without breaking the evidence ledger or final-answer validator.

We are intentionally doing this in small pieces instead of rewriting the whole agent.

---

# What should happen next

## 1. Connect the controller to `agent.py`

This is the immediate next step.

The current agent already has a large tool loop, evidence ledger, authorization checks, and final-answer validation.

We should add a small controller-aware execution layer rather than replacing all of that code.

The desired flow is:

```text
Qwen tool request
        ↓
Controller-aware execution layer
        ↓
Existing tool system
        ↓
Tool result
        ↓
Evidence ledger + controller state
        ↓
Qwen
```

## 2. Run the full midpoint test

Once connected, Atlas should complete the entire task without relying on Qwen to remember the required order.

We should verify that it can:

- inspect the BEFORE state
- calculate the TARGET
- perform both required moves
- perform the AFTER inspection
- confirm the midpoint is exactly `[0.0, 0.0, 0.0]`
- produce a final answer that matches the evidence

## 3. Test failure cases

We should then deliberately test things such as:

- the first move fails
- the second move fails
- verification is skipped
- Qwen tries to finalize early
- Qwen asks for an unrelated write
- a tool returns an error

Atlas should fail safely in each case.

## 4. Generalize the controller

Only after the midpoint test works end-to-end should we make the controller more general.

The long-term goal is not a special **goalpost controller**.

The goal is a system that can understand many tasks as:

```text
BEFORE → TARGET → ACTIONS → AFTER → COMPLETE
```

The exact number and type of actions should come from the user's request and the evidence planner.

## 5. Expand the General Evidence Planner

After the controller is stable, we can test the planner with different questions and evidence needs.

The planner should learn to answer three simple questions:

1. **Do we already know this?**
2. **Can an existing tool find it?**
3. **If not, do we actually need a new tool?**

Only the third case should lead us to consider building a new Blender capability.

---

# The bigger goal

Atlas is not supposed to be a chatbot that talks about Blender.

The goal is an agent that can **inspect an environment, gather evidence, reason about that evidence, make authorized changes, verify those changes, and give a factual answer.**

The important design choice is that no single part of the system gets to make all of those decisions alone.

**Qwen is good at reasoning.**

**Python is good at control and state.**

**Blender tools provide the evidence.**

Together, they form the Atlas architecture.

---

# Current status in one sentence

**Atlas can already inspect Blender scenes, gather and validate evidence, reason without inventing facts, and has the core pieces for controlled modifications; the next major task is to connect the new controller to the main agent and prove the full modification loop end-to-end.**

---

## Developer note

This README is intentionally written in simple language so that it can be used as a quick project status document.

For the full technical history and detailed handoff, see:

`ATLAS_HANDOFF_CONTEXT.txt`
