# Atlas Current Development Handoff

**Updated:** August 28, 2026
**Current branch:** `feat/unreal-composite-production-operation`

## Current milestone

Atlas now has a provider-neutral **controller capability runtime boundary** layered above the existing Unreal production architecture.

The current architecture is:

```text
Agent task intent
 -> AgentTaskRequest
 -> Agent entrypoint adapter
 -> Agent entrypoint router
 -> Agent process classification
 -> Capability admission
 -> Capability execution
 -> registered controller capability
 -> Unreal production controller integration
 -> Unreal production runtime adapter
 -> existing authorization / execution / recovery
 -> Unreal transport / environment
```

The generic controller layer is deliberately provider-neutral. Unreal is registered as an explicit capability rather than being hard-coded into the generic dispatcher.

## Completed in this development session

### Unreal heterogeneous production transaction

- Added the deterministic heterogeneous production composer.
- Production phases are composed as:
  - Blueprint
  - Actor Composite
  - Sequencer
  - Render
- Production recovery supports fresh reassessment and explicit replacement authorization across the production transaction.
- Added production executor, recovery adapter, controller bridge, planning boundary, runtime integration, and controller integration layers.
- Added autonomous-loop coverage for exact replacement authorization and non-repeated reassessment.

### Generic controller capability architecture

Added and validated:

- `controller/capability_request.py`
- `controller/capability_dispatch.py`
- `controller/capability_registry.py`
- `controller/capability_selection.py`
- `controller/capability_admission.py`
- `controller/capability_execution.py`
- `controller/unreal_production_capability.py`
- `controller/atlas_controller_runtime.py`
- `controller/agent_capability_bootstrap.py`
- `controller/agent_capability_runtime.py`
- `controller/agent_task_request.py`
- `controller/agent_entrypoint_router.py`
- `controller/agent_process_runtime.py`
- `controller/agent_entrypoint_adapter.py`
- `controller/agent_entrypoint_runtime.py`

The trust-boundary rules are enforced:

```text
raw agent request
    ↓
explicit admission
    ↓
canonical CapabilityRequest
    ↓
resolved registered capability
    ↓
execution
```

Execution cannot accept a raw `AgentTaskRequest` through the admitted-execution API. Legacy agent routes cannot be executed through the controller-owned execution seam. Capability selection itself does not execute handlers.

### Unreal capability integration

`UnrealProductionControllerIntegration` exposes the generic capability contract with `execute(CapabilityRequest)`.

Execution requires an explicitly supplied `UnrealAuthorizedProductionPlan` under the `authorized_production` request context. The generic capability layer does not manufacture Unreal authorization.

### Agent entrypoint integration

The new agent-entrypoint runtime provides an explicit path:

```text
AgentTaskRequest
 -> AtlasAgentEntrypointRuntime.dispatch()
 -> AtlasAgentProcessRuntime.classify()
 -> controller-owned route only
 -> execute_classified()
 -> AtlasControllerRuntime.execute_request()
```

Unmatched/legacy requests are returned to the caller without execution. The existing Blender/Qwen compatibility entrypoint remains separate and has not been replaced by this generic controller path.

## Latest validated test state

Latest focused entrypoint runtime test:

```text
3 passed
```

Latest controller/agent boundary run before this handoff update:

```text
53 passed
```

Earlier in this development session the broader production/controller regression suite reached:

```text
87 passed
```

The 87-test figure predates some of the later controller/entrypoint additions, so the full combined suite should be rerun after the current pull before declaring the entire branch green.

## Important current limitation

The real Unreal Blueprint integration status remains separate from the generic controller work.

The previously documented live Blueprint integration issue involved transport failures such as:

```text
Unreal transport failed for operation 'inspect_blueprint_state'
```

That live-runtime issue has not been revalidated during the current controller-focused work. Controller tests are not proof that live Unreal transport is healthy.

## Runtime / Unreal constraints

- Qwen proposes/reasons; it is never the execution authority.
- Python/Atlas owns validation, authorization, ordering, execution state, verification, recovery, and completion.
- Unreal is an execution environment/adapter, not the canonical Atlas Digital Twin authority.
- Successful writes never substitute for independent verification.
- Do not modify `unreal/AtlasUnrealHarness/Content/AtlasTest/BP_AtlasTest.uasset` as part of controller-layer work.
- The existing local `.uasset` modification is known to exist and must be preserved unless explicitly instructed otherwise.
- Photogrammetry remains upstream of Blender.
- Atlas remains focused on soccer-field-related digital twins and their production pipeline.

## Architectural direction

The next work should continue toward a **single real agent-to-controller request path** while preserving the existing Blender compatibility path.

Desired end state:

```text
Agent reasoning
      ↓
explicit capability intent
      ↓
AgentTaskRequest
      ↓
entrypoint runtime
      ↓
capability admission
      ↓
capability execution
      ↓
provider-specific integration
      ↓
authorization
      ↓
execution / evidence / verification / recovery
```

Do not create another parallel dispatcher, router, or authorization mechanism.

## Next development step

1. Pull and run the current combined controller/agent regression suite.
2. Add the smallest possible integration from the real Atlas agent-facing request source into `AtlasAgentEntrypointRuntime` without changing the existing Blender/Qwen behavior.
3. Validate that explicit Unreal production requests can enter through the generic entrypoint path with an already-authorized production artifact.
4. Only after that path is stable, consider extending the same mechanism to other provider capabilities.
5. Separately, restore/revalidate the real Unreal transport before declaring the live Blueprint production milestone complete.

## Useful resume commands

```powershell
cd "C:\Users\Gavin's PC\Desktop\Atlas-Unreal-Aider"

git status
git pull origin feat/unreal-composite-production-operation

python -m pytest tests/test_agent_entrypoint_runtime.py -q

python -m pytest tests/test_agent_process_runtime.py tests/test_agent_entrypoint_router.py tests/test_agent_task_request.py tests/test_agent_capability_bootstrap.py tests/test_agent_capability_runtime.py tests/test_capability_admission.py tests/test_capability_execution.py tests/test_controller_capability_dispatch.py tests/test_controller_capability_registry.py tests/test_unreal_production_capability.py tests/test_atlas_controller_runtime.py tests/test_unreal_production_controller_integration.py -q
```

For live Unreal validation, first confirm the runtime is actually running before interpreting transport failures as code failures.
