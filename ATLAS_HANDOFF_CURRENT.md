# Atlas Current Development Handoff

**Updated:** August 24, 2026 — active development session  
**Branch:** `feat/replan-race-gate`  
**Current work:** authorization-bound Blender live-write path  
**Purpose:** canonical resume point for Atlas Blender-Agent development.

## Current position

Atlas is actively being developed toward a controlled Blender write path in which no scene-writing operation can execute without explicit capability admission, exact action authorization, independent verification, and an immutable receipt.

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

The current development increment extends that architecture toward a single, authorization-bound live-write choke point. These newest changes have **not yet been runner-validated**.

## Latest files added / changed

### `planning/blender_capability_catalog.py`

Adds explicit capability metadata for Blender tools.

Each registered capability is classified as scene-writing or read-only, and scene-writing capabilities explicitly require verification. Unknown capabilities fail closed.

Current registered write capabilities include:

- `move_object`
- `set_object_rotation`
- `create_empty_marker`
- `create_collection`
- `parent_object`
- `move_object_to_collection`
- `rename_object`
- `delete_object`

Inspection/read capabilities are kept separate from write authority.

### `tests/test_blender_capability_catalog.py`

Focused coverage for capability registration, write classification, verification requirements, and fail-closed handling of unknown capabilities.

### `planning/replan_authorization.py`

`ReplanAuthorization` remains the immutable recovery authorization bound to fresh evidence and the exact replacement action list. Its invariants reject malformed digests and invalid authorization identity values.

### `planning/blender_write_authorization.py`

Adds `BlenderWriteAuthorization` for ordinary scene-writing operations. It can only be issued for a registered write capability that requires verification and is bound to the exact `ActionSpec`.

A changed action no longer matches the authorization.

### `tests/test_blender_write_authorization.py`

Covers:

- authorized `move_object`;
- rejection of read-only `inspect_scene` as a write;
- rejection of changed action arguments after authorization.

### `planning/blender_execution_boundary.py`

Now supports the authorization-bound write path and continues to require `ReplanAuthorization` specifically for corrective execution rather than accepting an arbitrary authorization object.

### `planning/blender_execution_receipt.py`

Receipts now support authorization binding through:

- `BlenderExecutionReceipt.create_authorized(...)`
- `BlenderExecutionReceipt.matches_authorization(...)`

The authorization identifier is represented by a digest, so the receipt is bound to the authorization without storing the raw authorization identifier.

### `tests/test_authorized_write_receipt_binding.py`

Focused coverage for authorization-bound receipt creation and authorization mismatch behavior.

### `planning/blender_live_write_gate.py`

Adds the final pre-live choke point:

```text
ActionSpec
 -> BlenderWriteAuthorization
 -> BlenderLiveWriteGate
 -> BlenderExecutionBoundary
 -> verified result
 -> authorization-bound receipt
```

The gate refuses to call the execution boundary when the action no longer matches its authorization, and it verifies that the returned receipt remains bound to the authorization.

### `tests/test_blender_live_write_gate.py`

Covers the important zero-write precondition: a changed action must be rejected before the execution boundary is invoked.

### `planning/blender_live_write_result.py`

Introduces an explicit final-write outcome contract:

- `VERIFIED` — authoritative verification succeeded and a receipt exists;
- `BLOCKED` — verification/integrity did not establish success and no receipt is issued.

This prevents an ambiguous third state such as “executor reported success but verification was uncertain.”

### `tests/test_blender_live_write_result.py`

Covers blocked outcomes, required block reasons, and the verified-outcome receipt contract.

## Existing core architecture

```text
Qwen / agent proposal
 -> Atlas validation
 -> fresh evidence
 -> planning / corrective planning
 -> capability admission
 -> explicit authorization
 -> BlenderAutonomousExecutor
 -> BlenderLiveWriteGate / BlenderExecutionBoundary
 -> BlenderToolAdapter
 -> normalized Blender result
 -> independent verification
 -> immutable authorization-bound receipt
 -> fresh evidence
 -> completion or conservative recovery
```

### Core production files

- `planning/blender_result_contract.py` — strict immutable `BlenderExecutionResult(tool, ok, state, details)` and fail-closed normalization.
- `planning/blender_tool_adapter.py` — explicit Blender capability registry and legacy `status`/`error` normalization at the adapter edge.
- `planning/blender_capability_catalog.py` — explicit read/write capability authority classification.
- `planning/blender_execution_boundary.py` — raw, verified, receipt-bound, and authorized-replan execution APIs.
- `planning/blender_write_authorization.py` — exact-action authorization for scene-writing capabilities.
- `planning/blender_live_write_gate.py` — final authorization-bound pre-live execution choke point.
- `planning/blender_live_write_result.py` — explicit `VERIFIED` versus `BLOCKED` outcome contract.
- `planning/replan_authorization.py` — immutable evidence+action authorization for corrective replans.
- `planning/blender_execution_receipt.py` — immutable receipt binding exact tool arguments, normalized result, and optionally authorization identity.
- `planning/blender_verification.py` — fail-closed success verification.
- `planning/blender_autonomous_executor.py` — autonomous runtime connection, last-result/receipt tracking, and receipt matching.

Qwen is the proposal layer only. Atlas owns validation, authorization, execution boundaries, evidence, receipts, and verification. Photogrammetry remains upstream of Blender for the future Digital Twin pipeline.

## Validation status

### Proven results

- **Test 313 passed** — earlier action-runner validation.
- **141 passed** — earlier focused suite baseline.
- Windows/Blender generalized corrective-runtime gate passed with **4 receipts** and an injected external change followed by successful replan/recovery.
- Full-suite collection was repaired by removing the stale Unreal transport test that imported missing `planning.unreal_adapter_production`.
- Latest complete reported full-suite result: **589 passed / 18 failed**.

### Important validation rule

**Do not report the current branch as green.**

The authoritative latest full-suite result is still:

```text
589 passed / 18 failed
```

The newest capability/write-authorization/live-write changes have **not** yet been covered by a reported runner result. Therefore the following are implementation milestones, not test-passed milestones:

- `blender_capability_catalog.py`
- `blender_write_authorization.py`
- authorization-bound receipt changes
- `blender_live_write_gate.py`
- `blender_live_write_result.py`
- their newest focused tests

## Current known issues

1. Corrective-runtime integration still needs separation from Blender-specific result/receipt assumptions.
2. Some generic corrective-runtime tests use synthetic results such as `{"status": "created"}`. Do not weaken the strict Blender result contract; normalization belongs at `BlenderToolAdapter`.
3. Marker evidence completeness is checked too early in several failing paths. Fix sequencing, not verification strictness.
4. Marker task-definition expectations currently conflict with the implementation's evidence list and need reconciliation against the intended declarative contract.
5. One older `BlenderToolAdapter` test expects raw underlying behavior while the current adapter intentionally normalizes legacy results.
6. `planning.unreal_adapter_production` is absent; the stale test importing it was removed. Unreal is not the current blocker.
7. Local Windows checkout has untracked `.blend` fixtures. Leave them untracked unless explicitly required.
8. No newer runner result has been reported for the latest authorization/live-write changes.
9. The actual live `move_object` path still needs to be proven end-to-end through the Windows/Blender subprocess with authoritative post-execution state verification.
10. The adversarial case where the executor reports success but authoritative Blender state disagrees still needs a live/integration proof that produces `BLOCKED` and prevents subsequent writes.

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

Live proof uses actual Windows/Blender execution. The corrective runtime is kept Python 3.9 compatible. Qwen is treated as an agent/proposal layer and does not receive direct Blender execution authority.

The user has explicitly authorized workflow testing again. Nevertheless, only results actually reported by the active runner are treated as verified.

## Exact next steps to resume development

1. **Run the newest focused tests through the active runner.** Start with capability, write-authorization, receipt-binding, live-gate, and live-write-result tests.
2. **Run the full suite** and replace the old `589/18` failure list with the actual current failures. Do not assume the old categories remain unchanged.
3. **Fix integration regressions before expanding architecture.** Keep generic corrective-runtime contracts independent of Blender-specific result/receipt assumptions.
4. **Preserve the strict result contract.** Legacy `status`/`error` shapes must be normalized only at `planning/blender_tool_adapter.py`.
5. **Fix marker evidence sequencing** so evidence is captured/validated at the correct lifecycle stage rather than weakening verification.
6. **Reconcile the marker declarative contract** with the intended single-action/evidence semantics.
7. **Resolve the adapter compatibility expectation** against the intentional normalized adapter API.
8. **Prove the controlled live write:** authorized `move_object` -> actual Blender subprocess -> authoritative scene verification -> `VERIFIED` -> authorization-bound receipt.
9. **Prove the failure path:** executor reports success while authoritative state disagrees -> `BLOCKED` -> no receipt -> no subsequent write.
10. **Only after that is green**, generalize the live-write path to the remaining admitted write capabilities without introducing bespoke lifecycle orchestration per tool.
11. **Then move to reusable multi-operation production task composition** using the same capability admission, exact authorization, fresh observation, independent verification, receipt, and interruption/replanning guarantees.
12. After the generalized runtime is green, extend continuation/resume state, stronger task/session identity, broader authorized Blender operations, and later Digital Twin/photogrammetry intake contracts. Unreal production remains later.

## Architectural constraints

- Qwen never receives direct Blender execution authority.
- Only explicitly admitted Blender capabilities execute.
- Corrective planning uses fresh world state.
- `ReplanAuthorization` must match fresh evidence and the exact replacement action list.
- Ordinary scene writes must match an exact `BlenderWriteAuthorization`.
- Receipts bind the exact executed action/result and, for authorized writes, the authorization identity.
- Missing, stale, changed, or unbound authorization fails closed.
- Strict verified execution accepts only the structured Blender result contract.
- Legacy result normalization belongs at the Blender adapter boundary.
- `VERIFIED` requires authoritative verification and a receipt; `BLOCKED` carries no receipt.
- Exhausting a corrective step budget is not success.
- Failed or unverifiable final verification cannot produce completion.
- Avoid bespoke per-tool lifecycle orchestration in place of the generalized runtime.
- Photogrammetry is upstream of Blender; Atlas owns canonical Digital Twin identity/state for the soccer-field-focused production pipeline.
