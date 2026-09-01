# Atlas Current Development Handoff

**Updated:** September 1, 2026 — active Atlas development
**Blender continuation branch:** `feat/blender-stage11-mainline`
**Blender Stage 11 PR:** #49 — controlled live mutation harness
**Latest Blender branch HEAD:** `c4e2e473926ef18944390e1f9ce7520bf1382b4c`
**Latest known local full-suite result from the development PC:** **1033 passed, 5 skipped**

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

## Blender — verified September 1 milestone

The first controlled real Blender mutation has now been **proven locally** through the Atlas execution boundary.

Controlled live proof:

```text
Blender:          4.4
operation:        move_object
object:           Goal_Left_post
before:           [0.0, 5.302, 0.0]
after:            [0.25, 5.302, 0.0]
authorization:    atlas-stage11-live-mutation
```

The mutation launched a real Blender process, wrote the `.blend`, then performed a fresh independent Blender inspection. The persisted location matched the requested target. The fixture was then restored and independently verified at its original location.

The execution path now establishes:

```text
explicit authorization
        ↓
validated Blender action
        ↓
real Blender execution
        ↓
immutable execution receipt
        ↓
fresh Blender inspection
        ↓
expected vs observed state comparison
        ↓
immutable persistence evidence
        ↓
verified action completion
```

The reusable Blender execution boundary now exposes a closed-loop primitive that returns the operation result, execution receipt, independent inspection result, and persistence evidence together. It deliberately does **not** create authorization; authorization remains owned by the planning layer.

Persistence evidence fails closed when inspection is unsuccessful or expected and observed state differ.

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
**NEXT**

Stage 12 should build on the reusable closed-loop primitive rather than creating another one-off live harness. The next increment should remain controlled and deterministic: broaden the execution contract to support additional already-proven Blender capabilities while preserving explicit authorization, independent inspection, persistence evidence, and fail-closed behavior.

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
- Do not run workflow/action-runner tests without explicit authorization.

## Resume point

The Blender Stage 11 live gate is complete. Continue from the reusable closed-loop Blender execution boundary and begin Stage 12 with the smallest additional controlled capability that demonstrates genuine architectural progress. Keep Unreal render-receipt integration as the parallel Unreal track. Do not merge the Blender PR or invoke workflow/action-runner tests without explicit authorization.
