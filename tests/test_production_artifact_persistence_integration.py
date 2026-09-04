import json

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.production_artifact import (
    ProductionArtifactManifest,
    verify_blender_closed_loop_lineage,
)
from planning.production_artifact_store import ProductionArtifactStore


def test_blender_closed_loop_artifact_survives_durable_persistence_round_trip(tmp_path):
    calls = []
    location = [0.0, 5.233, 0.0]

    def executor(tool, arguments):
        calls.append((tool, dict(arguments)))
        if tool == "move_object":
            location[:] = list(arguments["location"])
            return {
                "ok": True,
                "state": "moved",
                "details": {
                    "object_name": arguments["object_name"],
                    "location": list(location),
                },
            }
        if tool == "inspect_scene":
            return {
                "ok": True,
                "state": "inspected",
                "details": {
                    "objects": [
                        {"name": "Goal_Left_post", "location": list(location)}
                    ]
                },
            }
        raise AssertionError(f"unexpected Blender tool: {tool}")

    boundary = BlenderExecutionBoundary(executor)
    closed_loop = boundary.execute_with_persistence(
        "move_object",
        {
            "file_name": "scene.blend",
            "object_name": "Goal_Left_post",
            "location": [0.25, 5.233, 0.0],
        },
        "inspect_scene",
        {"file_name": "scene.blend"},
        {"Goal_Left_post": [0.25, 5.233, 0.0]},
        lambda result: {
            "Goal_Left_post": result.details["objects"][0]["location"]
        },
    )

    manifest = ProductionArtifactManifest.from_blender_closed_loop(
        artifact_id="blender-goal-v007",
        canonical_digital_twin_id="soccer-twin-001",
        representation_type="blender-scene",
        artifact_path="production/scene.blend",
        operation_receipt=closed_loop.operation_receipt,
        persistence_evidence=closed_loop.persistence_evidence,
        workflow_provenance={"name": "broadcast-goal-preparation", "version": 1},
        source_artifact_ids=("photogrammetry-reconstruction-v004",),
        engine="Blender",
        engine_version="4.4",
    )

    lineage_digest = manifest.digest()
    store = ProductionArtifactStore(str(tmp_path / "artifact.json"))
    store.save(manifest)

    persisted_payload = json.loads((tmp_path / "artifact.json").read_text(encoding="utf-8"))
    assert persisted_payload["manifest_digest"] == lineage_digest

    restored = store.load()
    verify_blender_closed_loop_lineage(
        restored,
        closed_loop.operation_receipt,
        closed_loop.persistence_evidence,
    )

    assert restored.snapshot() == manifest.snapshot()
    assert restored.digest() == lineage_digest
    assert restored.canonical_digital_twin_id == "soccer-twin-001"
    assert restored.artifact_path == "production/scene.blend"
    assert calls == [("move_object", {
        "file_name": "scene.blend",
        "object_name": "Goal_Left_post",
        "location": [0.25, 5.233, 0.0],
    }), ("inspect_scene", {"file_name": "scene.blend"})]


def test_persisted_artifact_rejects_lineage_substitution(tmp_path):
    calls = []
    location = [0.0, 5.233, 0.0]

    def executor(tool, arguments):
        calls.append((tool, dict(arguments)))
        if tool == "move_object":
            location[:] = list(arguments["location"])
            return {
                "ok": True,
                "state": "moved",
                "details": {
                    "object_name": arguments["object_name"],
                    "location": list(location),
                },
            }
        if tool == "inspect_scene":
            return {
                "ok": True,
                "state": "inspected",
                "details": {
                    "objects": [
                        {"name": "Goal_Left_post", "location": list(location)}
                    ]
                },
            }
        raise AssertionError(f"unexpected Blender tool: {tool}")

    boundary = BlenderExecutionBoundary(executor)
    closed_loop = boundary.execute_with_persistence(
        "move_object",
        {"object_name": "Goal_Left_post", "location": [0.25, 5.233, 0.0]},
        "inspect_scene",
        {"file_name": "scene.blend"},
        {"Goal_Left_post": [0.25, 5.233, 0.0]},
        lambda result: {
            "Goal_Left_post": result.details["objects"][0]["location"]
        },
    )
    manifest = ProductionArtifactManifest.from_blender_closed_loop(
        artifact_id="blender-goal-v008",
        canonical_digital_twin_id="soccer-twin-001",
        representation_type="blender-scene",
        artifact_path="production/scene.blend",
        operation_receipt=closed_loop.operation_receipt,
        persistence_evidence=closed_loop.persistence_evidence,
    )
    store = ProductionArtifactStore(str(tmp_path / "artifact.json"))
    store.save(manifest)

    replacement_loop = boundary.execute_with_persistence(
        "move_object",
        {"object_name": "Goal_Left_post", "location": [0.50, 5.233, 0.0]},
        "inspect_scene",
        {"file_name": "scene.blend"},
        {"Goal_Left_post": [0.50, 5.233, 0.0]},
        lambda result: {
            "Goal_Left_post": result.details["objects"][0]["location"]
        },
    )

    restored = store.load()
    try:
        verify_blender_closed_loop_lineage(
            restored,
            replacement_loop.operation_receipt,
            replacement_loop.persistence_evidence,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("persisted artifact accepted unrelated Blender lineage")

    assert restored.digest() == manifest.digest()
    assert calls == [
        ("move_object", {"object_name": "Goal_Left_post", "location": [0.25, 5.233, 0.0]}),
        ("inspect_scene", {"file_name": "scene.blend"}),
        ("move_object", {"object_name": "Goal_Left_post", "location": [0.50, 5.233, 0.0]}),
        ("inspect_scene", {"file_name": "scene.blend"}),
    ]
