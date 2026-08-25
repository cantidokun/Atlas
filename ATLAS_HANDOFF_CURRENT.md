# Atlas Current Development Handoff

**Updated:** August 25, 2026 — current resume checkpoint  
**Branch:** `feat/replan-race-gate`  
**Current HEAD:** `7e853d4b01e6716a5636cd9e0728f5c4fcb4717b`  
**Current work:** authorization-bound Blender live-write path and authoritative verification  
**Purpose:** canonical resume point for Atlas Blender-Agent development.

## Current session state

Atlas remains in active authorization-bound Blender live-write development. The local Windows checkout was synchronized to the branch HEAD and the focused live-write gate suite was run successfully. No full-suite or real-Blender rotation probe has yet been reported after the latest implementation changes.

The target controlled write contract is:

```text
capability admission
 -> exact BlenderWriteAuthorization
 -> BlenderLiveWriteGate
 -> BlenderExecutionBoundary
 -> normalized verified result
 -> immutable authorization-bound receipt
 -> authoritative final-state verification
 -> VERIFIED / BLOCKED
```

The latest proven major live milestone remains the generalized Blender corrective runtime with live interruption/replanning:

```text
ATLAS GENERALIZED BLENDER CORRECTIVE RUNTIME GATE: PASS
receipts = 4
external_change_injected = true
```

## Current implementation

### Capability and authorization

`planning/blender_capability_catalog.py` provides explicit capability metadata. Registered scene-writing capabilities include `move_object`, `set_object_rotation`, `create_empty_marker`, `create_collection`, `parent_object`, `move_object_to_collection`, `rename_object`, and `delete_object`. Read/inspection capabilities remain separate and unknown capabilities fail closed.

`planning/blender_write_authorization.py` issues exact-action write authorization only for admitted write capabilities requiring verification. Authorization identity is normalized and the same normalized identity is preserved through authorization and receipt binding. Changed action arguments do not match an existing authorization.

`planning/replan_authorization.py` remains the immutable corrective authorization bound to fresh evidence and the exact replacement action list.

### Execution and receipts

`planning/blender_execution_boundary.py` exposes distinct raw, verified, receipt-bound, authorization-bound-write, and corrective-replan execution APIs. The authorized-write path requires an exact `ActionSpec` plus `BlenderWriteAuthorization`.

`planning/blender_execution_receipt.py` supports authorization-bound receipts and `matches_authorization(...)`; the authorization identifier is represented by a digest rather than storing the raw identifier.

`planning/blender_tool_adapter.py` remains the normalization boundary for legacy Blender result shapes such as `status`/`error`. The strict `planning/blender_result_contract.py` must not be weakened to accommodate legacy forms.

### Live write gate and authoritative verification

`planning/blender_live_write_gate.py` is the shared final write choke point. It rejects an action that no longer matches its authorization, requires the execution boundary's normalized result plus receipt, requires the receipt to match authorization, and requires a configured authoritative verifier before returning `VERIFIED`. Verifier exceptions and malformed verifier returns fail closed.

`planning/blender_live_write_result.py` defines the explicit outcome contract:

- `VERIFIED` — authoritative verification succeeds and an authorization-bound receipt exists.
- `BLOCKED` — integrity/verification does not establish success; no receipt is exposed by the outcome.

`planning/blender_live_verification.py` provides independent authoritative post-write checking of the requested action against verifier-reported final state.

`live_qwen_object_rotation.py` has been moved onto the shared authorization-bound live-write architecture.

## Tests and results

Focused live-write/authorization tests present on the branch include:

- `tests/test_blender_live_write_gate.py`
- `tests/test_blender_live_write_write_gate_outcomes.py` (if present in the local checkout, retain the actual filename from `tests/`)
- `tests/test_blender_live_write_gate_outcomes.py`
- `tests/test_blender_live_write_gate_invariants.py`
- `tests/test_blender_live_write_gate_no_second_write.py`
- `tests/test_blender_live_write_gate_executor_failure.py`
- `tests/test_blender_live_write_gate_authorization_failures.py`
- `tests/test_blender_live_write_gate_receipt_sanitization.py`
- `tests/test_blender_live_verification.py`
- `tests/test_blender_write_authorization_fail_closed.py`
- `tests/test_blender_write_authorization_identity.py`

Current reported results:

```text
python -m pytest -q tests/test_blender_live_write_gate.py
1 passed in 0.13s

Complete focused live-write/authorization suite
PASSED
```

The latest authoritative complete full-suite baseline remains:

```text
589 passed / 18 failed
```

Earlier proven results remain:

```text
Test 313 passed
141 passed
ATLAS GENERALIZED BLENDER CORRECTIVE RUNTIME GATE: PASS
receipts = 4
external_change_injected = true
```

Do **not** describe the current branch as fully green. The focused suite passing does not replace the `589 passed / 18 failed` full-suite baseline, and no new real-Blender rotation result has been reported yet.

## Runtime / development setup

```text
C:\Users\Gavin's PC\Desktop\Atlas
branch: feat/replan-race-gate
tracking: origin/feat/replan-race-gate
```

The user successfully synchronized the local checkout to:

```text
7e853d4 (HEAD -> feat/replan-race-gate, origin/feat/replan-race-gate)
test: preserve normalized authorization identity
```

Focused validation is run from the Atlas repository root with Python/pytest. Live proof requires the user's Windows machine and actual Blender process. The corrective runtime remains Python 3.9 compatible. Qwen is the proposal layer only and never receives direct Blender execution authority.

The local checkout contains untracked `.blend` fixtures; leave them untouched unless explicitly required.

## Known issues / unfinished work

1. The focused live-write/authorization suite passes, but the full suite has not been rerun after the latest changes.
2. The actual live `move_object` path still needs end-to-end Windows/Blender proof with authoritative post-execution state verification.
3. The adversarial case where executor success conflicts with authoritative Blender state still needs live/integration proof producing `BLOCKED`, no receipt, and no subsequent write.
4. Corrective-runtime integration still needs separation from Blender-specific result/receipt assumptions.
5. Some generic corrective-runtime tests use synthetic results such as `{"status": "created"}`; normalize these at `BlenderToolAdapter`, not by weakening the strict Blender result contract.
6. Marker evidence completeness is checked too early in several failing paths; fix lifecycle sequencing rather than weakening verification.
7. Marker task-definition expectations need reconciliation with the intended declarative contract.
8. One older `BlenderToolAdapter` test expects raw underlying behavior while the current adapter intentionally normalizes legacy results.
9. `planning.unreal_adapter_production` is absent; the stale importing test was removed. Unreal is not the current blocker.
10. No new full-suite result has superseded the `589 passed / 18 failed` baseline.

## Exact next steps

1. From the synchronized Atlas root, run the focused suite again only if a reproducibility check is needed; the latest reported focused suite already passed.
2. Run the full suite with `python -m pytest -q` and record the actual current result.
3. Fix any integration regressions before adding further architecture; keep generic corrective-runtime contracts independent of Blender-specific result/receipt assumptions.
4. Preserve strict result normalization at `BlenderToolAdapter`.
5. Fix marker evidence sequencing and reconcile marker declarative expectations.
6. Resolve the older adapter compatibility expectation against the intentional normalized adapter API.
7. Run the normal real-Blender rotation probe using the active local runner and require `VERIFIED` plus an authorization-bound receipt.
8. Run the adversarial real-Blender probe and require `BLOCKED`, no receipt, and no second write.
9. Prove the authorized `move_object` path end-to-end: capability admission -> exact authorization -> actual Blender subprocess -> normalized result -> receipt -> authoritative final-state verification -> `VERIFIED`.
10. Only after those proofs are green, generalize the shared live-write path to the remaining admitted write capabilities.
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
