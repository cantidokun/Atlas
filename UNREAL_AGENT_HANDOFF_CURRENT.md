# Atlas Unreal Agent — Current Development Handoff

**Updated:** September 2, 2026
**Branch:** `integrate-origin-main-with-render-receipt`
**Controller-boundary checkpoint:** focused host/controller suite green

## Current checkpoint

The Unreal Agent development has now progressed through the **agent-to-controller trust boundary**. The Python/controller side is green for the current focused tests, while live Unreal Blueprint production remains a separate, still-open engine-dependent milestone.

The important distinction is:

```text
controller-layer green
≠
live Unreal Blueprint boundary green
```

The controller path now has a host-owned execution context capable of carrying already-authorized Unreal production state into the explicit agent/controller request path.

## What is completed

### Provider-neutral controller boundary

The explicit request path is:

```text
model response
 ↓
ATLAS_CONTROLLER_REQUEST
 ↓
AgentControllerIntent
 ↓
AgentTaskRequest
 ↓
AgentControllerHost
 ↓
AgentControllerLoopAdapter
 ↓
AgentEntrypointRuntime
 ↓
AgentProcessRuntime
 ↓
capability admission
 ↓
capability execution
 ↓
UnrealProductionControllerIntegration
```

Ordinary Blender/Qwen reasoning and tool execution remain outside this controller path.

### Trusted execution context

`AgentExecutionContext` is host-owned and scoped to one agent execution.

It carries already-authorized provider context and does not create authorization. Provider selection comes only from the parsed controller request. Model-supplied capability, intent metadata, or context values cannot create or replace trusted state.

Within one execution context, provider context replacement is prohibited. Replacement requires a new execution context.

### Trusted Unreal binding

`TrustedUnrealContext` binds:

```text
UnrealAuthorizedProductionPlan
+ authoritative UnrealTaskIntent
+ approved sequence asset path
```

The authorization's plan intent ID must match the authoritative Unreal task intent ID before the context can be installed.

### Host lifecycle

`AgentControllerHost` owns the controller runtime, process runtime, loop adapter, and execution context. It also provides the explicit Unreal production composition point for an already-authorized production integration/context pair.

This is the source-level foundation required before permitting real model-driven Unreal production execution.

## Latest validated test state

Focused controller/agent boundary suite:

```text
62 passed
```

The validated scope includes:

- controller intent parsing
- nested explicit request extraction
- trusted context behavior
- trusted Unreal context validation
- execution-context provider binding
- controller loop adapter
- agent controller host lifecycle
- synthetic agent-to-controller end-to-end behavior

No live Unreal workflow/action-runner test was run for this checkpoint.

## Existing live Unreal proof

The previously established live Unreal proof remains the reference for the existing production/render boundary, including the Named Pipe transport, real Unreal execution, independent evidence, and render receipt verification.

Those live results do not automatically validate the newer model-to-controller host path.

## Blueprint production milestone

The narrow Blueprint production sequence remains:

```text
READ   inspect_blueprint_state
WRITE  set_blueprint_metadata
WRITE  compile_blueprint
VERIFY verify_blueprint_state
```

The remaining live Blueprint issue previously identified is that the post-mutation Blueprint evidence must expose persisted metadata under the `metadata` field. The mutation/compile execution itself had already succeeded; the failure was in the evidence shape.

The intended evidence remains:

```json
{
  "asset_path": "/Game/AtlasTest/BP_AtlasTest.BP_AtlasTest",
  "blueprint_name": "BP_AtlasTest",
  "compile_status": "success",
  "is_up_to_date": true,
  "generated_class": "...",
  "metadata": {
    "AtlasMutation": "production-boundary-1"
  }
}
```

Do not expand into arbitrary Blueprint graph authoring until this narrow production boundary is green.

## Next development gate

When development resumes, first finish the source-level integration between the actual agent-facing runtime and `AgentControllerHost` without disturbing the existing Blender/Qwen path.

Then, after that boundary is explicitly ready, the next engine-dependent gate is the live Unreal controller-to-production execution test using a real pre-authorized `TrustedUnrealContext`.

The live Blueprint evidence issue should be revalidated separately and must not be conflated with controller-layer success.

## Architectural progression

The intended provider path remains:

```text
Atlas task intent
 ↓
plan
 ↓
authorization
 ↓
trusted host context
 ↓
explicit model/controller request
 ↓
capability admission
 ↓
production execution
 ↓
fresh evidence
 ↓
independent verification
 ↓
recovery if required
```

Every capability must preserve this control philosophy.

## Architectural invariants

- Atlas owns the canonical Digital Twin.
- Atlas plans and authorizes.
- Qwen proposes/reasons; it is never the execution authority.
- Unreal executes authorized operations.
- Unreal provides evidence; Atlas independently verifies it.
- Successful writes are never proof of resulting state.
- Recovery requires fresh evidence.
- Replacement requires fresh exact authorization.
- The Unreal Agent does not become a second autonomous authority.
- Preserve the Named Pipe wire protocol.
- Keep Unreal isolated from Blender and the action/workflow runner.
- Do not introduce entity discovery or an Atlas-side entity cache to compensate for fixture problems.
- Do not weaken fail-closed validation.
- Preserve language-agnostic subsystem contracts for future C++ replacement of performance-sensitive components.
