# Atlas Current Development Handoff

**Updated:** August 25, 2026 — live rotation gate milestone  
**Branch:** `feat/replan-race-gate`  
**Current work:** authorization-bound Blender live-write path and authoritative verification  
**Purpose:** canonical resume point for Atlas Blender-Agent development.

## Current session state

Atlas remains in active authorization-bound Blender live-write development. The local Windows checkout is synchronized with `origin/feat/replan-race-gate`. The focused live-write/authorization suite passed, and the real Blender rotation probe has now produced both required live outcomes:

```text
ATLAS BLENDER LIVE WRITE VERIFIED: PASS
ATLAS BLENDER LIVE WRITE ADVERSARIAL GATE: PASS
```

This is the current milestone: the shared write gate has been exercised against a real Blender process for the rotation capability, both for legitimate authoritative success and for an executor-success/authoritative-mismatch adversarial case.

The controlled write contract is:

```text
capability admission
 -> exact BlenderWriteAuthorization
 -> BlenderLiveWriteGate
 -> BlenderExecutionBoundary
 -> normalized verified result
 -> immutable authorization-bound receipt
 -> fresh authoritative final-state verification
 -> VERIFIED / BLOCKED
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

`live_blender_write_gate_rotation.py` is the direct live rotation probe. It executes `set_object_rotation`, performs fresh `inspect_object_transform` verification in a separate Blender process, and has a deliberate adversarial verifier that requires an impossible target to prove false-success containment.

`live_qwen_object_rotation.py` has been moved onto the shared authorization-bound live-write architecture.

## Tests and results

Focused live-write/authorization tests present on the branch include:

- `tests/test_blender_live_write_gate.py`
- `tests/test_blender_live_write_gate_outcomes.py`
- `tests/test_blender_live_write_gate_invariants.py`
- `tests/test_blender_live_write_gate_no_second_write.py`
- `tests/test_blender_live_write_gate_executor_failure.py`
- `tests/test_blender_live_write_gate_authorization_failures.py`
- `tests/test_blender_live_write_gate_receipt_sanitization.py`
- `tests/test_blender_live_verification.py`
- `tests/test_blender_write_authorization_fail_closed.py`
- `tests/test_blender_write_authorization_identity.py`

Current reported focused result:

```text
python -m pytest -q tests/test_blender_live_write_gate.py
1 passed in 0.13s

Complete focused live-write/authorization suite
PASSED
```

Current live Blender results:

```text
python live_blender_write_gate_rotation.py --case incorrect --adversarial
ATLAS BLENDER LIVE WRITE ADVERSARIAL GATE: PASS

python live_blender_write_gate_rotation.py --case incorrect
ATLAS BLENDER LIVE WRITE VERIFIED: PASS
```

The adversarial live result establishes that an executor-success path can be rejected by fresh authoritative state verification and terminate as `BLOCKED` rather than escaping as false success. The normal live result establishes the legitimate rotation path reaches `VERIFIED` with the gate's receipt requirement satisfied.

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

Do **not** describe the current branch as fully green. The focused suite and live rotation probe are green, but no new full-suite result has superseded the `589 passed / 18 failed` baseline.

## Runtime / development setup

```text
C:\Users\Gavin's PC\Desktop\Atlas
branch: feat/replan-race-gate
tracking: origin/feat/replan-race-gate
```

The local checkout is synchronized to the branch. Focused validation is run from the Atlas repository root with Python/pytest. Live proof runs through the user's Windows machine and actual Blender process. The corrective runtime remains Python 3.9 compatible. Qwen is the proposal layer only and never receives direct Blender execution authority.

The local checkout contains untracked `.blend` fixtures; leave them untouched unless explicitly required.

## Known issues / unfinished work

1. The focused live-write/authorization suite and real Blender rotation proof are green, but the full suite has not been rerun after the latest changes.
2. The authorized `move_object` path still needs end-to-end live proof through the same shared gate.
3. The rotation adversarial proof demonstrates `BLOCKED` after authoritative mismatch, but the next broader integration proof should explicitly instrument and report the zero-second-write invariant for the production path.
4. Corrective-runtime integration still needs separation from Blender-specific result/receipt assumptions.
5. Some generic corrective-runtime tests use synthetic results such as `{"status": "created"}`; normalize these at `BlenderToolAdapter`, not by weakening the strict Blender result contract.
6. Marker evidence completeness is checked too early in several failing paths; fix lifecycle sequencing rather than weakening verification.
7. Marker task-definition expectations need reconciliation with the intended declarative contract.
8. One older `BlenderToolAdapter` test expects raw underlying behavior while the current adapter intentionally normalizes legacy results.
9. `planning.unreal_adapter_production` is absent; the stale importing test was removed. Unreal is not the current blocker.
10. No new full-suite result has superseded the `589 passed / 18 failed` baseline.

## Exact next steps

1. Run the full suite with `python -m pytest -q` from the synchronized Atlas root and record the actual current result.
2. Fix any integration regressions before adding further architecture; keep generic corrective-runtime contracts independent of Blender-specific result/receipt assumptions.
3. Preserve strict result normalization at `BlenderToolAdapter`.
4. Fix marker evidence sequencing and reconcile marker declarative expectations.
5. Resolve the older adapter compatibility expectation against the intentional normalized adapter API.
6. Build the live `move_object` proof through the shared gate: capability admission -> exact authorization -> actual Blender subprocess -> normalized result -> receipt -> authoritative final-state verification -> `VERIFIED`.
7. Add/execute an explicit production-path zero-second-write invariant for authoritative mismatch, not merely the rotation probe's final `BLOCKED` result.
8. Generalize the shared live-write path to the remaining admitted write capabilities only after their individual live proofs are established.
9. Then resume reusable multi-operation production task composition, continuation/resume, stronger task/session identity, broader authorized Blender operations, and later Digital Twin/photogrammetry intake contracts. Unreal production remains later.

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
