# Atlas Current Development Handoff

**Updated:** August 25, 2026 — live multi-operation composition + continuation/resume checkpoint  
**Branch:** `feat/replan-race-gate`  
**Purpose:** canonical resume point for Atlas Blender-Agent development.

## Current verified milestone

The latest authoritative local validation remains:

```text
FULL OFFLINE PYTEST SUITE: 652 passed, 0 failed
```

No newer full-suite result has been established since that run. The `652 passed / 0 failed` result supersedes the earlier `622 passed / 30 failed` and `649 passed / 3 failed` results.

The same development increment established live Blender-backed evidence for five mutation capabilities, each with a legitimate authoritative-success result and an adversarial authoritative-mismatch result:

| Capability | Legitimate live proof | Adversarial live proof |
| --- | --- | --- |
| `rotate_object` | `VERIFIED` | `BLOCKED` |
| `move_object` | `VERIFIED` | `BLOCKED` |
| `delete_object` | `VERIFIED` | `BLOCKED` |
| `create_empty_marker` | `VERIFIED` | `BLOCKED` |
| `move_object_to_collection` | `VERIFIED` | `BLOCKED` |

## Newest completed milestone — LIVE MULTI-OPERATION COMPOSITION

The real Blender runner produced:

```text
ATLAS BLENDER LIVE MULTI-OPERATION COMPOSITION: PASS
ATLAS BLENDER LIVE STALE AUTHORIZATION ZERO-WRITE GATE: PASS
```

This is now an explicitly live-proven production-composition milestone, separate from the offline suite.

The live composition proof demonstrated:

```text
fresh Blender observation
 -> first production mutation
 -> real external Blender state interruption
 -> stale corrective authorization presented
 -> stale authorization rejected before mutation
 -> stale executor writes: 0
 -> fresh observation
 -> new corrective authorization
 -> replacement mutation
 -> fresh authoritative final-state verification
 -> PASS
```

The live probe is `live_blender_multi_operation_corrective_composition.py`.

The probe uses the supported live production fixture by default:

```text
file: object_move_INCORRECT.blend
object: Goal_Left_post
```

Do not interpret earlier failed runs of this probe as production failures. They exposed harness/fixture issues that were corrected before the final PASS. The final two PASS lines above are the authoritative live evidence.

## Production composition architecture

`planning/production_multi_operation_corrective_task.py` is the thin production-facing composition boundary. It delegates lifecycle behavior to the generalized corrective runtime and only adds the production constraint that every emitted action must be an admitted, verification-required Blender scene-writing capability.

It does not introduce bespoke per-tool lifecycle orchestration.

Synthetic composition tests now cover:

```text
3 passed — basic production composition, interruption/replanning, capability admission
4 passed — including explicit stale-authorization zero-write rejection
```

Synthetic `set_value` remains deliberately absent from the production Blender capability catalog.

## Continuation / resume milestone — CONTRACT IMPLEMENTED, NOT YET LIVE-PROVEN

The first reusable continuation state contract is now implemented:

`planning/continuation_resume.py`

It stores task identity, completed actions, last observed evidence, and the authorization identity. It deliberately does **not** reuse the saved authorization during resume.

Resume behavior is:

```text
saved continuation state
 -> fresh authoritative evidence required
 -> issue new ReplanAuthorization for remaining actions
 -> execute only against fresh evidence
```

The focused continuation contract tests are green:

```text
2 passed
```

This is currently **offline-contract evidence only**. A real interrupted Blender continuation/resume proof has not yet been executed and must not be claimed as live-proven.

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

`planning/blender_capability_catalog.py` provides explicit capability metadata and separates read/inspection capabilities from scene-writing capabilities. Unknown capabilities fail closed.

### Exact write authorization

`planning/blender_write_authorization.py` creates exact-action authorization for admitted scene writes. Changed action arguments do not match an existing authorization.

### Corrective authorization

`planning/replan_authorization.py` provides immutable corrective authorization bound to fresh evidence and the exact replacement action list. A stale or changed world invalidates the prior corrective authorization.

### Execution boundary

`planning/blender_execution_boundary.py` provides distinct raw, verified, receipt-bound, authorization-bound-write, and corrective-replan execution APIs. Production Blender execution remains behind the strict boundary.

### Result normalization

`planning/blender_tool_adapter.py` is the compatibility boundary for legacy Blender result shapes. The strict result contract remains structured. The historical `_normalize_result()` helper remains as a compatibility wrapper while adapter dispatch returns canonical `BlenderExecutionResult` objects.

### Receipts

`planning/blender_execution_receipt.py` provides immutable execution receipts and authorization binding through `matches_authorization(...)`.

### Live write gate

`planning/blender_live_write_gate.py` is the shared final write choke point. It requires capability admission, exact write authorization, normalized execution, a receipt, receipt/authorization binding, and fresh authoritative verification before returning `VERIFIED`. Verifier failures fail closed.

### Corrective runtime

The corrective runtime is generalized rather than bespoke per-tool orchestration. Fresh observation, replanning, exact authorization, protected execution, receipt binding, and re-observation are mandatory lifecycle stages.

Multi-step corrective execution re-observes before each mutation and prevents stale authorization from reaching the executor.

## Validation state

Verified:

```text
FULL OFFLINE PYTEST SUITE: 652 passed, 0 failed
Continuation contract: 2 passed
Live write gate: 5 capabilities with VERIFIED + BLOCKED evidence
Live multi-operation composition: PASS
Live stale-authorization zero-write gate: PASS
```

The full offline suite has not been rerun after adding the continuation contract and live composition harness changes. Therefore, do not claim `652 passed` as validation of those newest changes; it remains the last completed full-suite baseline.

## Current model/runtime setup

```text
OS / shell: Windows PowerShell
Atlas root: C:\Users\Gavin's PC\Desktop\Atlas
Branch: feat/replan-race-gate
Python test runner: python -m pytest
Blender: controlled external execution target through the Atlas Blender runner
```

## Exact next steps to resume development

1. Run the continuation contract tests again if needed and then run a **fresh full suite** because new continuation code was added after the last 652-test run.
2. Build a production continuation/resume coordinator around `ContinuationState` without allowing saved authorization replay.
3. Simulate interruption after a real completed operation while retaining its receipt/continuation state.
4. Re-observe Blender from a fresh process on resume.
5. Prove the old continuation state cannot directly authorize the remaining mutation against changed evidence.
6. Issue a fresh `ReplanAuthorization` from resume evidence and execute the remaining mutation through the protected Blender boundary.
7. Add the real Windows/Blender interrupted-resume probe.
8. Prove adversarial stale/mismatched continuation produces `BLOCKED` with zero writes.
9. Only after live continuation/resume is proven should the next architecture increment be Digital Twin identity/revision and production-task persistence.

### First command

```powershell
git status --short --branch
```

Then validate the current branch from the cleanest available state.

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
