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
feat/unreal-composite-production-operation
```

Atlas is currently working through the **real Unreal Engine Blueprint production boundary**.

The current Unreal proof path is:

```text
Python planner
 ↓
Unreal operation/schema validation
 ↓
Production adapter
 ↓
Named-pipe transport
 ↓
Unreal harness/editor
 ↓
Real Blueprint asset
 ↓
Independent Blueprint inspection / verification
```

## Real Unreal Blueprint fixture

A deterministic Unreal Blueprint fixture now exists at:

```text
/Game/AtlasTest/BP_AtlasTest.BP_AtlasTest
```

Repository asset:

```text
unreal/AtlasUnrealHarness/Content/AtlasTest/BP_AtlasTest.uasset
```

The fixture is generated and saved by an Unreal harness commandlet. Manual editor creation is not required for the integration fixture.

The fixture commandlet is located at:

```text
unreal/AtlasUnrealHarness/Source/AtlasUnrealHarness/AtlasBlueprintFixtureCommandlet.cpp
unreal/AtlasUnrealHarness/Source/AtlasUnrealHarness/AtlasBlueprintFixtureCommandlet.h
```

The UE 5.6 harness has successfully compiled after the Blueprint metadata/save-package implementation changes.

## Blueprint production operations

The Unreal tool boundary now includes:

- `inspect_blueprint_state`
- `set_blueprint_metadata`
- `compile_blueprint`
- `verify_blueprint_state`

Blueprint package paths are normalized and validated. Metadata key/value strings are normalized. Blueprint verification requires an explicit expected compile status.

The intended metadata mutation path is:

```text
inspect_blueprint_state
 ↓
set_blueprint_metadata
 ↓
compile_blueprint
 ↓
verify_blueprint_state
```

## Latest checkpoint — August 27, 2026

The current real integration suite reports:

```text
1 failed, 2 passed
```

The remaining failure is:

```text
test_real_unreal_blueprint_metadata_mutation_persists_after_compile
```

The important result is that the real metadata mutation itself now succeeds. The executor reaches:

```text
result.success is True
```

The remaining failure is an evidence-shape issue:

```text
KeyError: 'metadata'
```

`BuildBlueprintState()` does not yet expose the Blueprint metadata map in its returned `observed_state`. The next change is therefore to serialize the metadata into the Blueprint evidence, after which the focused target is:

```text
3 passed
```

The Blueprint production milestone is **not yet declared green**.

The exact current handoff is:

```text
UNREAL_AGENT_HANDOFF_CURRENT.md
```

and the dated session handoff is:

```text
docs/ATLAS_HANDOFF_2026-08-27_0200EDT.md
```

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

The established conditional control pattern is:

```text
already correct
    → target satisfied
    → skip writes
    → fresh verification

incorrect
    → target unsatisfied
    → authorized writes
    → fresh verification
```

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

The Blueprint fixture is only the first real production-boundary proof. Future capabilities must reuse the generic transport, authorization, evidence, and verification architecture.

---

# Cinematic sports production direction

Atlas is intended for sports-field-related digital twins and production workflows around real athletes.

The wider production repertoire includes:

- impact frames
- smear frames
- cinematic bleed
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

# Resume the current Unreal milestone

First confirm whether Unreal is running:

```powershell
Get-Process UnrealEditor -ErrorAction SilentlyContinue |
    Select-Object ProcessName,Id,Path
```

Build the harness if required:

```powershell
& "C:\Program Files\Epic Games\UE_5.6\Engine\Build\BatchFiles\Build.bat" `
  AtlasUnrealHarnessEditor `
  Win64 `
  Development `
  -Project="$PWD\unreal\AtlasUnrealHarness\AtlasUnrealHarness.uproject" `
  -WaitMutex `
  -architecture=x64
```

Then run:

```powershell
python -m pytest tests/test_unreal_blueprint_real_integration.py -q
```

The immediate implementation task is to expose Blueprint metadata in `BuildBlueprintState()` evidence. Do not expand Blueprint graph authoring until the focused real integration suite is green.

After the focused suite reaches `3 passed`, run:

```powershell
python -m pytest -q
```

Do not declare the Blueprint production-boundary milestone complete until the focused real integration suite and the full regression suite both pass.
