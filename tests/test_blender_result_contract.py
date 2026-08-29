import pytest
from types import MappingProxyType

from planning.blender_result_contract import normalize_blender_result


def test_normalizes_valid_result():
    result = normalize_blender_result("move_object", {"ok": True, "state": "applied", "details": {"object": "Goal_Left_post"}})
    assert result.tool == "move_object"
    assert result.ok is True
    assert result.state == "applied"
    assert result.details == {"object": "Goal_Left_post"}


def test_details_default_to_empty_object():
    result = normalize_blender_result("inspect_object", {"ok": True, "state": "verified"})
    assert result.details == {}


def test_missing_required_result_field_blocks():
    with pytest.raises(ValueError):
        normalize_blender_result("move_object", {"ok": True})


def test_invalid_result_shape_blocks():
    with pytest.raises(TypeError):
        normalize_blender_result("move_object", ["ok"])


def test_invalid_details_blocks():
    with pytest.raises(TypeError):
        normalize_blender_result("move_object", {"ok": True, "state": "applied", "details": []})


def test_result_is_immutable():
    result = normalize_blender_result("move_object", {"ok": False, "state": "blocked"})
    with pytest.raises(Exception):
        result.state = "applied"


def test_legacy_transform_evidence_preserves_full_state():
    raw = {
        "status": "ok",
        "object_name": "Goal_Left_post",
        "location": [1.0, 2.0, 0.0],
        "rotation_degrees": [0.0, 0.0, 0.0],
    }
    result = normalize_blender_result("inspect_object_transform", raw)
    assert result.ok is True
    assert result.state == raw
    assert result.state["location"] == [1.0, 2.0, 0.0]


def test_legacy_transform_not_found_is_failed_evidence_with_state():
    raw = {"status": "object_not_found", "object_name": "Goal_Left_post"}
    result = normalize_blender_result("inspect_object_transform", raw)
    assert result.ok is True
    assert result.state == raw


def test_mapping_state_is_accepted_by_shared_result_contract():
    state = MappingProxyType({
        "status": "ok",
        "object_name": "Goal_Left_post",
        "location": [1.0, 2.0, 0.0],
    })
    result = normalize_blender_result(
        "inspect_object_transform",
        {"ok": True, "state": state},
    )
    assert result.state is state
    assert result.state["location"] == [1.0, 2.0, 0.0]


def test_explicit_mutation_evidence_is_exposed_for_write_results():
    result = normalize_blender_result(
        "delete_object",
        {
            "status": "ok",
            "object_name": "Cleanup_Target",
            "mutation_performed": True,
        },
    )
    assert result.ok is True
    assert result.mutation_performed is True
    assert result.details["mutation_performed"] is True


def test_absent_delete_result_exposes_no_mutation():
    result = normalize_blender_result(
        "delete_object",
        {
            "status": "already_absent",
            "object_name": "Cleanup_Target",
            "mutation_performed": False,
        },
    )
    assert result.ok is True
    assert result.mutation_performed is False


def test_missing_mutation_evidence_remains_unknown_for_compatibility():
    result = normalize_blender_result(
        "move_object",
        {"ok": True, "state": "applied", "details": {"object": "Goal_Left_post"}},
    )
    assert result.mutation_performed is None


def test_invalid_mutation_evidence_is_rejected():
    result = normalize_blender_result(
        "delete_object",
        {
            "status": "ok",
            "object_name": "Cleanup_Target",
            "mutation_performed": "yes",
        },
    )
    with pytest.raises(TypeError, match="result mutation_performed must be boolean"):
        _ = result.mutation_performed
