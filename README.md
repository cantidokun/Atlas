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

Atlas keeps an **evidence ledger**. Every successful tool result is recorded there.

### 2. Final-answer checking

A Python validator checks Qwen's proposed answer against the evidence. For example, if the tool says `symmetric_about_origin = false`, Atlas will reject an answer that says the objects are symmetric about the world origin.

The validator was also fixed so it does not mistake phrases such as **"not confirmed"** for a positive confirmation.

### 3. Evidence planning

Atlas now gives Qwen a way to request a specific piece of missing evidence.

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

This is the first version of the **General Evidence Planner** from the roadmap. It is still limited and needs more testing.

### 4. A real controller state machine

We also built a separate controller for authorized modification tasks.

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

For the current midpoint task, Atlas must measure the starting relationship, calculate the target, move both authorized objects, inspect the relationship again, and only then report success.

A successful first move is **not** enough to mark the task complete. A failed write also does not count as a completed step.

This is an important change because Python, not Qwen, now owns the required sequence.

---

# Roadmap status

## Stage 1 — Basic Blender Agent

**Status: COMPLETE**

Atlas can connect to Blender, inspect objects, use tools, and communicate with the local reasoning model.

## Stage 2 — Reliable Evidence

**Status: COMPLETE**

Atlas records successful tool results and uses them as the evidence base for its answers. It also has factuality rules and a final-answer validator.

## Stage 3 — Mandatory Evidence Acquisition

**Status: COMPLETE**

Prompt instructions alone were not enough. Qwen could say that it needed an inspection and then answer without actually doing it. We solved this by putting mandatory acquisition in Python.

## Stage 4 — Evidence Validation and Recommendation Restraint

**Status: COMPLETE**

Atlas passed the recommendation-restraint test. It can measure an offset without automatically calling it an error or inventing outside requirements.

## Stage 5 — General Evidence Planner

**Status: IN PROGRESS**

The first planner exists. It lets Qwen request a specific missing piece of evidence, lets Python check whether that request is already satisfied, and runs an available tool when it is not.

The next work is to test this with more task types and make sure the planner works as a normal part of the main agent loop.

## Stage 6 — Reliable Modification Control

**Status: CORE PIECES BUILT / MAIN LOOP INTEGRATION NEXT**

We have built:

- controller state
- target calculation
- required-write tracking
- write-result tracking
- post-write verification
- completion gates
- controller runtime
- an adapter between the controller and the existing agent design

The remaining job is to connect that adapter to the main `agent.py` tool-execution boundary and run the full task end-to-end.

---

# What just happened

The latest work focused on making Atlas safer and more reliable when it changes Blender files.

We first added a state machine. Then we added tests. Then we tightened the completion rules so Atlas cannot call a task complete while required writes are still missing.

We then built a small runtime that can execute the next required controller action without asking Qwen to decide the order.

Finally, we added a small bridge that is designed to connect that runtime to the existing agent loop without replacing the evidence ledger or final-answer validator.

We are deliberately doing this in small pieces instead of rewriting the whole agent.

---

# What should happen next

### 1. Connect the controller bridge to `agent.py`

This is the immediate next step. The current agent already has a tool loop, evidence ledger, authorization checks, and final-answer validation. We should add the bridge at the tool-execution boundary instead of replacing those systems.

### 2. Run the full midpoint test

Atlas should be able to inspect the BEFORE state, calculate the TARGET, perform both required moves, perform the AFTER inspection, confirm the midpoint is exactly `[0.0, 0.0, 0.0]`, and produce a final answer that matches the evidence.

### 3. Test failure cases

We should test:

- first move fails
- second move fails
- verification is skipped
- Qwen tries to finish early
- Qwen asks for an unrelated write
- a tool returns an error

Atlas should fail safely in each case.

### 4. Generalize the controller

Once the midpoint task works end-to-end, the controller should be generalized beyond goalposts.

The long-term pattern is:

```text
BEFORE → TARGET → ACTIONS → AFTER → COMPLETE
```

The user's request and the evidence planner should determine what those actions are.

### 5. Expand the General Evidence Planner

After the controller is stable, test the planner with different questions and evidence needs.

The planner should answer:

1. **Do we already know this?**
2. **Can an existing tool find it?**
3. **If not, do we actually need a new tool?**

Only the third case should lead us to consider building a new Blender capability.

---

# The bigger goal

Atlas is not supposed to be a chatbot that only talks about Blender.

The goal is an agent that can **inspect an environment, gather evidence, reason about that evidence, make authorized changes, verify those changes, and give a factual answer.**

The system is split on purpose:

- **Qwen is good at reasoning.**
- **Python is good at control and state.**
- **Blender tools provide the evidence.**

Together, they form the Atlas architecture.

---

## Current status in one sentence

**Atlas can already inspect Blender scenes, gather and validate evidence, reason without inventing facts, and has the core pieces for controlled modifications; the next major task is to connect the controller to the main agent and prove the full modification loop end-to-end.**

For the full technical history, see `ATLAS_HANDOFF_CONTEXT.txt`.
