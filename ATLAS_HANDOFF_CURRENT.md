# Atlas Current Development Handoff

**Updated:** August 25, 2026 — generalized live-write and corrective-runtime milestone  
**Branch:** `feat/replan-race-gate`  
**Current work:** authorization-bound Blender live-write path, authoritative verification, and reusable corrective runtime  
**Purpose:** canonical resume point for Atlas Blender-Agent development.

## Current milestone

Atlas has now demonstrated the generalized Blender live-write gate against five real Blender-backed mutation capabilities. Every capability has both a legitimate authoritative-success proof and an adversarial authoritative-mismatch proof.

| Capability | Legitimate live proof | Adversarial live proof |
| --- | --- | --- |
| `rotate_object` | `VERIFIED` | `BLOCKED` |
| `move_object` | `VERIFIED` | `BLOCKED` |
| `delete_object` | `VERIFIED` | `BLOCKED` |
| `create_empty_marker` | `VERIFIED` | `BLOCKED` |
| `move_object_to_collection` | `VERIFIED` | `BLOCKED` |

The demonstrated control flow is:

```text
capability admission
 -> exact BlenderWriteAuthorization
 -> BlenderLiveWriteGate
 -> BlenderExecutionBoundary
 -> normalized result
 -> authorization-bound immutable receipt
 -> fresh authoritative final-state verification
 -> VERIFIED / BLOCKED
```

The adversarial probes establish that an executor-success signal is not sufficient when fresh authoritative evidence contradicts the requested final state. The gate fails closed as `BLOCKED` rather than exposing a successful receipt.

## Corrective-runtime milestone

The reusable corrective runtime has also been brought through its current compatibility boundary without expanding the production Blender capability registry.

The following focused clusters are green on this branch:

```text
receipt / authorization / live-verification cluster: 12 passed
corrective-runtime cluster: 6 passed
```

The corrective runtime now distinguishes:

- strict production Blender execution through `BlenderExecutionBoundary`;
- generic/in-memory corrective executors through the generic corrective execution boundary.

Synthetic corrective tests may use operations such as `set_value`; `set_value` remains deliberately absent from the production Blender capability catalog. This prevents a test abstraction from becoming an accidental production Blender write capability.

Fresh observation, replanning, exact corrective authorization, execution, receipt binding, and re-observation remain the required corrective lifecycle.

## Current code / architecture

### Capability and authorization

`planning/blender_capability_catalog.py` provides explicit capability metadata. Registered scene-writing capabilities include `move_object`, `set_object_rotation`, `create_empty_marker`, `create_collection`, `parent_object`, `move_object_to_collection`, `rename_object`, and `delete_object`. Read/inspection capabilities remain separate and unknown capabilities fail closed.

`planning/blender_write_authorization.py` issues exact-action write authorization only for admitted write capabilities requiring verification. Authorization identity is normalized and preserved through authorization and receipt binding. Changed action arguments do not match an existing authorization.

`planning/replan_authorization.py` remains the immutable corrective authorization bound to fresh evidence and the exact replacement action list.

### Execution and receipts

`planning/blender_execution_boundary.py` exposes distinct raw, verified, receipt-bound, authorization-bound-write, and corrective-replan execution APIs. The authorized-write path requires an exact `ActionSpec` plus `BlenderWriteAuthorization`.

`planning/blender_execution_receipt.py` supports authorization-bound receipts and `matches_authorization(...)`; the authorization identifier is represented by a digest rather than storing the raw identifier.

`planning/blender_tool_adapter.py` remains the normalization boundary for legacy Blender result shapes such as `status`/`error`. The strict `planning/blender_result_contract.py` must not be weakened to accommodate legacy forms.

`planning/blender_live_write_gate.py` is the shared final write choke point. It rejects actions that no longer match authorization, requires normalized execution plus a receipt, requires receipt/authorization binding, and requires authoritative verification before returning `VERIFIED`. Verifier exceptions and malformed verifier returns fail closed.

`planning/blender_live_write_result.py` defines the explicit outcome contract:

- `VERIFIED` — authoritative verification succeeds and an authorization-bound receipt exists.
- `BLOCKED` — integrity/verification does not establish success; no receipt is exposed by the outcome.

`planning/blender_live_verification.py` provides independent authoritative post-write checking.

### Corrective runtime

The corrective runtime is intentionally generic at its orchestration boundary. Explicitly injected synthetic executors do not need to masquerade as Blender capabilities. Production Blender execution remains protected by the strict Blender capability boundary.

The runtime re-observes fresh state before planning and after each authorized mutation. A stale or changed world invalidates the previous corrective authorization; the replacement action list must be authorized against the fresh evidence before execution.

## Live probes

The branch contains direct live probes for:

- `live_blender_write_gate_rotation.py`
- `live_blender_write_gate_move.py`
- `live_blender_write_gate_delete.py`
- `live_blender_write_gate_marker.py`
- `live_blender_write_gate_collection.py`

Each has now produced both required live outcomes: legitimate `VERIFIED` and adversarial `BLOCKED`.

## Current validation state

Verified in this development session:

```text
12 focused receipt/authorization/live-verification tests: PASS
6 focused corrective-runtime tests: PASS
5 Blender capabilities: VERIFIED + adversarial BLOCKED
```

The full suite was previously measured at:

```text
622 passed / 30 failed
```

That result is now stale because the subsequent fixes cleared the receipt/live-verification cluster and the corrective-runtime cluster. A fresh full-suite run is therefore the next required validation checkpoint. Do **not** claim the full suite is green until that run is actually performed.

## Known remaining work

1. Run a fresh `python -m pytest -q` from the synchronized Atlas root and record the new result.
2. Resolve remaining integration failures without weakening strict Blender capability admission or authoritative verification.
3. Preserve legacy-result normalization at `BlenderToolAdapter`, not inside the strict result contract.
4. Reconcile any remaining marker evidence lifecycle/declarative-task expectations if they appear in the fresh suite.
5. Reconcile any remaining adapter compatibility expectations against the intentional normalized adapter API.
6. Preserve and expand the explicit zero-second-write invariant for authoritative mismatch in the production live path.
7. After the full suite is stable, continue reusable multi-operation production task composition and then continuation/resume integrity.

## Exact next command

From:

```text
C:\Users\Gavin's PC\Desktop\Atlas
```

run:

```powershell
python -m pytest -q
```

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
- Do not add generic test operations such as `set_value` to the production Blender capability catalog.
- Avoid bespoke per-tool lifecycle orchestration in place of the generalized runtime.
- Photogrammetry is upstream of Blender; Atlas owns canonical Digital Twin identity/state for the soccer-field-focused production pipeline.
