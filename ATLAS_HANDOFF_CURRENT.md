# Atlas Current Development Handoff

**Updated:** September 15, 2026
**Current branch:** `reconcile/unreal-autonomy-origin-20c6d10`
**HEAD:** `9625dd712c05126ae2b12c85d4cf034a396cb58a` (supersedes the earlier checkpoint `fe2322f7e76caf3115e3e5be6dafce05d62251ca`; the milestone commits are `e1a1285` documentation checkpoint, `fe4bba2` controller live-gate tests, `72a6578` Blueprint semantic verification, `a964ab6` Blueprint documentation closeout, `87b7e82` render-state semantic verification, `9625dd7` render-state documentation closeout)
**Latest controller-boundary commit:** `fe2322f` — `test: align synthetic Unreal result fixtures with strict contract`
**Status:** reconciled + deterministic green + live controller-to-Unreal production green + live Blueprint production green

## Current milestone

Atlas now has a provider-neutral **agent-to-controller execution boundary** layered above the existing Unreal production architecture while preserving the established Blender/Qwen compatibility path.

As of September 15, 2026 the boundary has been reconciled with the origin branch and **validated against real Unreal execution**: an already-authorized Unreal production operation travels the complete host-owned controller path and returns fresh independently produced evidence, a matching render receipt, and a typed controller result contract.

```text
reconciled baseline
 └── 09015d9 → c0321bd → bac08e8 → fe2322f
```

**SUPERSEDED (2026-09-15) — HISTORICAL:** the live controller path is green; the live Blueprint production boundary is separate and is still not green. **CURRENT STATE:** both are green — the narrow Blueprint production boundary was live-gated on September 15, 2026 with Atlas semantic verification (see `UNREAL_AGENT_HANDOFF_CURRENT.md`, "Live Blueprint semantic verification gate").

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

The focused host/controller regression checkpoint is green on the reconciled branch:

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

The result/evidence hardening layer that was previously unvalidated has now been merged from origin, resolved to origin's strict exact-type `verified_render` implementation, and validated on both Python 3.11.16 and Python 3.9.6.

The explicitly authorized live controller gate has also passed:

```text
tests/test_agent_controller_host_production_real_integration.py
1 passed in 10.77s
```

No other live Unreal/action-runner test was run as part of this development layer.

## Existing live Unreal proof

The existing live Unreal production/render receipt proof remains valid as previously established, including the real Named Pipe transport, production execution path, independent evidence, and render receipt verification.

**SUPERSEDED (2026-09-15) — HISTORICAL:** the live Blueprint production boundary remains a separate milestone and must not be considered green merely because the controller-layer tests pass. It was subsequently gated green on its own live evidence, not on the controller-layer tests.

## Unreal Blueprint status

**CURRENT STATE (2026-09-15): the narrow Blueprint production boundary is GREEN, live-gated against real UE 5.6.1 over the existing Named Pipe transport, and Blueprint semantic verification is implemented, registered and live-proven (3 passed; `evidence_ledger[3].verified is True` on the metadata mutation path, `evidence_ledger[2].verified is True` on the compile-only path). Full record: `UNREAL_AGENT_HANDOFF_CURRENT.md`.**

The narrow Blueprint production boundary follows:

```text
READ   inspect_blueprint_state
WRITE  set_blueprint_metadata
WRITE  compile_blueprint
VERIFY verify_blueprint_state
```

**SUPERSEDED (2026-09-15) — HISTORICAL:** the previously identified remaining live issue is evidence shape: Blueprint state evidence must expose persisted metadata under `metadata` after the mutation/compile sequence. **Resolved live:** the persisted metadata appears under `metadata` at the mutation, compile, verify and fresh-inspection stages, and verification now binds asset identity, compile status and the authorized metadata key/value.

The real Blueprint integration suite has since been gated green (September 15, 2026). Arbitrary Blueprint graph authoring remains out of scope and would need its own design gate.

## Next development step

1. Confirm the reconciled branch and HEAD. The September 15 checkpoint working tree carries 7 tracked
   documentation modifications plus the applied two-line test-only mapping repair; nothing is committed.
2. The test-only `_variant` mapping repair is **APPLIED (September 15, 2026)** in the working tree
   (two lines: `from collections.abc import Mapping` and `if not isinstance(value, Mapping):`), and both
   live controller production tests were rerun green against a real UE 5.6.1 editor (1 passed in 9.53s and
   1 passed in 6.10s) with the fixture restored to 0/0/0, identity rotation, 1/1/1.
3. Residual follow-up (same defect class, NOT fixed — out of scope for the controller gate):
`tests/test_unreal_composite_real_integration.py`,
`tests/test_unreal_heterogeneous_recovery_real_integration.py`,
`tests/test_unreal_production_workflow_real_integration.py`,
`tests/test_unreal_material_variant_real_integration.py`.
4. The live Blueprint production boundary was completed and gated green on September 15, 2026 (metadata mutation, compile, verify, and verified metadata evidence) ? Blueprint production is green. Render configuration/state semantic verification (`verify_render_state`) was subsequently promoted to the executor's semantic-verification registry and live-gated green the same day (1 passed on Unreal Engine 5.6.1 over the existing Named Pipe; `result.evidence_ledger[2].verified is True`), with the executor now the sole producer of the render-state `verified` flag and the verifier no longer setting it. The render-job identity semantic-verification milestone was then implemented, deterministically validated, and live-gated green against the real Movie Render Queue path: 47 R-J1?R-J8 cases passed on both Python 3.11 and 3.9, and the real render-workflow gate passed 1/1 on Unreal Engine 5.6.1 over the existing Named Pipe with `job_state["job_id"] == result.job_id`. The receipt and persisted receipt carried the same job identity. The tracked `AtlasRenderConfig.uasset` was restored byte-for-byte to HEAD after the live save side effect. The render-job identity milestone is complete; its remaining deferred issues are documented in `UNREAL_AGENT_HANDOFF_CURRENT.md`. The next active development surface now requires a fresh architectural assessment.
5. Only run live Unreal/action-runner gates when explicitly authorized.

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
