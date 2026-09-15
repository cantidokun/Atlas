# Atlas Unreal Agent — Current Development Handoff

**Updated:** September 15, 2026
**Branch:** `reconcile/unreal-autonomy-origin-20c6d10`
**HEAD:** `fe2322f7e76caf3115e3e5be6dafce05d62251ca`
**Status:** reconciled + deterministic green + live controller-to-Unreal production green

## Current checkpoint

The Unreal Agent work has been reconciled with the origin branch, and the **agent-to-controller trust boundary has now been validated against real Unreal execution**.

This is the first live proof that an already-authorized Unreal production operation can travel the complete host-owned controller path and return fresh independently produced evidence, a matching render receipt, and a typed controller result contract.

```text
live controller path green
≠
live Blueprint production boundary green
```

## Reconciled baseline

The branch chain from the previous local autonomy commit is:

```text
09015d9  feat: integrate Unreal autonomy into controller runtime
   ↓
c0321bd  fix: compose agent controller boundary from AgentControllerHost
   ↓
bac08e8  Merge origin/integrate-origin-main-with-render-receipt (12 commits)
   ↓
fe2322f  test: align synthetic Unreal result fixtures with strict contract
```

- `c0321bd` — the agent-facing runtime now composes its controller boundary from `AgentControllerHost` (host-owned runtime plus loop) instead of constructing `AtlasAgentEntrypointRuntime` and `AgentControllerLoopAdapter` directly. Committed alone; `agent.py` only.
- `bac08e8` — reconciliation merge. Exactly one conflict, `planning/unreal_production_workflow.py`, resolved to origin's strict exact-type `verified_render` implementation so that a typed `UnrealProductionExecutionResult` is required for production/render intent binding and no duck-typed self-comparison remains. The merge preserved the local `normalize_unreal_production_event` failure semantics (a failed workflow result becomes `success=False` rather than being raised), the local recovery-action capability admission, and all 14 local-only implementation paths from `09015d9`.
- `fe2322f` — test-only repair of two synthetic fixtures in `tests/test_agent_controller_host_unreal_synthetic_end_to_end.py` that had been passing only because of the removed duck-typed `verified_render` fallback.

The reconciliation is deterministic green on both Python 3.11.16 and Python 3.9.6.

## Live controller-to-production gate — PASSED

Exact test:

```text
tests/test_agent_controller_host_production_real_integration.py
```

Exact command:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_agent_controller_host_production_real_integration.py -m integration -q -s
```

Result:

```text
1 passed in 10.77s
```

This is a newly created, integration-marked, test-only live gate harness. It drives the complete real path:

```text
model text
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
TrustedUnrealContext
 ↓
Unreal production capability
 ↓
Windows Named Pipe
 ↓
real Unreal
 ↓
fresh evidence
 ↓
render receipt
 ↓
UnrealProductionResultContract
```

## Live Unreal details

```text
Unreal Engine 5.6.1
UnrealEditor-Cmd.exe
unreal/AtlasUnrealHarness/AtlasUnrealHarness.uproject
\\.\pipe\AtlasUnrealTransport
```

The C++ transport server starts from `AtlasTransportServer.cpp` (started by the `AtlasUnrealTransport` module's `StartupModule`).

The expected live harness state requires the fixture map to be loaded:

```text
/Game/AtlasTest/Generated/AtlasRenderFixture
```

Launching the editor without that fixture map can leave `GEngine->GetWorldContexts()[0]` pointing at a cleaned-up world, which makes the server-side entity lookup fail with:

```text
Actor not found for entity_id: FIELD_SURFACE
```

This was diagnosed as a pre-existing harness/setup characteristic and was **not** fixed during this gate.

## Real production operation

The proven composite production operation was reused unchanged for the live gate:

```text
FIELD_SURFACE composite production
 - set_actor_location        → 10 / 20 / 30
 - set_actor_rotation        → pitch 0 / yaw 15 / roll 0
 - set_actor_scale           → 1.1
 - apply_material_variant    → liquid_surface
 - apply_niagara_variant     → goal_burst
 - sequencer playback range  → 1–24
 - render                    → 1280x720 PNG
 - MRQ                       → 24 frames
```

The render completed successfully. The Unreal-side log confirms the render pipeline executed and finished the submitted job.

The fixture was restored afterwards and verified at:

```text
location 0 / 0 / 0
identity rotation
scale 1 / 1 / 1
```

## Trust boundary proof

The model output deliberately attempted to supply forged authorization and context:

```text
authorized_production : FORGED-BY-MODEL
intent                : FORGED-BY-MODEL (model-declared intent metadata)
sequence path         : /Game/Forged/ModelSequence
```

The host-installed `TrustedUnrealContext` overrode those values. The admitted and executed request used:

- the host-authorized production plan,
- the trusted `UnrealTaskIntent`,
- the trusted sequence asset path.

The model's values were not accepted as authority; its declared intent string survived only as diagnostic metadata on the request.

**The agent controller host trust boundary has now been validated against real Unreal execution.**

## Evidence and receipt

Fresh post-execution evidence:

```text
operation    : inspect_render_job
entity       : FIELD_SURFACE
source       : unreal-editor-atlas-transport
verified     : True
evidence digest : 81bbf55a6c29b589d3dda5f57de8dcfdeb15203617811233712a0fa810e7d853
```

The evidence job ID matched the actual render job.

Render receipt:

```text
receipt matched final evidence : True
render job ID   : B6F524E9-4527-4804-27A4-B7BD92A1CBB6
receipt digest  : aab94cdf375f00454290275e8e70493001e4d020861b8d0789787791c11240c7
```

Persisted artifact for independent inspection:

```text
C:\Users\Gavin's PC\AppData\Local\Temp\atlas-live-gate-evidence\host-path-render-receipt.json
```

## Final result contract

```text
execution.controller_executed = True
capability                    = unreal_production
event operation               = start
snapshot state                = complete
workflow_result.success       = True
verified_render               = True
failed                        = False
requires_recovery             = False
integration.complete          = True
```

The production instance was an exact `UnrealProductionExecutionResult`, and these identities matched:

```text
render.intent_id
trusted intent
production plan intent
```

`contract.final_evidence` is the verified evidence object and `contract.receipt` is the verified receipt object.

The result was grounded in real engine readback rather than merely trusting the controller request: an independent post-execution read confirmed the committed live state (location 10/20/30, material variant `liquid_surface`, Niagara variant `goal_burst`).

## New live test harness (untracked)

```text
tests/test_agent_controller_host_production_real_integration.py
```

It is an untracked, uncommitted, test-only live gate harness. It was **not** committed, and no existing production or test source was modified by the live gate.

## Test-only compatibility repair — APPLIED (September 15, 2026)

The older live test:

```text
tests/test_agent_controller_production_real_integration.py
```

was RED under the hardened evidence contract until the repair below. `UnrealEvidence.observed_state` is frozen into a `MappingProxyType` tree while its helper `_variant` requires `isinstance(value, dict)`, so the helper raises:

```text
material.variant missing from Unreal evidence
```

even though the value is present and readable. This is a **test-only** incompatibility, not a production defect; production code has no such assumption on frozen evidence.

Smallest justified repair (originally proposed):

```text
use collections.abc.Mapping rather than dict in the test helper
```

**APPLIED (September 15, 2026):** the repair is implemented in the working tree as a two-line test-only
change (`from collections.abc import Mapping`; `if not isinstance(value, Mapping):`). It is not committed.

Both live controller production tests were then rerun against a real UE 5.6.1 editor launched with the
fixture map:

```text
tests/test_agent_controller_production_real_integration.py      : 1 passed in 9.53s
tests/test_agent_controller_host_production_real_integration.py : 1 passed in 6.10s
host-gate render job id   : 1F901C1E-4AA7-6477-D7FB-81B91ED0FD94
host-gate evidence digest : 5481a35eb952e80179ba2d48e9e92d80b1657581bfcfad9482c3efc195e77c11
host-gate receipt digest  : e92769129aab7795126e66420ef4b48acff42e4813610e02166f794d4b3aec2e
live readback after execution : location 10/20/30; fixture restored to 0/0/0, identity rotation, 1/1/1
tracked harness assets    : byte-identical before/after (sha256)
```

Residual follow-up (same defect class, NOT fixed — out of scope for the controller gate):

```text
tests/test_unreal_composite_real_integration.py
tests/test_unreal_heterogeneous_recovery_real_integration.py
tests/test_unreal_production_workflow_real_integration.py
tests/test_unreal_material_variant_real_integration.py
```

Each still requires `dict` where the frozen `observed_state` supplies a `MappingProxyType`, so they fail
the same way on a live run until the same one-line repair is authorized.

## Harness setup follow-up

The Unreal harness currently depends on launching with:

```text
/Game/AtlasTest/Generated/AtlasRenderFixture
```

because the server-side entity lookup uses:

```text
GEngine->GetWorldContexts()[0]
```

while fixture provisioning uses the editor world. The C++ transport server was **not** modified during this gate.

A durable C++ active-editor-world fallback is a possible future harness improvement, separate from the controller milestone.

## Latest validated test state (deterministic)

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

No live Unreal, Action Runner, Named Pipe, Blender, or Qwen testing was performed before the live gate, other than the explicitly authorized live controller gate recorded above.

## Existing live Unreal proof

The previously established live Unreal production/render receipt proof remains valid, and the new live controller gate now sits above it on the same transport and the same proven operation.

## Blueprint production milestone

Blueprint remains a **separate, engine-dependent milestone and is not green**. The narrow sequence is still:

```text
READ   inspect_blueprint_state
WRITE  set_blueprint_metadata
WRITE  compile_blueprint
VERIFY verify_blueprint_state
```

The remaining live issue is evidence shape: persisted Blueprint metadata must appear under `metadata` in the post-mutation verified Blueprint state.

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

Do not expand into arbitrary Blueprint graph authoring until this narrow production boundary is green. Do not begin Blueprint work while the follow-up items below are open.

## Next development gate

Current status:

```text
RECONCILED + DETERMINISTIC GREEN + LIVE CONTROLLER-TO-UNREAL PRODUCTION GREEN
```

The `AgentControllerHost` → real Unreal production boundary is now validated.

The immediate follow-up is:

```text
A. test-only _variant Mapping compatibility repair   — DONE (Sept 15, working tree)
B. rerun both live controller production tests       — DONE (1 passed / 1 passed, live UE 5.6.1)
```

Then the next genuine architectural/engine milestone is:

```text
LIVE BLUEPRINT PRODUCTION BOUNDARY
```

specifically:

- narrow Blueprint metadata mutation;
- compile;
- verify;
- ensure persisted metadata appears under `metadata` in post-mutation evidence.

Blueprint production is **not** green.

## Resume checklist for the next session

1. Confirm the branch and HEAD:

```text
branch : reconcile/unreal-autonomy-origin-20c6d10
HEAD   : fe2322f7e76caf3115e3e5be6dafce05d62251ca
```

2. Confirm the working tree state. At the September 15 checkpoint it holds 7 tracked documentation
   modifications (this handoff set) plus the applied two-line test-only repair in
   `tests/test_agent_controller_production_real_integration.py`; the untracked live gate harness and the
   pre-existing Aider artifacts are still untracked. Nothing has been committed.
3. Do not pull, merge, rebase, reset or stash: the branch is already reconciled with origin, and `09015d9` is published elsewhere.
4. Run the deterministic focused suite first (see the numbers above) before any live run.
5. For live runs, launch the editor with the fixture map and confirm the harness reports its fixtures ready before running the gate.
6. Apply item A of the follow-up (test-only, one line), then rerun both live controller production tests.
7. Only then consider the live Blueprint production boundary.

Do not push, do not open a PR, and do not begin Blueprint work as part of the controller milestone.

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

- Atlas is the canonical authority.
- Qwen/model providers reason and propose only.
- Models cannot authorize execution.
- `AgentControllerHost` owns trusted execution context.
- `TrustedUnrealContext` is host-installed.
- Capability admission remains fail-closed.
- Unreal executes authorized operations.
- Unreal evidence must be fresh.
- Render receipts must match verified evidence.
- Recovery requires fresh evidence and replacement authorization.
- There is no second authority and no alternate execution path.
- The Named Pipe transport remains the existing transport.
- Blender and Qwen remain isolated from this Unreal milestone.
- Preserve canonical Digital Twin ownership in Atlas.
- Preserve language-agnostic subsystem contracts for future C++ replacement of performance-sensitive components.
- Do not introduce entity discovery or an Atlas-side entity cache to compensate for fixture problems.
- Do not weaken fail-closed validation.
- Do not run workflow/action-runner tests unless explicitly authorized.
