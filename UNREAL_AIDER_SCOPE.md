# Atlas Unreal Agent — Aider Scope

## Purpose

This workspace is for continued development of the Atlas Unreal Agent only. It starts from the existing Unreal validation work and must not replace or restructure the existing Atlas architecture.

## Current gate

The real Unreal Engine 5.6 smoke test has passed, the first real Unreal production/render-receipt paths have been proven, the agent-to-controller trust boundary has been reconciled with origin and validated against real Unreal execution, Blueprint semantic verification is live-proven, render-state semantic verification is live-proven, render-job identity semantic verification is live-proven, and the composite actor production boundary is now deterministic-green and live-proven against UE 5.6.1.

The composite production milestone is closed with:

```text
28 passed — composite deterministic suite
20 passed — schema/executor regression
1 passed  — live UE 5.6.1 composite gate
48 passed — post-helper targeted regression
```

The live composite gate proved the real Named Pipe path for:

```text
inspect_target_actors
→ set_actor_location / verify_actor_location
→ set_actor_rotation / verify_actor_rotation
→ set_actor_scale / verify_actor_scale
→ inspect_material_state / apply_material_variant / verify_material_variant
→ inspect_niagara_state / apply_niagara_variant / verify_niagara_variant
→ composite restoration
```

The only live failure encountered in this milestone was a test-only evidence-container assumption: frozen `MappingProxyType` evidence was rejected by a helper requiring concrete `dict`. The smallest repair was to use `collections.abc.Mapping`. Production code was not changed.

Current branch and HEAD:

```text
reconcile/unreal-autonomy-origin-20c6d10
ad780241ee5ef7e409efbf6a02b69abee792c1a1
```

`ad780241` is the current published checkpoint and has parent `5ecf429` (render-job identity semantic-verification documentation closeout).

## Current milestone — September 17, 2026

The explicit model-to-controller path has a host-owned execution context and has been validated against real Unreal execution. The Unreal production path now contains independently live-proven boundaries for controller trust, Blueprint semantic verification, render-state semantic verification, render-job identity semantic verification, and composite actor production.

Composite production is intentionally thin: it groups already-authorized primitive actor mutations; it does not create a new transport primitive, new authorization authority, or new evidence architecture.

The proven composite planner/executor boundary is:

```text
CompositeActorProductionOperation
 ↓
UnrealTaskPlanner
 ↓
UnrealTaskPlan
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

## Architectural invariants

- Atlas owns the canonical Digital Twin.
- The Unreal Agent reasons and plans; it does not authorize.
- Atlas authorization remains authoritative.
- The host-owned execution context may carry already-authorized state, but it does not create authorization.
- The model cannot create, replace, or select trusted authorization state through its response payload.
- The Unreal adapter executes authorized operations.
- Unreal provides independent execution evidence.
- Atlas verifies that evidence independently.
- The Unreal adapter remains stateless.
- Mutation failures and uncertain state require fresh authoritative evidence before recovery.
- Automatic mutation retry is prohibited.
- Composite production remains a convenience grouping over existing primitives, not a new authority layer.
- Preserve the existing Named Pipe wire protocol.
- Keep Unreal isolated from Blender and the action/workflow runner.

## Aider operating rules

1. Preserve existing Unreal contracts and fail-closed behavior.
2. Do not weaken, remove, bypass, or rewrite tests merely to make them pass.
3. Do not modify Blender-specific implementation or tests unless a shared-interface change is demonstrably required and explicitly reviewed.
4. Preserve the disposable Unreal harness and keep the established smoke-test behavior intact after relevant changes.
5. Prefer small, deterministic changes with regression coverage.
6. Keep Unreal-specific code and tests clearly scoped.
7. Treat `UNREAL_AGENT_HANDOFF_CURRENT.md` as the authoritative Unreal continuation context.
8. For complex changes, audit before editing and verify affected tests before committing when test execution is authorized.
9. Do not introduce a second authorization authority inside Unreal or the generic controller layer.
10. Do not revisit AdapterExecutionBridge or Option B.
11. Do not change the existing Named Pipe wire protocol.
12. Do not introduce entity discovery or an Atlas-side entity cache.
13. Do not add metrics unless a source audit establishes a concrete need.
14. Do not run workflow/action-runner tests unless the user explicitly authorizes them.
15. Continue isolated source-level development when it cannot create system conflicts.
16. Stop at the next genuine Unreal-dependent gate rather than inventing additional engine-specific complexity prematurely.

## Existing Unreal work

The current architecture includes the Unreal Agent planning boundary, capability registry, strict operation contract, deterministic task planning, engine-neutral evidence contract, production adapter boundary, Windows Named Pipe transport, plan executor, recovery policy, reassessment decision/planner, recovery orchestrator/coordinator, disposable Unreal Engine 5.6 validation harness, heterogeneous production boundary, render receipt verification, provider-neutral controller capability runtime, render-state semantic verification, render-job identity semantic verification, Blueprint semantic verification, and composite actor production.

## Composite production milestone — COMPLETE AND LIVE-PROVEN

The composite boundary groups five already-authorized primitive mutation types:

```text
set_actor_location
set_actor_rotation
set_actor_scale
apply_material_variant
apply_niagara_variant
```

The grouping is deterministic and stable: transforms first, material second, Niagara third. The planner expands every primitive into the existing READ/WRITE/VERIFY execution shape, so every mutation remains independently auditable and semantically verified.

Deterministic validation:

```text
28 passed — tests/test_unreal_composite_operation.py
              tests/test_unreal_composite_verification_evidence.py
              tests/test_unreal_production_roundtrip.py
20 passed — tests/test_unreal_tool_schema.py
              tests/test_unreal_plan_executor.py
```

Live validation:

```text
test: tests/test_unreal_composite_real_integration.py::test_real_unreal_composite_production_applies_verifies_and_restores
engine: UE 5.6.1
transport: \\.\pipe\AtlasUnrealTransport
result: 1 passed in 4.79s
```

Post-repair regression:

```text
48 passed in 0.35s
```

The live test reached real Unreal before the test-only mapping issue, and after the repair it completed the full mutation/verification/restoration path. The test restoration executes from `finally`; it does not constitute a separate post-restore observation, so documentation must not overstate it as an independently read-back restoration proof.

## Test-only immutable-evidence compatibility repair

`tests/test_unreal_composite_real_integration.py` originally assumed nested evidence values were concrete `dict` instances. The real evidence contract freezes nested mappings, so valid `MappingProxyType` values were rejected by the helper even though the evidence was present and readable.

The published repair is:

```python
from collections.abc import Mapping

if not isinstance(value, Mapping):
    raise AssertionError(...)
```

This helper is intentionally test-only. Its purpose is to let integration tests consume the immutable evidence contract without weakening production immutability or changing the execution/evidence architecture.

Residual same-class helper audits remain possible in other live tests; they are not part of the closed composite milestone unless one of those tests is explicitly exercised.

## Controller trust-boundary milestone — PASSED, AND VALIDATED AGAINST REAL UNREAL EXECUTION

The agent controller host trust boundary has now been validated live: a model response carrying forged authorization and context could not substitute host-installed trusted state, the authorized production executed against a real Unreal editor, and the result returned fresh verified evidence, a matching render receipt, and a typed controller result contract.

## Blueprint status

**GREEN and live-gated against real UE 5.6.1.** Blueprint semantic verification is implemented, registered and live-proven. Arbitrary Blueprint graph authoring remains out of scope and requires its own design gate.

## Render-state status

**GREEN and live-gated against real UE 5.6.1.** `verify_render_state` is registered in the executor semantic-verification map and the executor is the sole producer of the verified flag.

## Render-job identity status

**COMPLETE AND LIVE-PROVEN.** `verify_render_job` and job-addressed `inspect_render_job` bind the engine-observed job identity to the authorization-bound expectation. The real Movie Render Queue workflow gate passed against UE 5.6.1, and receipt/persisted receipt carried the same job identity.

Deferred render-job issues remain intentionally separate:

- relative output-file normalization;
- stronger frame/range/frame-count verification;
- render-job recovery;
- sequence-asset continuity;
- cross-plan output-directory/output-format binding;
- artifact completeness versus frame range;
- multi-job/distributed rendering;
- editor-session persistence;
- broader MRQ expansion;
- future receipt/HMAC redesign and result-contract evolution where required.

## Fresh architecture review — next active surface

The composite milestone should not be expanded further. The next review should address **production continuity across already-proven domains**, not introduce another convenience wrapper.

The candidate boundary is a narrow **shot-level production continuity gate** that binds, within one already-authorized intent, the existing sequence asset, sequencer range, render configuration, render submission, render-job identity, and final evidence/receipt chain.

The review must preserve these constraints:

- no new transport primitive;
- no second authorization authority;
- no cross-plan entity discovery or cache;
- no speculative distributed-rendering architecture;
- use existing operation contracts where possible;
- fresh engine reads remain authoritative;
- expected state remains derived only from authorized plan arguments;
- each WRITE still has the appropriate VERIFY immediately following it;
- render-job identity remains bound exactly as already proven;
- recovery remains fail-closed and never automatically retries a mutation.

Before implementation, the next gate should audit specifically for the remaining continuity risks already identified around sequence-asset continuity, render frame/range/frame-count semantics, and output-directory/output-format binding. The goal is to prove one coherent authorized production intent from scene state through render submission and verified result without creating a monolithic orchestration layer.

## Git/workspace separation

The Unreal Aider workspace remains isolated from the Blender development workspace. Work on Unreal should occur from the dedicated Unreal development checkout/branch. Do not point Aider at the Blender checkout.

## Aider handoff

Before local implementation work:

- confirm the dedicated Unreal checkout state;
- pull the latest published branch checkpoint;
- keep Aider separate from the Atlas Python runtime where appropriate;
- never commit secrets;
- use `UNREAL_AGENT_HANDOFF_CURRENT.md` plus the composite closeout and next-architecture-review documents as continuation context;
- use local edit/test/commit loops only when the relevant tests are authorized;
- keep GitHub Actions as the remote regression authority;
- do not run the action/workflow runner unless the user explicitly authorizes it.

Aider is an implementation tool, not a replacement for the Atlas architecture, Git history, or regression gates.
