from planning.digital_twin_intake import IntakeState, create_reconstruction_intake
from planning.digital_twin_representation import (
    ProductionTool,
    RepresentationState,
    create_representation_contract,
    mark_representation_state,
)


def test_intake_and_representation_remain_separate_boundaries():
    intake = create_reconstruction_intake(
        "intake-001",
        "field-001",
        "capture-001",
        "PhotogrammetryTool",
        "reconstruction-001",
    )
    representation = create_representation_contract(
        "field-001",
        "field-001-blender-r1",
        "field-001-r1",
        ProductionTool.BLENDER,
        "scene://field-001",
    )

    assert intake.state is IntakeState.RECEIVED
    assert representation.state is RepresentationState.CREATED

    verified = mark_representation_state(representation, RepresentationState.VERIFIED)
    assert verified.state is RepresentationState.VERIFIED
    assert intake.state is IntakeState.RECEIVED
