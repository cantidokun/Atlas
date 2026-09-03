# OpenHands Transition Guide

This guide records the planned transition to an OpenHands-assisted Atlas development workflow. It is now aligned with the September 3, 2026 Atlas architecture.

## Current Atlas position

**Active branch:** `feat/blender-stage11-mainline`  
**PR #49:** open, draft, unmerged  
**Current development stage:** Stage 16 — Qwen proposal integration into Atlas-owned authorization/runtime boundary.

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

Atlas has live-proven generic autonomous execution, partial-progress recovery, dependency-aware serial recovery, semantic soccer-production tasks, and a versioned soccer-production catalog.

The current Stage 16 Qwen chain is:

```text
Qwen
  -> Ollama structured output
  -> provider validation
  -> trusted soccer-production catalog
  -> QwenProductionProposal
  -> ProductionTaskDefinition
  -> AtlasTaskDefinition
  -> QwenProductionTaskHandoff
  -> existing Atlas ActionAuthorization
  -> existing AutonomousTaskRuntime
  -> controlled Blender execution
  -> fresh independent verification
```

The local proposal-only Qwen smoke test has been user-verified. The first full Qwen-authorized Blender mutation harness is implemented but has not yet been user-verified.

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

Inspect `ATLAS_HANDOFF_CURRENT.md`, `README.md`, `docs/ATLAS_ARCHITECTURE_CONTRACT.md`, and the relevant engine handoff before major work.

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
Update handoffs/readmes
  ↓
Commit
```

The next established Atlas milestone is not chosen by the model alone. It must remain consistent with the authoritative handoff and architecture contract.

## Current Stage 16 rule

Until the full Qwen-authorized Blender runtime proof is live-verified:

- keep Qwen proposal-only at the model boundary;
- do not let model output create an authorization receipt directly;
- use `QwenProductionTaskHandoff` for provenance/integrity checking;
- reuse the existing Atlas `ActionAuthorization` mechanism;
- reuse the existing `AutonomousTaskRuntime`;
- do not introduce Qwen-specific execution or recovery logic;
- do not automatically retry failed writes;
- require fresh independent verification after writes.

After the runtime proof succeeds, extend the same boundary into the already-proven Atlas recovery/replan machinery.

## Unreal boundary

The Unreal Engine 5.6 render/artifact/verification/receipt path remains proven locally. Cross-process Unreal render-job recovery is not implemented. Durable receipt persistence must not be described as job persistence.

## Transition checklist

- [ ] Confirm the actual Atlas checkout path.
- [ ] Confirm branch and working-tree state.
- [ ] Read current Atlas and Unreal handoffs.
- [ ] Verify OpenHands in a disposable workspace before granting Atlas access.
- [ ] Preserve Docker/WSL isolation.
- [ ] Start with read-only Atlas inspection.
- [ ] Add build/test access before engine control.
- [ ] Use controlled host bridges for operations that cannot safely run inside the OpenHands environment.
- [ ] Keep Blender and Unreal repository boundaries explicit.
- [ ] Increase autonomy only after reliability is demonstrated.

## Important principles

### Keep repositories separate

Do not merge Blender and Unreal repositories merely to make agent coordination easier.

### Keep interfaces stable

Cross-system communication should use explicit contracts rather than shared implementation assumptions.

### Keep humans in control of high-impact decisions

Autonomy increases only as reliability is proven.

### Preserve development safety

Greater agent autonomy does not mean unrestricted Windows-machine access.

## Reference note

Installation commands for OpenHands, Docker, WSL, and related tooling may change. Verify current official instructions when the transition actually begins. The Atlas architectural boundaries in this document are the durable requirements.