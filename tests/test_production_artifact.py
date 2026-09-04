import pytest

from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_persistence_evidence import BlenderPersistenceEvidence
from planning.blender_execution_result import BlenderExecutionResult
from planning.production_artifact import ProductionArtifactError, ProductionArtifactManifest, verify_blender_closed_loop_lineage


def _verified_blender_pair():
    operation_receipt = BlenderExecutionReceipt.create(
        "move_object",
        {"file_name": "scene.blend", "object_name": "Goal_Left_post", "location": [0.5, 5.233, 0.0]},
        BlenderExecutionResult(
            tool="move_object",
            ok=True,
            state="moved",
            details={"object_name": "Goal_Left_post", "location": [0.5, 5.233, 0.0]},
        ),
    )
    persistence_evidence = BlenderPersistenceEvidence.create(
        operation_tool="move_object",
        operation_arguments_digest=operation_receipt.arguments_digest,
        inspection_tool="inspect_scene",
        expected_state_digest="expected-state-digest",
        observed_state_digest="expected-state-digest",
    )
    return operation_receipt, persistence_evidence


def _closed_loop_manifest(receipt, evidence):
    return ProductionArtifactManifest.from_blender_closed_loop(
        artifact_id="atlas-blender-artifact-001",
        canonical_digital_twin_id="atlas-soccer-digital-twin",
        representation_type="blender-scene",
        artifact_path="scene.blend",
        operation_receipt=receipt,
        persistence_evidence=evidence,
    )


def test_closed_loop_lineage_verification_accepts_exact_pair():
    receipt, evidence = _verified_blender_pair()
    manifest = _closed_loop_manifest(receipt, evidence)
    verify_blender_closed_loop_lineage(manifest, receipt, evidence)


def test_closed_loop_lineage_verification_rejects_receipt_substitution():
    receipt, evidence = _verified_blender_pair()
    manifest = _closed_loop_manifest(receipt, evidence)
    replacement = BlenderExecutionReceipt.create(
        "move_object",
        {"file_name": "scene.blend", "object_name": "Goal_Left_post", "location": [1.0, 5.302, 0.0]},
        BlenderExecutionResult(
            tool="move_object",
            ok=True,
            state="moved",
            details={"object_name": "Goal_Left_post", "location": [1.0, 5.302, 0.0]},
        ),
    )
    with pytest.raises(ProductionArtifactError, match="Blender receipt and persistence evidence operation arguments do not match"):
        verify_blender_closed_loop_lineage(manifest, replacement, evidence)


def test_closed_loop_lineage_verification_rejects_evidence_substitution():
    receipt, evidence = _verified_blender_pair()
    manifest = _closed_loop_manifest(receipt, evidence)
    evidence_snapshot = evidence.snapshot()
    evidence_snapshot["operation_arguments_digest"] = "substituted-operation-arguments-digest"
    replacement = BlenderPersistenceEvidence.from_snapshot(evidence_snapshot)
    with pytest.raises(ProductionArtifactError, match="Blender receipt and persistence evidence operation arguments do not match"):
        verify_blender_closed_loop_lineage(manifest, receipt, replacement)


def test_closed_loop_lineage_verification_rejects_cross_operation_pair():
    receipt, evidence = _verified_blender_pair()
    manifest = _closed_loop_manifest(receipt, evidence)
    evidence_snapshot = evidence.snapshot()
    evidence_snapshot["operation_tool"] = "delete_object"
    replacement = BlenderPersistenceEvidence.from_snapshot(evidence_snapshot)
    with pytest.raises(ProductionArtifactError, match="Blender receipt and persistence evidence operation tools do not match"):
        verify_blender_closed_loop_lineage(manifest, receipt, replacement)
