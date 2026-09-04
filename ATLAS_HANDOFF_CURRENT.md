# Atlas Current Development Handoff

**Updated:** September 4, 2026 — Blender Stage 17 production artifact lineage is implemented through durable persistence, focused integration regression coverage, and user-verified real Blender proof.
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

A focused Blender pipeline regression exercises the existing `BlenderExecutionBoundary.execute_with_persistence(...)` closed loop, constructs a production artifact from its immutable receipt/evidence, independently verifies the exact lineage binding, round-trips the manifest, and confirms that manifest construction does not trigger another Blender operation or inspection.

`planning/production_artifact_store.py` provides durable versioned JSON persistence for the immutable manifest, with deterministic serialization, atomic replacement, file flushing, and fail-closed reload validation. The persistence boundary is explicitly Windows-safe: POSIX directory fsync is retained where supported, while Windows treats the already-flushed replacement file as the platform durability boundary rather than falsely failing after a successful atomic replacement.

A new integration regression covers the complete offline contract: one Blender boundary closed loop produces the receipt/evidence, the immutable manifest binds them, the manifest is durably persisted, the persisted envelope is reloaded, and independent lineage verification confirms the exact original receipt/evidence. A second proof rejects substitution of a later unrelated Blender receipt/evidence pair against the persisted artifact manifest.

### Blender Stage 17 — LIVE VERIFIED

The user executed `python live_blender_production_artifact_proof.py` locally against the real Blender 4.4 adapter after pulling commit `5306a6b`.

The proof completed successfully:

```text
ATLAS LIVE BLENDER PRODUCTION ARTIFACT PROOF: PASS
REAL BLENDER WRITE -> FRESH SCENE INSPECTION -> IMMUTABLE RECEIPT/EVIDENCE -> DURABLE MANIFEST -> RELOAD -> EXACT LINEAGE VERIFIED
```

Verified live values:

```text
artifact_id                    = atlas-blender-live-proof-001
artifact_path                  = parent_task_INCORRECT.blend
canonical_digital_twin_id      = atlas-soccer-digital-twin-proof
observed_location              = [0.5, 5.233, 0.0]
manifest_digest                = 491dbd365c388db7b5d85bc0ead6760a3dcf44a7300403575410663b7cf166f1
operation_receipt_digest       = 11641aebe30361f151598fdd44d58a42a250d602f73b91c7ae002e4fd4d3ba9c
persistence_evidence_digest    = c02e64de921535eb5e0f12dd301b94294dfab9b5585c32cd5814e518a8873f2b
```

This establishes the real Blender write, fresh independent scene inspection, immutable execution receipt and persistence evidence, durable manifest persistence, reload integrity, and exact lineage binding without introducing an additional execution or authorization layer.

## Next development target

With the Blender Stage 17 gate now live verified, the next work is to extend the same provenance contract to the existing Unreal receipt boundary. This should remain provenance-only: connect existing verified Unreal execution evidence to production artifact lineage without introducing execution or authorization behavior into the manifest layer.

Cross-process Unreal render-job recovery remains a separate, unimplemented capability and must not be implied by receipt persistence or by this provenance extension.

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
- Do not run workflow/action-runner tests unless explicitly authorized.

## PR status

PR #49 remains open, draft, and unmerged. **Do not merge unless explicitly requested.**
