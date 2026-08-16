import pytest

from qwen_planning_bridge import build_proposal_from_qwen, extract_task_plan_proposal
from task_planner import TaskPlanValidationError


def _text():
    return '''Reasoning text\nATLAS_TASK_PLAN: {"evidence": [{"tool": "inspect_scene", "arguments": {"file_name": "scene.blend"}, "name": "scene"}], "actions": [{"tool": "move_object", "arguments": {"file_name": "scene.blend", "object_name": "Goal_Left_post", "location": [1, 2, 3]}, "name": "move"}]}\n'''


def _raw_json_text():
    return '{"evidence": [{"tool": "inspect_scene", "arguments": {"file_name": "scene.blend"}, "name": "scene"}], "actions": []}'


def test_extracts_marked_json_plan():
    proposal = extract_task_plan_proposal(_text())
    assert proposal is not None
    assert proposal["actions"][0]["tool"] == "move_object"


def test_extracts_strict_raw_json_plan():
    proposal = extract_task_plan_proposal(_raw_json_text())
    assert proposal is not None
    assert proposal["evidence"][0]["tool"] == "inspect_scene"


def test_ignores_unmarked_non_json_model_text():
    assert extract_task_plan_proposal("here is the plan") is None


def test_invalid_json_is_ignored():
    assert extract_task_plan_proposal("ATLAS_TASK_PLAN: {not-json}") is None


def test_raw_unrelated_json_is_ignored():
    assert extract_task_plan_proposal('{"request_type": "evidence_request"}') is None


def test_valid_proposal_becomes_inert_planning_state():
    proposal = build_proposal_from_qwen(
        _text(),
        allowed_tools={"inspect_scene", "move_object"},
    )
    assert proposal is not None
    assert proposal.actions[0].tool == "move_object"
    assert proposal.actions[0].arguments["location"] == [1, 2, 3]


def test_disallowed_tool_is_rejected_before_planning():
    with pytest.raises(TaskPlanValidationError):
        build_proposal_from_qwen(
            _text(),
            allowed_tools={"inspect_scene"},
        )


def test_empty_content_has_no_plan():
    assert build_proposal_from_qwen("") is None
