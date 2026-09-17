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

The shared branch now carries the September 17 overnight documentation closeout. The published feature branch still contains the parallel shot-continuity implementation; the fully reconciled local candidate has **not** yet been published to the shared branch.

Latest documented milestones:

```text
Controller trust boundary              COMPLETE + LIVE
Blueprint semantic verification        COMPLETE + LIVE
Render-state semantic verification     COMPLETE + LIVE
Render-job identity verification       COMPLETE + LIVE
Composite actor production             COMPLETE + LIVE
Shot-level production continuity       LIVE-PROVEN in local reconciled candidate
```

The intended published shot-continuity contract is recorded in `docs/UNREAL_SESSION_CLOSEOUT_2026-09-17.md` and the local reconciliation record. It preserves inclusive Atlas frame semantics, translates the inclusive end frame to Unreal MRQ's half-open boundary exactly once, verifies fresh effective frame evidence, binds sequence identity through the authorized production plan, and verifies the exact PNG frame set.

The current shared branch should **not** be treated as the final reconciled shot-continuity state yet. Before publication of the reconciled candidate, run the fresh live continuity gate, the affected deterministic regression, and fixture byte verification, then fast-forward only. No force-push.

---

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

## Unreal Engine status

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

The latest shot-continuity work proved a complete production-to-render continuity path against real UE 5.6.1 in a fresh editor session. The live proof included exact sequence identity, inclusive frame-range continuity, MRQ boundary translation, output directory/format continuity, exact job identity, PNG frame-set completeness, receipt issuance/persistence, and fixture restoration.

The implementation deliberately did **not** add a new Named Pipe operation, second authorization authority, generic workflow engine, entity cache, or distributed-rendering layer.

### Shot-level production continuity

The authoritative Atlas semantics are inclusive:

```text
start_frame ... end_frame
expected PNG frame set = every authorized frame in that inclusive range
```

The Unreal/MRQ boundary translates this once:

```text
CustomStartFrame = Atlas start_frame
CustomEndFrame   = Atlas end_frame + 1
```

Fresh render-job evidence exposes the semantic inclusive range plus the explicit `end_frame_exclusive` engine-boundary diagnostic. Final continuity verification compares fresh evidence to the authorized production values and requires exact PNG frame coverage, including rejection of missing, duplicate, unexpected, or frame-number-less artifacts.

The receipt remains the existing evidence-bound structure:

```text
job_id
sequence_asset_path
evidence_digest
receipt_digest
```

The parallel receipt extension that duplicated observed continuity fields into the receipt digest was rejected during reconciliation because those fields are already covered by the evidence digest and do not provide an independent integrity property.

### Overnight reconciliation state

At session close the shared branch and the local reconciled candidate were intentionally kept separate. The local candidate `97487d0` is the reviewed reconciliation target but has not been published. See:

```text
docs/UNREAL_SHOT_CONTINUITY_RECONCILIATION.md
docs/UNREAL_SESSION_CLOSEOUT_2026-09-17.md
```

### Open Unreal boundary item

MRQ queue accumulation / artifact attribution remains a separate architectural risk. Fresh editor sessions are required for live continuity gates because prior queue jobs can otherwise create ambiguous callback artifact attribution. This issue is intentionally not folded into shot continuity tonight.

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

Development is intentionally paused at the end of the September 17 session.

Resume from:

```text
C:\Users\Gavin's PC\Desktop\Atlas-Unreal-Aider
```

First read:

```text
UNREAL_AGENT_HANDOFF_CURRENT.md
docs/UNREAL_SESSION_CLOSEOUT_2026-09-17.md
docs/UNREAL_SHOT_CONTINUITY_RECONCILIATION.md
```

Then inspect the shared branch versus the local reconciled candidate. The next authorized action is a fresh live gate on the reconciled candidate followed by deterministic regression and fixture byte verification. Only after those are green should the shared branch be advanced by fast-forward. No force-push.
