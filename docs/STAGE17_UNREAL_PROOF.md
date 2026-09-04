# Atlas Stage 17 — Unreal Production-Artifact Proof

## Purpose

This is the final human validation gate for Stage 17 Unreal production-artifact lineage. It validates provenance integration around an already-proven Unreal Engine 5.6 render boundary; it does not introduce another render execution path.

## Required boundary

The input receipt/evidence pair must come from the existing verified Unreal render workflow:

```text
render configuration
  → configuration verification
  → Movie Render Queue submission
  → dynamic job ID
  → asynchronous job inspection
  → semantic completion verification
  → actual output artifact discovery
  → filesystem validation
  → verified UnrealEvidence
  → UnrealRenderReceipt
```

The Stage 17 harness then performs only:

```text
verified evidence snapshot
  → immutable receipt reconstruction
  → ProductionArtifactManifest construction
  → durable ProductionArtifactStore persistence
  → reload
  → independent exact-lineage verification
```

No render is submitted, no Unreal job is started, no authorization is performed, and no recovery is attempted by the Stage 17 harness.

## Canonical snapshots

`UnrealEvidence.snapshot()` / `UnrealEvidence.from_snapshot(...)` and `UnrealRenderReceipt.snapshot()` / `UnrealRenderReceipt.from_snapshot(...)` are the canonical detached serialization boundaries. Snapshot reconstruction is fail-closed on unexpected fields.

## Proof command

From the Atlas repository, with the evidence and receipt snapshots produced by the existing verified Unreal boundary:

```powershell
python live_unreal_production_artifact_proof.py `
  --evidence <PATH_TO_UNREAL_EVIDENCE_JSON> `
  --receipt <PATH_TO_UNREAL_RECEIPT_JSON> `
  --artifact-id atlas-unreal-stage17-proof-001 `
  --canonical-digital-twin-id <CANONICAL_ATLAS_DIGITAL_TWIN_ID> `
  --artifact-path <EXACT_RENDER_OUTPUT_PATH> `
  --engine-version 5.6 `
  --output unreal-production-artifact-proof.json
```

For `--artifact-path`, use the exact path present in the verified evidence `observed_state.output_files`. The lineage contract rejects paths that are not independently observed render outputs.

## Expected result

```text
ATLAS LIVE UNREAL PRODUCTION ARTIFACT PROOF: PASS
VERIFIED UNREAL RENDER EVIDENCE -> IMMUTABLE RECEIPT -> PROVENANCE MANIFEST -> DURABLE STORE -> RELOAD -> EXACT LINEAGE VERIFIED
```

The JSON output reports the artifact ID/path, canonical Digital Twin ID, Unreal engine/version, manifest digest, render receipt digest, and render evidence digest. Record those exact values as the human proof evidence.

## Important non-regression rule

Receipt persistence is not Unreal runtime job persistence. Cross-process Unreal render-job recovery remains outside Stage 17 and is not implied by this proof.
