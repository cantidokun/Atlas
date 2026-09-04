import pytest

from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_persistence_evidence import BlenderPersistenceEvidence
from planning.blender_result_contract import BlenderExecutionResult
from planning.production_artifact import ProductionArtifactError, ProductionArtifactManifest
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_render_receipt import UnrealRenderReceipt


def _blender_pair():
    arguments = {"file_name": "scene.blend", "object_name": "Goal_Left_post", "location": [0.0, 0.0, 0.0]}
    result = BlenderExecutionResult(tool="move_object", ok=True, state="moved", details={"object_name": "Goal_Left_post"})
    inspection = BlenderExecutionResult(tool="inspect_scene", ok=True, state="inspected", details={"Goal_Left_post": {"location": [0.0, 0.0, 0.0]}})
    receipt = BlenderExecutionReceipt.create("move_object", arguments, result)
    evidence = BlenderPersistenceEvidence.create(
        "move_object", arguments, "inspect_scene",
        inspection.details, inspection.details, inspection,
    )
    return receipt, evidence


def _unreal_pair():
    evidence = UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=("FIELD_SURFACE",),
        observed_state={
            "job_id": "job-001",
            "sequence_asset_path": "/Game/Atlas/Sequence",
            "status": "completed",
            "success": True,
            "failed": False,
            "output_files": ["C:/renders/AtlasRender_0001.png"],
        },
        verified=True,
        source="engine-test",
    )
    return UnrealRenderReceipt.issue(evidence), evidence


def test_blender_factory_rejects_non_blender_engine():
    receipt, evidence = _blender_pair()
    with pytest.raises(ProductionArtifactError, match="Blender artifact lineage engine must be Blender"):
        ProductionArtifactManifest.from_blender_closed_loop(
            artifact_id="artifact-001",
            canonical_digital_twin_id="twin-001",
            representation_type="blender-scene",
            artifact_path="scene.blend",
            operation_receipt=receipt,
            persistence_evidence=evidence,
            engine="Unreal",
        )


def test_unreal_factory_rejects_non_unreal_engine():
    receipt, evidence = _unreal_pair()
    with pytest.raises(ProductionArtifactError, match="Unreal artifact lineage engine must be Unreal"):
        ProductionArtifactManifest.from_unreal_render_receipt(
            artifact_id="artifact-001",
            canonical_digital_twin_id="twin-001",
            representation_type="unreal-render",
            artifact_path="C:/renders/AtlasRender_0001.png",
            render_receipt=receipt,
            render_evidence=evidence,
            engine="Blender",
        )
