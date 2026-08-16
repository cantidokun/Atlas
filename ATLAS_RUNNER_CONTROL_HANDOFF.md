# Atlas Runner & Control Architecture Handoff

**Date:** 2026-08-16
**Repository:** cantidokun/Atlas
**Working branch:** `ai/level2-runner-setup`
**Purpose:** Preserve the current state, decisions, safety boundaries, and next steps for future Atlas development sessions.

## 1. Overall goal

Atlas is being developed toward an AI-assisted local development and production system for soccer-field digital twins. The long-term goal is for Atlas to reason about tasks, gather evidence, propose actions, execute only through trusted capabilities, verify results, recover from failures, and iterate with minimal manual computer operation by the user.

The user should remain the owner/final authority for major security, architecture, and machine-level changes, but should not have to manually run routine tests or act as the bridge between GitHub, the local LLM, Python, Blender, and the Windows PC.

Target loop:

```text
Task
  -> reasoning/planning
  -> evidence
  -> Python-side validation/authorization
  -> trusted tool dispatch
  -> execution
  -> independent verification
  -> correction/retry when appropriate
```

## 2. Runner status

A GitHub Actions self-hosted runner named `atlas-local` is installed and registered on the user's Windows PC.

Current runner labels:
- `self-hosted`
- `Windows`
- `X64`
- `local-win`

Runner location:
- `C:\actions-runner`

The runner was registered manually and is currently being run with:

```powershell
.\run.cmd
```

It was intentionally **not** installed as a Windows service yet. This keeps the setup reversible while the architecture is being validated.

### Future user action

After the control architecture is stable, install `atlas-local` as a Windows service so it starts automatically with Windows. This is a machine-level change and must be explained to the user before performing it.

## 3. Automatic local testing

The local test workflow is:

`.github/workflows/local-tests.yml`

Routine pushes to `ai/**` are configured to execute the Atlas offline test suite automatically on the `atlas-local` runner.

The test command is deliberately narrow:

```text
scripts/run-tests.ps1
    -> python -m pytest -q
```

The workflow uses `cmd.exe` as its GitHub Actions shell and explicitly starts PowerShell with:

```text
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ".\scripts\run-tests.ps1"
```

This was chosen because Windows PowerShell execution policy initially blocked GitHub's temporary PowerShell wrapper. The fix is process-level only; Windows-wide execution policy was not changed.

The runner has already successfully executed the Atlas suite locally. The latest relevant run before the current authorization fix reached 112 passing tests and 2 failures.

## 4. Important security decision

Do **not** give the local LLM unrestricted shell, Python, or Blender access.

The intended boundary is:

```text
Qwen/local LLM
   -> structured proposal
   -> Atlas validation
   -> evidence requirements
   -> trusted Python authorization
   -> trusted capability registry
   -> argument validation
   -> deterministic dispatcher
   -> Blender/tool execution
   -> independent verification
```

Core principle:

> Qwen reasons. Python decides. Trusted tools execute. Verification confirms.

The model must not be able to redefine whether a tool is read-only or write-capable.

## 5. Current control architecture

Important modules already present on `ai/level2-runner-setup` include:

- `task_planner.py`
- `task_plan_authorization.py`
- `task_execution.py`
- `task_runtime_bridge.py`
- `action_plan.py`
- `evidence_plan.py`
- `tools/dispatcher.py`
- existing controller/orchestration modules
- Qwen planning/evidence/action bridge modules

### Trusted authorization

`task_plan_authorization.py` sits between model planning output and executable planning state. It checks evidence completion, allowed tools, explicit write authorization, and—when supplied—trusted Python write-tool metadata.

### Trusted dispatcher

`tools/dispatcher.py` defines trusted capability sets.

Read-only tools currently include:
- `inspect_scene`
- `inspect_mesh`
- `inspect_scene_health`
- `inspect_scene_settings`
- `inspect_object_relationship`
- `inspect_soccer_components`

Write tools currently include:
- `create_collection`
- `create_empty_marker`
- `move_object`

The dispatcher validates the tool name, checks trusted capability, validates arguments against the registered Python function signature, and only then calls the registered function.

It must reject arbitrary tools/functions and deny write tools unless Python explicitly enables writes.

### Execution runtime

`task_execution.py` coordinates authorized evidence completion and deterministic action sequencing. It does not itself gain arbitrary process or Blender access; the actual executor is supplied by the caller.

It requires authorization before execution, executes one action at a time, records success/failure, blocks verification until all actions complete, and requires an independent successful verification before finalization.

## 6. Current known failing tests

The latest local runner result was:

```text
112 passed
2 failed
```

The two failures were:

1. `test_qwen_action_gate.py::test_valid_action_proposal_is_still_denied_by_default`
2. `test_task_execution.py::test_write_authorization_is_not_implicit`

The failure showed that one authorization path was still relying on the model-provided `requires_write` value when the trusted write registry was not explicitly supplied.

A fix was committed:

`01229f6 — Fix write authorization to use trusted capability registry`

The intended behavior is that trusted Python capability metadata, not Qwen output, determines whether a tool is a write operation.

**Do not assume the fix is green until the local GitHub Actions run confirms it.**

Expected target after the fix is all tests passing; the exact count should be taken from the actual run rather than hard-coded.

## 7. What has NOT been enabled yet

The following should remain outside the automatic routine-test runner until deliberately designed and approved:

- direct Ollama/Qwen execution from GitHub Actions
- arbitrary local shell commands
- unrestricted Python execution from model output
- real Blender write access from Qwen
- arbitrary filesystem access
- installation of software/packages
- access to credentials/secrets
- system configuration changes
- automatic merging to `main`

## 8. Next development sequence

### Immediate

1. Confirm the local test run after commit `01229f6`.
2. If failures remain, inspect the actual failing assertions and fix the control-layer bug rather than weakening the tests.
3. Add/finish dispatcher argument validation tests and trusted capability enforcement tests.
4. Ensure the full offline suite is green.

### Then

5. Build the simulated agent loop:

```text
Task
 -> structured Qwen-style proposal
 -> validation
 -> evidence
 -> authorization
 -> trusted dispatch
 -> simulated result
 -> verification
 -> final result
```

The simulated loop should not modify real Blender state.

6. Connect the local Qwen/Ollama model to the planning interface only after the simulated loop is proven.

7. Add a controlled Blender execution backend. Real Blender write access is a high-level security change and must be explained to the user before enabling it.

8. After the architecture is stable, convert `atlas-local` into a Windows service so the runner starts automatically.

9. Clean up PR #2, update its description to reflect the final architecture, verify all tests, and only then consider merging into `main`.

## 9. User interaction policy

The user explicitly wants a 6th-grade reading-level explanation whenever a high-level change requires their input.

Do not ask the user to run routine tests anymore; the runner is intended to remove that requirement.

Ask the user before:
- installing the runner as a permanent Windows service
- granting Atlas new filesystem/system access
- connecting Qwen/Ollama in a way that enables local execution
- granting real Blender write access
- changing security boundaries
- merging major architecture changes into `main`

For ordinary code changes and routine test failures, continue autonomously through GitHub and the self-hosted runner.

## 10. Long-term Atlas vision

The runner/control architecture is infrastructure for the broader Atlas goal, not the end product.

Long-term example:

```text
Soccer footage
 -> analysis/tracking
 -> field/digital-twin understanding
 -> task reasoning
 -> evidence gathering
 -> controlled Blender/VFX operations
 -> render/output inspection
 -> correction
 -> verified result
```

Atlas is exclusively concerned with soccer-field-related digital twins. Future VFX/cinematic capabilities include effects such as impact frames, smear frames, cinematic bleed, match-cut transformations, and environments temporarily behaving like water, smoke, glass, liquid metal, or other fluid-like materials.

The control architecture should remain general enough to support these production tasks while keeping execution bounded by trusted capabilities and independent verification.

## 11. Current status summary

```text
GitHub repository                 DONE
Self-hosted Windows runner        DONE
Automatic routine testing         DONE
Process-only PowerShell bypass    DONE
Evidence/control primitives       BUILT
Trusted capability registry       BUILT
Tool dispatcher                   BUILT / being hardened
Argument validation               BUILT / being hardened
Write authorization               BUILT / latest fix awaiting green test
Simulated agent loop              NEXT
Local Qwen/Ollama integration     LATER
Controlled Blender backend        LATER
Automatic Windows runner service  LATER
Main-branch integration           LATER
```

## 12. Handoff rule

When resuming this work, first inspect the current `ai/level2-runner-setup` branch and the latest Local Tests run. Do not rely on this handoff's stated test count if newer runs exist.

The first question should be:

> Did the local runner pass the latest control-layer tests after `01229f6`?

Then continue from the next incomplete item above.
