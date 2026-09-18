# Unreal Composite Production — Milestone Closeout

**Date:** September 17, 2026  
**Branch:** `reconcile/unreal-autonomy-origin-20c6d10`  
**Checkpoint:** `1ba04f71b7cf9f20cd74a33670c332502b715529`  

## Status

**COMPLETE AND LIVE-PROVEN.**

The composite actor production boundary is now proven both deterministically and against a real Unreal Engine 5.6.1 editor over the established Windows Named Pipe transport.

## Scope

The composite operation is intentionally thin. It groups already-authorized primitive actor mutations without introducing a new transport primitive, authorization source, evidence type, or orchestration authority.

Supported primitive mutations:

```text
set_actor_location
set_actor_rotation
set_actor_scale
apply_material_variant
apply_niagara_variant
```

The composite ordering is deterministic:

```text
transforms
  ↓
material
  ↓
Niagara
```

The planner expands every primitive into the existing Atlas execution model, including fresh READs where required and an immediate semantic VERIFY after each WRITE.

## Deterministic validation

```text
28 passed
  tests/test_unreal_composite_operation.py
  tests/test_unreal_composite_verification_evidence.py
  tests/test_unreal_production_roundtrip.py

20 passed
  tests/test_unreal_tool_schema.py
  tests/test_unreal_plan_executor.py
```

After the live-test compatibility correction, the combined targeted regression was rerun:

```text
48 passed in 0.35s
```

## Live Unreal validation

Exact test:

```text
tests/test_unreal_composite_real_integration.py::test_real_unreal_composite_production_applies_verifies_and_restores
```

Exact command:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_unreal_composite_real_integration.py::test_real_unreal_composite_production_applies_verifies_and_restores -q -s
```

Result:

```text
1 passed in 4.79s
```

Environment:

```text
Unreal Engine 5.6.1
\\.\pipe\AtlasUnrealTransport
FIELD_SURFACE fixture
```

The live gate exercised:

```text
inspect_target_actors
→ set_actor_location / verify_actor_location
→ set_actor_rotation / verify_actor_rotation
→ set_actor_scale / verify_actor_scale
→ inspect_material_state / apply_material_variant / verify_material_variant
→ inspect_niagara_state / apply_niagara_variant / verify_niagara_variant
→ restoration plan
```

The test's restoration executes in a `finally` block. This proves the restoration execution completed without raising during a passing run; it does not constitute a separate post-restore readback proof, and the milestone record does not claim one.

## Live issue encountered and corrected

The first live connection attempt initially failed only because the Unreal Named Pipe server was not running. Once the editor transport was running, the test reached real Unreal and exposed a test-only evidence-shape assumption.

`UnrealEvidence.observed_state` is frozen into immutable nested mappings. The integration-test helper `_variant()` required concrete `dict` instances and therefore rejected valid `MappingProxyType` values.

The smallest repair was:

```python
from collections.abc import Mapping

if not isinstance(value, Mapping):
    raise AssertionError(...)
```

This was committed as:

```text
ad780241  test: accept immutable variant evidence in live composite gate
```

The repair is deliberately confined to the live integration test. It does not weaken evidence immutability and does not modify the production adapter, executor, verifier, transport, capability registry, or C++ harness.

## Architecture result

The composite boundary now demonstrates another complete Atlas execution slice:

```text
authorized composite intent
        ↓
UnrealTaskPlanner
        ↓
existing READ / WRITE / VERIFY operations
        ↓
UnrealPlanExecutor
        ↓
UnrealAdapterProduction
        ↓
Windows Named Pipe
        ↓
real Unreal Editor
        ↓
fresh evidence
        ↓
semantic verification
```

This milestone is therefore closed. Additional composite capabilities should not be added merely to enlarge the abstraction.

## Deferred work

The following items remain outside this milestone:

- relative output-file normalization;
- stronger render frame/range/frame-count semantics;
- render-job recovery;
- sequence-asset continuity;
- cross-plan output-directory/output-format binding;
- artifact completeness versus frame range;
- multi-job/distributed rendering;
- editor-session persistence;
- broader Movie Render Queue expansion;
- future receipt/HMAC redesign and result-contract evolution where required.

These are architectural follow-ups, not defects in the completed composite boundary.
