# Atlas Current Development Handoff

**Updated:** August 23, 2026 7:44 PM EDT  
**Branch:** `feat/replan-race-gate`  
**HEAD:** `1e2f4a5` (`test: cover legacy Blender result normalization`)  
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

No newer green full-suite result has been reported after the latest regression baseline.

## Current architecture

```text
Qwen / agent proposal
 -> Atlas validation
 -> fresh evidence
 -> corrective planning
 -> explicit authorization
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
- `planning/blender_execution_boundary.py` — raw, verified, receipt-bound, and authorized-replan execution APIs.
- `planning/blender_execution_receipt.py` — immutable receipt binding exact tool arguments and normalized result.
- `planning/blender_verification.py` — fail-closed success verification.
- `planning/blender_autonomous_executor.py` — autonomous runtime connection, last-result/receipt tracking, and receipt matching.

Qwen is the proposal layer only. Atlas owns validation, authorization, execution boundaries, evidence, receipts, and verification. Photogrammetry remains upstream of Blender for the future Digital Twin pipeline.

## Recent commits

- `1e2f4a5` — `test: cover legacy Blender result normalization`
- `9696b85` — `fix: normalize legacy Blender tool status results`
- `f8f2ad8` — `fix: keep corrective runtime Python 3.9 compatible`
- `47c0174` — `feat: wire observer interruption hook into generalized live gate`
- `77c98a2` — `feat: add interruption-aware corrective runtime observer`
- `0ef2043` — `test: enforce receipt sequence for corrective runtime`
- `515c5a8` — `fix: replan corrective actions directly from each fresh observation`
- `0411975` — `feat: allow corrective recovery to replan from supplied fresh evidence`
- `895709a978bc7faa33118cb36fec59f5cb520bef6` — removed stale `tests/test_unreal_transport_failure_boundary.py` after collection failed on missing `planning.unreal_adapter_production`.

## Validation status

- **Test 313 passed** — earlier action-runner validation.
- **141 passed** — earlier focused suite baseline.
- Full-suite collection was subsequently repaired by removing the stale Unreal transport test.
- Latest complete run: **589 passed / 18 failed**.
- Those 18 failures are real integration/contract regressions, concentrated around corrective-runtime compatibility, legacy synthetic result shapes, marker evidence sequencing, marker task action count, and one adapter compatibility expectation.

**Do not report the branch as green. The authoritative latest full-suite result is `589 passed / 18 failed`.**

## Current known issues

1. `BlenderExecutionBoundary.execute_authorized_replan()` currently routes every authorized corrective action through `execute_with_receipt()`, coupling generic corrective-runtime tests to Blender-specific result/receipt assumptions.
2. Some generic corrective-runtime tests use synthetic results such as `{"status": "created"}`. Do not weaken the strict Blender result contract; normalization belongs at `BlenderToolAdapter`.
3. Marker evidence completeness is being checked before marker-specific evidence is available in several failing paths. Fix sequencing, not verification strictness.
4. `test_marker_task_definition_is_declarative_and_write_verified` currently observes two actions where the intended contract is one.
5. One older `BlenderToolAdapter` test expects raw underlying behavior while the current adapter intentionally normalizes legacy results.
6. `planning.unreal_adapter_production` is absent; the stale test importing it was removed. Unreal is not the current blocker.
7. Local Windows checkout has untracked `.blend` fixtures including `atlas_live_mutation.blend`, `atlas_live_smoke.blend`, `object_move_CORRECT.blend`, `object_move_INCORRECT.blend`, `marker_task_CORRECT.blend`, `marker_task_INCORRECT.blend`, and related fixtures. Leave them untracked unless explicitly required.
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

Live proof uses actual Windows/Blender execution. Corrective runtime was kept Python 3.9 compatible. Workflow/action-runner tests are not current proof unless explicitly run and reported. The generalized corrective-runtime milestone is supported by the live Windows/Blender gate above.

## Exact resume sequence

1. Start from `feat/replan-race-gate` at `1e2f4a5` unless a newer commit is explicitly established.
2. Do not weaken `planning/blender_result_contract.py`, `planning/blender_verification.py`, or receipt validation to satisfy generic tests.
3. Separate generic corrective-runtime execution from Blender-specific result/receipt assumptions at the integration point.
4. Keep legacy `status` normalization confined to `planning/blender_tool_adapter.py`.
5. Preserve stale-authorization rejection, exact-action binding, immutable receipts, fresh-observation replanning, interruption handling, and independent verification.
6. Fix marker evidence sequencing and the marker declarative single-action contract.
7. Resolve the adapter compatibility expectation against the intentional normalized API.
8. Run `python -m pytest -q` and use the new result as the authoritative baseline.
9. Continue resolving issues until the full suite is green.
10. After green, proceed to reusable multi-operation production task composition with the same authorization, receipt, fresh-observation, independent-verification, and interruption-recovery guarantees.
11. Then extend continuation/resume state, stronger task/session identity, broader authorized Blender operations, and later Digital Twin/photogrammetry intake contracts. Unreal production remains later.

## Architectural constraints

- Qwen never receives direct Blender execution authority.
- Only explicitly admitted Blender capabilities execute.
- Corrective planning uses fresh world state.
- Authorization must match fresh evidence and the exact action.
- Receipts bind the exact executed action/result.
- Missing, stale, or unbound receipts fail closed.
- Strict verified execution accepts only the structured Blender result contract.
- Legacy result normalization belongs at the Blender adapter boundary.
- Exhausting a corrective step budget is not success.
- Failed or unverifiable final verification cannot produce completion.
- Avoid bespoke per-tool lifecycle orchestration in place of the generalized runtime.
- Photogrammetry is upstream of Blender; Atlas owns canonical Digital Twin identity/state for the soccer-field-focused production pipeline.
