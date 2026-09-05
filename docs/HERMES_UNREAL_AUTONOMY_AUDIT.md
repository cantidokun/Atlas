# Hermes Unreal Autonomy Audit

## Purpose

Use Hermes as an analysis and engineering-acceleration worker to determine the exact remaining work required for Atlas's Unreal subsystem to satisfy the autonomous-production contract.

This is an **audit-first** task. Do not begin by changing code.

## Repository

Repository: `cantidokun/Atlas`

Primary scope: `unreal/AtlasUnrealHarness/` and all Atlas-side Python/controller contracts that directly govern Unreal execution, evidence, receipts, provenance, verification, recovery, and controller integration.

Read the Git history, current `main`, relevant branches/PRs, current handoffs, architecture contracts, tests, and implementation together. Historical implementations are evidence, not authority.

## Required architectural boundary

Atlas authority remains:

```text
Qwen / AI
  -> reason and propose structured production intent

Python / Atlas
  -> validate, resolve, authorize, execute, track, verify, recover

Blender / Unreal
  -> controlled production execution

Independent verification
  -> establish what actually happened
```

Hermes must not recommend or introduce a second authorization system, scheduler, recovery engine, or autonomous execution authority inside Unreal merely for convenience.

Qwen, Hermes, and OpenHands remain non-authoritative reasoning/development actors. Atlas-owned validation, authorization, execution tracking, verification, and recovery boundaries must remain intact.

## Audit questions

### 1. Autonomous execution completeness

Trace the complete Unreal path:

```text
production intent
  -> authorization
  -> trusted controller context
  -> Unreal request
  -> transport
  -> UE execution
  -> job state
  -> independent inspection
  -> output artifact
  -> evidence
  -> receipt
  -> production artifact lineage
```

Identify any point that still requires manual intervention, hidden assumptions, or a non-deterministic handoff.

### 2. Recovery completeness

Audit failure behavior for at least:

- request validation failure
- transport failure
- Unreal/editor process termination
- Movie Render Queue failure
- interrupted/partial render
- missing output artifact
- invalid or corrupt output artifact
- lost job state
- receipt/evidence mismatch
- restart between submission and inspection
- restart between evidence creation and provenance persistence

Determine exactly what state survives each failure and where recovery is currently impossible.

Explicitly account for the known limitation: the Unreal render-job registry is currently in-memory. Durable receipt persistence is **not** equivalent to durable job persistence.

### 3. Evidence and provenance completeness

Trace and verify:

```text
authorized intent
  -> actual Unreal operation
  -> actual job identity
  -> actual observed UE state
  -> actual artifact
  -> independent evidence
  -> receipt
  -> ProductionArtifactManifest
```

Find every place where provenance could become ambiguous, forged, detached from actual execution, or unverifiable after restart.

### 4. Controller trust boundary

Verify that protected Unreal intent, authorization context, sequence path, and production state originate from trusted Atlas context rather than model-supplied values.

Confirm that contradictory model values remain diagnostic only and cannot become authority.

Do not weaken this boundary.

### 5. Git-history archaeology

Use Git history to identify:

- previously working Unreal components that were later lost or removed;
- changes that introduced regressions or architectural divergence;
- abandoned implementations that contain useful invariants;
- code that should **not** be restored because the current architecture supersedes it;
- commits/PRs that establish the strongest known Unreal behavior.

For every historical recommendation, identify the relevant commit/PR and explain why the component should or should not return.

### 6. Current-vs-required contract analysis

Compare the actual Unreal implementation against:

- `ATLAS_HANDOFF_CURRENT.md`
- `README.md`
- `UNREAL_AGENT_HANDOFF_CURRENT.md`
- `docs/ATLAS_ARCHITECTURE_CONTRACT.md`
- `docs/OPENHANDS_TRANSITION_GUIDE.md`
- current Python Unreal contracts and provenance/evidence code

Separate claims into:

- implemented
- deterministic-test verified
- live verified
- implemented but unverified
- historical only
- missing

Never promote an older test result to validation of newer code.

### 7. C++ interoperability

Identify interfaces whose contracts should remain language-neutral so performance-critical implementations can later move between Python and C++ without changing authority semantics or higher-level orchestration.

### 8. Autonomous-state gap map

Produce this exact classification:

```text
A. COMPLETE
B. IMPLEMENTED / UNVERIFIED
C. PARTIALLY IMPLEMENTED
D. MISSING
E. HISTORICAL COMPONENT WORTH RESTORING
F. HISTORICAL COMPONENT THAT SHOULD STAY DEAD
```

Then assign each remaining item:

```text
P0 — blocks autonomous state
P1 — required for production reliability
P2 — hardening
P3 — optimization / convenience
```

## Deliverable

Return a technically grounded report containing:

1. executive assessment of current Unreal autonomy;
2. end-to-end architecture trace;
3. exact autonomy blockers;
4. recovery-gap analysis;
5. evidence/provenance-gap analysis;
6. controller trust-boundary findings;
7. Git-history findings with commit/PR references;
8. recommended implementation sequence;
9. risks and regressions to avoid;
10. a final minimal set of changes required to bring Unreal to high-confidence autonomous state.

## Important restrictions

- Audit first; do not modify production code during the initial audit.
- Do not invent new authority systems.
- Do not introduce model-controlled authorization.
- Do not silently change the authorized plan.
- Do not auto-retry failed writes.
- Do not claim job recovery when only receipt persistence exists.
- Do not claim live verification from deterministic tests alone.
- Do not run Atlas workflow/action-runner tests unless explicitly authorized.
- Preserve repository boundaries and existing engine adapter contracts.

## Desired end state

The target is not unrestricted model control. The target is a reliable Atlas-owned autonomous production loop in which Unreal can execute authorized work, independently establish what actually happened, preserve sufficient state/evidence for recovery, and produce verifiable production-artifact lineage without requiring a human to manually shepherd every intermediate step.

Hermes should optimize for **finding the shortest safe path to that state**, not for maximizing the amount of new code.
