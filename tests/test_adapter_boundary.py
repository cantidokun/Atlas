from planning.digital_twin_adapter_contract import is_stale
from planning.digital_twin_intake import create_reconstruction_intake
from planning.digital_twin_representation import ProductionTool, create_representation_contract


def test_canonical_to_representation_boundary():
    intake = create_reconstruction_intake(
        "intake-001", "field-001", "capture-001", "photogrammetry", "recon-001"
    )
    representation = create_representation_contract(
        "field-001", "field-001-blender-r1", "field-001-r1", ProductionTool.BLENDER, "scene://field-001"
    )
    assert intake.twin_candidate_id == representation.twin_id
    assert not is_stale(representation, "field-001-r1")
