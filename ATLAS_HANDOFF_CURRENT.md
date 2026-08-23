# Atlas Current Development Handoff

**Updated:** August 23, 2026 4:45 PM EDT  
**Branch:** `feat/replan-race-gate`  
**HEAD:** `1e2f4a5` (`test: cover legacy Blender result normalization`)  
**Purpose:** canonical resume point for Atlas Blender-Agent development.

## Current position

**MAJOR LIVE MILESTONE PASSED:** generalized Blender corrective runtime with live interruption/replanning.

The Windows/Blender live gate previously completed with:

```text
ATLAS GENERALIZED BLENDER CORRECTIVE RUNTIME GATE: PASS
receipts = 4
external_change_injected = true
```

Final independently observed state:

```text
Goal_Left_post
location = [1.0, 0.0, 0.0]
rotation = [0.0, 0.0, 45.0]

Goal_Right_post
location = [-1.0, 0.0, 0.0]
rotation = [0.0, 0.0, -45.0]
```

The proven loop is:

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

## Current architecture

Protected production path:

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

### Result contract

`planning/blender_result_contract.py` defines immutable `BlenderExecutionResult(tool, ok, state, details)` and strict normalization. Missing/invalid `ok` or `state`, malformed `details`, or non-object results fail closed. Legacy `status` results are normalized at the adapter edge rather than weakening the verified contract.

### Adapter

`planning/blender_tool_adapter.py` contains `BlenderToolAdapter`. It exposes only the explicit tool registry, preserves validated arguments, and converts legacy `status`/`error` responses to the shared `ok`/`state`/`details` shape.

### Execution boundary

`planning/blender_execution_boundary.py` provides:

- `execute()` — backward-compatible raw adapter execution.
- `execute_verified()` — strict normalized-result verification.
- `execute_with_receipt()` — verified execution plus immutable receipt.
- `execute_authorized_replan()` — requires exactly one authorized `ActionSpec`, revalidates authorization against fresh evidence, then executes with receipt binding.

### Receipt

`planning/blender_execution_receipt.py` defines immutable `BlenderExecutionReceipt`. It hashes the exact tool arguments and normalized result and can verify that a receipt still matches the executed action/result.

### Verification

`planning/blender_verification.py` is fail-closed: only a `BlenderExecutionResult` for the expected tool with `ok=True` is accepted as successful.

### Autonomous executor

`planning/blender_autonomous_executor.py` connects the autonomous runtime to the protected boundary. It resolves capabilities through `create_blender_command_registry()`, records the last normalized result and receipt, and exposes `receipt_matches_last_execution()`.

## Recent commits / changes

- `1e2f4a5` — `test: cover legacy Blender result normalization`
- `9696b85` — `fix: normalize legacy Blender tool status results`
- `f8f2ad8` — `fix: keep corrective runtime Python 3.9 compatible`
- `47c0174` — `feat: wire observer interruption hook into generalized live gate`
- `77c98a2` — `feat: add interruption-aware corrective runtime observer`
- `0ef2043` — `test: enforce receipt sequence for corrective runtime`
- `515c5a8` — `fix: replan corrective actions directly from each fresh observation`
- `0411975` — `feat: allow corrective recovery to replan from supplied fresh evidence`

## Validation history

Confirmed live / focused results from the active development conversation:

- **Test 313 passed** — earlier action-runner validation.
- **141 passed** — earlier focused suite baseline.
- A subsequent full `python -m pytest -q` initially stopped during collection because `tests/test_unreal_transport_failure_boundary.py` imported missing `planning.unreal_adapter_production`; that stale test was removed in commit `895709a978bc7faa33118cb36fec59f5cb520bef`.
- The next full-suite run reached actual tests: **589 passed / 18 failed**.
- The 18 failures were identified as contract/integration regressions concentrated around corrective-runtime compatibility, legacy synthetic result shapes, marker evidence sequencing, and marker task action count. They were not collection failures.

Do **not** claim the current branch is green. The authoritative latest reported full-suite result is **589 passed / 18 failed**.

## Current known issues

1. **Corrective-runtime / Blender boundary contract mismatch.** `BlenderExecutionBoundary.execute_authorized_replan()` currently always calls `execute_with_receipt()`. Generic corrective-runtime tests that use synthetic executors/results therefore cross into Blender-specific receipt/result assumptions.
2. **Legacy synthetic result compatibility.** Some corrective-runtime tests use shapes such as `{"status": "created"}`. Legacy normalization should remain at the Blender adapter edge; do not weaken `BlenderExecutionResult` or verified execution to accept arbitrary legacy shapes globally.
3. **Marker evidence sequencing.** Several marker tests fail because evidence-completeness validation occurs before marker-specific evidence is available. Fix sequencing/contract rather than bypassing verification.
4. **Marker task definition.** `test_marker_task_definition_is_declarative_and_write_verified` currently observes two actions where the test expects one; reconcile the declarative task definition without weakening write verification.
5. **BlenderToolAdapter compatibility.** One older test expects raw underlying adapter behavior while the current adapter normalizes results. Preserve the intentional normalization contract and determine whether the affected test belongs to the legacy/raw API or normalized adapter API.
6. **Unreal production adapter.** `planning.unreal_adapter_production` is not present on the current branch; the stale transport-boundary test that imported it was removed. Unreal remains later-stage work, not the current blocker.
7. **Untracked Blender fixtures.** The user's Windows checkout contains local `.blend` fixtures including `atlas_live_mutation.blend`, `atlas_live_smoke.blend`, `object_move_CORRECT.blend`, `object_move_INCORRECT.blend`, `marker_task_CORRECT.blend`, `marker_task_INCORRECT.blend`, and related CORRECT/INCORRECT fixtures. Leave these untracked unless explicitly needed in source control.

## Runtime / development setup

Current development is being exercised from the user's Windows PowerShell checkout:

```text
C:\Users\Gavin's PC\Desktop\Atlas
branch: feat/replan-race-gate
tracking: origin/feat/replan-race-gate
```

The live Blender proof runs against actual Windows/Blender execution. The corrective runtime was explicitly kept Python 3.9 compatible. The test command used by the active runner is:

```powershell
python -m pytest -q
```

The current branch source is also being inspected/committed through GitHub. The user's local checkout was reported clean except for the untracked `.blend` fixtures; source changes were committed and pushed.

Qwen is the agent/proposal layer; it does not receive direct Blender execution authority. Atlas remains the authorization, validation, execution-boundary, evidence, receipt, and verification layer.

Workflow/action-runner tests are not to be represented as current proof unless explicitly run and reported by the user. The live Windows/Blender gate is the authoritative proof of the generalized corrective-runtime milestone.

## Immediate resume plan

1. Fix the corrective-runtime/Blender-boundary separation without weakening the strict Blender result contract.
2. Keep legacy `status` normalization localized to `BlenderToolAdapter`.
3. Preserve fail-closed authorization, receipt binding, and independent verification.
4. Fix marker evidence sequencing so required evidence exists before evidence-completeness validation.
5. Reconcile the marker declarative task to the intended single-action contract.
6. Reconcile the affected `BlenderToolAdapter` compatibility test with the intentional normalized API.
7. Run the complete suite again:

```powershell
python -m pytest -q
```

8. Use the new failure count as the next authoritative baseline; do not report success until the full suite is green.
9. Once green, proceed to the next architectural milestone: reusable multi-operation production task composition with the same authorization, receipt, fresh-observation, independent-verification, and interruption-recovery guarantees.
10. After that, extend continuation/resume state, stronger task/session identity, broader authorized Blender operations, and later Digital Twin/photogrammetry intake contracts. Unreal production workflows remain later.

## Architectural constraints to preserve

- Qwen never receives direct Blender execution authority.
- Only explicitly admitted Blender capabilities execute.
- Corrective planning uses fresh world state.
- Authorization must match the fresh evidence and exact action.
- Receipts bind to the exact executed action/result.
- Missing, stale, or unbound receipts fail closed.
- Strict verified execution accepts only the structured Blender result contract.
- Legacy result normalization belongs at the Blender adapter boundary.
- Exhausting a corrective step budget is not success.
- Failed or unverifiable final verification cannot produce completion.
- Do not replace generalized production runtime behavior with bespoke per-tool lifecycle orchestration.
- Photogrammetry is upstream of Blender; Atlas owns canonical Digital Twin identity/state for the soccer-field-focused production pipeline.
