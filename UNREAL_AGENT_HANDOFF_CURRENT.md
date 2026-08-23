# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 22, 2026 — composite production verification evidence
**Current focus:** Controlled composite actor production — transform + material + Niagara verification
**Current branch:** `feat/unreal-composite-production-operation`
**Current state:** composite planning, capability validation, production transport execution, and independent post-write semantic verification are implemented. The focused composite Python gate is green at 19 tests on the latest user-run revision; the real-Unreal gate is the remaining proof boundary.

## Latest completed milestone

The composite production path now decomposes a single production intent into deterministic, capability-validated operations:

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

## Verification evidence contract

`UnrealAdapterProduction` deliberately emits evidence with `verified=False`. `UnrealPlanExecutor` now flips a VERIFY evidence record to `verified=True` only after Atlas-side semantic verification succeeds. A verification failure therefore remains a hard execution failure rather than being represented as successful evidence.

Focused regression coverage now includes:

- semantic transform verification;
- material and Niagara variant verification;
- immediate write/verify execution boundaries;
- composite planner capability validation;
- composite verification evidence marked verified only after independent proof.

## Immediate testing gate

Run the focused composite suite:

```powershell
python -m pytest tests/test_unreal_verification_evidence_contract.py tests/test_unreal_composite_verification_evidence.py tests/test_unreal_transform_verification_planner.py tests/test_unreal_composite_operation.py tests/test_unreal_plan_executor.py tests/test_unreal_tool_schema.py -q
```

Then run the real Unreal gate:

```powershell
python -m pytest tests/test_unreal_composite_real_integration.py -vv -s
```

The real integration mutates `FIELD_SURFACE`, proves all five post-write verification boundaries against fresh Unreal evidence, and restores the original transform/material/Niagara state in `finally`.

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
