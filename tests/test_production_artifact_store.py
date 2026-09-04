import json

import pytest

from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_persistence_evidence import BlenderPersistenceEvidence
from planning.blender_result_contract import BlenderExecutionResult
from planning.production_artifact import ProductionArtifactManifest
from planning.production_artifact_store import (
    ProductionArtifactStore,
    ProductionArtifactStoreError,
)


def _manifest():
    arguments = {
        "file_name": "scene.blend",
        "object_name": "Goal_Left_post",
        "location": [0.25, 5.302, 0.0],
    }
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
    return ProductionArtifactManifest.from_blender_closed_loop(
        artifact_id="blender-goal-v006",
        canonical_digital_twin_id="soccer-twin-001",
        representation_type="blender-scene",
        artifact_path="production/scene.blend",
        operation_receipt=receipt,
        persistence_evidence=evidence,
        workflow_provenance={"name": "broadcast-goal-preparation", "version": 1},
        source_artifact_ids=("photogrammetry-reconstruction-v004",),
        engine_version="4.4",
    )


def test_store_round_trip_preserves_manifest_integrity(tmp_path):
    manifest = _manifest()
    store = ProductionArtifactStore(str(tmp_path / "artifact.json"))

    store.save(manifest)
    restored = store.load()

    assert restored.snapshot() == manifest.snapshot()
    assert restored.digest() == manifest.digest()


def test_store_is_deterministic_for_same_manifest(tmp_path):
    manifest = _manifest()
    first = ProductionArtifactStore(str(tmp_path / "first.json"))
    second = ProductionArtifactStore(str(tmp_path / "second.json"))

    first.save(manifest)
    second.save(manifest)

    assert (tmp_path / "first.json").read_bytes() == (tmp_path / "second.json").read_bytes()


def test_store_rejects_unknown_envelope_fields(tmp_path):
    path = tmp_path / "artifact.json"
    store = ProductionArtifactStore(str(path))
    store.save(_manifest())

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["authorization"] = "atlas-issued"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProductionArtifactStoreError, match="store fields are invalid"):
        store.load()


def test_store_rejects_manifest_digest_tampering(tmp_path):
    path = tmp_path / "artifact.json"
    store = ProductionArtifactStore(str(path))
    store.save(_manifest())

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["manifest"]["artifact_path"] = "production/tampered.blend"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProductionArtifactStoreError, match="integrity check failed"):
        store.load()


def test_store_rejects_manifest_digest_substitution(tmp_path):
    path = tmp_path / "artifact.json"
    store = ProductionArtifactStore(str(path))
    store.save(_manifest())

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["manifest_digest"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProductionArtifactStoreError, match="integrity check failed"):
        store.load()


def test_store_rejects_unsupported_version(tmp_path):
    path = tmp_path / "artifact.json"
    store = ProductionArtifactStore(str(path))
    store.save(_manifest())

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["store_version"] = 99
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProductionArtifactStoreError, match="version is unsupported"):
        store.load()


def test_store_does_not_mutate_manifest(tmp_path):
    manifest = _manifest()
    digest = manifest.digest()
    store = ProductionArtifactStore(str(tmp_path / "artifact.json"))

    store.save(manifest)

    assert manifest.digest() == digest
    assert not hasattr(store, "execute")
    assert not hasattr(store, "authorize")
