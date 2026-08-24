# Atlas Current Development Handoff

**Updated:** August 24, 2026 — current resume checkpoint  
**Branch:** `feat/replan-race-gate`  
**Latest documented code commit:** `f9b6ca5710dbc4724775c7ee75ba3fef83597e08`  
**Latest documentation commit:** `81df3d320bebf7738e6fdc9eb856177fcde27844`  
**Current work:** authorization-bound Blender live-write path and independent authoritative verification  
**Purpose:** canonical resume point for Atlas Blender-Agent development.

## Current session state

Atlas remains in the authorization-bound Blender live-write development phase. The latest implementation changes are not yet runner-validated. The previous session ended after documenting the work; no new test result has been established since then.

The target controlled write contract is:

```text
capability admission
 -> exact BlenderWriteAuthorization
 -> BlenderLiveWriteGate
 -> BlenderExecutionBoundary
 -> normalized verified result
 -> immutable authorization-bound receipt
 -> independent authoritative state verification
 -> VERIFIED / BLOCKED
```

The latest **proven major milestone** remains the generalized Blender corrective runtime with live interruption/replanning. The Windows/Blender live gate previously passed with:

```text
ATLAS GENERALIZED BLENDER CORRECTIVE RUNTIME GATE: PASS
receipts = 4
external_change_injected = true
```

The proven corrective loop remains:

```text
fresh evidence
 -> plan
 -> authorize
 -> execute
 -> immutable receipt
 -> fresh evidence
 -> external interruption
 -> replan
 -> reauthorize
 -> execute
 -> independent verification
 -> COMPLETE
```

## Architecture and files

### Capability and authorization

`planning/blender_capability_catalog.py` provides explicit capability metadata. Registered scene-writing capabilities include `move_object`, `set_object_rotation`, `create_empty_marker`, `create_collection`, `parent_object`, `move_object_to_collection`, `rename_object`, and `delete_object`. Read/inspection capabilities remain separate and unknown capabilities fail closed.

`planning/blender_write_authorization.py` issues exact-action write authorization only for admitted write capabilities requiring verification. Changed action arguments no longer match an existing authorization.

`planning/replan_authorization.py` remains the immutable corrective authorization bound to fresh evidence and the exact replacement action list.

### Execution and receipts

`planning/blender_execution_boundary.py` exposes distinct raw, verified, receipt-bound, authorization-bound-write, and corrective-replan execution APIs. The authorized-write path requires an exact `ActionSpec` plus `BlenderWriteAuthorization`.

`planning/blender_execution_receipt.py` supports `create_authorized(...)` and `matches_authorization(...)`. The authorization identifier is represented by a digest rather than storing the raw identifier.

`planning/blender_tool_adapter.py` remains the normalization boundary for legacy Blender result shapes such as `status`/`error`; the strict `planning/blender_result_contract.py` must not be weakened to accommodate legacy forms.

### Live write gate and verification

`planning/blender_live_write_gate.py` is the shared final write choke point. It rejects an action that no longer matches its authorization and consumes the execution boundary's `(verified_result, receipt)` return shape.

`planning/blender_live_write_result.py` defines the explicit outcome contract:

- `VERIFIED` — authoritative verification succeeds and an authorization-bound receipt exists.
- `BLOCKED` — integrity/verification does not establish success; no receipt is issued.

`planning/blender_live_verification.py` is the newest independent verification helper. `verify_authoritative_write(...)` checks the final authoritative state separately from executor success and rejects verifier failure or state disagreement.

**Important integration state:** `blender_live_verification.py` has been implemented and focused-tested, but it is **not yet integrated into `BlenderLiveWriteGate`**. Until that integration is complete, receipt binding alone must not be described as the final authoritative live-write proof.

`live_qwen_object_rotation.py` has been moved onto the shared authorization-bound live-write architecture.

### Tests added/changed

Relevant focused tests include:

- `tests/test_blender_capability_catalog.py`
- `tests/test_replan_authorization_invariants.py`
- `tests/test_blender_write_authorization.py`
- `tests/test_authorized_write_receipt_binding.py`
- `tests/test_blender_live_write_gate.py`
- `tests/test_blender_live_write_gate_outcomes.py`
- `tests/test_blender_live_write_gate_invariants.py`
- `tests/test_blender_live_write_result.py`
- `tests/test_blender_live_verification.py`

These tests have been added/changed but **have not received a new authoritative runner result** in the current development increment.

## Validation status

Do not report the current branch as green.

Latest complete reported full-suite result:

```text
589 passed / 18 failed
```

Earlier proven results:

```text
Test 313 passed
141 passed
ATLAS GENERALIZED BLENDER CORRECTIVE RUNTIME GATE: PASS
receipts = 4
external_change_injected = true
```

The generalized Windows/Blender corrective-runtime gate is the latest proven live Blender milestone. The newer capability/authorization/live-write/authoritative-verification changes remain implementation-only until the active runner reports results.

## Known issues / unfinished work

1. `planning/blender_live_verification.py` is not yet integrated into `BlenderLiveWriteGate`.
2. The actual live `move_object` path still needs end-to-end Windows/Blender proof with authoritative post-execution state verification.
3. The adversarial case where executor success conflicts with authoritative Blender state still needs live/integration proof producing `BLOCKED`, no receipt, and no subsequent write.
4. Corrective-runtime integration still needs separation from Blender-specific result/receipt assumptions.
5. Some generic corrective-runtime tests use synthetic results such as `{"status": "created"}`; normalize these at `BlenderToolAdapter`, not by weakening the strict Blender result contract.
6. Marker evidence completeness is checked too early in several failing paths; fix lifecycle sequencing rather than weakening verification.
7. Marker task-definition expectations need reconciliation with the intended declarative contract.
8. One older `BlenderToolAdapter` test expects raw underlying behavior while the current adapter intentionally normalizes legacy results.
9. `planning.unreal_adapter_production` is absent; the stale importing test was removed. Unreal is not the current blocker.
10. Local Windows checkout has untracked `.blend` fixtures; leave them untracked unless explicitly required.
11. No new runner result has superseded the `589 passed / 18 failed` baseline.

## Runtime / development setup

```text
C:\Users\Gavin's PC\Desktop\Atlas
branch: feat/replan-race-gate
tracking: origin/feat/replan-race-gate
```

Primary validation command:

```powershell
python -m pytest -q
```

Live proof requires actual Windows/Blender execution. The corrective runtime remains Python 3.9 compatible. Qwen is the proposal layer only and never receives direct Blender execution authority.

## Exact next steps

1. Integrate `planning/blender_live_verification.py` into `BlenderLiveWriteGate` so `VERIFIED` requires authoritative final-state confirmation, not merely receipt binding.
2. Run the newest focused tests through the active runner when development/testing is intentionally resumed.
3. Run the full suite and replace the `589/18` baseline with the actual current result.
4. Fix integration regressions before adding further architecture; keep generic corrective-runtime contracts independent of Blender-specific result/receipt assumptions.
5. Preserve strict result normalization at `BlenderToolAdapter`.
6. Fix marker evidence sequencing and reconcile marker declarative expectations.
7. Resolve the older adapter compatibility expectation against the intentional normalized adapter API.
8. Prove: authorized `move_object` -> actual Blender subprocess -> authoritative verification -> `VERIFIED` + authorization-bound receipt.
9. Prove: executor reports success + authoritative state disagrees -> `BLOCKED` + no receipt + no subsequent write.
10. Only after the above is green, generalize the shared live-write path to the remaining admitted write capabilities.
11. Then resume reusable multi-operation production task composition, continuation/resume, stronger task/session identity, broader authorized Blender operations, and later Digital Twin/photogrammetry intake contracts. Unreal production remains later.

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
- `VERIFIED` requires authoritative verification and a receipt; `BLOCKED` carries no receipt.
- Exhausting a corrective step budget is not success.
- Failed or unverifiable final verification cannot produce completion.
- Avoid bespoke per-tool lifecycle orchestration in place of the generalized runtime.
- Photogrammetry is upstream of Blender; Atlas owns canonical Digital Twin identity/state for the soccer-field-focused production pipeline.
