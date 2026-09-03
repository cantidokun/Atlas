import copy

import pytest

from planning.production_artifact import ProductionArtifactError, ProductionArtifactManifest


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


def test_manifest_binds_artifact_to_canonical_digital_twin():
    manifest = ProductionArtifactManifest.from_snapshot(VALID)
    snapshot = manifest.snapshot()
    assert snapshot["canonical_digital_twin_id"] == "soccer-twin-001"
    assert snapshot["representation_type"] == "blender-scene"
    assert snapshot["source_artifact_ids"] == ["photogrammetry-reconstruction-v004"]
    assert manifest.digest()


def test_manifest_digest_is_deterministic():
    first = ProductionArtifactManifest.from_snapshot(VALID)
    second = ProductionArtifactManifest.from_snapshot(copy.deepcopy(VALID))
    assert first.digest() == second.digest()


def test_manifest_round_trip_preserves_lineage():
    manifest = ProductionArtifactManifest.from_snapshot(VALID)
    restored = ProductionArtifactManifest.from_snapshot(manifest.snapshot())
    assert restored.snapshot() == manifest.snapshot()
    assert restored.digest() == manifest.digest()


def test_manifest_fails_closed_on_digest_tampering():
    manifest = ProductionArtifactManifest.from_snapshot(VALID)
    digest = manifest.digest()
    manifest.metadata["stage"] = "tampered"
    with pytest.raises(ProductionArtifactError, match="integrity check failed"):
        manifest.verify_integrity(digest)


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


def test_manifest_does_not_expose_execution_or_authorization():
    manifest = ProductionArtifactManifest.from_snapshot(VALID)
    assert not hasattr(manifest, "execute")
    assert not hasattr(manifest, "authorize")
    assert not hasattr(manifest, "run")
