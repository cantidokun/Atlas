# Atlas Current Development Handoff

**Updated:** August 24, 2026 — active development session  
**Branch:** `feat/replan-race-gate`  
**Latest implementation:** `e8dfad14fdc413f6d808eff2a311bff1f03e2fa3`  
**Latest focused tests:** `f3b5d2d5f23dd6edd4ebce0dc38406561e80b314`  
**Purpose:** canonical resume point for Atlas Blender-Agent development.

## Current position

The latest proven major milestone remains the generalized Blender corrective runtime with live interruption/replanning. The Windows/Blender live gate previously passed with:

```text
ATLAS GENERALIZED BLENDER CORRECTIVE RUNTIME GATE: PASS
receipts = 4
external_change_injected = true
```

The proven loop remains:

```text
fresh evidence -> plan -> authorize -> execute -> immutable receipt
-> fresh evidence -> external interruption -> replan -> reauthorize
-> execute -> independent verification -> COMPLETE
```

The latest reported full-suite result remains **589 passed / 18 failed**. No newer runner result has been reported for the newest implementation commits.

## Latest implementation increment

`planning/blender_execution_boundary.py` now explicitly requires `ReplanAuthorization` for `execute_authorized_replan()` rather than accepting an arbitrary authorization object. This makes the fresh-evidence binding explicit at the Blender boundary and prevents a generic `ActionAuthorization` from being accidentally reused for corrective replanning.

`tests/test_blender_replan_authorization_boundary.py` adds focused coverage for:

- rejecting ordinary `ActionAuthorization` at the corrective Blender boundary;
- accepting a `ReplanAuthorization` bound to the exact fresh evidence and action;
- refusing stale evidence before the executor is called.

This is intentionally a narrow contract hardening change. It does not move authorization into the transport layer or weaken receipt/verification requirements.

## Current architecture

```text
Qwen / agent proposal
 -> Atlas validation
 -> fresh evidence
 -> corrective planning
 -> explicit ReplanAuthorization
 -> BlenderAutonomousExecutor
 -> BlenderExecutionBoundary
 -> BlenderToolAdapter / authorized capability
 -> normalized result
 -> immutable execution receipt
 -> fresh independent evidence
 -> verification / replan
 -> completion or conservative recovery
```

Key production files:

- `planning/blender_result_contract.py` — strict immutable `BlenderExecutionResult(tool, ok, state, details)` and fail-closed normalization.
- `planning/blender_tool_adapter.py` — explicit Blender capability registry and legacy `status`/`error` normalization at the adapter edge.
- `planning/blender_execution_boundary.py` — raw, verified, receipt-bound, and authorized-replan execution APIs; corrective replans now require `ReplanAuthorization`.
- `planning/replan_authorization.py` — immutable evidence+action authorization for recovery replans.
- `planning/blender_execution_receipt.py` — immutable receipt binding exact tool arguments and normalized result.
- `planning/blender_verification.py` — fail-closed success verification.
- `planning/blender_autonomous_executor.py` — autonomous runtime connection, last-result/receipt tracking, and receipt matching.

Qwen is the proposal layer only. Atlas owns validation, authorization, execution boundaries, evidence, receipts, and verification. Photogrammetry remains upstream of Blender for the future Digital Twin pipeline.

## Validation status

- **Test 313 passed** — earlier action-runner validation.
- **141 passed** — earlier focused suite baseline.
- Full-suite collection was repaired by removing the stale Unreal transport test that imported missing `planning.unreal_adapter_production`.
- Latest complete run: **589 passed / 18 failed**.
- The 18 failures are real integration/contract regressions, concentrated around corrective-runtime compatibility, legacy synthetic result shapes, marker evidence sequencing, marker task action count, and adapter compatibility.
- The newest replan-authorization hardening has **not** yet been covered by a reported runner result.

**Do not report the branch as green. The authoritative latest full-suite result is `589 passed / 18 failed`.**

## Current known issues

1. Corrective-runtime integration still needs separation from Blender-specific result/receipt assumptions.
2. Some generic corrective-runtime tests use synthetic results such as `{"status": "created"}`. Do not weaken the strict Blender result contract; normalization belongs at `BlenderToolAdapter`.
3. Marker evidence completeness is checked too early in several failing paths. Fix sequencing, not verification strictness.
4. Marker task-definition expectations currently conflict with the implementation's evidence list and need reconciliation against the intended declarative contract.
5. One older `BlenderToolAdapter` test expects raw underlying behavior while the current adapter intentionally normalizes legacy results.
6. `planning.unreal_adapter_production` is absent; the stale test importing it was removed. Unreal is not the current blocker.
7. Local Windows checkout has untracked `.blend` fixtures. Leave them untracked unless explicitly required.
8. No newer validation has been reported after the `589/18` baseline.

## Runtime / development setup

```text
C:\Users\Gavin's PC\Desktop\Atlas
branch: feat/replan-race-gate
tracking: origin/feat/replan-race-gate
```

Development and validation command:

```powershell
python -m pytest -q
```

Live proof uses actual Windows/Blender execution. Corrective runtime was kept Python 3.9 compatible. The action runner is available and the user has explicitly authorized workflow testing again; nevertheless, only results actually reported by the runner are treated as verified.

## Exact resume sequence

1. Run the focused new replan-boundary tests and then the full suite through the active runner.
2. Use the resulting failures as the authoritative work queue; do not assume the old 589/18 categories are unchanged.
3. Preserve explicit `ReplanAuthorization` binding to fresh evidence and exact replacement actions.
4. Separate generic corrective-runtime execution from Blender-specific result/receipt assumptions at the integration point.
5. Keep legacy `status` normalization confined to `planning/blender_tool_adapter.py`.
6. Fix marker evidence sequencing and reconcile the marker declarative single-action contract.
7. Resolve the adapter compatibility expectation against the intentional normalized API.
8. Continue until the full suite is green.
9. After green, proceed to reusable multi-operation production task composition with the same authorization, receipt, fresh-observation, independent-verification, and interruption-recovery guarantees.
10. Then extend continuation/resume state, stronger task/session identity, broader authorized Blender operations, and later Digital Twin/photogrammetry intake contracts. Unreal production remains later.

## Architectural constraints

- Qwen never receives direct Blender execution authority.
- Only explicitly admitted Blender capabilities execute.
- Corrective planning uses fresh world state.
- `ReplanAuthorization` must match fresh evidence and the exact replacement action list.
- Receipts bind the exact executed action/result.
- Missing, stale, or unbound receipts fail closed.
- Strict verified execution accepts only the structured Blender result contract.
- Legacy result normalization belongs at the Blender adapter boundary.
- Exhausting a corrective step budget is not success.
- Failed or unverifiable final verification cannot produce completion.
- Avoid bespoke per-tool lifecycle orchestration in place of the generalized runtime.
- Photogrammetry is upstream of Blender; Atlas owns canonical Digital Twin identity/state for the soccer-field-focused production pipeline.
