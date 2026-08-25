# Atlas Current Development Handoff

**Updated:** August 25, 2026 — current development checkpoint  
**Branch:** `feat/replan-race-gate`  
**Purpose:** canonical resume point for Atlas Blender-Agent development.

## Current verified milestone

The latest authoritative local validation reported in the development session is:

```text
FULL OFFLINE PYTEST SUITE: 652 passed, 0 failed
```

This fresh result superseded the earlier `622 passed / 30 failed` and `649 passed / 3 failed` results.

The same development increment also established live Blender-backed evidence for five mutation capabilities, each with a legitimate authoritative-success result and an adversarial authoritative-mismatch result:

| Capability | Legitimate live proof | Adversarial live proof |
| --- | --- | --- |
| `rotate_object` | `VERIFIED` | `BLOCKED` |
| `move_object` | `VERIFIED` | `BLOCKED` |
| `delete_object` | `VERIFIED` | `BLOCKED` |
| `create_empty_marker` | `VERIFIED` | `BLOCKED` |
| `move_object_to_collection` | `VERIFIED` | `BLOCKED` |

These live results are separate from the offline suite and must continue to be backed by actual Blender runner output.

## Current architecture

Atlas uses a protected proposal-to-execution pipeline:

```text
Qwen / AI proposal
 -> ActionSpec / task validation
 -> explicit capability admission
 -> exact BlenderWriteAuthorization or ReplanAuthorization
 -> BlenderLiveWriteGate / corrective runtime
 -> BlenderExecutionBoundary
 -> normalized BlenderExecutionResult
 -> immutable authorization-bound receipt
 -> fresh authoritative observation
 -> VERIFIED / BLOCKED or corrective replan
```

Qwen never receives direct Blender execution authority. Blender is an execution target, not the authority that decides completion.

### Capability admission

`planning/blender_capability_catalog.py`

Provides explicit capability metadata and separates read/inspection capabilities from scene-writing capabilities. Current production scene-writing capabilities include:

- `move_object`
- `set_object_rotation`
- `create_empty_marker`
- `create_collection`
- `parent_object`
- `move_object_to_collection`
- `rename_object`
- `delete_object`

Unknown capabilities fail closed.

### Exact write authorization

`planning/blender_write_authorization.py`

Creates exact-action authorization for admitted scene writes. Authorization identity is normalized and preserved through execution/receipt binding; changed action arguments do not match an existing authorization.

### Corrective authorization

`planning/replan_authorization.py`

Provides immutable corrective authorization bound to fresh evidence and the exact replacement action list. A stale or changed world invalidates the prior corrective authorization.

### Execution boundary

`planning/blender_execution_boundary.py`

Provides distinct raw, verified, receipt-bound, authorization-bound-write, and corrective-replan execution APIs. Production Blender execution remains behind the strict boundary.

### Result normalization

`planning/blender_tool_adapter.py`

Is the compatibility boundary for legacy Blender result shapes such as `status`/`error`. The strict `planning/blender_result_contract.py` remains structured and is not weakened to accommodate legacy forms. The historical `_normalize_result()` helper remains as a compatibility wrapper while adapter dispatch returns canonical `BlenderExecutionResult` objects.

### Receipts

`planning/blender_execution_receipt.py`

Provides immutable execution receipts and authorization binding through `matches_authorization(...)`. The authorization identifier is represented by a digest rather than storing the raw identifier.

### Live write gate

`planning/blender_live_write_gate.py`

Is the shared final write choke point. It requires:

1. capability admission;
2. exact write authorization;
3. normalized execution;
4. an execution receipt;
5. receipt/authorization binding; and
6. fresh authoritative verification before returning `VERIFIED`.

Verifier exceptions and malformed verifier returns fail closed. `BLOCKED` does not expose a successful receipt.

### Live verification

`planning/blender_live_verification.py`

Provides independent authoritative post-write checking of final Blender state. It is deliberately separate from executor-reported success.

### Live outcome

`planning/blender_live_write_result.py`

Defines the explicit terminal write outcomes:

- `VERIFIED` — authoritative final-state verification succeeded and an authorization-bound receipt exists.
- `BLOCKED` — integrity or authoritative verification did not establish success; no receipt is exposed as successful completion.

### Corrective runtime

The corrective runtime is intentionally generalized rather than bespoke per-tool orchestration. It distinguishes strict production Blender execution from generic/in-memory corrective executors used by isolated tests.

The required corrective lifecycle is:

```text
fresh observation
 -> corrective planning
 -> exact ReplanAuthorization
 -> protected execution
 -> receipt binding
 -> re-observation
 -> continue / VERIFIED / BLOCKED / replan
```

Multi-step corrective execution explicitly re-observes before each mutation and prevents stale authorization from reaching the executor.

Synthetic corrective tests may use `set_value`; this is deliberately not a production Blender capability.

## Files and tools added/changed in the current increment

Core production files currently central to the milestone:

```text
planning/blender_capability_catalog.py
planning/blender_write_authorization.py
planning/replan_authorization.py
planning/blender_execution_boundary.py
planning/blender_execution_receipt.py
planning/blender_result_contract.py
planning/blender_tool_adapter.py
planning/blender_live_write_gate.py
planning/blender_live_write_result.py
planning/blender_live_verification.py
```

Live Blender probes:

```text
live_blender_write_gate_rotation.py
live_blender_write_gate_move.py
live_blender_write_gate_delete.py
live_blender_write_gate_marker.py
live_blender_write_gate_collection.py
```

Focused validation files include the receipt/authorization/live-gate tests, corrective-runtime tests, adapter/result-contract tests, marker conditional/declarative tests, and multi-step corrective executor tests that were cleared during this development increment.

## Test history and completed validation

The development increment progressed through these authoritative results:

```text
622 passed / 30 failed
649 passed / 3 failed
652 passed / 0 failed
```

The final result above was:

```text
python -m pytest -q
652 passed in 1.26s
```

Focused clusters cleared during the increment included:

```text
receipt / authorization / live-verification: 12 passed
corrective-runtime: 6 passed
adapter/runtime compatibility: 6 passed
```

The final three adapter result-contract failures were resolved by preserving the historical `_normalize_result()` compatibility helper while keeping canonical adapter dispatch on `BlenderExecutionResult`.

The live Blender evidence separately established legitimate `VERIFIED` and adversarial `BLOCKED` outcomes for the five capabilities listed above.

## Current model/runtime setup

The current execution architecture is Python-first at the Atlas orchestration layer, with Blender as the controlled production execution target. The model/agent side proposes actions; Atlas owns validation, capability admission, authorization, execution boundaries, receipts, authoritative verification, and recovery.

Current documented runtime environment from the development session:

```text
OS / shell: Windows PowerShell
Atlas root: C:\Users\Gavin's PC\Desktop\Atlas
Branch: feat/replan-race-gate
Python test runner: python -m pytest
Blender: controlled external execution target through the Atlas Blender boundary/runner
```

No additional model-version or hardware claim is recorded here unless it has been explicitly established by runner output.

## Known issues / constraints

No offline pytest failures remain at the latest reported baseline.

The following are still development requirements rather than completed milestones:

- The five live capability proofs are not a substitute for end-to-end proof of arbitrary multi-operation production composition.
- A green offline suite does not itself prove a live Blender execution path.
- Production multi-operation corrective composition has not yet been established as an end-to-end milestone.
- Interruption/world-change handling must be demonstrated in a real composed task, including proof that stale authorization cannot execute.
- Authoritative final-state disagreement must continue to fail closed as `BLOCKED` with no false completion and no implicit second write.
- Continuation/resume integrity has not yet been proven and should follow, not precede, multi-operation composition.
- Photogrammetry remains upstream of Blender; Blender receives the initial reconstruction for analysis, cleanup, correction, and preparation.
- Atlas remains focused on soccer-field-related digital twins; do not broaden the architecture around unrelated environments.

## Exact next steps to resume development

1. Start from `feat/replan-race-gate` and confirm the working tree is synchronized.
2. Do not reopen already-green authorization, receipt, adapter normalization, or corrective-runtime work unless new evidence requires it.
3. Build a production-facing multi-operation task that composes multiple already-proven Blender capabilities through the generalized corrective runtime.
4. Require fresh observation and exact authorization for each individual mutation.
5. Execute the first mutation and bind its receipt.
6. Re-observe before the next mutation.
7. Inject or simulate a world change between operations and prove the previous authorization cannot reach Blender.
8. Replan from fresh evidence using a new `ReplanAuthorization` and continue through the protected execution boundary.
9. Prove an authoritative final `VERIFIED` completion for the composed task.
10. Prove an adversarial final-state disagreement produces `BLOCKED`, exposes no successful receipt, and performs no implicit retry/second write.
11. Preserve the zero-second-write invariant on authoritative mismatch.
12. After that end-to-end composition proof is green, begin continuation/resume integrity across interrupted production tasks.

### First command

```powershell
git status --short --branch
```

Then proceed from the clean `652 passed, 0 failed` baseline.

## Architectural constraints

- Qwen never receives direct Blender execution authority.
- Only explicitly admitted Blender capabilities execute.
- Corrective planning uses fresh world state.
- `ReplanAuthorization` must match fresh evidence and the exact replacement action list.
- Ordinary scene writes must match an exact `BlenderWriteAuthorization`.
- Receipts bind the exact executed action/result and, for authorized writes, authorization identity.
- Missing, stale, changed, or unbound authorization fails closed.
- Strict verified execution accepts only the structured Blender result contract.
- Legacy result normalization belongs at `BlenderToolAdapter`.
- `VERIFIED` requires authoritative verification and a receipt; `BLOCKED` carries no successful receipt.
- Exhausting a corrective step budget is not success.
- Failed or unverifiable final verification cannot produce completion.
- Do not add generic test operations such as `set_value` to the production Blender capability catalog.
- Avoid bespoke per-tool lifecycle orchestration in place of the generalized runtime.
- C++ interoperability remains a future architectural requirement; keep subsystem boundaries and contracts language-agnostic so performance-critical components can be replaced incrementally without a wholesale rewrite.
- Photogrammetry is upstream of Blender; Atlas owns canonical Digital Twin identity/state for the soccer-field-focused production pipeline.
