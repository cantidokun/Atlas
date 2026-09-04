import pytest

from planning.production_artifact import ProductionArtifactError, ProductionArtifactManifest, verify_unreal_render_lineage
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_render_receipt import UnrealRenderReceipt


def _evidence(**overrides):
    state = {
        "job_id": "job-lineage-123",
        "status": "finished",
        "finished": True,
        "success": True,
        "failed": False,
        "sequence_asset_path": "/Game/Atlas/Sequence",
        "output_directory": "Saved/AtlasRenderOutput",
        "output_format": "png",
        "output_files": ["C:/renders/AtlasRender_0001.png"],
    }
    state.update(overrides)
    return UnrealEvidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=state, verified=True, source="artifact-lineage-test")


def test_unreal_receipt_binds_to_production_artifact_manifest():
    evidence = _evidence()
    receipt = UnrealRenderReceipt.issue(evidence)
    manifest = ProductionArtifactManifest.from_unreal_render_receipt(
        artifact_id="atlas-unreal-render-001",
        canonical_digital_twin_id="atlas-soccer-digital-twin",
        representation_type="unreal-render",
        artifact_path="C:/renders/AtlasRender_0001.png",
        render_receipt=receipt,
        render_evidence=evidence,
        engine_version="5.6",
    )
    verify_unreal_render_lineage(manifest, receipt, evidence)
    assert manifest.receipt_digests == (receipt.receipt_digest,)
    assert manifest.evidence_digests == (receipt.evidence_digest,)
    assert manifest.canonical_digital_twin_id == "atlas-soccer-digital-twin"
    assert manifest.engine == "Unreal"


def test_unreal_manifest_rejects_engine_substitution_at_construction():
    evidence = _evidence()
    receipt = UnrealRenderReceipt.issue(evidence)
    with pytest.raises(ProductionArtifactError, match="engine must be Unreal"):
        ProductionArtifactManifest.from_unreal_render_receipt(
            artifact_id="atlas-unreal-render-001",
            canonical_digital_twin_id="atlas-soccer-digital-twin",
            representation_type="unreal-render",
            artifact_path="C:/renders/AtlasRender_0001.png",
            render_receipt=receipt,
            render_evidence=evidence,
            engine="Blender",
        )


def test_unreal_lineage_rejects_engine_substitution():
    evidence = _evidence()
    receipt = UnrealRenderReceipt.issue(evidence)
    manifest = ProductionArtifactManifest.from_unreal_render_receipt(
        artifact_id="atlas-unreal-render-001",
        canonical_digital_twin_id="atlas-soccer-digital-twin",
        representation_type="unreal-render",
        artifact_path="C:/renders/AtlasRender_0001.png",
        render_receipt=receipt,
        render_evidence=evidence,
    )
    tampered = ProductionArtifactManifest(
        artifact_id=manifest.artifact_id,
        canonical_digital_twin_id=manifest.canonical_digital_twin_id,
        representation_type=manifest.representation_type,
        artifact_path=manifest.artifact_path,
        source_artifact_ids=manifest.source_artifact_ids,
        workflow_provenance=manifest.workflow_provenance,
        evidence_digests=manifest.evidence_digests,
        receipt_digests=manifest.receipt_digests,
        engine="Blender",
        engine_version=manifest.engine_version,
        metadata=manifest.metadata,
        manifest_version=manifest.manifest_version,
    )
    with pytest.raises(ProductionArtifactError, match="lineage engine is invalid"):
        verify_unreal_render_lineage(tampered, receipt, evidence)


def test_unreal_manifest_rejects_artifact_path_not_observed_by_render():
    evidence = _evidence()
    receipt = UnrealRenderReceipt.issue(evidence)
    with pytest.raises(ProductionArtifactError, match="artifact path is not present in verified render outputs"):
        ProductionArtifactManifest.from_unreal_render_receipt(
            artifact_id="atlas-unreal-render-001",
            canonical_digital_twin_id="atlas-soccer-digital-twin",
            representation_type="unreal-render",
            artifact_path="C:/renders/AtlasRender_0002.png",
            render_receipt=receipt,
            render_evidence=evidence,
        )


def test_unreal_lineage_rejects_artifact_path_substitution():
    evidence = _evidence()
    receipt = UnrealRenderReceipt.issue(evidence)
    manifest = ProductionArtifactManifest.from_unreal_render_receipt(
        artifact_id="atlas-unreal-render-001",
        canonical_digital_twin_id="atlas-soccer-digital-twin",
        representation_type="unreal-render",
        artifact_path="C:/renders/AtlasRender_0001.png",
        render_receipt=receipt,
        render_evidence=evidence,
    )
    tampered = ProductionArtifactManifest(
        artifact_id=manifest.artifact_id,
        canonical_digital_twin_id=manifest.canonical_digital_twin_id,
        representation_type=manifest.representation_type,
        artifact_path="C:/renders/AtlasRender_0002.png",
        source_artifact_ids=manifest.source_artifact_ids,
        workflow_provenance=manifest.workflow_provenance,
        evidence_digests=manifest.evidence_digests,
        receipt_digests=manifest.receipt_digests,
        engine=manifest.engine,
        engine_version=manifest.engine_version,
        metadata=manifest.metadata,
        manifest_version=manifest.manifest_version,
    )
    with pytest.raises(ProductionArtifactError, match="artifact path is not present in verified render outputs"):
        verify_unreal_render_lineage(tampered, receipt, evidence)


def test_unreal_lineage_rejects_evidence_substitution():
    evidence = _evidence()
    receipt = UnrealRenderReceipt.issue(evidence)
    manifest = ProductionArtifactManifest.from_unreal_render_receipt(
        artifact_id="atlas-unreal-render-001",
        canonical_digital_twin_id="atlas-soccer-digital-twin",
        representation_type="unreal-render",
        artifact_path="C:/renders/AtlasRender_0001.png",
        render_receipt=receipt,
        render_evidence=evidence,
    )
    changed = _evidence(output_files=["C:/renders/AtlasRender_0002.png"])
    with pytest.raises(ProductionArtifactError, match="does not match render evidence"):
        verify_unreal_render_lineage(manifest, receipt, changed)


def test_unreal_manifest_rejects_mismatched_receipt_at_construction():
    evidence = _evidence()
    receipt = UnrealRenderReceipt.issue(evidence)
    changed = _evidence(job_id="job-other")
    with pytest.raises(ProductionArtifactError, match="does not match render evidence"):
        ProductionArtifactManifest.from_unreal_render_receipt(
            artifact_id="atlas-unreal-render-001",
            canonical_digital_twin_id="atlas-soccer-digital-twin",
            representation_type="unreal-render",
            artifact_path="C:/renders/AtlasRender_0001.png",
            render_receipt=receipt,
            render_evidence=changed,
        )


def test_unreal_manifest_rejects_missing_output_files():
    evidence = _evidence(output_files=None)
    receipt = UnrealRenderReceipt.issue(evidence)
    with pytest.raises(ProductionArtifactError, match="must include output_files"):
        ProductionArtifactManifest.from_unreal_render_receipt(
            artifact_id="atlas-unreal-render-001",
            canonical_digital_twin_id="atlas-soccer-digital-twin",
            representation_type="unreal-render",
            artifact_path="C:/renders/AtlasRender_0001.png",
            render_receipt=receipt,
            render_evidence=evidence,
        )


def test_unreal_manifest_lineage_is_deterministic():
    evidence = _evidence()
    receipt = UnrealRenderReceipt.issue(evidence)
    first = ProductionArtifactManifest.from_unreal_render_receipt(
        artifact_id="atlas-unreal-render-001",
        canonical_digital_twin_id="atlas-soccer-digital-twin",
        representation_type="unreal-render",
        artifact_path="C:/renders/AtlasRender_0001.png",
        render_receipt=receipt,
        render_evidence=evidence,
        workflow_provenance={"workflow": "broadcast-goal-preparation", "version": 1},
    )
    second = ProductionArtifactManifest.from_unreal_render_receipt(
        artifact_id="atlas-unreal-render-001",
        canonical_digital_twin_id="atlas-soccer-digital-twin",
        representation_type="unreal-render",
        artifact_path="C:/renders/AtlasRender_0001.png",
        render_receipt=receipt,
        render_evidence=evidence,
        workflow_provenance={"version": 1, "workflow": "broadcast-goal-preparation"},
    )
    assert first == second
    assert first.digest() == second.digest()
