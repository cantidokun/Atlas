import pytest

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.production_artifact import (
    ProductionArtifactManifest,
    verify_blender_closed_loop_lineage,
)


def test_real_boundary_closed_loop_constructs_and_verifies_production_artifact():
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
                        {
                            "name": "Goal_Left_post",
                            "location": list(location),
                        }
                    ]
                },
            }
        raise AssertionError("unexpected Blender tool")

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
        artifact_id="blender-goal-v004",
        canonical_digital_twin_id="soccer-twin-001",
        representation_type="blender-scene",
        artifact_path="production/scene.blend",
        operation_receipt=closed_loop.operation_receipt,
        persistence_evidence=closed_loop.persistence_evidence,
        workflow_provenance={
            "name": "broadcast-goal-preparation",
            "version": 1,
        },
        source_artifact_ids=("photogrammetry-reconstruction-v004",),
        engine_version="4.4",
    )

    verify_blender_closed_loop_lineage(
        manifest,
        closed_loop.operation_receipt,
        closed_loop.persistence_evidence,
    )

    restored = ProductionArtifactManifest.from_snapshot(manifest.snapshot())
    assert restored.digest() == manifest.digest()
    assert restored.canonical_digital_twin_id == "soccer-twin-001"
    assert restored.artifact_path == "production/scene.blend"
    assert restored.evidence_digests == (closed_loop.persistence_evidence.digest(),)
    assert restored.receipt_digests == (closed_loop.operation_receipt.digest(),)
    assert [tool for tool, _ in calls] == ["move_object", "inspect_scene"]


def test_production_artifact_manifest_does_not_execute_or_verify_blender_again():
    calls = []

    def executor(tool, arguments):
        calls.append(tool)
        if tool == "move_object":
            return {
                "ok": True,
                "state": "moved",
                "details": {"location": [0.25, 5.233, 0.0]},
            }
        return {
            "ok": True,
            "state": "inspected",
            "details": {
                "objects": [
                    {"name": "Goal_Left_post", "location": [0.25, 5.233, 0.0]}
                ]
            },
        }

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
        artifact_id="blender-goal-v005",
        canonical_digital_twin_id="soccer-twin-001",
        representation_type="blender-scene",
        artifact_path="production/scene.blend",
        operation_receipt=closed_loop.operation_receipt,
        persistence_evidence=closed_loop.persistence_evidence,
    )
    digest = manifest.digest()

    verify_blender_closed_loop_lineage(
        manifest,
        closed_loop.operation_receipt,
        closed_loop.persistence_evidence,
    )

    assert manifest.digest() == digest
    assert calls == ["move_object", "inspect_scene"]
    assert not hasattr(manifest, "execute")
    assert not hasattr(manifest, "authorize")
    assert not hasattr(manifest, "run")
