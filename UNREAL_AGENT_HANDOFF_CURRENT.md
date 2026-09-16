# Atlas Unreal Agent — Current Development Handoff

**Updated:** September 15, 2026
**Branch:** `reconcile/unreal-autonomy-origin-20c6d10`
**HEAD:** `fe2322f7e76caf3115e3e5be6dafce05d62251ca`
**Status:** reconciled + deterministic green + live controller-to-Unreal production green + live Blueprint production green (Blueprint semantic verification live-proven) + live render-state semantic verification green (render-state verification promoted to the executor registry and live-proven)

## Current checkpoint

The Unreal Agent work has been reconciled with the origin branch, and the **agent-to-controller trust boundary has now been validated against real Unreal execution**.

This is the first live proof that an already-authorized Unreal production operation can travel the complete host-owned controller path and return fresh independently produced evidence, a matching render receipt, and a typed controller result contract.

```text
live controller path green
≠
live Blueprint production boundary green
```

**SUPERSEDED (2026-09-15):** that distinction no longer holds — the live Blueprint production boundary has since been gated green against real UE 5.6.1 over the existing Named Pipe transport, and Blueprint semantic verification is implemented, registered and live-proven. See "Blueprint production milestone" and "Live Blueprint semantic verification gate" below.

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

**CURRENT STATE (2026-09-15): the narrow Blueprint production boundary is GREEN and live-gated, and Blueprint semantic verification is implemented, registered and live-proven — see "Live Blueprint semantic verification gate" below.**

**SUPERSEDED (2026-09-15) — HISTORICAL:** Blueprint remains a **separate, engine-dependent milestone and is not green**. The narrow sequence is still:

```text
READ   inspect_blueprint_state
WRITE  set_blueprint_metadata
WRITE  compile_blueprint
VERIFY verify_blueprint_state
```

**SUPERSEDED (2026-09-15) — HISTORICAL:** the remaining live issue is evidence shape: persisted Blueprint metadata must appear under `metadata` in the post-mutation verified Blueprint state. **Resolved:** the transport serializes `metadata` inside the Blueprint state, and the September 15 gate proved it present at the mutation, compile, verify and fresh-inspection stages over the real engine.

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

That intended evidence shape is now the observed shape (verified live). The verification contract additionally binds asset identity, compile status and — when the plan carries it — the authorized metadata key/value.

**UPDATED (2026-09-15):** the narrow production boundary is now green, so graph authoring is no longer blocked *by that boundary*; arbitrary Blueprint graph authoring remains out of scope and would need its own design gate.

## Live Blueprint semantic verification gate — PASSED (September 15, 2026)

Exact test:

```text
tests/test_unreal_blueprint_real_integration.py
```

Exact command:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_unreal_blueprint_real_integration.py -m integration -q -s
```

Result:

```text
3 passed
```

The narrow Blueprint production boundary is green and live-gated against real Unreal Engine 5.6.1 over the
existing Named Pipe transport (`\\.\pipe\AtlasUnrealTransport`, fixture
`/Game/AtlasTest/BP_AtlasTest.BP_AtlasTest`):

```text
metadata mutation path (inspect -> set_blueprint_metadata -> compile_blueprint -> verify_blueprint_state)
    : evidence_ledger[3].verified is True
compile-only path (inspect -> compile_blueprint -> verify_blueprint_state)
    : evidence_ledger[2].verified is True
missing-asset negative path : failed closed
fresh post-plan inspection  : authorized metadata still present, compile_status success
```

Semantic verification contract now in force:

- expected state is authorization-bound plan state (asset path and compile status from the VERIFY operation's
  own authorized arguments; metadata key/value from the paired authorized `set_blueprint_metadata` WRITE in
  the same plan) — never derived from returned evidence, the model, or the engine;
- verification consumes fresh Unreal evidence (the VERIFY arm issues its own read);
- asset identity is verified (observed `asset_path` must equal the authorized asset path);
- Blueprint compile status is verified against the authorized `expected_compile_status`;
- the authorized metadata key/value is verified when the metadata mutation plan is present (observed key
  present, value a string, exactly equal to the normalized authorized value);
- unrelated metadata keys are tolerated (the fixture's independent `AtlasTestMarker` is observed live and ignored);
- fail-closed behavior is preserved (missing mapping/key, non-string value, value/identity/status mismatch all
  raise through the existing failure-record mechanism; plan-shape violations are rejected before dispatch);
- `verify_blueprint_state` sets `verified=True` only after the semantic comparison succeeds — the operation is
  registered in the executor's semantic-verification registry and its verifier call site is unconditional for
  that operation name, so registration alone can never produce a vacuous pass.

Executor plumbing (no planner, tool schema, capability registry, adapter, authorization, recovery, transport or
C++ change was required): Blueprint `asset_path` continuity is enforced in execution-shape validation for
`set_blueprint_metadata` -> `compile_blueprint` -> `verify_blueprint_state`, and the metadata expectation is
resolved positionally from the authorized metadata WRITE at index-2.

Deterministic results at this milestone:

```text
Blueprint suites (semantic contract + verifier + planning) : 37 passed
Executor core                                             : 16 passed
Four affected contract surfaces                            : 37 passed
Canonical focused suite (13 modules)                       : 160 passed, 2 deselected
Broader deterministic sweep                                : 766 passed, 5 skipped
Python 3.9 Blueprint parity                                : 37 passed
Python 3.9 executor/contract parity                        : 53 passed
```

Fixture safety: the live metadata write persists through `UPackage::SavePackage`; the tracked
`BP_AtlasTest.uasset` was afterwards restored to the committed HEAD bytes
(`db15ec03c624fe1ad4f38b17e3b86f0064393111a384346f375bac30a63cdb7a`), so the repository fixture baseline is
unchanged.

Explicitly deferred (not part of this milestone): `verify_render_state` flag asymmetry; Blueprint metadata
recovery coverage; verifier exception-type cleanup; production-spec Blueprint metadata expressiveness;
`is_up_to_date` binding; the unused `evidence` parameter in the semantic-verification registry helper; and the
live fixture value-idempotency limitation (the authorized value pre-existed, so the live pass proves the
post-condition rather than a first-time write).

**SUPERSEDED (2026-09-15, later the same day):** the `verify_render_state` flag asymmetry has since been
resolved — render-state verification is registered in the executor's semantic-verification registry and the
verifier-internal flag producer was removed. See "Live render-state semantic verification gate" below. The
other items in this deferred list remain deferred.

## Live render-state semantic verification gate — PASSED (September 15, 2026)

`verify_render_state` is now a first-class Atlas semantic verification: deterministic green and
live-proven.

```text
.venv/Scripts/python.exe -m pytest tests/test_unreal_render_real_integration.py -m integration -q -s
Unreal Engine 5.6.1-44394996+++UE5+Release-5.6 over the existing Atlas Named Pipe transport
1 collected, 1 passed
result.evidence_ledger[2].verified is True
```

The contract now in force:

- `verify_render_state` is registered in the executor's semantic-verification registry
  (`_is_semantically_verified`).
- The executor is the sole producer of `evidence.verified` for render-state verification;
  `verify_render_config` itself no longer sets the flag — it compares, raises on mismatch and returns the
  evidence unchanged, matching every other verifier.
- Expected state comes only from the authorized `verify_render_state` operation arguments; the preceding
  `configure_render` write is not an expectation source.
- The verifier compares all six render configuration fields with the unchanged
  `normalize_render_config` behavior (strict key/type validation plus output-directory canonicalization;
  no new case folding and no new heuristics).
- Identity remains `entity_ids` only; the engine-reported `render.asset_path` is explicitly not bound and
  stays deferred.
- No pairing helper, index arithmetic or render-specific execution-shape rule was added: the generic
  write-to-verify pairing already covers `configure_render` to `verify_render_state`.
- `verified_render`, the production result contract and the receipt are unchanged — render-state evidence
  is a local evidence flag and cannot feed the result contract.

Historical correction recorded with this milestone: the earlier handoff wording implied that the flag
asymmetry meant render-state evidence never carried `verified=True`. The design audit proved the old
verifier set the flag itself, so the real asymmetry was the missing executor registry membership plus a
second, independent flag producer. The historical statements are preserved above and marked superseded.

Engine-side evidence for the live pass: four sequential client connections — `inspect_render_state`,
`configure_render` (followed by `LogSavePackage: Moving output files for package:
/Game/AtlasTest/AtlasRenderConfig`), `verify_render_state` on its own new connection after that save, and
the fresh post-plan `inspect_render_state` — so verification used fresh engine evidence rather than the
write's return value.

Deterministic results:

```text
render semantic matrix (T-R1..T-R8)     : 24 passed
render/executor/contract focused set    : 94 passed
canonical focused suite                 : 160 passed, 2 deselected
Python 3.9 render/executor parity       : 94 passed
Python 3.9 canonical focused suite      : 160 passed, 2 deselected
deterministic sweep                     : 1072 passed, 5 skipped, 22 deselected
```

Fixture safety: all four tracked harness assets (`AtlasRenderConfig.uasset`, `BP_AtlasTest.uasset`,
`AtlasSequencerFixtureSequence.uasset`, `AtlasRenderFixture.umap`) were byte-identical before and after the
gate; the engine re-serialized the render config to the same bytes because the fixture already carried the
configured values (the same value-idempotency limitation recorded for Blueprint).

What the live gate proves, and what it does not: it proves the promoted flag is reached on real engine
evidence. It cannot distinguish the old flag producer from the new one, because both yield `verified=True`
live; the deterministic single-authority test (T-R8) proves the flag's source is now the executor registry.

Scope held: no planner, tool schema, capability registry, authorization, evidence-contract, adapter,
recovery, result-contract, receipt, C++ or transport change — two production lines (registry membership;
removed verifier-internal flag) plus tests.

Explicitly deferred for this surface: render-state asset-path identity binding; `output_format` case
normalization; png-only Atlas-side enforcement; the `verify_render_config` isinstance guard;
replay/freshness proof beyond the execution-path guarantee; the unused `evidence` parameter in the
semantic-verification registry helper; the older non-runtime `tools/apply_unreal_render_*.py` patch
scripts; and broader render-result semantics (Movie Render Queue execution, render job/result verification
and `verified_render`), which remain separate.

## Next development gate

Current status:

```text
RECONCILED + DETERMINISTIC GREEN
+ LIVE CONTROLLER-TO-UNREAL PRODUCTION GREEN
+ LIVE BLUEPRINT PRODUCTION BOUNDARY GREEN (semantic verification live-proven)
+ LIVE RENDER-STATE SEMANTIC VERIFICATION GREEN (registry promotion live-proven)
```

The `AgentControllerHost` → real Unreal production boundary is validated, and the narrow Blueprint production boundary has since been gated green with Atlas semantic verification.

The immediate follow-up is:

```text
A. test-only _variant Mapping compatibility repair   — DONE (Sept 15, working tree)
B. rerun both live controller production tests       — DONE (1 passed / 1 passed, live UE 5.6.1)
```

Then the next genuine architectural/engine milestone was:

```text
LIVE BLUEPRINT PRODUCTION BOUNDARY — COMPLETED AND GATED GREEN (2026-09-15)
```

specifically:

- narrow Blueprint metadata mutation — done;
- compile — done;
- verify — done;
- ensure persisted metadata appears under `metadata` in post-mutation evidence — done and live-proven.

Then:

```text
RENDER-STATE SEMANTIC VERIFICATION — COMPLETED AND GATED GREEN (2026-09-15)
```

specifically:

- `verify_render_state` registered in the executor's semantic-verification registry — done;
- executor as the sole producer of the render-state `verified` flag — done;
- verifier-internal flag producer removed (`verify_render_config`) — done;
- expectation limited to the authorized VERIFY arguments, with unchanged normalization — done;
- live gate on UE 5.6.1 over the existing Named Pipe — done (1 passed, `evidence_ledger[2].verified is True`).

**SUPERSEDED (2026-09-15):** "Blueprint production is **not** green." It is green — see the live gate section above. **SUPERSEDED (2026-09-15, later the same day):** the render configuration/state semantic-verification parity surface (`verify_render_state`) has since had its design gate (CLEAR WITH MINOR FINDINGS), was promoted to the executor's semantic-verification registry and was live-gated green — see "Live render-state semantic verification gate" below. The next engine-dependent surface to investigate is the render **job**/result layer (Movie Render Queue submission and job-state verification), which remains separate and needs its own design gate.

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
7. The live Blueprint production boundary was gated green on September 15, 2026 (see the live gate section above).
8. Render-state semantic verification was then promoted to the executor's registry, implemented and live-gated the same day (1 passed on UE 5.6.1; `evidence_ledger[2].verified is True`; see "Live render-state semantic verification gate" above). The next engine-dependent surface is the render **job**/result layer (Movie Render Queue submission and job-state verification), which needs its own design gate.

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
