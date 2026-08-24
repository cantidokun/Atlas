# Atlas Current Development Handoff

**Updated:** August 24, 2026 — end of active development session  
**Branch:** `feat/replan-race-gate`  
**Latest documented code commit:** `f9b6ca5710dbc4724775c7ee75ba3fef83597e08`  
**Current work:** authorization-bound Blender live-write path and independent authoritative verification  
**Purpose:** canonical resume point for Atlas Blender-Agent development.

## Session stop state

The user is done developing the Blender agent for the night. **Do not run workflow tests automatically on resume unless explicitly requested.** The action runner is available again, but the newest authorization/live-write changes below have not yet been runner-validated.

Atlas is being developed toward a controlled Blender write path in which no scene-writing operation can execute without explicit capability admission, exact action authorization, independent verification, and an immutable receipt.

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

The current development increment extends that architecture toward a single authorization-bound live-write choke point. These newest changes have **not yet been runner-validated**.

## Latest files added / changed this session

### `planning/blender_capability_catalog.py`

Adds explicit capability metadata for Blender tools. Each registered capability is classified as scene-writing or read-only, and scene-writing capabilities explicitly require verification. Unknown capabilities fail closed.

Current registered write capabilities include:

- `move_object`
- `set_object_rotation`
- `create_empty_marker`
- `create_collection`
- `parent_object`
- `move_object_to_collection`
- `rename_object`
- `delete_object`

Inspection/read capabilities remain separate from write authority.

### `tests/test_blender_capability_catalog.py`

Focused coverage for capability registration, write classification, verification requirements, and fail-closed handling of unknown capabilities.

### `planning/replan_authorization.py`

`ReplanAuthorization` remains the immutable recovery authorization bound to fresh evidence and the exact replacement action list. Its invariants reject malformed digests and invalid authorization identity values.

### `tests/test_replan_authorization_invariants.py`

Covers malformed digests, blank authorization identifiers, and invalidation when evidence or authorized actions change.

### `planning/blender_write_authorization.py`

Adds `BlenderWriteAuthorization` for ordinary scene-writing operations. It can only be issued for a registered write capability that requires verification and is bound to the exact `ActionSpec`.

A changed action no longer matches the authorization.

### `tests/test_blender_write_authorization.py`

Covers authorized `move_object`, rejection of read-only `inspect_scene` as a write, and rejection of changed action arguments after authorization.

### `planning/blender_execution_boundary.py`

Supports the authorization-bound write path and requires `ReplanAuthorization` specifically for corrective execution rather than accepting an arbitrary authorization object.

The existing boundary contracts remain distinct:

- `execute()` — backward-compatible raw adapter result;
- `execute_verified()` — normalized, independently verified result;
- `execute_with_receipt()` — verified result plus immutable receipt;
- `execute_authorized_write()` — exact `ActionSpec` + `BlenderWriteAuthorization` path;
- `execute_authorized_replan()` — exact one-action corrective path bound to fresh evidence and `ReplanAuthorization`.

### `planning/blender_execution_receipt.py`

Receipts support authorization binding through:

- `BlenderExecutionReceipt.create_authorized(...)`
- `BlenderExecutionReceipt.matches_authorization(...)`

The authorization identifier is represented by a digest, so the receipt is bound to the authorization without storing the raw authorization identifier.

### `tests/test_authorized_write_receipt_binding.py`

Focused coverage for authorization-bound receipt creation and authorization mismatch behavior.

### `planning/blender_live_write_gate.py`

Adds the final authorization-bound pre-live choke point. It refuses to invoke the execution boundary when the action no longer matches its authorization.

The gate now consumes the boundary's `(verified_result, receipt)` return shape and produces the explicit `BlenderLiveWriteOutcome` contract rather than treating receipt creation alone as sufficient proof.

### `tests/test_blender_live_write_gate.py`

Covers the zero-write precondition: a changed action must be rejected before the execution boundary is invoked.

### `tests/test_blender_live_write_gate_outcomes.py`

Covers the `VERIFIED` and `BLOCKED` gate outcomes.

### `tests/test_blender_live_write_gate_invariants.py`

Adds regression coverage around receipt validity and the invariant that an unbound/incomplete receipt cannot constitute verified live-write success.

### `planning/blender_live_write_result.py`

Introduces an explicit final-write outcome contract:

- `VERIFIED` — authoritative verification succeeded and a receipt exists;
- `BLOCKED` — verification/integrity did not establish success and no receipt is issued.

This prevents an ambiguous third state such as “executor reported success but verification was uncertain.”

### `tests/test_blender_live_write_result.py`

Covers blocked outcomes, required block reasons, and the verified-outcome receipt contract.

### `planning/blender_live_verification.py`

Newest session addition. Provides an independent `verify_authoritative_write(...)` helper that evaluates final authoritative state separately from executor success. It blocks when the verifier reports failure or when returned authoritative state disagrees with the requested action arguments.

### `tests/test_blender_live_verification.py`

Covers matching authoritative state, an executor-success/authoritative-state mismatch, and verifier failure.

### `live_qwen_object_rotation.py`

The live object-rotation path was brought under the authorization-bound write path so the existing rotation capability can use the shared authorization/live-gate architecture rather than bespoke write authorization.

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
- `planning/blender_execution_boundary.py` — raw, verified, receipt-bound, and authorization-bound execution APIs.
- `planning/blender_write_authorization.py` — exact-action authorization for scene-writing capabilities.
- `planning/blender_live_write_gate.py` — final authorization-bound pre-live execution choke point.
- `planning/blender_live_write_result.py` — explicit `VERIFIED` versus `BLOCKED` outcome contract.
- `planning/blender_live_verification.py` — independent authoritative post-write verification helper.
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

The authoritative latest full-suite result remains:

```text
589 passed / 18 failed
```

The newest capability/write-authorization/live-write/authoritative-verification changes have **not** yet been covered by a reported runner result. Therefore these are implementation milestones, not test-passed milestones:

- `blender_capability_catalog.py`
- `blender_write_authorization.py`
- authorization-bound receipt changes
- `blender_live_write_gate.py`
- `blender_live_write_result.py`
- `blender_live_verification.py`
- their newest focused tests
- the live object-rotation integration change

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
11. `planning/blender_live_verification.py` is currently a focused verification helper; it has not yet been integrated into `BlenderLiveWriteGate`. That integration is the next coding step.

## Runtime / development setup

```text
C:\Users\Gavin's PC\Desktop\Atlas
branch: feat/replan-race-gate
tracking: origin/feat/replan-race-gate
```

Primary validation command when development resumes:

```powershell
python -m pytest -q
```

Live proof uses actual Windows/Blender execution. The corrective runtime is kept Python 3.9 compatible. Qwen is treated as an agent/proposal layer and does not receive direct Blender execution authority.

The action runner is available again, but **do not run workflow tests automatically on resume**; the user explicitly stopped development for the night and the newest changes must be validated when development is intentionally resumed.

## Exact next steps to resume development

1. **Do not start by adding another abstraction.** First inspect and integrate `planning/blender_live_verification.py` into `BlenderLiveWriteGate` so `VERIFIED` requires authoritative state confirmation, not merely receipt binding.
2. Run the newest focused tests through the active runner only when explicitly requested.
3. Run the full suite and replace the old `589/18` baseline with the actual current result. Do not assume the old failure categories remain unchanged.
4. Fix integration regressions before expanding architecture. Keep generic corrective-runtime contracts independent of Blender-specific result/receipt assumptions.
5. Preserve the strict result contract. Legacy `status`/`error` shapes must be normalized only at `planning/blender_tool_adapter.py`.
6. Fix marker evidence sequencing so evidence is captured/validated at the correct lifecycle stage rather than weakening verification.
7. Reconcile the marker declarative contract with the intended single-action/evidence semantics.
8. Resolve the adapter compatibility expectation against the intentional normalized adapter API.
9. Prove the controlled live write: authorized `move_object` -> actual Blender subprocess -> authoritative scene verification -> `VERIFIED` -> authorization-bound receipt.
10. Prove the failure path: executor reports success while authoritative state disagrees -> `BLOCKED` -> no receipt -> no subsequent write.
11. Only after that is green, generalize the live-write path to the remaining admitted write capabilities without introducing bespoke lifecycle orchestration per tool.
12. Then move to reusable multi-operation production task composition using the same capability admission, exact authorization, fresh observation, independent verification, receipt, and interruption/replanning guarantees.
13. After the generalized runtime is green, extend continuation/resume state, stronger task/session identity, broader authorized Blender operations, and later Digital Twin/photogrammetry intake contracts. Unreal production remains later.

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
