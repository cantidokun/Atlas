# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 23, 2026 — mixed-domain recovery gate complete; live recovery-sequence gate added
**Current focus:** Real-Unreal validation of the explicit multi-operation recovery sequence without weakening the Named Pipe boundary
**Current branch:** `feat/unreal-composite-production-operation`
**Current state:** composite planning, capability validation, production transport execution, independent post-write semantic verification, full-plan executor preflight, semantic write-to-verifier binding, explicit failure reassessment, recovery disposition, plan-bound replacement execution, an explicit end-to-end recovery coordinator, and heterogeneous material/Niagara recovery coverage are implemented and tested.

## Latest completed milestone

The deterministic heterogeneous and mixed-domain recovery gate is green:

```text
python -m pytest tests/test_unreal_recovery_mixed_domain.py tests/test_unreal_recovery_heterogeneous_domains.py tests/test_unreal_recovery_live_sequence.py tests/test_unreal_recovery_sequence.py tests/test_unreal_recovery_replacement.py tests/test_unreal_failure_reassessment.py tests/test_unreal_plan_executor.py tests/test_unreal_plan_authorization.py -q

38 passed
```

The composite production path decomposes a single production intent into deterministic, capability-validated operations:

```text
READ  inspect_target_actors
WRITE set_actor_location
VERIFY verify_actor_location
WRITE set_actor_rotation
VERIFY verify_actor_rotation
WRITE set_actor_scale
VERIFY verify_actor_scale
READ  inspect_material_state
WRITE apply_material_variant
VERIFY verify_material_variant
READ  inspect_niagara_state
WRITE apply_niagara_variant
VERIFY verify_niagara_variant
```

Each write is immediately followed by a semantic verification boundary. Transform verification compares fresh Unreal observations against the requested location/rotation/scale; material and Niagara verification compare the observed variant names.

The complete composite production path has passed against the real Unreal transport, including application, independent verification, and restoration of the original state.

## Execution-containment boundaries

`UnrealPlanExecutor` preflights every operation in the complete ordered plan before the first transport call using the central `UnrealCapabilityRegistry` operation contract.

The executor also binds each supported production write to its required semantic verifier before execution:

```text
set_actor_location       -> verify_actor_location
set_actor_rotation       -> verify_actor_rotation
set_actor_scale          -> verify_actor_scale
apply_material_variant   -> verify_material_variant
apply_niagara_variant    -> verify_niagara_variant
```

A same-entity verification is therefore not sufficient by itself. A plan cannot substitute a semantically unrelated verifier for the mutation it claims to prove. These checks are executor-side defense-in-depth; planner-generated plans remain validated by the planner.

## Failure containment and recovery boundary

`UnrealPlanExecutionFailure` preserves the failed operation, target entities, operation arguments, completed evidence, and completed operation arguments.

The failure object exposes `reassessment_plan()`, producing a fresh, read-only Unreal inspection plan for the failed operation's entity scope. Recovery reassessment deliberately contains no WRITE operations and does not replay the failed mutation.

The recovery sequence layer supports the complete multi-write control loop:

```text
Production failure
       ↓
Fresh read-only reassessment
       ↓
Per-operation disposition
       ↓
Replacement-only plan
       ↓
Separate replacement authorization
       ↓
Ordered Unreal execution
       ↓
Immediate semantic verification
       ↓
Verified recovery completion
```

`build_reassessment_plan()` covers every supported write through the failure boundary while deduplicating equivalent state-domain reads. `assess_reassessment_sequence()` classifies each relevant write as `already_applied`, `replacement_required`, or `manual_review`. `build_replacement_plan()` emits only the writes requiring replacement, preserving their original order and semantic verifiers.

`execute_recovery_sequence()` is the explicit coordinator for that control loop. It requires an authorization receipt for the fresh reassessment and **never creates a replacement authorization itself**. If replacement is required, a separately issued authorization bound to the newly constructed replacement plan must be supplied. If recovery is already applied or requires manual review, a replacement authorization is rejected rather than silently consumed.

## Heterogeneous and mixed-domain recovery coverage

Recovery now handles the same semantics across the non-transform production domains already supported by the composite path:

```text
Transform write
      ↓
Material variant write
      ↓
Niagara variant write
      ↓
Mixed-domain failure/recovery
```

The recovery sequence correctly maps composite `variant` write arguments into the verifier-specific semantic contracts:

```text
apply_material_variant -> {"name": <variant>} -> verify_material_variant
apply_niagara_variant   -> {"name": <variant>} -> verify_niagara_variant
```

The deterministic gate proves that a failure after multiple heterogeneous writes reassesses every relevant prior state domain, leaves already-applied domains untouched, and authorizes replacement only for the unresolved domain.

## Real Unreal recovery boundary

A new integration test has been added:

```text
tests/test_unreal_recovery_sequence_real_integration.py
```

It uses the actual production adapter and Windows Named Pipe transport to:

1. read the live `FIELD_SURFACE` actor;
2. apply a real location mutation;
3. model a post-write verification failure using the captured execution context;
4. build the new recovery-sequence reassessment plan;
5. read fresh state from the live Unreal Editor;
6. classify the prior write as `already_applied`;
7. restore the original live state.

This deliberately proves the **new recovery-sequence layer** against real Unreal without inventing a transport-side failure mechanism or weakening the Named Pipe boundary. It does not yet claim that a real engine-side write failure has been induced.

The existing real coordinator integration test remains useful as a lower-level regression for the same no-retry principle.

## Verified recovery contract

The deterministic recovery gates cover:

- read-only reassessment planning
- failed-entity scope preservation
- fresh reassessment evidence
- explicit per-operation recovery disposition
- `already_applied` detection
- `replacement_required` detection
- `manual_review` for unusable evidence
- replacement-only plan reconstruction
- rejection of invalid replacement dispositions
- rejection of mismatched recovery entity scope
- rejection of stale plan authorization before transport
- coordinator refusal to replace without a separate replacement authorization
- coordinator execution only through the newly authorized replacement plan
- material variant recovery
- Niagara variant recovery
- mixed-domain no-replay behavior

## Real Unreal integration gate

The complete composite production test has passed against the live Unreal transport:

```text
python -m pytest tests/test_unreal_composite_real_integration.py -vv -s

1 passed
```

The new real recovery-sequence gate is now the next engine-dependent proof:

```powershell
python -m pytest tests/test_unreal_recovery_sequence_real_integration.py -vv -s
```

A successful run will establish the new recovery sequence against live Unreal state. A skipped run because the Editor/pipe is unavailable is environmental, not a code failure.

## Recovery invariants

- A malformed later operation cannot cause an earlier real-Unreal mutation.
- Every write requires an immediate verification operation.
- Every supported production write requires its matching semantic verifier.
- Verification requires fresh evidence and independent Atlas-side semantic proof.
- Runtime transport failures stop execution immediately.
- Completed evidence and operation arguments remain available through `UnrealPlanExecutionFailure` for recovery coordination.
- Recovery reassessment is read-only and scoped to the relevant failed-plan entities.
- Recovery must reassess fresh Unreal state and must not silently retry a failed mutation.
- Recovery disposition is derived only from fresh reassessment evidence.
- Assessment never authorizes or executes a mutation.
- `already_applied` must not trigger an unnecessary replacement mutation.
- `replacement_required` produces a new plan that requires explicit authorization.
- The coordinator never creates replacement authorization implicitly.
- Replacement execution is plan-bound; stale reassessment authorization is rejected before transport.
- Manual review cannot be converted into an automatic replacement.
- Material and Niagara replacement verification must use their domain-specific semantic evidence contracts.

## Testing gate

After implementation changes, run:

```powershell
python -m pytest tests/test_unreal_recovery_mixed_domain.py tests/test_unreal_recovery_heterogeneous_domains.py tests/test_unreal_recovery_live_sequence.py tests/test_unreal_recovery_sequence.py tests/test_unreal_recovery_replacement.py tests/test_unreal_failure_reassessment.py tests/test_unreal_plan_executor.py tests/test_unreal_plan_authorization.py -q
```

Then run:

```powershell
python -m pytest tests/test_unreal_recovery_sequence_real_integration.py -vv -s
```

And retain the existing composite real-Unreal regression:

```powershell
python -m pytest tests/test_unreal_composite_real_integration.py -vv -s
```

## Next development boundary

The immediate next gate is the new real-Unreal recovery-sequence integration test. If it passes, the next engineering question is whether the Unreal harness can expose a deterministic **real engine-side failure after one or more successful writes** without modifying the Named Pipe protocol or introducing test-only production behavior. If that can be done cleanly, add that integration coverage. If not, preserve the existing real live-state reassessment proof and move to the next production capability rather than weakening the execution boundary.

The progression is now:

```text
Transform recovery
       ↓
Material recovery
       ↓
Niagara recovery
       ↓
Mixed-domain failure/recovery       ✓
       ↓
Real-Unreal recovery reassessment   ← NEXT GATE
       ↓
Real engine-side failure recovery   ← only if safely supportable
       ↓
Next Unreal production capability
```

Do not broaden into Blender development for this work. Do not modify the action/workflow runner. Do not weaken the Named Pipe boundary or fail-closed authorization model.

## Architectural invariants

- Atlas owns the Twin.
- Unreal Agent reasons/plans.
- Atlas authorizes.
- Unreal adapter executes.
- Unreal provides evidence.
- Atlas verifies semantic state independently.
- Verification evidence is marked verified only after independent proof.
- Failures require fresh evidence and explicit recovery.
- Recovery reassessment is read-only and never an implicit retry.
- Recovery disposition is informational/coordination state, not authorization.
- Replacement mutations require explicit plan-bound authorization.
- The Unreal Agent must never become a second autonomous authority separate from Atlas.
- Keep development isolated from the action/workflow runner.
- Do not weaken fail-closed validation.
- Preserve stateless Unreal adapter behavior.
- Preserve independent evidence verification.
- Do not change the existing Named Pipe wire protocol.
- Keep Unreal and Blender development isolated.
