# Unreal Stage 17 — Live Production-Artifact Proof

## Purpose

This is the final human validation gate for the Unreal Stage 17 production-artifact lineage boundary.

The proof consumes evidence already produced and independently verified by the existing Unreal 5.6 render boundary. It does not submit a render, execute Unreal, authorize production work, schedule a job, or recover a render job.

## Required evidence

Provide a JSON snapshot with exactly these fields:

```json
{
  "operation_name": "inspect_render_job",
  "entity_ids": ["..."],
  "observed_state": {
    "job_id": "...",
    "sequence_asset_path": "/Game/...",
    "status": "finished",
    "finished": true,
    "success": true,
    "failed": false,
    "output_files": [".../AtlasRender_0001.png"]
  },
  "source": "...",
  "verified": true
}
```

The matching receipt JSON must contain exactly:

```json
{
  "job_id": "...",
  "sequence_asset_path": "/Game/...",
  "evidence_digest": "..."
}
```

The receipt must have been issued from the exact evidence snapshot supplied to the harness.

## Proof command

From the Atlas repository root:

```powershell
python .\live_unreal_production_artifact_proof.py `
  --evidence .\<verified-evidence>.json `
  --receipt .\<matching-receipt>.json `
  --artifact-id atlas-unreal-live-proof-001 `
  --canonical-digital-twin-id atlas-soccer-digital-twin-proof `
  --artifact-path "<exact output path from observed_state.output_files>" `
  --engine-version 5.6 `
  --output .\unreal-production-artifact-proof.json
```

## Acceptance

The proof is accepted only when all of the following are true:

1. The harness reports `ATLAS LIVE UNREAL PRODUCTION ARTIFACT PROOF: PASS`.
2. The persisted manifest reloads successfully.
3. The manifest engine is `Unreal`.
4. The artifact path exactly matches an independently observed render output.
5. Receipt and evidence digests remain identical after reload.
6. Independent lineage verification succeeds.

A successful result proves provenance for that concrete render artifact. It does not prove cross-process Unreal render-job recovery.

## Boundary rule

The harness is intentionally downstream of the existing render proof:

```text
UE 5.6 render
  -> inspect_render_job
  -> verify_render_job_evidence() (authoritative independent verification boundary)
  -> verified UnrealEvidence
  -> UnrealRenderReceipt.issue()
  -> ProductionArtifactManifest
  -> ProductionArtifactStore
  -> reload
  -> independent lineage verification
```

The authoritative verification function is `verify_render_job_evidence` in `planning/unreal_evidence_contract.py`.
It validates semantic completion (`status in ('completed', 'finished')`, `finished == True`, `success == True`, `failed == False`), canonical job/sequence identity, non-empty `output_files`, and physical existence, accessibility, and non-zero byte size of every output artifact on the local filesystem. Only when all checks pass is `UnrealEvidence` constructed with `verified=True`. No caller or test manually asserts `verified=True`.

No second Unreal execution path should be introduced for this gate.
