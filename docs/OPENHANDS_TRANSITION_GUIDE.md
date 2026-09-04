# OpenHands Transition Guide

This guide records the planned transition to an OpenHands-assisted Atlas development workflow and is aligned with the September 4, 2026 end-of-night architecture checkpoint.

## Current Atlas position

**Active branch:** `main`  
**Current development stage:** Stage 17 — production-artifact lineage, IN PROGRESS.

The current control model is:

```text
Qwen / AI
    -> reason and propose structured production intent

Python / Atlas
    -> validate, resolve, authorize, execute, track state, verify, recover

Blender / Unreal
    -> controlled production execution

Independent verification
    -> establish what actually happened
```

Qwen must never receive direct execution or authorization authority.

## Current proven architecture

Atlas has live-proven autonomous execution/recovery foundations, dependency-aware serial recovery, semantic soccer-production tasks, Qwen proposal/authorization/recovery integration, and production-artifact lineage.

Stage 17 currently provides:

```text
canonical Atlas Digital Twin
    ↓
production representation
    ↓
independent evidence
    ↓
engine receipt
    ↓
ProductionArtifactManifest
    ↓
durable persistence
    ↓
exact lineage verification
```

Blender Stage 17 is live verified against Blender 4.4. Unreal Stage 17 provenance is implemented and regression-verified, while the final human gate is a disposable proof using evidence emitted by the already proven Unreal Engine 5.6 render boundary.

## Unreal boundary

The proven Unreal path is:

```text
render configuration
  -> verification
  -> Movie Render Queue submission
  -> dynamic job ID
  -> asynchronous inspection
  -> semantic completion verification
  -> actual artifact discovery
  -> filesystem validation
  -> verified inspect_render_job evidence
  -> UnrealRenderReceipt
  -> durable receipt persistence
```

Stage 17 continues from that verified evidence/receipt pair into the provenance manifest. The proof harness does not submit or execute a render and does not implement Unreal job recovery.

Cross-process Unreal render-job recovery is not implemented. Durable receipt persistence must not be described as job persistence.

## Controller-to-Unreal trust boundary

The current mainline controller host is intentionally narrow while the historical stronger controller-host architecture remains isolated in PR #50 because that branch diverged substantially from current `main`.

Protected Unreal requests use `TrustedUnrealContext` as the authority source for protected intent, authorization context, sequence path, and production state. Model-supplied protected intent and production flags cannot replace or disable host-owned trusted values. The controller-to-Unreal integration seam independently rejects incomplete trusted context before execution.

No second authorization system, scheduler, recovery engine, or Unreal execution path is introduced.

## Repository boundaries

Keep the Blender and Unreal codebases/repositories separate. Cross-system work should use explicit contracts and adapters rather than merged implementation state.

Atlas owns the canonical Digital Twin. Photogrammetry remains upstream reconstruction; Blender handles analysis/cleanup/correction/preparation; Unreal is downstream production execution.

## Safe OpenHands operating rules

1. Preserve repository boundaries.
2. Treat C++ interoperability as a core architectural requirement.
3. Prefer language-neutral subsystem contracts.
4. Preserve Atlas-owned authorization, runtime, verification, evidence, and recovery boundaries.
5. Never weaken tests merely to make a change pass.
6. Inspect current handoffs/docs/issues before major architectural changes.
7. Avoid unrelated modifications.
8. Do not reset, discard, or overwrite unrelated user work.
9. Make coherent, reviewable commits.
10. Increase autonomy progressively and only after deterministic validation.
11. Do not give Qwen, OpenHands, or an external model direct production authority merely for convenience.
12. Do not introduce a second execution engine, authorization system, scheduler, or recovery system when an existing Atlas path already exists.
13. Do not force-merge heavily diverged historical branches into current `main` merely to recover architecture; selectively transplant validated invariants instead.
14. Preserve the distinction between live-proven behavior, regression-verified behavior, and pending human validation.

## C++ interoperability

Atlas remains Python-first/hybrid, not Python-locked.

Python is appropriate for AI/LLM interaction, reasoning, high-level planning, orchestration, experimentation, tooling, and suitable Blender automation.

C++ must remain viable for performance-critical runtime, geometry/spatial computation, high-performance vision, simulation, concurrency, GPU-facing systems, Unreal integration, and other native-sensitive paths.

Prefer:

```text
Python implementation
        ↓
Language-neutral contract
        ↓
C++ implementation
```

over Python-specific contracts that make later native replacement difficult.

## Progressive access model

### Level 1 — Source access

OpenHands may inspect and modify the Atlas repository, update documentation, and use Git.

### Level 2 — Build/test access

Add deterministic tests, static analysis, and builds as appropriate.

### Level 3 — Controlled Unreal access

Only after source/test work is reliable. Determine which operations require the Windows host and whether a controlled bridge is required.

### Level 4 — Broader production execution

Do not enable unrestricted production authority. This requires separate architectural and security review.

## Current development workflow

Before work:

```bash
git status
git branch --show-current
```

Inspect `ATLAS_HANDOFF_CURRENT.md`, `README.md`, `docs/ATLAS_ARCHITECTURE_CONTRACT.md`, and `UNREAL_AGENT_HANDOFF_CURRENT.md` before major work.

After work:

```bash
git status
git diff
```

Keep changes bounded and preserve unrelated local work.

## Autonomous development loop

A mature OpenHands task may follow:

```text
Inspect
  ↓
Determine next established milestone
  ↓
Implement
  ↓
Run appropriate tests
  ↓
Diagnose/fix
  ↓
Retest
  ↓
Update current handoffs/readmes
  ↓
Commit
```

The next established Atlas milestone is not chosen by the model alone. It must remain consistent with the authoritative handoff and architecture contract.

## Current end-of-night resume point

The next session should begin from `main` and preserve this order:

1. Pull the latest `main`.
2. Run focused deterministic tests covering the September 4 Unreal/controller trust-boundary increments.
3. Run the human UE 5.6 Stage 17 provenance proof using the existing verified render evidence/receipt pair.
4. Run `live_unreal_production_artifact_proof.py` against that detached evidence/receipt pair.
5. Confirm manifest persistence, reload, exact lineage, and digest identities.
6. Resume selective integration of validated pieces from PR #50 only after the Stage 17 gate.

Do not run workflow/action-runner tests for the live gate unless explicitly authorized.

## Important principles

### Keep repositories separate

Do not merge Blender and Unreal repositories merely to make agent coordination easier.

### Keep interfaces stable

Cross-system communication should use explicit contracts rather than shared implementation assumptions.

### Keep humans in control of high-impact decisions

Autonomy increases only as reliability is proven.

### Preserve development safety

Greater agent autonomy does not mean unrestricted Windows-machine access.

### Preserve evidence status honestly

Never present an older test result as validation of newer commits. Clearly distinguish implementation, regression verification, live verification, and pending human validation.

## Reference note

Installation commands for OpenHands, Docker, WSL, and related tooling may change. Verify current official instructions when the transition actually begins. The Atlas architectural boundaries in this document are the durable requirements.

Historical dated handoff snapshots are archival records and should not be rewritten.