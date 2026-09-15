# Atlas Unreal Agent — Aider Scope

## Purpose

This workspace is for continued development of the Atlas Unreal Agent only. It starts from the existing Unreal validation work and must not replace or restructure the existing Atlas architecture.

## Current gate

The real Unreal Engine 5.6 smoke test has passed, the first real Unreal production/render-receipt paths have been proven, and the agent-to-controller trust boundary has now been reconciled with origin and validated against real Unreal execution.

The reconciled branch is deterministic green, and the explicitly authorized live controller gate passed. The next engine-dependent milestone is the live Blueprint production boundary, which is separate and is not green.

Current branch and HEAD:

```text
reconcile/unreal-autonomy-origin-20c6d10
fe2322f7e76caf3115e3e5be6dafce05d62251ca
```

## Current milestone — September 15, 2026

The explicit model-to-controller path has a host-owned execution context and has been validated against real Unreal execution:

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
provider integration
```

The host owns trusted provider context for one agent execution. Trusted Unreal context is installed from an already-authorized production artifact and authoritative Unreal task intent.

The reconciled branch currently reports:

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

The explicitly authorized live controller gate also passed:

```text
tests/test_agent_controller_host_production_real_integration.py
1 passed in 10.77s
```

No other workflow/action-runner tests were run.

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

The current architecture includes the Unreal Agent planning boundary, capability registry, strict operation contract, deterministic task planning, engine-neutral evidence contract, production adapter boundary, Windows Named Pipe transport, plan executor, recovery policy, reassessment decision/planner, recovery orchestrator/coordinator, disposable Unreal Engine 5.6 validation harness, heterogeneous production boundary, render receipt verification, and provider-neutral controller capability runtime.

## Controller trust-boundary milestone — PASSED, AND VALIDATED AGAINST REAL UNREAL EXECUTION

The agent controller host trust boundary has now been validated live: a model response carrying forged authorization and context could not substitute host-installed trusted state, the authorized production executed against a real Unreal editor, and the result returned fresh verified evidence, a matching render receipt, and a typed controller result contract.

The current source-level controller boundary proves:

1. model output is recognized only through the explicit `ATLAS_CONTROLLER_REQUEST` marker;
2. the request is parsed into a typed `AgentControllerIntent`;
3. the intent becomes the canonical `AgentTaskRequest`;
4. the host provides the controller runtime and execution context;
5. trusted provider state is resolved from the model request's provider only;
6. model-supplied context cannot override trusted context values;
7. trusted Unreal context requires an already-authorized production plan and matching authoritative task intent;
8. provider context cannot be replaced inside the same execution context;
9. legacy Blender/Qwen paths remain separate from controller execution.

## Current Unreal production boundary

The existing Unreal production architecture remains:

```text
Atlas plan
    ↓
authorization
    ↓
production adapter
    ↓
Windows Named Pipe
    ↓
real Unreal Editor
    ↓
execution
    ↓
fresh evidence
    ↓
independent verification
```

The successful render receipt proof remains part of the established live boundary. The newer host/controller path is not yet a live Unreal proof.

## Blueprint status

Blueprint remains a separate engine-dependent milestone. Its intended narrow production sequence is:

```text
READ   inspect_blueprint_state
WRITE  set_blueprint_metadata
WRITE  compile_blueprint
VERIFY verify_blueprint_state
```

The previously identified live issue is persistence of Blueprint metadata in the returned evidence shape. Do not expand into arbitrary Blueprint graph authoring until the narrow metadata/compile boundary is independently green.

## Next development phase

The source-level host integration and the live controller-to-production gate are both complete.

When development resumes:

1. the test-only `_variant` Mapping compatibility repair in `tests/test_agent_controller_production_real_integration.py` — APPLIED (September 15, 2026), so the helper accepts `collections.abc.Mapping` instead of requiring `dict` (evidence is now frozen);
2. both live controller production tests rerun green against real Unreal (1 passed each);
3. then begin the separate live Blueprint production boundary: narrow metadata mutation, compile, verify, and persisted metadata under `metadata` in post-mutation evidence.

Items 1 and 2 are closed as of September 15, 2026. Residual follow-up (same defect class, NOT fixed — out of scope for the controller gate): `tests/test_unreal_composite_real_integration.py`, `tests/test_unreal_heterogeneous_recovery_real_integration.py`, `tests/test_unreal_production_workflow_real_integration.py`, `tests/test_unreal_material_variant_real_integration.py`.

Blueprint work must not begin until it is separately authorized as its own live gate, and no existing contract may be weakened to make a live test pass.

## Git/workspace separation

The Unreal Aider workspace remains isolated from the Blender development workspace. Work on Unreal should occur from the dedicated Unreal development checkout/branch. Do not point Aider at the Blender checkout.

## Aider handoff

Before local implementation work:

- confirm the dedicated Unreal checkout state;
- use the intended Unreal development branch;
- keep Aider separate from the Atlas Python runtime where appropriate;
- never commit secrets;
- use `UNREAL_AGENT_HANDOFF_CURRENT.md` and this scope document as continuation context;
- use local edit/test/commit loops only when the relevant tests are authorized;
- keep GitHub Actions as the remote regression authority;
- do not run the action/workflow runner unless the user explicitly authorizes it.

Aider is an implementation tool, not a replacement for the Atlas architecture, Git history, or regression gates.
