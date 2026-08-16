# Atlas Development Log

## August 16, 2026 — Controller Integration

### Goal
Move mandatory modification sequencing from Qwen into Python control.

### Work completed

1. Built `controller_state.py`.
   - Tracks BEFORE, TARGET, WRITE, AFTER, and COMPLETE.
   - Calculates target positions from measured evidence.
   - Requires all required writes before verification can complete.

2. Built `controller_runtime.py`.
   - Executes one controller-owned action at a time.
   - Does not ask Qwen to choose the order of mandatory actions.

3. Built `controller_bridge.py`.
   - Detects the current authorized midpoint workflow.
   - Connects the runtime to the existing agent design.
   - Hydrates the controller from relationship evidence already collected by the main agent.

4. Built `controller_execution_adapter.py`.
   - Mirrors controller-owned results into the existing tool history and evidence ledger.
   - Provides a small boundary for the live agent to call.
   - Syncs the controller's BEFORE state from the existing evidence ledger.

5. Added `controller_integration.py`.
   - Provides the final integration boundary for the live agent.
   - Lets Python decide when Qwen must temporarily give up control of the mandatory action sequence.
   - Uses the same tool executor and evidence state as the existing agent loop.

6. Added controller integration tests.
   - Confirms Python takes control after BEFORE evidence exists.
   - Confirms the first and second writes are selected in order.
   - Confirms one write cannot mark the task complete.
   - Confirms a failed write does not advance the controller.

### Important discovery

During integration work, we found that the controller could be activated after the main agent had already collected BEFORE evidence, but the controller itself did not yet know about that evidence.

That would have caused it to repeat the initial inspection instead of immediately taking over at the correct point.

Evidence hydration was added to `controller_bridge.py`. The controller can now start from the verified BEFORE state already stored by Atlas.

### Live-agent integration

The next problem was how to connect the controller to the existing `agent.py` without rewriting its large reasoning loop.

We added `run_agent_with_controller.py` as a thin live entrypoint.

It loads the existing `agent.py`, checks its structure, and inserts a controller hook immediately before the existing Ollama/Qwen request. This means:

```text
Existing agent.py
      ↓
Controller hook
      ↓
Is mandatory controller work still required?
      ↓
YES → Python executes the required action
NO  → Qwen runs normally
```

Controller results are added to the same evidence ledger and tool history used by the existing agent. A synthetic assistant tool request is also added so the controller-generated tool result stays valid conversation history for Ollama/Qwen.

This gives us a real live-agent integration path without duplicating the entire agent loop.

### Local environment verification

The live test confirmed the local environment is usable:

- Python 3.9.6
- Ollama 0.32.13
- `qwen3:8b`
- Blender 4.4
- Atlas Blender tool execution

### Live end-to-end result

The real `goalpost_test.blend` file was inspected before modification.

BEFORE:

```text
Goal_Left_post  = [0.0, 5.302, 0.0]
Goal_Right_Post = [0.0, -5.164, 0.0]
Midpoint        = [0.0, 0.069, 0.0]
```

The controller calculated:

```text
Adjustment      = [0.0, -0.069, 0.0]
Goal_Left_post  = [0.0, 5.233, 0.0]
Goal_Right_Post = [0.0, -5.233, 0.0]
```

Both `move_object` writes executed successfully.

A separate `inspect_object_relationship` call then verified:

```text
Goal_Left_post  = [0.0, 5.233, 0.0]
Goal_Right_Post = [0.0, -5.233, 0.0]
Midpoint        = [0.0, 0.0, 0.0]
Distance        = 10.466 units
Symmetric       = true
```

This proves the controller can complete the tested multi-write modification sequence against a real Blender file.

### Failure found after successful modification

The first Qwen final answer did not include all required temporal evidence.

The evidence validator correctly rejected it because it was missing:

- BEFORE positions
- BEFORE midpoint
- TARGET positions
- positional adjustment
- FINAL VERIFIED state

Qwen then requested another relationship inspection even though the required final evidence was already available. The final inspection was correct, but the run reached the maximum reasoning-step limit before Qwen produced an accepted final answer.

Important conclusion:

**The Blender modification and verification succeeded. The remaining failure was final-answer recovery.**

### Finalization fix

Added:

`controller_finalization.py`

This module builds a deterministic final report from the authoritative evidence ledger when a controller-owned midpoint task has completed.

It requires:

- a BEFORE relationship snapshot
- successful `move_object` writes
- a complete FINAL relationship snapshot
- final midpoint exactly `[0.0, 0.0, 0.0]`

The report explicitly separates:

```text
INITIAL MEASURED STATE
CALCULATED TARGET STATE
FINAL VERIFIED STATE
```

The live entrypoint now stops cleanly after a completed controller task instead of spending another Qwen reasoning cycle trying to rediscover the final answer.

### Formatting hardening

The first finalization regression exposed a harmless but real formatting issue: Python could render mathematically zero values as `-0.000`.

The vector formatter now normalizes values that round to zero before display.

A dedicated regression test was added so a future change cannot reintroduce negative zero into final reports.

### Tests added

`test_controller_entrypoint.py` checks the deterministic finalization hook.

`test_controller_finalization.py` checks:

- complete state-aware final report generation
- no negative zero in final reports
- refusal to finalize without post-write verification
- refusal to finalize when the final midpoint is wrong

The local offline suite now passes:

```text
24 passed in 0.06s
```

A GitHub Actions workflow was also added at:

`.github/workflows/tests.yml`

The workflow is intended to run the offline suite on pushes and pull requests. The latest local pass is the current authoritative test result; no hosted CI run has been confirmed in this handoff yet.

### Current gate

The offline architecture is now green.

The next required test is local and live:

```text
python .\run_agent_with_controller.py
```

The test must use a restored copy of `goalpost_test.blend` so the controller starts from the known BEFORE state.

The expected new behavior is:

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
Deterministic final report
      ↓
Clean exit
```

After that passes, development can continue without another local test until a new Blender/Ollama integration boundary is reached.

### Next architecture step

After the live regression passes, generalize the controller pattern into a task-neutral action plan:

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

Do not add another goalpost-specific rule or Blender write tool merely to solve this test.
