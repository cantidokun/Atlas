# Atlas Unreal Agent

## Current status

The Unreal Agent has a tested production/recovery architecture for controlled Unreal operations and now has a provider-neutral **agent-to-controller trust boundary** above that production stack.

Current branch:

```text
integrate-origin-main-with-render-receipt
```

The current focused controller/agent boundary checkpoint is:

```text
62 passed
```

No live Unreal/action-runner test was run for that checkpoint.

## Operating model

```text
AI / Unreal Agent
    ↓
explicit controller intent
    ↓
host-owned trusted execution context
    ↓
Atlas validation + authorization
    ↓
Unreal adapter execution
    ↓
Unreal evidence
    ↓
independent Atlas semantic verification
```

The Unreal Agent is not an independent authorization authority.

The host-owned execution context carries already-authorized state; it does not create authorization.

## Production boundaries already proven

The current production architecture covers:

- Actor inspection and transforms
- Material variants
- Niagara variants
- Sequencer playback range
- Composite production plans
- Windows Named Pipe execution
- Independent semantic verification
- Fresh-state recovery
- Explicit replacement authorization
- Heterogeneous recovery
- Real render execution and receipt verification

Every supported production write is paired with independent verification.

## Agent-to-controller boundary

Explicit controller requests use:

```text
ATLAS_CONTROLLER_REQUEST: { ... }
```

The request is parsed without execution into `AgentControllerIntent`, then normalized to `AgentTaskRequest`.

The host owns:

```text
AgentControllerHost
    ├── AgentEntrypointRuntime
    ├── AgentProcessRuntime
    ├── AgentControllerLoopAdapter
    └── AgentExecutionContext
```

Trusted provider context is selected only by the parsed request provider. Model-supplied capability, intent metadata, and context values cannot create or replace trusted execution state.

## Trusted Unreal context

`TrustedUnrealContext` binds:

```text
UnrealAuthorizedProductionPlan
+ authoritative UnrealTaskIntent
+ approved sequence asset path
```

The production plan's intent ID must match the authoritative Unreal task intent ID before the context can be installed.

This provides the source-level foundation for future real model-driven Unreal production execution without making the model an authorization authority.

## Sequencer

```text
READ  inspect_sequencer_state
WRITE set_sequencer_playback_range
VERIFY verify_sequencer_playback_range
```

Sequencer verification compares fresh Unreal state with the requested frame range rather than trusting the write response.

## Recovery

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
Independent verification
```

`already_applied` operations are not replayed. `replacement_required` operations require new exact authorization. `manual_review` never becomes an automatic mutation.

## Blueprint — current development target

Blueprint remains the next engine-dependent production capability.

The narrow first production slice is:

```text
READ   inspect_blueprint_state
WRITE  set_blueprint_metadata
WRITE  compile_blueprint
VERIFY verify_blueprint_state
```

The live mutation/compile path had been proven to execute, but the remaining known issue is evidence shape: persisted Blueprint metadata must appear in the verified Blueprint state under `metadata`.

The intended state evidence is:

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

## Validation status

The Python/controller boundary currently has a green focused checkpoint of:

```text
62 passed
```

This does not replace the live Unreal integration gate.

When the source-level host integration is complete and explicitly authorized, run the relevant live Unreal gate. Separately revalidate the Blueprint evidence boundary before declaring Blueprint production-complete.

## Next after Blueprint

After Blueprint reaches a complete production boundary, build Render:

```text
READ   inspect_render_state
WRITE  configure_render
VERIFY verify_render_state
```

Movie Render Queue execution should follow only after deterministic render configuration verification is established.

## Invariants

- Atlas owns the canonical Digital Twin.
- Atlas authorizes Unreal mutations.
- Unreal executes only within the authorized plan.
- Unreal supplies evidence; Atlas verifies independently.
- Failed mutations require fresh evidence and explicit recovery.
- Replacement mutations require new plan-bound authorization.
- The model never becomes the authorization authority.
- The Named Pipe wire protocol remains stable.
- Unreal remains isolated from Blender and the action/workflow runner.
- Failure injection belongs only in the disposable validation harness.
- Do not weaken fail-closed validation.
