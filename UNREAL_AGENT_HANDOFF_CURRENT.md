# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 23, 2026 — multi-operation execution preflight boundary
**Current focus:** Multi-operation production execution with failure containment
**Current branch:** `feat/unreal-composite-production-operation`
**Current state:** composite planning, capability validation, production transport execution, independent post-write semantic verification, and full-plan executor preflight are implemented.

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

## New execution-containment boundary

`UnrealPlanExecutor` now preflights **every operation in the complete ordered plan before the first transport call** using the central `UnrealCapabilityRegistry` operation contract.

This closes a partial-mutation hazard where an externally constructed plan could contain a malformed later operation: previously, earlier mutations could reach Unreal before the later malformed operation was discovered. The executor now fails closed before any Unreal mutation when any operation in the plan violates the capability/argument contract.

This is deliberately executor-side defense-in-depth. Planner-generated plans remain validated by the planner; the executor remains the final execution boundary.

## Failure containment invariants

- A malformed later operation cannot cause an earlier real-Unreal mutation.
- Every write still requires an immediate verification operation.
- Verification still requires fresh evidence and independent Atlas-side semantic proof.
- Runtime transport failures stop execution immediately.
- Completed evidence and operation arguments remain available through `UnrealPlanExecutionFailure` for recovery coordination.
- Recovery must reassess fresh Unreal state and must not silently retry a failed mutation.
- Replacement mutations require explicit authorization.

## Immediate testing gate

Run the focused executor/composite regression suite:

```powershell
python -m pytest tests/test_unreal_plan_executor.py tests/test_unreal_transform_verification_planner.py tests/test_unreal_composite_operation.py tests/test_unreal_tool_schema.py -q
```

Then run the real Unreal composite gate:

```powershell
python -m pytest tests/test_unreal_composite_real_integration.py -vv -s
```

The real integration remains the engine-dependent proof boundary. The new preflight change itself is Python-side and should be established by the focused suite before spending another live Unreal run.

## Architectural invariants

- Atlas owns the Twin.
- Unreal Agent reasons/plans.
- Atlas authorizes.
- Unreal adapter executes.
- Unreal provides evidence.
- Atlas verifies semantic state independently.
- Verification evidence is marked verified only after independent proof.
- Failures require fresh evidence and explicit recovery.
- Replacement mutations require explicit plan-bound authorization.
- The Unreal Agent must never become a second autonomous authority separate from Atlas.
- Keep development isolated from the action/workflow runner.
- Do not weaken fail-closed validation.
- Preserve stateless Unreal adapter behavior.
- Preserve independent evidence verification.
- Do not change the existing Named Pipe wire protocol.
- Keep Unreal and Blender development isolated.
