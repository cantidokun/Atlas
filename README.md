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
integrate-origin-main-with-render-receipt
```

The Unreal work has now reached a provider-neutral **agent-to-controller trust boundary** above the existing production stack.

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

The focused host/controller test suite is green:

```text
62 passed
```

This confirms the current source-level intent parsing, trusted-context handling, host lifecycle, controller loop boundary, Unreal trusted-context binding, and synthetic end-to-end controller path.

No live Unreal/action-runner test was run for this checkpoint.

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

Blueprint remains a separate engine-dependent milestone. The current narrow sequence is:

```text
READ   inspect_blueprint_state
WRITE  set_blueprint_metadata
WRITE  compile_blueprint
VERIFY verify_blueprint_state
```

The previously identified remaining live issue is evidence shape: persisted Blueprint metadata must appear under `metadata` in the independently observed state after mutation and compilation.

The Blueprint milestone is **not yet declared green**, and graph authoring must not be expanded until this narrow boundary is complete.

## Next Unreal gate

After the source-level host integration is complete, the next engine-dependent step is a live controller-to-Unreal production test using a real pre-authorized `TrustedUnrealContext`.

Blueprint evidence validation remains a separate live gate.

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

Bring the branch up to date:

```powershell
cd "C:\Users\Gavin's PC\Desktop\Atlas-Unreal-Aider"
git pull --ff-only origin integrate-origin-main-with-render-receipt
```

The next source-level task is to connect the actual Atlas agent-facing runtime to `AgentControllerHost` without changing the existing Blender/Qwen path.

After that boundary is stable, the next explicitly authorized engine-dependent gate is a live controller-to-Unreal production test using a real authorized Unreal context.

Separately, revalidate the live Blueprint metadata evidence boundary before declaring Blueprint production-complete.
