import json
from pathlib import Path

import pytest

from planning.production_artifact import (
    ProductionArtifactError,
    ProductionArtifactManifest,
    verify_unreal_render_lineage,
)
from planning.production_artifact_store import (
    ProductionArtifactStore,
    ProductionArtifactStoreError,
)
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_render_receipt import UnrealRenderReceipt


def _evidence(*, job_id="render-job-001", sequence_asset_path="/Game/Atlas/Sequences/Soccer"):
    return UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=(job_id,),
        observed_state={
            "job_id": job_id,
            "sequence_asset_path": sequence_asset_path,
            "status": "completed",
        },
        source="unreal-inspection-adapter",
        verified=True,
    )


def test_unreal_render_lineage_survives_durable_manifest_round_trip(tmp_path: Path):
    evidence = _evidence()
    receipt = UnrealRenderReceipt.issue(evidence)
    manifest = ProductionArtifactManifest.from_unreal_render_receipt(
        artifact_id="atlas-unreal-render-001",
        canonical_digital_twin_id="atlas-soccer-digital-twin-001",
        representation_type="unreal-render",
        artifact_path="renders/soccer-001.exr",
        render_receipt=receipt,
        render_evidence=evidence,
        source_artifact_ids=("atlas-blender-artifact-001",),
        engine_version="5.x",
    )

    store = ProductionArtifactStore(str(tmp_path / "artifact.json"))
    store.save(manifest)
    reloaded = store.load()

    verify_unreal_render_lineage(reloaded, receipt, evidence)
    assert reloaded.snapshot() == manifest.snapshot()
    assert reloaded.digest() == manifest.digest()


def test_persisted_unreal_artifact_rejects_lineage_substitution(tmp_path: Path):
    evidence = _evidence()
    receipt = UnrealRenderReceipt.issue(evidence)
    manifest = ProductionArtifactManifest.from_unreal_render_receipt(
        artifact_id="atlas-unreal-render-001",
        canonical_digital_twin_id="atlas-soccer-digital-twin-001",
        representation_type="unreal-render",
        artifact_path="renders/soccer-001.exr",
        render_receipt=receipt,
        render_evidence=evidence,
    )
    store = ProductionArtifactStore(str(tmp_path / "artifact.json"))
    store.save(manifest)
    before = store.load()

    substitute_evidence = _evidence(
        job_id="render-job-002",
        sequence_asset_path="/Game/Atlas/Sequences/Other",
    )
    substitute_receipt = UnrealRenderReceipt.issue(substitute_evidence)

    with pytest.raises(ProductionArtifactError):
        verify_unreal_render_lineage(before, substitute_receipt, substitute_evidence)

    after = store.load()
    assert after.snapshot() == before.snapshot()
    assert after.digest() == before.digest()


def test_persisted_unreal_manifest_rejects_tampered_envelope(tmp_path: Path):
    evidence = _evidence()
    receipt = UnrealRenderReceipt.issue(evidence)
    manifest = ProductionArtifactManifest.from_unreal_render_receipt(
        artifact_id="atlas-unreal-render-001",
        canonical_digital_twin_id="atlas-soccer-digital-twin-001",
        representation_type="unreal-render",
        artifact_path="renders/soccer-001.exr",
        render_receipt=receipt,
        render_evidence=evidence,
    )
    path = tmp_path / "artifact.json"
    store = ProductionArtifactStore(str(path))
    store.save(manifest)

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["manifest"]["artifact_path"] = "renders/tampered.exr"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProductionArtifactStoreError):
        store.load()
