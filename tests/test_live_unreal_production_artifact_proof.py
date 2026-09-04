import json
from pathlib import Path

import pytest

from live_unreal_production_artifact_proof import main
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_evidence_digest import digest_evidence
from planning.unreal_render_receipt import UnrealRenderReceipt


def _write_inputs(tmp_path: Path):
    evidence = UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=("render-job-001",),
        observed_state={
            "job_id": "render-job-001",
            "sequence_asset_path": "/Game/Atlas/Sequences/Soccer",
            "status": "completed",
            "success": True,
            "failed": False,
            "output_files": ["Saved/AtlasRenderOutput/AtlasRender_0001.png"],
        },
        source="real-unreal-inspection",
        verified=True,
    )
    receipt = UnrealRenderReceipt.issue(evidence)
    evidence_path = tmp_path / "evidence.json"
    receipt_path = tmp_path / "receipt.json"
    evidence_path.write_text(
        json.dumps(
            {
                "operation_name": evidence.operation_name,
                "entity_ids": list(evidence.entity_ids),
                "observed_state": dict(evidence.observed_state),
                "source": evidence.source,
                "verified": evidence.verified,
            }
        ),
        encoding="utf-8",
    )
    receipt_path.write_text(
        json.dumps(
            {
                "job_id": receipt.job_id,
                "sequence_asset_path": receipt.sequence_asset_path,
                "evidence_digest": receipt.evidence_digest,
            }
        ),
        encoding="utf-8",
    )
    return evidence, receipt, evidence_path, receipt_path


def test_live_unreal_proof_harness_completes_without_engine_execution(tmp_path, monkeypatch, capsys):
    evidence, receipt, evidence_path, receipt_path = _write_inputs(tmp_path)
    output_path = tmp_path / "manifest.json"

    monkeypatch.setattr(
        "sys.argv",
        [
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
            "Saved/AtlasRenderOutput/AtlasRender_0001.png",
            "--output",
            str(output_path),
        ],
    )

    main()
    captured = capsys.readouterr().out

    assert "ATLAS LIVE UNREAL PRODUCTION ARTIFACT PROOF: PASS" in captured
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["store_version"] == 1
    assert payload["manifest"]["engine"] == "Unreal"
    assert payload["manifest"]["canonical_digital_twin_id"] == "atlas-soccer-digital-twin-proof"
    assert payload["manifest"]["artifact_path"] == "Saved/AtlasRenderOutput/AtlasRender_0001.png"
    assert payload["manifest_digest"] == json.loads(captured[captured.index("{"):])["manifest_digest"]
    assert receipt.evidence_digest == digest_evidence(evidence)


def test_harness_rejects_receipt_evidence_substitution(tmp_path, monkeypatch):
    _, _, evidence_path, receipt_path = _write_inputs(tmp_path)
    receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_payload["evidence_digest"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt_payload), encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
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
            "Saved/AtlasRenderOutput/AtlasRender_0001.png",
            "--output",
            str(tmp_path / "manifest.json"),
        ],
    )

    with pytest.raises(Exception):
        main()
