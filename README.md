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

**Development is paused at the end of the September 18, 2026 Unreal session.** The published shared branch is at:

```text
71728480a425f80c700c913aa00f376c254114bb
```

Current authoritative Unreal position:

```text
Controller trust boundary              COMPLETE + LIVE
Blueprint semantic verification        COMPLETE + LIVE
Render-state semantic verification     COMPLETE + LIVE
Render-job identity verification       COMPLETE + LIVE
Composite actor production             COMPLETE + LIVE
Shot-level production continuity       COMPLETE + LIVE-PROVEN + PUBLISHED
MRQ artifact attribution (Slice 1+2)   COMPLETE + LIVE-PROVEN + PUBLISHED
MRQ start-callback identity (Slice D)  COMPLETE + LIVE-PROVEN + PUBLISHED
MRQ submission outcome propagation     COMPLETE + LIVE-PROVEN + PUBLISHED
MRQ queue isolation design review      COMPLETE - CLEAR WITH MINOR FINDINGS
MRQ pass-failure attribution review    COMPLETE - CLEAR WITH MINOR FINDINGS
```

The September 17–18 Unreal work established identity-bound artifact attribution, identity-bound start monitoring, truthful submission acceptance/rejection, and a design conclusion that the shared MRQ queue remains the default. Queue consumption/deletion and private queue migration remain unimplemented and unauthorized.

The pass-failure review is closed on measured evidence. Two genuine retained-job failure mechanisms were exercised on the unmodified baseline; both aborted the MRQ pass before a later queue job executed. Therefore a healthy Atlas render being clobbered by a later pass-level failure was **not demonstrated**, and no receipt-correctness claim is made. A small state-fidelity correction remains a separate design question; its receipt impact is explicitly unproven. F9 — failed jobs not being readable through the authorized inspection path — remains a separate follow-up.

## Current Unreal development intent

No production implementation is authorized while the session is paused.

The next work item is a **read-only design decision** on whether the small MRQ pass-failure **state-fidelity** correction is worth implementing at all. This must not be presented as a receipt-correctness fix unless new evidence establishes that connection.

Standing decisions:

```text
Shared MRQ queue semantics          DEFAULT
Queue consumption/deletion           DEFERRED / NOT AUTHORIZED
Private queue isolation              DEFERRED / trigger-based (T1-T4)
Automatic mutation retry             PROHIBITED
Exact render-job identity            PRESERVED
Receipt from fresh verified evidence ONLY
```

The authoritative current handoff is `UNREAL_AGENT_HANDOFF_CURRENT.md`; the current architecture pointer is `docs/UNREAL_NEXT_ARCHITECTURE_REVIEW.md`; the September 18 pause record is `docs/UNREAL_SESSION_CLOSEOUT_2026-09-18.md`.


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

### Reconciliation and publication state

The reconciled candidate `97487d0` has been published on the shared branch as merge `d582af3`. The merge was documentation-only relative to the validated implementation: every blob under `planning/`, `tests/` and `unreal/AtlasUnrealHarness/Source/` is identical between `97487d0` and `d582af3`. See:

```text
docs/UNREAL_SHOT_CONTINUITY_RECONCILIATION.md
docs/UNREAL_SESSION_CLOSEOUT_2026-09-17.md
```

### Open Unreal boundary item

**MRQ artifact attribution is COMPLETE + LIVE-PROVEN** (published at `8ecf7db`): the job identity guard is live-proven in a multi-submission single-editor session, foreign callback artifacts are discarded, PNG artifacts must be contained within the authorized output directory, and exact frame-set verification remains active. **Slice D adds monitoring-state identity**: `OnIndividualJobStarted` writes `Status`/`StatusMessage`/`Progress` only for the exact registered executor job, proven in one editor session whose queue already held foreign jobs. Slice 3 queue consumption remains separate and unimplemented, and the private-queue migration is not authorized.

The queue-lifecycle design review (`docs/UNREAL_MRQ_QUEUE_LIFECYCLE_DESIGN_REVIEW.md`, `CLEAR WITH MINOR FINDINGS`, read-only) concluded that accumulation is no longer a provenance correctness risk, retained the current shared MRQ queue semantics as the default, rejected queue consumption for now, and deferred an Atlas-owned private queue instance with recorded entry criteria. The former operator precondition (fresh editor session + empty queue) is no longer load-bearing for attribution.

**MRQ submission outcome propagation is COMPLETE + LIVE-PROVEN**: the submission call and its observation of the engine's active executor happen in one game-thread task, so a refused submission is an immediate typed failure (measured 1.50 s in a clean live session) instead of a 300 s poll timeout, an unprovable outcome fails closed as ambiguous, and a rejected submission exposes no job identity and produces no receipt. No protocol, job-identity, receipt, queue or timeout contract changed.

**Next architectural review (nothing authorized): is queue isolation / a private queue instance worth its lifecycle surface?** The shared queue still accumulates jobs, and a rejected submission still leaves its allocated job behind by design; the question is whether isolating Atlas's own queue is worth the larger lifecycle it introduces. That is a read-only design gate and has not been started. Queue consumption and the private-queue migration remain unimplemented.

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

Development is intentionally paused.

Resume from:

```powershell
cd "C:\Users\Gavin's PC\Desktop\Atlas-Unreal-Aider"
git status
```

First read:

```text
UNREAL_AGENT_HANDOFF_CURRENT.md
docs/UNREAL_SESSION_CLOSEOUT_2026-09-18.md
docs/UNREAL_NEXT_ARCHITECTURE_REVIEW.md
```

The next authorized action is a read-only design gate deciding whether the
MRQ pass-failure state-fidelity correction is worth implementing. Receipt
impact remains explicitly unproven.

Do not begin queue consumption, private-queue migration, registry pruning,
or any new Unreal feature until that gate is cleared.

Never touch the Blender checkout:

```text
C:\Users\Gavin's PC\Desktop\Atlas
```
