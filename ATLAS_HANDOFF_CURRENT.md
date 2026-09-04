# Atlas Current Development Handoff

**Updated:** September 4, 2026
**Current branch:** `integrate-origin-main-with-render-receipt`
**Latest controller-boundary commit:** `f2e8ccf4` — `test: harden Unreal controller result evidence contract`

## Current milestone

Atlas now has a provider-neutral **agent-to-controller execution boundary** layered above the existing Unreal production architecture while preserving the established Blender/Qwen compatibility path.

The current controller architecture is:

```text
Agent model response
 -> explicit ATLAS_CONTROLLER_REQUEST marker
 -> AgentControllerIntent
 -> AgentTaskRequest
 -> AgentControllerHost / AgentControllerLoopAdapter
 -> AgentEntrypointRuntime
 -> AgentProcessRuntime classification
 -> capability admission
 -> capability execution
 -> registered provider capability
 -> provider-specific integration
 -> typed controller result contract
 -> evidence / verification / receipt / recovery
```

The model is never the authorization source. Trusted provider context is installed by the host and selected only by the parsed request's provider.

## Completed in the current development session

### Explicit model-to-controller request boundary

The agent-facing controller seam includes:

- `controller/agent_controller_intent.py`
- `controller/agent_controller_response_bridge.py`
- `controller/agent_controller_loop.py`
- `controller/agent_execution_context.py`
- `controller/agent_controller_host.py`
- `controller/agent_task_request.py`
- `controller/agent_entrypoint_contract.py`
- `controller/agent_entrypoint_router.py`
- `controller/agent_process_runtime.py`
- `controller/agent_entrypoint_runtime.py`

The model may request a controller capability only through the explicit structured marker:

```text
ATLAS_CONTROLLER_REQUEST: { ... }
```

Ordinary model responses continue through the existing agent/Blender path unchanged.

The parser accepts nested JSON payloads and does not execute anything. The bridge converts the parsed request into the canonical task-request seam.

### Host-owned trusted execution context

`AgentExecutionContext` owns trusted provider state for one agent execution. It can install typed `TrustedUnrealContext` instances or other typed `AgentTrustedContext` values.

Trusted context resolution follows this rule:

```text
parsed model request provider
        ↓
host-owned execution context lookup
        ↓
already-installed trusted context
```

The model's capability, intent metadata, and context values do not select or create trusted state.

Provider context replacement is prohibited within the same execution context. A new execution context is required for replacement.

### Host lifecycle boundary

`AgentControllerHost` now owns:

```text
AgentEntrypointRuntime
        +
AgentExecutionContext
        +
AgentControllerLoopAdapter
```

The host can optionally accept an existing process/runtime, provides a typed Unreal production factory binding an already-authorized `UnrealProductionControllerIntegration` and `TrustedUnrealContext`, and applies the same host-trust rule to explicit `dispatch()` as to model-originated controller requests.

Caller-owned `AgentTaskRequest` objects remain unchanged when trusted context is bound.

### Unreal trust binding

`TrustedUnrealContext` binds:

```text
UnrealAuthorizedProductionPlan
        +
authoritative UnrealTaskIntent
        +
approved sequence asset path
```

The binding validates that the authorized production plan and authoritative intent share the same intent ID. Model-supplied context cannot replace these trusted values at the controller boundary.

### Synthetic host-to-Unreal composition boundary

The synthetic integration path exercises the real Atlas controller stack through a typed Unreal production integration with only the irreversible external execution replaced by a deterministic test seam.

The validated path proves:

```text
model request / explicit dispatch
 -> host
 -> trusted context
 -> Unreal capability admission
 -> Unreal controller integration
 -> synthetic execution seam
```

A forged model authorization/context cannot replace the host-installed `UnrealAuthorizedProductionPlan`, authoritative intent, or sequence asset path. An Unreal production request without host-installed authorization fails closed and does not invoke the integration.

### Unreal controller result / evidence boundary

`UnrealProductionControllerEvent` now exposes a typed, engine-neutral `result_contract`.

The contract separates lifecycle execution state from verified render identity and carries only evidence that has already crossed Atlas's verification boundary:

```text
UnrealProductionControllerEvent
        ↓
UnrealProductionResultContract
        ↓
verified UnrealEvidence + matching UnrealRenderReceipt
```

For render-complete workflow results, the contract requires the final evidence to be verified, to originate from `inspect_render_job`, and to match the issued `UnrealRenderReceipt`. A mismatched evidence/receipt pair is rejected.

The contract does not create, infer, or extend authorization.

## Latest validated controller test state

The focused host/controller regression checkpoint completed successfully:

```text
89 passed in 1.07s
```

The current working tree also contains the next deterministic result/evidence hardening layer, which has not yet been run by the user as part of the focused checkpoint.

No live Unreal/action-runner test was run as part of this development layer.

## Existing live Unreal proof

The existing live Unreal production/render receipt proof remains valid as previously established, including the real Named Pipe transport, production execution path, independent evidence, and render receipt verification.

The live Blueprint production boundary remains a separate milestone and must not be considered green merely because the controller-layer tests pass.

## Unreal Blueprint status

The narrow Blueprint production boundary still follows:

```text
READ   inspect_blueprint_state
WRITE  set_blueprint_metadata
WRITE  compile_blueprint
VERIFY verify_blueprint_state
```

The previously identified remaining live issue is evidence shape: Blueprint state evidence must expose persisted metadata under `metadata` after the mutation/compile sequence.

The next Unreal-dependent gate remains the real Blueprint integration suite. Do not broaden into arbitrary Blueprint graph authoring until that boundary is green.

## Next development step

1. Pull the latest branch and run the focused host/controller suite including the new result/evidence tests.
2. Fix any deterministic contract regression without touching the live action runner.
3. Extend the result contract only where it clarifies verified evidence/receipt identity or lifecycle state without creating a second authority.
4. Keep the live Blueprint metadata/evidence correction separate from controller-host work.
5. Only run the live Unreal/action-runner gate when explicitly authorized.

## Architectural invariants

- Atlas owns the canonical Digital Twin.
- Qwen reasons and proposes; it never authorizes or directly executes production capabilities.
- Atlas owns validation, authorization, ordering, execution state, verification, and recovery.
- Unreal executes authorized operations and provides evidence.
- Verification must use fresh state and must not echo requested write arguments.
- Recovery requires fresh evidence.
- Replacement requires new exact authorization.
- The Unreal Agent is not a second autonomous authority.
- Preserve the Named Pipe wire protocol.
- Keep Unreal isolated from Blender and the action/workflow runner.
- Do not introduce entity discovery or an Atlas-side entity cache to solve fixture problems.
- Preserve fail-closed validation.
- Maintain language-agnostic boundaries so performance-critical implementations can later move into C++ incrementally.
- Do not run workflow/action-runner tests unless explicitly authorized.
