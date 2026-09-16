# Atlas

Atlas is an **AI-assisted sports virtual production and digital-twin platform** designed to turn captured sports footage and real-world environments into richer, more controllable production experiences.

Atlas is not a Blender-only agent. Blender is the first proven production environment, while Unreal Engine is being integrated as a complementary real-time production environment.

## Architecture

```text
Captured sports footage / real-world environment
                    ↓
          Dedicated photogrammetry
                    ↓
           Initial 3D reconstruction
                    ↓
               Blender Agent
        analyze / clean / correct / optimize
                    ↓
            Canonical Digital Twin
                    ↓
               Unreal Agent
          real-time production / VFX
                    ↓
          Independent Atlas verification
```

Photogrammetry is an upstream reconstruction capability. It is not a responsibility of the Blender Agent or Unreal Agent. The intended future boundary is dedicated photogrammetry software → Atlas intake → Blender analysis/cleanup/correction/optimization.

Atlas owns the canonical Digital Twin. Blender, Unreal, photogrammetry software, and other production tools are adapters/executors around that canonical state.

## Core operating principle

Atlas deliberately separates reasoning from execution:

```text
Qwen / AI
    → understand, reason, propose

Python / Atlas
    → validate, authorize, execute, track state, verify, recover

Production tools
    → perform the actual operation

Independent verification
    → confirm the resulting real state
```

Qwen is never the execution authority.

The production control loop is:

```text
Task
 ↓
Evidence
 ↓
Target-state evaluation
 ↓
Authorization
 ↓
Deterministic action sequence
 ↓
Production-tool execution
 ↓
Fresh independent verification
 ↓
Completion or conservative recovery
```

A successful write is never treated as proof that the desired state exists.

---

# Current development status

The current development branch is:

```text
reconcile/unreal-autonomy-origin-20c6d10
```

Current HEAD:

```text
fe2322f7e76caf3115e3e5be6dafce05d62251ca
```

The Unreal work has reached a provider-neutral **agent-to-controller trust boundary** above the existing production stack, and that boundary has now been validated against real Unreal execution.

The current source-level controller path is:

```text
Agent model response
 ↓
explicit ATLAS_CONTROLLER_REQUEST
 ↓
AgentControllerIntent
 ↓
AgentTaskRequest
 ↓
AgentControllerHost / AgentControllerLoopAdapter
 ↓
AgentEntrypointRuntime
 ↓
AgentProcessRuntime classification
 ↓
Capability admission
 ↓
Capability execution
 ↓
Provider-specific integration
 ↓
Authorization / execution / evidence / verification / recovery
```

Ordinary Blender/Qwen tool execution remains separate and unchanged by this controller seam.

The agent-facing runtime composes its controller boundary from `AgentControllerHost` (host-owned runtime plus loop) rather than constructing the entrypoint runtime and loop adapter directly, and the complete controller path has been validated live against real Unreal execution. See `UNREAL_AGENT_HANDOFF_CURRENT.md` for the live gate record.

## Controller trust boundary

The explicit model request marker is:

```text
ATLAS_CONTROLLER_REQUEST: { ... }
```

The marker is opt-in. Ordinary model responses are not routed into controller execution.

The host owns an `AgentExecutionContext` scoped to one agent execution. Trusted provider state is installed by the host and selected only from the parsed request provider. Model-supplied capability, intent metadata, and context values do not create or replace trusted state.

For Unreal, `TrustedUnrealContext` binds:

```text
UnrealAuthorizedProductionPlan
+ authoritative UnrealTaskIntent
+ approved sequence asset path
```

The production plan and authoritative task intent must share the same intent ID before the trusted context can be installed.

## Latest controller checkpoint

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

This confirms the current source-level intent parsing, trusted-context handling, host lifecycle, controller loop boundary, Unreal trusted-context binding, and synthetic end-to-end controller path.

The explicitly authorized live controller gate has also passed:

```text
tests/test_agent_controller_host_production_real_integration.py
1 passed in 10.77s
```

That gate drove an already-authorized `FIELD_SURFACE` composite production through the real controller host, the existing Named Pipe transport, and a real Unreal Engine 5.6.1 editor, and returned fresh verified evidence, a matching render receipt, and a typed controller result contract.

No other live Unreal/action-runner test was run for this checkpoint.

---

# Unreal Engine status

The existing Unreal architecture remains:

```text
Atlas plan
 ↓
Authorization
 ↓
Unreal production adapter
 ↓
Windows Named Pipe
 ↓
Unreal Editor / harness
 ↓
Execution
 ↓
Fresh evidence
 ↓
Independent verification
```

Previously established live proofs include real Unreal production execution and render receipt verification. Those proofs do not automatically validate the newer model-to-controller host path.

## Blueprint production boundary

**CURRENT STATE (2026-09-15): the narrow Blueprint production boundary is GREEN and live-gated against real Unreal Engine 5.6.1 over the existing Named Pipe transport, with Atlas semantic verification implemented, registered and live-proven (3 passed; `evidence_ledger[3].verified is True` on the metadata mutation path, `evidence_ledger[2].verified is True` on the compile-only path).** The narrow sequence that was completed is:

```text
READ   inspect_blueprint_state
WRITE  set_blueprint_metadata
WRITE  compile_blueprint
VERIFY verify_blueprint_state
```

**SUPERSEDED (2026-09-15) — HISTORICAL:** the previously identified remaining live issue is evidence shape: persisted Blueprint metadata must appear under `metadata` in the independently observed state after mutation and compilation. **Resolved live:** it does, and verification now binds asset identity, compile status and the authorized metadata key/value while tolerating unrelated metadata keys.

The Blueprint milestone is **declared green (2026-09-15)**; arbitrary Blueprint graph authoring remains out of scope and would require its own design gate.

## Next Unreal gate

The live controller-to-Unreal production test has passed using a real pre-authorized `TrustedUnrealContext`, so the controller host boundary is no longer source-level only.

The test-only repair is **APPLIED (September 15, 2026)** in the working tree (two lines:
`from collections.abc import Mapping` and `if not isinstance(value, Mapping):`), and both live controller
production tests were rerun green against a real UE 5.6.1 editor (1 passed in 9.53s and 1 passed in 6.10s)
with the fixture restored to 0/0/0, identity rotation, 1/1/1.

Residual follow-up (same defect class, NOT fixed — out of scope for the controller gate):
`tests/test_unreal_composite_real_integration.py`,
`tests/test_unreal_heterogeneous_recovery_real_integration.py`,
`tests/test_unreal_production_workflow_real_integration.py`,
`tests/test_unreal_material_variant_real_integration.py`.

After that, the next engine-dependent milestone was the live Blueprint production boundary — completed and gated green on September 15, 2026.

**SUPERSEDED (2026-09-15):** "Blueprint evidence validation remains a separate live gate, and Blueprint production is not green." Blueprint production is green and its evidence is now Atlas-verified. **CURRENT STATE (2026-09-15, later the same day):** render configuration/state semantic verification (`verify_render_state`) has also been promoted to the executor's semantic-verification registry and live-gated green (1 passed on Unreal Engine 5.6.1 over the existing Named Pipe transport; `result.evidence_ledger[2].verified is True`), with the executor now the sole producer of the render-state `verified` flag and the verifier itself no longer setting it. The next engine-dependent surface is the render **job**/result layer (Movie Render Queue submission and job-state verification), pending its own design gate.

---

# Blender proof already established

Blender remains the first proven execution environment.

Atlas has established:

- local Qwen/Ollama integration
- authoritative read-only evidence acquisition
- evidence ledgers and evidence reuse
- authorized writes
- ordered multi-step execution
- independent post-write verification
- deterministic finalization
- controlled write-failure recovery
- audit-trail ordering
- generic action plans
- generic evidence plans
- evidence-to-action orchestration
- structured Qwen planning
- conditional no-write and write-required paths
- generic post-action verification
- deterministic future generation and execution gating
- fail-closed recovery and replan authorization
- runtime-context fingerprinting
- continuation/runtime-integrity boundaries

The goalpost fixture remains a proof fixture, not the generic architecture.

---

# Digital Twin direction

Atlas owns the canonical Digital Twin and must distinguish canonical state from downstream production variants.

Production changes should be represented as explicit variants, overrides, or derived states rather than silently replacing canonical state.

Digital Twin identity is a separate semantic layer from geometry. Identity decisions must be conservative and based on stable identity anchors and authoritative evidence. Missing or conflicting identity evidence must not cause Qwen to guess or silently merge captures.

Future provenance should distinguish captured, reconstructed, inferred, Atlas-corrected, production-authored, and shot-specific temporary state.

---

# Unreal Engine direction

The Unreal Agent is being developed around the same Atlas control philosophy used for Blender:

```text
AI proposal
 ↓
Atlas validation
 ↓
Authorization
 ↓
Unreal execution
 ↓
Independent evidence
 ↓
Verification
```

Planned Unreal capabilities include:

- asset and scene organization
- Blueprint operations
- materials and look development
- lighting and Lumen workflows
- Nanite-enabled assets
- CineCamera and cinematic setup
- Sequencer and shot construction
- Movie Render Queue workflows
- real-time virtual-production operations

Future provider capabilities should reuse the generic controller, transport, authorization, evidence, and verification boundaries rather than introducing parallel dispatchers or authorization mechanisms.

---

# Cinematic sports production direction

Atlas is intended for sports-field-related digital twins and production workflows around real athletes.

The wider production repertoire includes:

- impact frames
- smear frames
- cinematic bleed
- chromatic aberration for impact accentuation
- match-cut transformations
- digital-twin compositing
- environmental interactions
- temporary liquid/fluid-like environmental behavior
- smoke, glass, metallic, and other material/environment transformations
- spatial overlays and field intelligence

These are production modules, not the definition of Atlas.

---

# Development rules

- Do not rewrite the entire agent.
- Do not remove the evidence ledger.
- Do not remove independent post-write verification.
- Do not make goalpost behavior the generic architecture.
- Do not give Qwen direct execution authority.
- Do not add tools without proving a real capability gap.
- Keep production-tool-specific behavior behind adapter boundaries.
- Treat successful production-tool writes as unverified until fresh evidence confirms the resulting state.
- Do not require manual editor setup for deterministic integration fixtures when the harness can create them.
- Keep photogrammetry upstream of Blender.
- Preserve canonical Digital Twin ownership in Atlas.
- Do not introduce a second generic controller or authorization authority.

---

# Local environments

The established Blender/Qwen environment is:

```text
Python 3.9.6
Ollama 0.32.13
qwen3:8b
Blender 4.4
```

The Unreal development environment currently uses Unreal Engine 5.6 with the local Unreal harness project under:

```text
unreal/AtlasUnrealHarness
```

---

# Resume the current Unreal development phase

```powershell
cd "C:\Users\Gavin's PC\Desktop\Atlas-Unreal-Aider"
git status
```

Resume on the reconciled branch:

```text
reconcile/unreal-autonomy-origin-20c6d10
fe2322f7e76caf3115e3e5be6dafce05d62251ca
```

Do not pull, merge, rebase, reset or stash: the branch is already reconciled with `origin/integrate-origin-main-with-render-receipt`, and the local autonomy commit it builds on is published on a separate remote branch.

The live controller-to-Unreal production gate has passed. The next steps are recorded in `UNREAL_AGENT_HANDOFF_CURRENT.md`:

1. the test-only `_variant` Mapping compatibility repair — APPLIED (September 15, 2026);
2. both live controller production tests rerun green against real Unreal (1 passed each);
3. the live Blueprint production boundary was then revalidated and gated green on September 15, 2026 (3 passed; semantic verification binds asset identity, compile status and the authorized metadata key/value).
