# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 23, 2026 — live recovery sequence gate
**Current focus:** Multi-operation production execution with failure containment, fresh-state recovery, and explicitly authorized replacement mutations
**Current branch:** `feat/unreal-composite-production-operation`
**Current state:** composite planning, capability validation, production transport execution, independent post-write semantic verification, full-plan executor preflight, semantic write-to-verifier binding, explicit failure reassessment, recovery disposition, plan-bound replacement execution, an explicit end-to-end recovery coordinator, heterogeneous material/Niagara recovery coverage, and a live-Unreal recovery-sequence gate are implemented and tested.

## Latest completed milestone

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

The recovery sequence layer now supports the complete multi-write control loop:

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

## Heterogeneous recovery coverage

Recovery now handles the same semantics across the non-transform production domains already supported by the composite path:

```text
Transform write
      ↓
Material variant write
      ↓
Niagara variant write
```

The recovery sequence maps material and Niagara write arguments to the canonical capability schema and preserves domain-specific semantic verification on replacement.

Focused deterministic tests prove that a material failure can reassess a previously applied transform and replace only the material mutation, while a Niagara failure can reassess both earlier domains and replace only Niagara. Mixed-domain coverage additionally proves that already-applied domains remain untouched while only the unresolved replacement is authorized and executed.

## Live Unreal recovery gate — PASS

The new engine-dependent recovery-sequence test has passed against the real Unreal transport:

```text
python -m pytest tests/test_unreal_recovery_sequence_real_integration.py -vv -s

1 passed
```

The live gate proves that the new recovery sequence can reassess the actual `FIELD_SURFACE` Actor state over the Windows Named Pipe after a simulated post-write failure without retrying the prior mutation. The test restores the original Actor state in a `finally` block.

This is the first live proof for the new multi-operation recovery-sequence layer. It does **not** yet prove a live heterogeneous material/Niagara failure because the current real Unreal harness does not expose a deterministic failure-injection surface for those operations.

## Real Unreal integration gate

The engine-dependent composite production test has also passed against the live Unreal transport:

```text
python -m pytest tests/test_unreal_composite_real_integration.py -vv -s

1 passed
```

This remains the current full composite apply/verify/restore proof boundary.

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

Then run both live gates:

```powershell
python -m pytest tests/test_unreal_recovery_sequence_real_integration.py -vv -s
python -m pytest tests/test_unreal_composite_real_integration.py -vv -s
```

## Next development boundary

The next target is the **real-Unreal heterogeneous recovery boundary**. Before adding more Python-only recovery logic, extend the disposable Unreal validation harness only enough to create a deterministic, authorized failure condition for one heterogeneous operation while preserving the Named Pipe protocol and Atlas authorization boundary. Then prove:

```text
live composite failure
       ↓
real fresh reassessment
       ↓
per-domain disposition
       ↓
replacement-only plan
       ↓
new exact authorization
       ↓
live replacement
       ↓
independent verification
       ↓
restore original state
```

Do not fake the failure in Python and call that a real Unreal test. Do not change the Named Pipe wire protocol. Do not broaden into Blender development for this work. Do not modify the action/workflow runner.

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
