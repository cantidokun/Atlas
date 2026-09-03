# Atlas

## What Atlas is

Atlas is an **AI-assisted sports virtual production and digital-twin platform** focused exclusively on soccer-field-related digital twins and production workflows.

Dedicated photogrammetry software is the upstream reconstruction stage. Blender analyzes, cleans, corrects, optimizes, and prepares the reconstruction. Unreal is a downstream controlled production environment around the canonical Atlas Digital Twin.

```text
Real-world soccer environment / captured soccer footage
                    ↓
          Dedicated photogrammetry
                    ↓
           Initial 3D reconstruction
                    ↓
               Blender Agent
        analyze / clean / correct / optimize
                    ↓
             Atlas Digital Twin
                    ↓
               Unreal Agent
          real-time production / VFX
```

Atlas is designed for source footage including 4K/UHD. Higher resolution changes processing, memory, storage, reconstruction, compositing, and render throughput requirements, not the core orchestration model.

## Authority model

```text
Qwen / AI
  → reason and propose structured production intent

Python / Atlas
  → validate, resolve, authorize, execute, track, verify, recover

Blender / Unreal
  → controlled production execution

Independent verification
  → establish what actually happened
```

Qwen is never the execution or authorization authority.

---

# Current position — September 3, 2026

**Active branch:** `feat/blender-stage11-mainline`  
**PR #49:** open, draft, unmerged  
**Current development stage:** **Stage 17 — production artifact lineage, IN PROGRESS**

Stage 13 multi-step partial-progress recovery is live-verified against Blender 4.4 and passed GitHub Actions. Stage 14 dependency-aware serial execution and cross-process recovery are implemented and live-verified. Stage 15 semantic soccer-production workflows and versioned catalog compilation are complete for the current contract.

Stage 16 Qwen integration is now live-verified through proposal, Atlas authorization, real Blender mutation, and two-process recovery with a fresh Qwen recovery recommendation.

## Stage 16 — Qwen integration — VERIFIED FOR CURRENT CONTRACT

```text
Qwen
  ↓
Ollama structured proposal
  ↓
strict provider-output validation
  ↓
trusted soccer-production catalog
  ↓
QwenProductionProposal
  ↓
ProductionTaskDefinition
  ↓
AtlasTaskDefinition
  ↓
QwenProductionTaskHandoff
  ↓
existing Atlas ActionAuthorization
  ↓
existing AutonomousTaskRuntime
  ↓
Blender execution boundary
  ↓
fresh independent verification
```

The provider and handoff boundaries reject model-supplied executors, authorization IDs, arbitrary tools, combined workflow/version identifiers, malformed parameters, and provenance drift. Qwen recovery recommendations are advisory only; Atlas derives the executable unfinished action from the persisted authorized task.

### Live Qwen-authorized Blender mutation — VERIFIED

```text
workflow=broadcast-goal-preparation
workflow_version=1
qwen_proposal=verified
catalog_validation=verified
semantic_task=verified
atlas_authorization=verified
existing_task_runtime=verified
blender_execution=verified
independent_final_verification=verified
```

### Live Qwen cross-process recovery — VERIFIED

```text
LIVE QWEN PRODUCTION RECOVERY VERIFIED
object=Goal_Left_post
workflow=broadcast-goal-preparation
workflow_version=1
qwen_provenance_recovered=verified
initial_authorization_recovered=verified
process_restart=verified
qwen_recovery_recommendation=verified
qwen_recovery_recommendation_advisory_only=verified
fresh_recovery_evidence=verified
qwen_workflow_target_revalidated=verified
completed_prerequisite_not_replayed=verified
replan_authorization=atlas-qwen-recovery-replan
replacement_execution=verified
independent_final_verification=verified
fixture_restored_location=[0.25, 5.302, 0.0]
fixture_restored_rotation=[0.0, 0.0, 0.0]
```

This proves that Qwen can participate in recovery reasoning without receiving recovery authority. Atlas retains sole control over fresh evidence, recovery classification, replan authorization, execution, and final verification.

---

# Stage 17 — Production artifact lineage

The next production-grade foundation is a first-class lineage contract between the canonical Atlas Digital Twin and its production representations.

`planning/production_artifact.py` introduces `ProductionArtifactManifest`, an immutable, deterministic provenance record for a Blender, Unreal, or other production artifact. It can bind:

- a stable canonical Digital Twin identifier;
- a concrete artifact representation and path;
- upstream source-artifact relationships;
- workflow/version/parameter provenance;
- independent evidence and execution-receipt digests;
- engine and engine-version metadata.

The manifest is deliberately non-executable. It provides no authorization, execution, scheduler, or recovery capability. Its purpose is to make artifact lineage portable across the Blender and Unreal stages without conflating a `.blend`, Unreal project, render output, or receipt with canonical Digital Twin identity.

Regression coverage verifies deterministic digests, round-trip reconstruction, fail-closed tamper detection, self-reference rejection, duplicate-source rejection, unknown-field rejection, and absence of execution/authorization authority.

This is an architectural foundation rather than a claim that the complete production asset graph is finished.

## Stage 17 next work

Extend the lineage contract into the existing Blender and Unreal receipt/evidence paths so a completed production operation can emit a lineage record linking its canonical Digital Twin, input artifacts, workflow provenance, and verified output artifacts.

Do not create a second execution, authorization, or recovery system for lineage tracking.

---

# Earlier proven architecture

### Stage 12 — task-aware autonomous execution and recovery
**COMPLETE FOR CURRENT CONTRACT**

### Stage 13 — multi-step partial-progress recovery
**COMPLETE FOR CURRENT CONTRACT**

### Stage 14 — dependency-aware task composition
**COMPLETE FOR CURRENT CONTRACT**

Explicit dependencies are validated, included in authorization/integrity digests, persisted through continuation, and recovered using checkpoint-derived completed prerequisites. Execution remains serial; parallel scheduling has not been introduced.

### Stage 15 — semantic soccer-production tasks
**COMPLETE FOR CURRENT CONTRACT**

`ProductionTaskDefinition`, reusable production fragments, target-state evaluation, soccer-production templates, and the versioned catalog are established. Current catalog workflow:

```text
broadcast-goal-preparation@1

file_name       -> string
object_name     -> string
target_location -> vector3
target_rotation -> vector3
```

---

# Unreal Agent status

The Unreal Engine 5.6 boundary is proven locally for the implemented render workflow:

- deterministic render configuration and verification;
- Movie Render Queue submission;
- dynamic job-ID binding;
- asynchronous render-job inspection;
- semantic completion verification;
- output artifact discovery;
- filesystem existence and non-zero-size validation;
- evidence-bound `UnrealRenderReceipt` creation;
- durable receipt persistence with fail-closed reload validation.

Controlled proof was 640x360, frames 1–2, PNG. This is a boundary test, not a source-footage resolution limit.

**Cross-process Unreal render-job recovery is not implemented.** Receipt persistence must not be described as job persistence.

---

# Digital Twin and production direction

Atlas owns the canonical Digital Twin. `.blend` files, Unreal projects, levels, render jobs, receipts, and output artifacts are production representations/state, not canonical identity.

The wider production repertoire may include impact frames, smear frames, chromatic aberration, cinematic bleed, match-cut transformations, spatial overlays, digital-twin compositing, and temporary liquid/smoke/glass/metallic environment effects.

These are production modules, not the definition of Atlas.

---

# Non-regression rules

- Qwen never receives direct execution or authorization authority.
- Model output remains untrusted until Atlas validates it.
- Never allow model-supplied authorization IDs or receipts to become Atlas authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from a transport/write response alone.
- Preserve independent verification and the evidence ledger.
- Keep engine-specific behavior behind adapter/tool boundaries.
- Preserve canonical Digital Twin identity separately from production artifacts.
- Do not introduce parallel execution until dependency semantics justify it independently.
- Do not claim cross-process Unreal job recovery unless implemented and verified.

## PR status

PR #49 remains open, draft, and unmerged. **Do not merge unless explicitly requested.**

## Resume point

**Stage 17:** integrate `ProductionArtifactManifest` into the existing evidence/receipt paths, beginning with a narrow Blender production-artifact lineage proof and then the corresponding Unreal boundary. Keep lineage observational/provenance-only; do not add another runtime authority layer.
