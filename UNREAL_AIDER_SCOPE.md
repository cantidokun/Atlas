# Atlas Unreal Agent — Aider Scope

## Purpose

This workspace is for continued development of the Atlas Unreal Agent only. It starts from the existing Unreal validation work and must not replace or restructure the existing Atlas architecture.

## Current gate

**Current session state — September 18, 2026: development is paused.**

The Unreal Agent has now proven and published the major production-boundary
milestones through MRQ submission outcome propagation:

```text
Controller trust boundary              COMPLETE + LIVE
Blueprint semantic verification        COMPLETE + LIVE
Render-state semantic verification     COMPLETE + LIVE
Render-job identity verification       COMPLETE + LIVE
Composite actor production             COMPLETE + LIVE
Shot-level production continuity       COMPLETE + LIVE-PROVEN + PUBLISHED
MRQ artifact attribution (Slice 1+2)   COMPLETE + LIVE-PROVEN + PUBLISHED
MRQ start-callback identity (Slice D)  COMPLETE + LIVE-PROVEN + PUBLISHED
MRQ submission outcome propagation     COMPLETE + LIVE-PROVEN + PUBLISHED
```

The current published branch is `reconcile/unreal-autonomy-origin-20c6d10`.
The implementation baseline for the current paused state is `7172848`;
the branch may advance only with documentation-only pause updates.

The MRQ queue lifecycle and queue-isolation reviews both returned **CLEAR WITH
MINOR FINDINGS**. Shared queue semantics remain the default. Queue
consumption/deletion and private-queue migration are not implemented and are
not authorized; private isolation remains a trigger-based future option (T1-T4).

The MRQ pass-failure attribution review also returned **CLEAR WITH MINOR
FINDINGS**, but measured B1 and B2 both abort the pass before the subsequent
queued job executes. Therefore the hypothesized healthy-job-then-pass-failure
clobber was not demonstrated and receipt impact remains **UNPROVEN**.

The next authorized action is a **read-only design gate** deciding whether a
small terminal-state state-fidelity correction is worthwhile. No production
implementation is authorized while paused.

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

The next active surface is **MRQ pass-failure state fidelity**.

This is a design question only:

> Is the small guard that prevents a stronger job-scoped terminal verdict from
> being overwritten by a later pass-scoped aggregate worth implementing?

Measured evidence must remain explicit:

- B1 and B2 were genuine UE 5.6.1 failures;
- both aborted the pass before the subsequent queue job executed;
- the healthy-job-then-pass-failure clobber was not reached;
- receipt impact is therefore unproven.

The next gate must not silently turn this into a receipt-correctness claim.

F9 (failed jobs unreadable through the authorized inspection path) remains
separate.

```text
Do not implement state-fidelity yet.
Do not start queue consumption.
Do not start private-queue migration.
Do not start registry pruning.
Do not touch Blender.
```

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
