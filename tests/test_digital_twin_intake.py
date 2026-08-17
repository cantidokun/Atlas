import pytest

from planning.digital_twin_intake import (
    IntakeState,
    ReconstructionIntake,
    create_reconstruction_intake,
)


def test_photogrammetry_reconstruction_enters_as_external_input():
    intake = create_reconstruction_intake(
        "intake-001",
        "field-001",
        "capture-2026-08",
        "PhotogrammetryTool",
        "reconstruction-001",
        "fp-001",
    )
    assert intake.state is IntakeState.RECEIVED
    assert intake.twin_candidate_id == "field-001"
    assert intake.reconstruction_id == "reconstruction-001"


def test_intake_does_not_have_canonical_revision_semantics():
    intake = ReconstructionIntake(
        "intake-001",
        "field-001",
        "capture-2026-08",
        "PhotogrammetryTool",
        "reconstruction-001",
    )
    assert not hasattr(intake, "revision_id")


def test_intake_requires_source_identity():
    with pytest.raises(ValueError, match="source_id"):
        create_reconstruction_intake(
            "intake-001",
            "field-001",
            "   ",
            "PhotogrammetryTool",
            "reconstruction-001",
        )
