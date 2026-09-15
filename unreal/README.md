# Atlas Unreal Engine Validation

This directory contains the disposable Unreal Engine validation harness for Atlas and documents the transition into the production Unreal execution boundary.

## Current purpose

The harness is the **real-Unreal regression fixture** for the Unreal Agent architecture. It is intentionally disposable and is not the production Unreal adapter.

The current production work has progressed beyond the original engine smoke test: the real Windows/Unreal transport, first actor-location write/restore path, and recovery reassessment path have now been exercised successfully.

## Project

Open:

```text
unreal/AtlasUnrealHarness/AtlasUnrealHarness.uproject
```

The project is Editor-only and the harness does not replace the production transport implementation.

The current harness targets **Unreal Engine 5.6**.

## Proven engine smoke test

The Unreal Automation Test:

```text
Atlas.UnrealAgent.OperationBoundary
```

has passed in Unreal Engine 5.6.1.

It remains a regression fixture and should continue to pass after relevant Unreal-side changes.

## Real production proof

The first real production Unreal execution path has also passed from the Atlas Python test suite against the running Unreal Editor.

Passed integration tests:

```text
tests/test_unreal_plan_executor_real_integration.py::test_real_unreal_plan_executor_location_write_and_restore

tests/test_unreal_recovery_coordinator_real_integration.py::test_real_unreal_recovery_coordinator_reassesses_live_state_without_retrying_write
```

These tests establish:

```text
Atlas operation
        ↓
production plan executor
        ↓
production Unreal adapter
        ↓
Windows Named Pipe transport
        ↓
real Unreal Editor
        ↓
Actor state
        ↓
independent evidence / verification
```

The recovery test additionally establishes that fresh live reassessment does **not** silently retry the previous mutation.

### Live controller-to-production proof (September 15, 2026)

The provider-neutral controller host path has now been exercised against this harness in real Unreal Engine 5.6.1:

```text
tests/test_agent_controller_host_production_real_integration.py
```

An already-authorized `FIELD_SURFACE` composite production travelled:

```text
model response → ATLAS_CONTROLLER_REQUEST → AgentControllerIntent → AgentTaskRequest
→ AgentControllerHost → AgentControllerLoopAdapter → AgentEntrypointRuntime
→ AgentProcessRuntime → capability admission → TrustedUnrealContext
→ Unreal production capability → \\.\pipe\AtlasUnrealTransport → real Unreal
→ fresh evidence → render receipt → UnrealProductionResultContract
```

The model supplied forged authorization and context; the host-installed `TrustedUnrealContext` overrode it and the execution used the host-authorized production plan, the trusted intent, and the trusted sequence asset path.

The live render completed (24 frames, 1280x720 PNG, Movie Render Queue), fresh `inspect_render_job` evidence was produced with `verified = True`, the receipt matched the final evidence, and the fixture was restored afterwards to location 0/0/0, identity rotation, scale 1/1/1.

This is a first production-boundary proof, not a claim that all future Unreal capabilities are implemented.

## Current real fixture identity

The current real integration fixture uses the exact Atlas entity mapping/tag:

```text
FIELD_SURFACE
```

If a live test reports:

```text
Actor not found for entity_id: FIELD_SURFACE
```

verify that the intended Unreal Actor has the exact `FIELD_SURFACE` mapping/tag expected by the current transport/server implementation. Do not compensate by inventing entity discovery or changing the Atlas entity contract.

## Production transport boundary

The Windows Named Pipe transport now has bounded behavior for the important failure modes:

- bounded connection availability timeout;
- overlapped request writes;
- overlapped response reads;
- bounded pending-read timeout;
- cancellation of a timed-out pending read before cleanup;
- explicit handling of pywin32 `ERROR_IO_PENDING` results;
- server-disconnect error classification;
- unchanged JSON request/response framing.

Focused transport boundary tests and the full Python regression suite have passed in the current development cycle.

## Architecture

```text
Atlas intent
    ↓
Unreal Agent / planner
    ↓
strict operation contract
    ↓
Atlas authorization
    ↓
UnrealPlanExecutor
    ↓
UnrealAdapterProduction
    ↓
Windows Named Pipe transport
    ↓
Unreal Engine
    ↓
independent evidence
    ↓
Atlas verification / recovery
```

The Unreal Agent does not become an execution authority. Atlas authorization remains authoritative.

## Current capability boundary

The current C++ transport server has a narrower executable operation surface than the Python planner declares. The first production capability has been implemented and proven through the actor inspection/location path.

Do not assume that future material, lighting, Sequencer, camera, or other planned capabilities are already executable merely because their Python-side contracts exist.

The next capability must be selected deliberately and implemented end-to-end:

```text
Atlas authorization
→ transport
→ Unreal execution
→ evidence
→ independent verification
```

## Expected live running state

The transport server starts automatically from `AtlasUnrealTransport` module startup (implemented in `AtlasTransportServer.cpp`) and listens on:

```text
\\.\pipe\AtlasUnrealTransport
```

The harness seeds its deterministic fixtures into the **active editor world** through a startup ticker. The expected live running state therefore requires the persistent fixture map to be loaded:

```text
/Game/AtlasTest/Generated/AtlasRenderFixture
```

The harness reports readiness in its log:

```text
Atlas transport server started successfully
Atlas Unreal fixtures ready in world 'AtlasRenderFixture'
```

Launching the editor without that fixture map can leave the first world context pointing at a cleaned-up world, because the server-side entity lookup resolves `GEngine->GetWorldContexts()[0]` while fixture provisioning uses the editor world. Every entity-scoped operation then fails with:

```text
Actor not found for entity_id: FIELD_SURFACE
```

This is a pre-existing harness/setup characteristic. Do not compensate for it with Atlas-side entity discovery or an entity cache. A durable C++ fallback to the active editor world (rather than indexing `GetWorldContexts()[0]`) is a possible future harness improvement, separate from the controller milestone.

## Regression rules

- Do not weaken a failing test to make it pass.
- Preserve the disposable harness.
- Preserve fail-closed validation.
- Do not change the existing Named Pipe wire protocol.
- Do not add entity discovery as a workaround for fixture configuration.
- Keep the Unreal adapter stateless.
- Keep Atlas as the authorization and verification authority.
- Do not run workflow/action-runner tests unless explicitly authorized by the user.

## Next milestone

The multi-operation production execution boundary with failure containment has since been implemented, and the provider-neutral controller host path has now been validated live against this harness (see `UNREAL_AGENT_HANDOFF_CURRENT.md`).

**SUPERSEDED (2026-09-15) — HISTORICAL:** the current next engine-dependent target is the **live Blueprint production boundary**: narrow metadata mutation, compile, verify, and persisted metadata under `metadata` in post-mutation evidence. It is **not** green and must not be conflated with the controller-layer success.

**CURRENT STATE (2026-09-15): that boundary is GREEN and live-gated against this harness** — `tests/test_unreal_blueprint_real_integration.py` passed 3 tests against Unreal Engine 5.6.1 over `\\.\pipe\AtlasUnrealTransport`, with Atlas semantic verification now binding asset identity, compile status and the authorized metadata key/value (`evidence_ledger[3].verified is True` on the metadata mutation path, `evidence_ledger[2].verified is True` on the compile-only path), while unrelated fixture metadata (`AtlasTestMarker`) is tolerated. The next engine-dependent surface to investigate is render configuration/state semantic-verification parity (`verify_render_state`), pending its own design gate.

The original Python-side proof set for this milestone was:

1. ordered evidence before mutation;
2. exact authorization of the ordered operation set;
3. correctly bound evidence for every operation;
4. deterministic execution cursor advancement;
5. safe stop on a later operation failure;
6. preservation of completed write targets;
7. fresh read-only recovery reassessment;
8. no automatic mutation retry;
9. explicit authorization for any replacement plan;
10. independent verification before completion.

After that boundary is green, run the expanded multi-operation scenario against the real Unreal Editor.

The narrow Blueprint metadata boundary is now green; Blueprint graph authoring remains out of scope and must not be expanded without its own design gate.

## Detailed continuation state

See:

```text
UNREAL_AGENT_HANDOFF_CURRENT.md
UNREAL_AIDER_SCOPE.md
```

for the current production-boundary status, architectural constraints, and exact next gate.