import pytest

from planning.digital_twin_representation import (
    ProductionTool,
    RepresentationState,
    TwinRepresentation,
    create_representation_contract,
    mark_representation_state,
)


def test_representation_contract_is_engine_neutral():
    representation = create_representation_contract(
        twin_id="field-001",
        representation_id="field-001-blender-r2",
        source_revision_id="field-001-r2",
        production_tool=ProductionTool.BLENDER,
        external_id="scene://field-001",
        source_fingerprint="abc123",
    )
    assert representation.twin_id == "field-001"
    assert representation.source_revision_id == "field-001-r2"
    assert representation.state is RepresentationState.CREATED


def test_representation_requires_external_identity():
    with pytest.raises(ValueError, match="external_id"):
        create_representation_contract(
            "field-001",
            "field-001-unreal-r1",
            "field-001-r2",
            ProductionTool.UNREAL,
            "   ",
        )


def test_representation_state_update_is_immutable():
    original = TwinRepresentation(
        "field-001",
        "field-001-unreal-r1",
        "field-001-r2",
        ProductionTool.UNREAL,
        "actor://FieldRoot",
    )
    updated = mark_representation_state(original, RepresentationState.VERIFIED)
    assert original.state is RepresentationState.CREATED
    assert updated.state is RepresentationState.VERIFIED
    assert updated.external_id == original.external_id


def test_tool_side_representation_is_never_marked_canonical_here():
    representation = create_representation_contract(
        "field-001",
        "field-001-unreal-r1",
        "field-001-r2",
        ProductionTool.UNREAL,
        "actor://FieldRoot",
    )
    assert not hasattr(representation, "canonical")
