import pytest

from planning.blender_persistence_evidence import BlenderPersistenceEvidence
from planning.blender_result_contract import BlenderExecutionResult


def _inspection(location):
    return BlenderExecutionResult(
        tool="inspect_scene",
        ok=True,
        state="inspected",
        details={"objects": [{"name": "Goal_Left_post", "location": list(location)}]},
    )


def test_persistence_evidence_binds_operation_and_fresh_state():
    arguments = {
        "file_name": "atlas_live_mutation.blend",
        "object_name": "Goal_Left_post",
        "location": [0.25, 5.302, 0.0],
    }
    expected_state = {"Goal_Left_post": [0.25, 5.302, 0.0]}
    observed_state = {"Goal_Left_post": [0.25, 5.302, 0.0]}
    inspection = _inspection([0.25, 5.302, 0.0])

    evidence = BlenderPersistenceEvidence.create(
        "move_object",
        arguments,
        "inspect_scene",
        expected_state,
        observed_state,
        inspection,
    )

    assert evidence.matches(
        "move_object", arguments, expected_state, observed_state, inspection
    )


def test_persistence_evidence_digest_is_deterministic():
    arguments = {"file_name": "fixture.blend", "object_name": "Goal_Left_post"}
    state = {"Goal_Left_post": [0.25, 0.0, 0.0]}
    inspection = _inspection([0.25, 0.0, 0.0])
    evidence = BlenderPersistenceEvidence.create(
        "move_object", arguments, "inspect_scene", state, state, inspection
    )

    assert evidence.digest() == evidence.digest()
    assert evidence.digest() == BlenderPersistenceEvidence.from_snapshot(evidence.snapshot()).digest()


def test_persistence_evidence_snapshot_round_trip_is_equal():
    arguments = {"file_name": "fixture.blend", "object_name": "Goal_Left_post"}
    state = {"Goal_Left_post": [0.25, 0.0, 0.0]}
    evidence = BlenderPersistenceEvidence.create(
        "move_object", arguments, "inspect_scene", state, state, _inspection([0.25, 0.0, 0.0])
    )

    restored = BlenderPersistenceEvidence.from_snapshot(evidence.snapshot())
    assert restored == evidence
    restored.verify_integrity(evidence.digest())


def test_persistence_evidence_snapshot_rejects_unknown_fields():
    arguments = {"file_name": "fixture.blend"}
    state = {"Goal_Left_post": [0.0, 0.0, 0.0]}
    evidence = BlenderPersistenceEvidence.create(
        "move_object", arguments, "inspect_scene", state, state, _inspection([0.0, 0.0, 0.0])
    )
    snapshot = evidence.snapshot()
    snapshot["unexpected"] = True

    with pytest.raises(ValueError, match="fields are invalid"):
        BlenderPersistenceEvidence.from_snapshot(snapshot)


def test_persistence_evidence_snapshot_rejects_mismatched_state_digests():
    arguments = {"file_name": "fixture.blend"}
    state = {"Goal_Left_post": [0.0, 0.0, 0.0]}
    evidence = BlenderPersistenceEvidence.create(
        "move_object", arguments, "inspect_scene", state, state, _inspection([0.0, 0.0, 0.0])
    )
    snapshot = evidence.snapshot()
    snapshot["observed_state_digest"] = "tampered"

    with pytest.raises(ValueError, match="state digests must match"):
        BlenderPersistenceEvidence.from_snapshot(snapshot)


def test_persistence_evidence_rejects_different_observed_state():
    arguments = {
        "file_name": "fixture.blend",
        "object_name": "Goal_Left_post",
        "location": [0.25, 0.0, 0.0],
    }
    expected_state = {"Goal_Left_post": [0.25, 0.0, 0.0]}
    observed_state = {"Goal_Left_post": [0.25, 0.0, 0.0]}
    inspection = _inspection([0.25, 0.0, 0.0])
    evidence = BlenderPersistenceEvidence.create(
        "move_object", arguments, "inspect_scene", expected_state, observed_state, inspection
    )

    changed_state = {"Goal_Left_post": [0.0, 0.0, 0.0]}
    changed_inspection = _inspection([0.0, 0.0, 0.0])
    assert not evidence.matches(
        "move_object", arguments, expected_state, changed_state, changed_inspection
    )


def test_persistence_evidence_creation_rejects_mismatched_state():
    inspection = _inspection([0.0, 0.0, 0.0])

    with pytest.raises(ValueError, match="expected and observed state to match"):
        BlenderPersistenceEvidence.create(
            "move_object",
            {"file_name": "fixture.blend", "object_name": "Goal_Left_post"},
            "inspect_scene",
            {"Goal_Left_post": [0.25, 0.0, 0.0]},
            {"Goal_Left_post": [0.0, 0.0, 0.0]},
            inspection,
        )


def test_persistence_evidence_requires_successful_inspection():
    inspection = BlenderExecutionResult(
        tool="inspect_scene",
        ok=False,
        state="failed",
        details={"error": "inspection failed"},
    )

    with pytest.raises(ValueError, match="successful inspection"):
        BlenderPersistenceEvidence.create(
            "move_object",
            {"file_name": "fixture.blend"},
            "inspect_scene",
            {},
            {},
            inspection,
        )
