# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 23, 2026 — fresh-state recovery disposition
**Current focus:** Multi-operation production execution with failure containment and recovery coordination
**Current branch:** `feat/unreal-composite-production-operation`
**Current state:** composite planning, capability validation, production transport execution, independent post-write semantic verification, full-plan executor preflight, semantic write-to-verifier binding, explicit failure reassessment planning, and fresh-state recovery disposition are implemented.

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

## Execution-containment boundaries

`UnrealPlanExecutor` preflights **every operation in the complete ordered plan before the first transport call** using the central `UnrealCapabilityRegistry` operation contract.

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

The failure object exposes `reassessment_plan()`, producing a fresh, read-only Unreal inspection plan for the failed operation's entity scope:

```text
READ  inspect_target_actors
VERIFY verify_target_actor_mapping
```

The reassessment plan deliberately contains **no WRITE operations** and does not replay the failed mutation. Recovery must execute the fresh-state reassessment explicitly, then construct and authorize any replacement mutation separately.

The failure object now also exposes `assess_reassessment(result)`. This compares the latest reassessment evidence against the failed operation's requested state and returns an explicit recovery disposition without authorizing or executing a mutation:

```text
already_applied       fresh state already matches the requested state
replacement_required  fresh state differs from the requested state
manual_review          no safe comparator or usable reassessment evidence
```

This closes the next recovery-coordination gap: the system can distinguish a mutation that actually took effect despite a later verification failure from a state that still requires an explicitly authorized replacement operation.

## Recovery invariants

- A malformed later operation cannot cause an earlier real-Unreal mutation.
- Every write requires an immediate verification operation.
- Every supported production write requires its matching semantic verifier.
- Verification requires fresh evidence and independent Atlas-side semantic proof.
- Runtime transport failures stop execution immediately.
- Completed evidence and operation arguments remain available through `UnrealPlanExecutionFailure` for recovery coordination.
- Recovery reassessment is read-only and scoped to the failed operation's entities.
- Recovery must reassess fresh Unreal state and must not silently retry a failed mutation.
- Recovery disposition is derived only from fresh reassessment evidence.
- Replacement mutations require explicit authorization.
- `assess_reassessment()` never authorizes or executes a mutation.

## Testing gate

After implementation changes, run the focused Unreal regression suite:

```powershell
python -m pytest tests/test_unreal_plan_executor.py tests/test_unreal_transform_verification_planner.py tests/test_unreal_composite_operation.py tests/test_unreal_tool_schema.py tests/test_unreal_plan_authorization.py tests/test_unreal_failure_reassessment.py -q
```

Then run the real Unreal composite gate:

```powershell
python -m pytest tests/test_unreal_composite_real_integration.py -vv -s
```

The real integration remains the engine-dependent proof boundary. The fresh-state recovery disposition is Python-side and should be established by the focused suites before another live Unreal run.

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
