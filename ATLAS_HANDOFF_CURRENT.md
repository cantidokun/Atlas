# Atlas Current Development Handoff

**Updated:** September 2, 2026 — active Atlas development
**Blender continuation branch:** `feat/blender-stage11-mainline`
**Blender Stage 11 PR:** #49 — controlled live mutation harness
**Latest Blender branch HEAD:** `1b226df40e3f89f44e209ab2654e546a102248e0`

## Current state

Atlas is advancing on two independent execution-environment tracks: Blender and Unreal. The authority model remains unchanged:

```text
Qwen / AI
  -> reason and propose

Python / Atlas
  -> validate, authorize, execute, track state, verify, recover

Blender / Unreal
  -> controlled production execution

Independent verification
  -> establish what actually happened
```

Qwen never receives direct production execution authority.

Atlas development now has standing authorization to run the appropriate local tests, GitHub Actions workflows, action-runner tests, and relevant live validation required by the development task. Workflow execution no longer requires a separate per-run user authorization.

## Blender — verified September 1 milestones

The first controlled real Blender mutation has been **proven locally** through the Atlas execution boundary.

Controlled live movement proof:

```text
Blender:          4.4
operation:        move_object
object:           Goal_Left_post
before:           [0.0, 5.302, 0.0]
after:            [0.25, 5.302, 0.0]
authorization:    atlas-stage11-live-mutation
```

Controlled live rotation proof:

```text
Blender:          4.4
operation:        set_object_rotation
object:           Goal_Left_post
before:           [0.0, 0.0, 0.0]
after:            [0.0, 0.0, 15.0]
authorization:    atlas-stage12-live-rotation
execution_receipt: verified
persistence_evidence: verified
fixture_restored: [0.0, 0.0, 0.0]
```

Both live paths launched real Blender, wrote the `.blend`, performed fresh independent inspection, compared expected and observed state, and restored the fixture where mutation testing was used.

The reusable Blender execution boundary now exposes a closed-loop primitive that returns the operation result, execution receipt, independent inspection result, and persistence evidence together. It deliberately does **not** create authorization; authorization remains owned by the planning layer.

Persistence evidence fails closed when inspection is unsuccessful or expected and observed state differ.

## Stage 12 — Closed-loop Blender Agent

**IN PROGRESS**

Source audit confirmed that the reusable closed-loop mutation boundary already existed, so no duplicate mutation layer was added.

The missing integration identified by the audit was narrower: the generic `AutonomousFutureRuntime` already persisted deterministic futures and continuation integrity, but it expected verification results to be supplied externally. Meanwhile `AtlasTaskDefinition` already held the authoritative evidence requests, target-state evaluator, action list, write policy, and verification policy.

A new task-level adapter now binds those existing systems:

```text
AtlasTaskDefinition
        ↓
initial authoritative evidence
        ↓
target-state evaluation
        ↓
explicit action authorization
        ↓
deterministic future generation
        ↓
AutonomousFutureRuntime checkpointing
        ↓
authorized Blender execution
        ↓
fresh task-defined evidence acquisition
        ↓
target-state verification
        ↓
COMPLETE or BLOCKED
```

Implemented in:

- `planning/autonomous_task_runtime.py` — task-aware bridge into the generic autonomous continuation runtime;
- `tests/test_autonomous_task_runtime.py` — focused coverage for authorized mutation, zero-write behavior, and failed fresh verification.

The adapter does not add engine-specific logic to `AutonomousFutureRuntime`, does not replace `BlenderExecutionBoundary`, and does not create a second authorization or receipt system.

## Blender roadmap

### Stage 1 — Basic Blender Agent
**COMPLETE**

### Stage 2 — Reliable Evidence
**COMPLETE**

### Stage 3 — Mandatory Evidence Acquisition
**COMPLETE**

### Stage 4 — Evidence Validation and Recommendation Restraint
**COMPLETE**

### Stage 5 — General Evidence Planner
**COMPLETE**

### Stage 6 — Reliable Modification Control
**COMPLETE**

### Stage 7 — General Action Planning
**COMPLETE**

### Stage 8 — Conditional Action Planning
**COMPLETE**

### Stage 9 — Qwen/Atlas Agent Reasoning Boundary
**COMPLETE FOR CURRENT CONTRACT**

### Stage 10 — Blender Adapter / Real Execution Bridge
**COMPLETE FOR CURRENT CONTROLLED WRITE PATH**

### Stage 11 — First Controlled Live Blender Operation
**COMPLETE — PROVEN LOCALLY**

### Stage 12 — Closed-loop Blender Agent
**IN PROGRESS**

### Immediate next gates

1. Keep the new task/runtime binding green across the full offline regression suite on Python 3.9 and 3.11.
2. Exercise the task-aware autonomous path against a real Blender fixture, not only fake executors.
3. Verify a real zero-write case and a real authorized-write case through the task definition path.
4. Verify a real failed postcondition produces `BLOCKED` without an automatic retry.
5. Extend continuation/recovery only where the current architecture demonstrates a real gap; do not duplicate existing receipt, authorization, or future-state infrastructure.

## Unreal — verified September 1 milestone

The local Unreal Engine 5.6 production boundary has also been exercised end to end.

Verified capabilities include:

- deterministic render configuration;
- render-state verification;
- Movie Render Queue submission;
- dynamic job-ID binding;
- asynchronous render-job inspection;
- completed-job semantic verification;
- MRQ output artifact discovery;
- filesystem artifact existence and non-zero-size validation;
- evidence-bound `UnrealRenderReceipt` creation;
- atomic `UnrealRenderReceiptStore` persistence and fail-closed reload validation.

The Unreal runtime job registry remains in-memory. Durable receipt persistence is on the Atlas/Python side. Cross-process recovery of Unreal runtime jobs has **not** been implemented.

## Required regression philosophy

Preserve coverage for:

- already-satisfied state -> zero writes;
- unsatisfied state -> exact authorized action order;
- successful write -> verification remains mandatory;
- verification failure -> `BLOCKED`;
- action failure -> recovery gate;
- mutated arguments/result -> receipt mismatch;
- malformed executor result -> rejected;
- wrong result tool -> rejected;
- invalid continuation identity -> rejected;
- authorized fresh-evidence replan -> accepted;
- unauthorized replan -> rejected;
- malformed Qwen reasoning -> rejected;
- unknown/non-capability tool -> rejected;
- Blender write without independent persistence evidence -> incomplete;
- Blender expected/observed persistence mismatch -> rejected;
- render job completion without artifacts -> rejected;
- declared render artifacts that do not exist -> rejected;
- tampered persisted render receipt -> rejected.

## Non-regression rules

- Never give Qwen direct production execution authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from a transport/write response alone.
- Keep engine-specific behavior behind adapter/tool boundaries.
- Preserve independent verification and the evidence ledger.
- Treat artifact existence as independently verified evidence, not an implication of job success.
- Do not claim cross-process Unreal render-job recovery unless it is separately implemented and verified.
- Preserve the canonical Digital Twin as distinct from Unreal, Blender, photogrammetry outputs, and temporary production artifacts.

## Resume point

Stage 11 live Blender proof is complete. Stage 12 is now being advanced through the task-aware autonomous runtime seam described above. The next meaningful proof is real Blender execution through `AtlasTaskDefinition` rather than another isolated mutation harness. Keep Unreal render-receipt integration as the parallel Unreal track. Workflow/action-runner execution is authorized as part of normal development; run the relevant validation needed for each meaningful implementation increment.
