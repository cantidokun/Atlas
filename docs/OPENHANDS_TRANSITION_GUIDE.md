# OpenHands Transition Guide

This guide records the planned OpenHands-assisted Atlas development workflow and is aligned with the September 6, 2026 M4/M5 checkpoint.

## Current Atlas position

**Active branch:** `main`  
**Current milestone:** M5 independent Unreal evidence verification is complete; M4 cross-process recovery is complete.

Latest M5 merge commit: `a9b6eb00e62f252cc3aa5b7ef81998797cb12f83`.

The current control model is:

```text
Qwen / AI / development models
    -> reason and propose structured production intent

Python / Atlas
    -> validate, resolve, authorize, execute, track state, verify, recover

Blender / Unreal
    -> controlled production execution

Independent verification
    -> establish what actually happened
```

Models and agent wrappers are never Atlas execution or authorization authorities.

## Current proven architecture

Atlas has live-proven autonomous execution/recovery foundations, dependency-aware serial recovery, semantic soccer-production tasks, Qwen proposal/authorization/recovery integration, and production-artifact lineage.

The Unreal path now includes both durable cross-process recovery and an authoritative independent evidence-verification boundary:

```text
Atlas durable job intent / state
        ↓
controlled Unreal submission
        ↓
Unreal worker + witness journal
        ↓
reconciliation / recovery
        ↓
raw observed render evidence
        ↓
independent Atlas verification
        ↓
verified UnrealEvidence
        ↓
UnrealRenderReceipt
        ↓
ProductionArtifactManifest
```

Blender Stage 17 is live verified against Blender 4.4. Unreal Stage 17 is live verified against real UE 5.6. The first Unreal proof uncovered a real state-consistency defect which was corrected before the successful proof.

## M4 — Cross-process Unreal render-job recovery

M4 is merged to `main`.

The recovery model is Atlas-owned and includes:

- durable `AtlasRenderJobRecord` state;
- durable intent before transport submission;
- Atlas-generated immutable job identity and attempt identity;
- coordinator lease/fencing and per-job ownership;
- process/session identity including process creation identity;
- contained Windows Job Object supervision;
- fail-closed behavior for unsupported uncontained attached recovery;
- Unreal witness journal outside `Saved`;
- attempt nonce/HMAC protections;
- per-attempt output isolation;
- engine-attested output manifests and independent disk hashing;
- full reconciliation catalog with stability checks;
- rogue/unmanaged job detection without silent adoption;
- explicit orphan/ambiguity states;
- identity-bound receipt creation with create-if-absent semantics;
- no automatic resubmission after uncertain execution acceptance.

The Unreal engine remains a controlled worker/witness. It does not own Atlas recovery authority.

## M5 — Independent evidence verification

M5 is merged to `main` via PR #68.

`verify_render_job_evidence(...)` is the authoritative verifier for raw observed Unreal render-job state. It fail-closes unless the evidence source, durable record identity, expected topology, output isolation, engine-attested manifest, independent disk hashes, and PNG/artifact integrity checks all agree.

Important distinction:

```text
Unreal transport
    -> observed state only

Atlas verifier
    -> verified=True only after independent proof

Receipt
    -> only from verified evidence

Provenance manifest
    -> downstream lineage only
```

M5 validation before merge:
- 39 evidence-verification tests passed;
- 15 recovery-coordinator tests passed;
- `pytest -k unreal`: 302 passed, 648 deselected;
- full `pytest`: 950 passed;
- GitHub Actions `Atlas Tests` for the M5 head completed successfully.

Do not run action-runner/workflow tests unless explicitly authorized.

## Controller-to-Unreal trust boundary

Protected Unreal requests use `TrustedUnrealContext` as the authority source for protected intent, authorization context, sequence path, and production state. Model-supplied protected intent and production flags cannot replace or disable host-owned trusted values.

The Unreal transport is an execution/transport boundary, not a second authorization system, scheduler, or recovery engine.

## Repository boundaries

Keep the Blender and Unreal codebases/repositories separate. Cross-system work should use explicit contracts and adapters rather than merged implementation state.

Atlas owns the canonical Digital Twin. Photogrammetry remains upstream reconstruction; Blender handles analysis/cleanup/correction/preparation; Unreal is downstream production execution.

## Safe OpenHands operating rules

1. Preserve repository boundaries.
2. Treat C++ interoperability as a core architectural requirement.
3. Prefer language-neutral subsystem contracts.
4. Preserve Atlas-owned authorization, runtime, verification, evidence, receipt, and recovery boundaries.
5. Never weaken tests merely to make a change pass.
6. Inspect current handoffs/docs/issues before major architectural changes.
7. Avoid unrelated modifications.
8. Do not reset, discard, or overwrite unrelated user work.
9. Make coherent, reviewable commits.
10. Increase autonomy progressively and only after deterministic validation.
11. Do not give Qwen, OpenHands, Hermes, or an external model direct production authority merely for convenience.
12. Do not introduce a second execution engine, authorization system, scheduler, or recovery system when an existing Atlas path already exists.
13. Do not force-merge heavily diverged historical branches into current `main`; selectively transplant validated invariants instead.
14. Preserve the distinction between live-proven behavior, regression-verified behavior, and pending human validation.
15. Treat the M4 recovery contract and M5 evidence verifier as protected invariants; changes require targeted red-team scrutiny.

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

## Development-model evaluation

Hermes is the development/agent interface; the underlying reasoning provider may be changed experimentally without changing the Atlas authority model.

The next-session experiment under consideration is **Gemini vs DeepSeek V4 Flash**, with emphasis on the tradeoff between token usage and reasoning quality in real Hermes development tasks.

**Astra and Claude 5 remain reserved for red-team evaluation.** This preserves a separate adversarial review layer while the development model is evaluated. ChatGPT may also independently inspect/evaluate Hermes-produced work.

The comparison should be measured using practical engineering outcomes:

```text
token efficiency
    +
reasoning quality
    +
architectural fidelity
    +
defect/regression rate
    +
test-fix efficiency
    +
red-team findings
    +
rework / time-to-merge
```

Do not interpret lower token use as success by itself. A cheaper model that creates more architectural drift or rework may be less efficient overall.

A model switch does not change Atlas authority, recovery semantics, evidence rules, or the human merge gate.

## Current development workflow

Before work:

```bash
git status
git branch --show-current
git log -5 --oneline
```

Inspect `ATLAS_HANDOFF_CURRENT.md`, `README.md`, `docs/ATLAS_ARCHITECTURE_CONTRACT.md`, and `UNREAL_AGENT_HANDOFF_CURRENT.md` before major work.

After work:

```bash
git status
git diff
```

Keep changes bounded and preserve unrelated local work.

## Autonomous development loop

A mature Hermes/OpenHands task may follow:

```text
Inspect
  ↓
Determine next established milestone
  ↓
Implement
  ↓
Run appropriate deterministic tests
  ↓
Diagnose/fix
  ↓
Retest
  ↓
Independent red-team review
  ↓
Update current handoffs/readmes
  ↓
Human merge decision
```

The next established Atlas milestone is not chosen by the model alone. It must remain consistent with the authoritative handoff and architecture contract.

## Current end-of-night resume point

The next session should begin from `main` with M4/M5 treated as completed baseline work.

1. Pull the latest `main`.
2. Read the current handoff set and architecture contract.
3. Do not reopen completed M4/M5 work unless a concrete regression is found.
4. Continue from the next unresolved milestone.
5. For Hermes model evaluation, compare Gemini vs DeepSeek V4 Flash on real implementation tasks while retaining Astra/Claude 5 for red-team review.

Do not run workflow/action-runner tests unless explicitly authorized.

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

Never present an older test result as validation of newer commits. Clearly distinguish implementation, regression verification, live verification, independent evidence verification, and pending human validation.

### Preserve adversarial independence

Changing the Hermes development model must not eliminate independent red-team scrutiny. Keep the strongest available review models separate from the model being optimized for day-to-day development efficiency.

## Reference note

Installation commands for OpenHands, Docker, WSL, Hermes, and related tooling may change. Verify current official instructions when the transition or provider change actually begins. The Atlas architectural boundaries in this document are the durable requirements.

Historical dated handoff snapshots are archival records and should not be rewritten.