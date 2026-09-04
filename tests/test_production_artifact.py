import copy

import pytest

from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_persistence_evidence import BlenderPersistenceEvidence
from planning.blender_result_contract import BlenderExecutionResult
from planning.production_artifact import (
    ProductionArtifactError,
    ProductionArtifactManifest,
    verify_blender_closed_loop_lineage,
)


VALID = {
    "manifest_version": 1,
    "artifact_id": "blender-goal-v001",
    "canonical_digital_twin_id": "soccer-twin-001",
    "representation_type": "blender-scene",
    "artifact_path": "production/goal_scene.blend",
    "source_artifact_ids": ["photogrammetry-reconstruction-v004"],
    "workflow_provenance": {
        "name": "broadcast-goal-preparation",
        "version": 1,
        "parameters": {
            "file_name": "scene.blend",
            "object_name": "Goal_Left_post",
            "target_location": [0.25, 5.302, 0.0],
            "target_rotation": [0.0, 0.0, 15.0],
        },
    },
    "evidence_digests": ["evidence-abc"],
    "receipt_digests": ["receipt-xyz"],
    "engine": "Blender",
    "engine_version": "4.4",
    "metadata": {"stage": "cleanup"},
}


def _verified_blender_pair():
    arguments = {"file_name": "scene.blend", "object_name": "Goal_Left_post", "location": [0.25, 5.302, 0.0]}
    result = BlenderExecutionResult(
        tool="move_object",
        ok=True,
        state="moved",
        details={"object_name": "Goal_Left_post", "location": [0.25, 5.302, 0.0]},
    )
    inspection = BlenderExecutionResult(
        tool="inspect_scene",
        ok=True,
        state="inspected",
        details={"Goal_Left_post": {"location": [0.25, 5.302, 0.0]}},
    )
    receipt = BlenderExecutionReceipt.create("move_object", arguments, result)
    evidence = BlenderPersistenceEvidence.create(
        "move_object",
        arguments,
        "inspect_scene",
        {"Goal_Left_post": {"location": [0.25, 5.302, 0.0]}},
        {"Goal_Left_post": {"location": [0.25, 5.302, 0.0]}},
        inspection,
    )
    return receipt, evidence


def _closed_loop_manifest(receipt, evidence):
    return ProductionArtifactManifest.from_blender_closed_loop(
        artifact_id="blender-goal-v002",
        canonical_digital_twin_id="soccer-twin-001",
        representation_type="blender-scene",
        artifact_path="production/goal_scene.blend",
        operation_receipt=receipt,
        persistence_evidence=evidence,
        workflow_provenance=VALID["workflow_provenance"],
        source_artifact_ids=("photogrammetry-reconstruction-v004",),
        engine_version="4.4",
    )


def test_manifest_binds_artifact_to_canonical_digital_twin():
    manifest = ProductionArtifactManifest.from_snapshot(VALID)
    snapshot = manifest.snapshot()
    assert snapshot["canonical_digital_twin_id"] == "soccer-twin-001"
    assert snapshot["representation_type"] == "blender-scene"
    assert snapshot["source_artifact_ids"] == ["photogrammetry-reconstruction-v004"]
    assert manifest.digest()


def test_manifest_binds_verified_blender_receipt_and_persistence_evidence():
    receipt, evidence = _verified_blender_pair()
    manifest = _closed_loop_manifest(receipt, evidence)
    assert manifest.evidence_digests == (evidence.digest(),)
    assert manifest.receipt_digests == (receipt.digest(),)
    assert manifest.digest()
    assert manifest.snapshot()["canonical_digital_twin_id"] == "soccer-twin-001"


def test_closed_loop_manifest_rejects_receipt_evidence_operation_mismatch():
    receipt, _ = _verified_blender_pair()
    arguments = {"file_name": "scene.blend", "object_name": "Goal_Left_post", "rotation": [0.0, 0.0, 15.0]}
    inspection_state = {"Goal_Left_post": {"location": [0.25, 5.302, 0.0]}}
    mismatched = BlenderPersistenceEvidence.create(
        "rotate_object",
        arguments,
        "inspect_scene",
        inspection_state,
        inspection_state,
        BlenderExecutionResult(
            tool="inspect_scene",
            ok=True,
            state="inspected",
            details=inspection_state,
        ),
    )
    with pytest.raises(ProductionArtifactError, match="operation (tools|arguments) do not match"):
        _closed_loop_manifest(receipt, mismatched)


def test_closed_loop_lineage_verification_accepts_exact_records():
    receipt, evidence = _verified_blender_pair()
    manifest = _closed_loop_manifest(receipt, evidence)
    verify_blender_closed_loop_lineage(manifest, receipt, evidence)


def test_closed_loop_lineage_verification_rejects_invalid_engine_binding():
    receipt, evidence = _verified_blender_pair()
    manifest = ProductionArtifactManifest(
        artifact_id="blender-goal-v002",
        canonical_digital_twin_id="soccer-twin-001",
        representation_type="blender-scene",
        artifact_path="production/goal_scene.blend",
        operation_receipt=None,
        engine="Unreal",
    ) if False else None
    valid = _closed_loop_manifest(receipt, evidence)
    invalid = ProductionArtifactManifest(
        artifact_id=valid.artifact_id,
        canonical_digital_twin_id=valid.canonical_digital_twin_id,
        representation_type=valid.representation_type,
        artifact_path=valid.artifact_path,
        source_artifact_ids=valid.source_artifact_ids,
        workflow_provenance=valid.workflow_provenance,
        evidence_digests=valid.evidence_digests,
        receipt_digests=valid.receipt_digests,
        engine="Unreal",
        engine_version=valid.engine_version,
        metadata=valid.metadata,
        manifest_version=valid.manifest_version,
    )
    with pytest.raises(ProductionArtifactError, match="Blender lineage engine is invalid"):
        verify_blender_closed_loop_lineage(invalid, receipt, evidence)


def test_blender_manifest_factory_rejects_unreal_engine():
    receipt, evidence = _verified_blender_pair()
    with pytest.raises(ProductionArtifactError, match="Blender artifact lineage engine must be Blender"):
        ProductionArtifactManifest.from_blender_closed_loop(
            artifact_id="blender-goal-v002",
            canonical_digital_twin_id="soccer-twin-001",
            representation_type="blender-scene",
            artifact_path="production/goal_scene.blend",
            operation_receipt=receipt,
            persistence_evidence=evidence,
            engine="Unreal",
        )


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
    with pytest.raises(ProductionArtifactError, match="operation arguments do not match"):
        verify_blender_closed_loop_lineage(manifest, replacement, evidence)


def test_closed_loop_lineage_verification_rejects_evidence_substitution():
    receipt, evidence = _verified_blender_pair()
    manifest = _closed_loop_manifest(receipt, evidence)
    evidence_snapshot = evidence.snapshot()
    evidence_snapshot["operation_arguments_digest"] = "substituted-operation-arguments-digest"
    replacement = BlenderPersistenceEvidence.from_snapshot(evidence_snapshot)
    with pytest.raises(ProductionArtifactError, match="operation arguments do not match"):
        verify_blender_closed_loop_lineage(manifest, receipt, replacement)


def test_closed_loop_lineage_verification_rejects_cross_operation_pair():
    receipt, evidence = _verified_blender_pair()
    manifest = _closed_loop_manifest(receipt, evidence)
    evidence_snapshot = evidence.snapshot()
    evidence_snapshot["operation_tool"] = "rotate_object"
    replacement = BlenderPersistenceEvidence.from_snapshot(evidence_snapshot)
    with pytest.raises(ProductionArtifactError, match="operation tools"):
        verify_blender_closed_loop_lineage(manifest, receipt, replacement)


def test_manifest_rejects_unverified_blender_inputs():
    receipt, _ = _verified_blender_pair()
    with pytest.raises(TypeError, match="BlenderPersistenceEvidence"):
        ProductionArtifactManifest.from_blender_closed_loop(
            artifact_id="blender-goal-v002",
            canonical_digital_twin_id="soccer-twin-001",
            representation_type="blender-scene",
            artifact_path="production/goal_scene.blend",
            operation_receipt=receipt,
            persistence_evidence=object(),
        )


def test_manifest_digest_is_deterministic():
    first = ProductionArtifactManifest.from_snapshot(VALID)
    second = ProductionArtifactManifest.from_snapshot(copy.deepcopy(VALID))
    assert first.digest() == second.digest()


def test_manifest_round_trip_preserves_lineage():
    manifest = ProductionArtifactManifest.from_snapshot(VALID)
    restored = ProductionArtifactManifest.from_snapshot(manifest.snapshot())
    assert restored.snapshot() == manifest.snapshot()
    assert restored.digest() == manifest.digest()


def test_manifest_is_deeply_immutable():
    manifest = ProductionArtifactManifest.from_snapshot(VALID)
    digest = manifest.digest()

    with pytest.raises(TypeError):
        manifest.metadata["stage"] = "tampered"
    with pytest.raises(TypeError):
        manifest.workflow_provenance["parameters"]["file_name"] = "tampered.blend"

    assert manifest.digest() == digest


def test_manifest_defensively_copies_nested_input_mappings():
    source = copy.deepcopy(VALID)
    manifest = ProductionArtifactManifest.from_snapshot(source)
    digest = manifest.digest()

    source["metadata"]["stage"] = "tampered"
    source["workflow_provenance"]["parameters"]["file_name"] = "tampered.blend"

    assert manifest.snapshot()["metadata"]["stage"] == "cleanup"
    assert manifest.snapshot()["workflow_provenance"]["parameters"]["file_name"] == "scene.blend"
    assert manifest.digest() == digest


def test_manifest_lineage_reference_changes_when_persisted_evidence_changes():
    receipt, evidence = _verified_blender_pair()
    manifest = ProductionArtifactManifest.from_blender_closed_loop(
        artifact_id="blender-goal-v003",
        canonical_digital_twin_id="soccer-twin-001",
        representation_type="blender-scene",
        artifact_path="production/goal_scene.blend",
        operation_receipt=receipt,
        persistence_evidence=evidence,
    )

    evidence_snapshot = evidence.snapshot()
    evidence_snapshot["operation_arguments_digest"] = "tampered-operation-arguments-digest"
    tampered_evidence = BlenderPersistenceEvidence.from_snapshot(evidence_snapshot)

    assert tampered_evidence.digest() != manifest.evidence_digests[0]
    assert manifest.evidence_digests == (evidence.digest(),)


def test_manifest_rejects_unknown_persisted_fields():
    snapshot = copy.deepcopy(VALID)
    snapshot["authorization"] = "atlas-issued"
    with pytest.raises(ProductionArtifactError, match="fields are invalid"):
        ProductionArtifactManifest.from_snapshot(snapshot)


def test_manifest_rejects_self_reference():
    snapshot = copy.deepcopy(VALID)
    snapshot["source_artifact_ids"] = [snapshot["artifact_id"]]
    with pytest.raises(ProductionArtifactError, match="cannot reference itself"):
        ProductionArtifactManifest.from_snapshot(snapshot)


def test_manifest_rejects_duplicate_source_ids():
    snapshot = copy.deepcopy(VALID)
    snapshot["source_artifact_ids"] = ["source-1", "source-1"]
    with pytest.raises(ProductionArtifactError, match="unique values"):
        ProductionArtifactManifest.from_snapshot(snapshot)


def test_manifest_rejects_malformed_persisted_sequence_fields():
    for field in ("source_artifact_ids", "evidence_digests", "receipt_digests"):
        snapshot = copy.deepcopy(VALID)
        snapshot[field] = "not-a-sequence"
        with pytest.raises(ProductionArtifactError, match="list or tuple"):
            ProductionArtifactManifest.from_snapshot(snapshot)


def test_manifest_does_not_expose_execution_or_authorization():
    manifest = ProductionArtifactManifest.from_snapshot(VALID)
    assert not hasattr(manifest, "execute")
    assert not hasattr(manifest, "authorize")
    assert not hasattr(manifest, "run")
