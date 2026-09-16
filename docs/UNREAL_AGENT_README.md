# Atlas Unreal Agent

## Current status

The Unreal Agent has a tested production/recovery architecture for controlled Unreal operations and now has a provider-neutral **agent-to-controller trust boundary** above that production stack.

Current branch:

```text
reconcile/unreal-autonomy-origin-20c6d10
```

Current HEAD:

```text
fe2322f7e76caf3115e3e5be6dafce05d62251ca
```

The reconciled branch is deterministic green:

```text
canonical focused suite (13 modules, exact command below) : 160 passed, 2 deselected
broader deterministic Unreal/controller/agent/
  capability/evidence/receipt sweep                 : 742 passed, 5 skipped
Python 3.9 focused parity (same 13 modules)         : 160 passed, 2 deselected
four directly affected contract surfaces
  (unreal_production_result_contract, unreal_production_workflow,
   unreal_evidence_contract, unreal_render_receipt) : 37 passed

CORRECTED 2026-09-15: the previously recorded focused figure
("268 passed, 1 skipped, 1 deselected") is not reproducible on fe2322f from any
recorded selection and is superseded by the figures above. Exact focused command:

.venv/Scripts/python.exe -m pytest tests/test_agent_controller_*.py tests/test_agent_entrypoint_*.py \
  tests/test_agent_execution_context.py tests/test_agent_trusted_context.py tests/test_agent_task_request.py \
  tests/test_agent_process_runtime.py tests/test_agent_process_runtime_identity.py \
  tests/test_capability_admission.py tests/test_capability_execution.py \
  tests/test_unreal_production_result_contract.py tests/test_unreal_evidence_contract.py \
  tests/test_unreal_render_receipt.py tests/test_unreal_render_receipt_store.py -m "not integration" -q
```

The explicitly authorized live controller gate has passed:

```text
tests/test_agent_controller_host_production_real_integration.py
1 passed in 10.77s
```

No other live Unreal/action-runner test was run for that checkpoint.

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

This boundary has been validated against real Unreal execution: a model response carrying forged authorization and context could not substitute the host-installed trusted state, and the authorized production executed against a real Unreal editor.

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

## Blueprint production boundary — GREEN (September 15, 2026)

Blueprint is no longer a development target: the narrow production boundary is live-gated against real Unreal Engine 5.6.1 over the existing Named Pipe transport, and its semantic verification is implemented, registered and live-proven (3 passed; `evidence_ledger[3].verified is True` on the metadata mutation path, `evidence_ledger[2].verified is True` on the compile-only path).

The narrow first production slice that was completed is:

```text
READ   inspect_blueprint_state
WRITE  set_blueprint_metadata
WRITE  compile_blueprint
VERIFY verify_blueprint_state
```

**SUPERSEDED (2026-09-15) — HISTORICAL:** the live mutation/compile path had been proven to execute, but the remaining known issue is evidence shape: persisted Blueprint metadata must appear in the verified Blueprint state under `metadata`. **Resolved live:** it does, at the mutation, compile, verify and fresh-inspection stages; Atlas verification additionally binds asset identity, compile status and the authorized metadata key/value, and tolerates unrelated metadata keys (the fixture's `AtlasTestMarker`).

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

The narrow production boundary is now green; arbitrary Blueprint graph authoring remains out of scope and would need its own design gate.

## Validation status

The reconciled Python/controller boundary is deterministic green (canonical focused suite 160 passed / 2 deselected — the earlier "268 focused" figure was not reproducible and is superseded; broader deterministic sweep 742 passed / 5 skipped as originally recorded, rising to 766 passed / 5 skipped with the Blueprint milestone cases; Python 3.9 parity confirmed), and the live Unreal controller gate has passed: a real Unreal Engine 5.6.1 editor executed an already-authorized `FIELD_SURFACE` composite production through the host-owned controller path and the existing Named Pipe transport, returning fresh verified evidence, a matching render receipt, and a typed controller result contract.

**SUPERSEDED (2026-09-15) — HISTORICAL:** the Blueprint evidence boundary remains a separate live gate and must be revalidated before declaring Blueprint production-complete. **Resolved:** the Blueprint production boundary was gated green the same day, with the metadata mutation and compile-only paths both returning Atlas-verified evidence. The test-only mapping compatibility repair in the older live controller test is **APPLIED (September 15, 2026)** and both live controller production tests were rerun green.

Residual follow-up (same defect class, NOT fixed): `tests/test_unreal_composite_real_integration.py`,
`tests/test_unreal_heterogeneous_recovery_real_integration.py`,
`tests/test_unreal_production_workflow_real_integration.py`,
`tests/test_unreal_material_variant_real_integration.py`.

## Next after Blueprint

With the Blueprint production boundary complete, Render configuration was next — and it is now done and live-gated: `verify_render_state` is registered in the executor's semantic-verification registry, the executor is the sole producer of its `verified` flag, the verifier no longer sets the flag itself, expected state comes only from the authorized VERIFY arguments, and normalization is unchanged. The earlier deferred "`verify_render_state` flag asymmetry" is resolved; note that the historical claim that this evidence never carried `verified=True` was inaccurate, because the old verifier set the flag itself — the real asymmetry was the missing registry membership plus that second flag producer:

```text
READ   inspect_render_state
WRITE  configure_render
VERIFY verify_render_state
```

Deterministic render configuration verification is now established (24 semantic matrix cases, deterministic green, and live-proven on UE 5.6.1). Movie Render Queue execution and render job/result verification are the next engine-dependent surface; they remain separate from this milestone and need their own design gate.

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
