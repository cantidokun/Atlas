"""One-shot failure-safe live proof execution script for Unreal Stage 17.

This script executes or recovers an authorized Unreal render job, authoritatively
verifies render evidence via verify_render_job_evidence(), issues an immutable
UnrealRenderReceipt, writes verified evidence and receipt snapshots, and invokes
the Stage 17 provenance harness (live_unreal_production_artifact_proof.py).

Guarantees:
- Uses UnrealRenderSubmissionService and AtlasRenderJobStore for durable intent persistence
- Reuses existing durable Atlas render job record if present to avoid duplicate renders
- Immediately persists durable intent before named-pipe transport transmission
- Never calls json.dumps() directly on mappingproxy objects
- Never manually sets verified=True
- Only issues receipt and writes snapshots upon authoritative verification pass
- Never submits a second render due to diagnostic/serialization failure
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping

from planning.unreal_adapter_production import create_production_adapter
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_evidence_contract import _thaw, verify_render_job_evidence
from planning.unreal_render_contract import UnrealRenderConfig
from planning.unreal_render_job_record import AtlasRenderJobRecord
from planning.unreal_render_job_states import RenderJobLifecycleState
from planning.unreal_render_job_store import AtlasRenderJobStore
from planning.unreal_render_receipt import UnrealRenderReceipt
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_submission import UnrealRenderSubmissionService


def safe_json(obj: Any) -> str:
    return json.dumps(_thaw(obj), indent=2, sort_keys=True)


def main() -> None:
    auth_id = "auth-stage17-live-proof"
    entity_id = "FIELD_SURFACE"
    sequence_path = "/Game/AtlasTest/AtlasSequencerFixtureSequence"
    digital_twin_id = "canonical-digital-twin-field-surface"
    output_parent = "C:/Users/Gavin's PC/Desktop/Atlas/unreal/AtlasUnrealHarness/Saved/MovieRenders"

    # M3 Durable Store and Submission Service
    store_dir = Path(".atlas_render_store")
    store = AtlasRenderJobStore(store_dir)
    receipt_store = UnrealRenderReceiptStore(Path("render_receipt.json"))
    adapter = create_production_adapter()

    submission_service = UnrealRenderSubmissionService(
        store=store,
        adapter=adapter,
        receipt_store=receipt_store,
    )

    render_config = UnrealRenderConfig(
        width=1280,
        height=720,
        start_frame=0,
        end_frame=24,
        output_directory=output_parent,
        output_format="png",
    )

    print("=== M3 DURABLE SUBMISSION ORCHESTRATION ===")
    sub_result = submission_service.submit_render(
        authorization_id=auth_id,
        canonical_digital_twin_id=digital_twin_id,
        sequence_asset_path=sequence_path,
        output_parent_directory=output_parent,
        render_config=render_config,
        entity_ids=(entity_id,),
    )

    record = sub_result.record
    job_id = record.unreal_job_id
    atlas_job_id = record.atlas_job_id

    print(f"DURABLE ATLAS JOB ID: {atlas_job_id}")
    print(f"UNREAL JOB ID: {job_id}")
    print(f"LIFECYCLE STATE: {record.lifecycle_state.value}")
    print(f"RECOVERY STATUS: {record.recovery_status.value}")

    if sub_result.acceptance_unknown:
        raise RuntimeError(
            f"Submission uncertainty for {atlas_job_id}: {record.failure_reason}. "
            "Deferring to reconciliation coordinator."
        )

    if not job_id:
        raise RuntimeError(f"Submission failed without unreal_job_id: {record.failure_reason}")

    # Poll inspect_render_job
    inspect_op = UnrealOperation(
        capability=UnrealCapability.RENDER,
        kind=UnrealOperationKind.READ,
        name="inspect_render_job",
        arguments={
            "entity_ids": (entity_id,),
            "job_id": job_id,
        },
        entity_ids=(entity_id,),
    )

    raw_job_state: Mapping[str, Any] | None = None
    inspect_source: str = ""
    for attempt in range(120):
        inspect_evidence = adapter.inspect(inspect_op, auth_id)
        raw_job_state = inspect_evidence.observed_state
        inspect_source = inspect_evidence.source

        status = raw_job_state.get("status")
        finished = raw_job_state.get("finished")
        progress = raw_job_state.get("progress")
        print(
            f"POLL {attempt + 1}: status={status} finished={finished} progress={progress}"
        )

        if finished is True:
            break
        time.sleep(1)

    if raw_job_state is None or raw_job_state.get("finished") is not True:
        raise RuntimeError("Render job did not finish within poll window.")

    # Pass raw inspect observed_state directly to verify_render_job_evidence()
    # (Authoritative verification boundary constructs verified UnrealEvidence; no manual verified=True)
    verified_evidence = verify_render_job_evidence(
        operation_name="inspect_render_job",
        entity_ids=(entity_id,),
        observed_state=raw_job_state,
        source=inspect_source,
        job_record=record,
        evidence_source_class="ENGINE_LIVE",
    )

    # Issue receipt strictly from verified evidence
    receipt = UnrealRenderReceipt.issue(verified_evidence)

    # Write verified evidence and receipt snapshots
    evidence_path = Path("verified_evidence.json")
    receipt_path = Path("render_receipt.json")
    evidence_path.write_text(
        json.dumps(verified_evidence.snapshot(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    receipt_store.save(receipt)

    output_files = verified_evidence.observed_state.get("output_files", ())
    if not output_files:
        raise RuntimeError("Verified evidence contains no output files.")
    artifact_path = output_files[0]

    # Run Stage 17 provenance harness
    cmd = [
        sys.executable,
        "live_unreal_production_artifact_proof.py",
        "--evidence",
        str(evidence_path),
        "--receipt",
        str(receipt_path),
        "--artifact-id",
        "atlas-unreal-live-proof-001",
        "--canonical-digital-twin-id",
        "atlas-soccer-digital-twin-proof",
        "--artifact-path",
        str(artifact_path),
        "--engine-version",
        "5.6",
        "--output",
        "unreal-production-artifact-proof.json",
    ]
    res = subprocess.run(cmd, check=True)
    if res.returncode == 0:
        print("STAGE 17 PROVENANCE HARNESS COMPLETED SUCCESSFULLY.")


if __name__ == "__main__":
    main()
