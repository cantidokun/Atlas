# Atlas Current Development Handoff

**Updated:** September 4, 2026 — Qwen Stage 16 runtime and cross-process recovery, including live Qwen-guided recovery recommendation binding, are live-verified; Stage 17 artifact-lineage foundation is implemented and regression-tested.
**Active branch:** `feat/blender-stage11-mainline`
**PR #49:** open, draft, unmerged
**Current stage:** Stage 17 — IN PROGRESS

## Authority model

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

Qwen never receives direct production execution or authorization authority.

## Stage 13–16 baseline

Stage 13 multi-step partial-progress recovery is complete for the current contract and live verified against Blender 4.4.

Stage 14 dependency-aware task composition is complete for the current contract. Dependency validation, exact authorization binding, serial deterministic execution, inherited prerequisite handling, and cross-process dependency-aware recovery have been implemented and live verified.

Stage 15 semantic soccer-production tasks are complete for the current contract. `ProductionTaskDefinition`, reusable fragments, target-state evaluation, canonical soccer-production templates, the versioned catalog, and semantic provenance persistence are established and live verified.

Stage 16 Qwen integration is live verified through proposal, Atlas authorization, real Blender mutation, cross-process recovery, and a fresh Qwen-guided recovery recommendation that remains advisory-only.

Current catalog contract:

```text
broadcast-goal-preparation@1

file_name       -> string
object_name     -> string
target_location -> vector3
target_rotation -> vector3
```

## Stage 16 — Qwen integration — LIVE VERIFIED

The complete Qwen-authorized Blender path and two-process recovery path have been user-verified. During recovery, a fresh Qwen recommendation is obtained after process restart and validated against the persisted canonical task. Atlas then derives and authorizes only the unfinished action through the existing recovery runtime.

The live recovery proof included:

```text
qwen_provenance_recovered=verified
initial_authorization_recovered=verified
process_restart=verified
qwen_recovery_recommendation=verified
qwen_recovery_recommendation_advisory_only=verified
fresh_recovery_evidence=verified
qwen_workflow_target_revalidated=verified
completed_prerequisite_not_replayed=verified
replacement_execution=verified
independent_final_verification=verified
```

No Qwen execution, authorization, scheduler, or recovery subsystem was introduced.

## Stage 17 — Production artifact lineage

`planning/production_artifact.py` defines `ProductionArtifactManifest`, a provenance-only contract connecting a production representation to the canonical Atlas Digital Twin, source artifacts, workflow provenance, verification evidence, execution receipts, engine metadata, and a deterministic integrity digest.

The Blender bridge `ProductionArtifactManifest.from_blender_closed_loop(...)` accepts only existing `BlenderExecutionReceipt` and `BlenderPersistenceEvidence` objects. It does not execute, authorize, or verify work itself.

Regression coverage proves verified Blender receipt/evidence binding, deterministic lineage, round-trip persistence, tamper detection, self-reference rejection, unknown-field rejection, and absence of execution/authorization APIs.

A focused Blender pipeline regression now exercises the existing `BlenderExecutionBoundary.execute_with_persistence(...)` closed loop, constructs a production artifact from its immutable receipt/evidence, independently verifies the exact lineage binding, round-trips the manifest, and confirms that manifest construction does not trigger another Blender operation or inspection.

## Next verification gate

The next live proof should use a real `BlenderExecutionBoundary.execute_with_persistence(...)` result to construct a `ProductionArtifactManifest`, then independently verify and persist the manifest. The proof should establish that the recorded lineage points to the same canonical Digital Twin and verified artifact path without introducing another execution or authorization layer.

After that, extend the same provenance contract to the existing Unreal receipt boundary. Cross-process Unreal render-job recovery remains a separate, unimplemented capability and must not be implied by receipt persistence.

## Non-regression rules

- Qwen remains proposal-only.
- Never accept model-supplied authorization IDs or receipts as authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from transport/write success alone.
- Preserve independent verification and the evidence ledger.
- Keep engine-specific behavior behind adapter/tool boundaries.
- Keep dependency-aware execution serial until concurrency is independently justified.
- Preserve canonical Digital Twin identity separately from production artifacts.
- Do not claim cross-process Unreal job recovery unless separately implemented and verified.

## PR status

PR #49 remains open, draft, and unmerged. **Do not merge unless explicitly requested.**