import pytest

from planning.blender_task_planner import BlenderTaskPlanner
from planning.qwen_blender_reasoning import QwenReasoningError, parse_qwen_reasoning, reasoning_to_intent


def valid_payload():
    return {
        "task_id": "qwen-001",
        "objective": "Correct the goal post rotation",
        "observation": "The left goal post is rotated incorrectly",
        "confidence": 0.94,
        "actions": [
            {"tool": "set_object_rotation", "arguments": {"file_name": "scene.blend", "object_name": "Goal_L", "rotation_degrees": [0, 0, 0]}}
        ],
        "success_evidence": ["Goal_L rotation matches target"],
    }


def test_valid_qwen_output_becomes_plannable_intent():
    reasoning = parse_qwen_reasoning(valid_payload())
    intent = reasoning_to_intent(reasoning)
    plan = BlenderTaskPlanner().plan(intent)
    assert reasoning.confidence == 0.94
    assert plan.actions[0].tool == "set_object_rotation"


@pytest.mark.parametrize(
    "field,value",
    [
        ("confidence", 2),
        ("confidence", True),
        ("actions", []),
        ("success_evidence", []),
        ("objective", ""),
    ],
)
def test_invalid_reasoning_is_rejected(field, value):
    payload = valid_payload()
    payload[field] = value
    with pytest.raises(QwenReasoningError):
        parse_qwen_reasoning(payload)


def test_unknown_blender_tool_stays_blocked_by_planner():
    payload = valid_payload()
    payload["actions"] = [{"tool": "execute_arbitrary_python", "arguments": {"code": "print(1)"}}]
    reasoning = parse_qwen_reasoning(payload)
    with pytest.raises(ValueError, match="not registered"):
        BlenderTaskPlanner().plan(reasoning_to_intent(reasoning))


def test_model_cannot_inject_non_object_arguments():
    payload = valid_payload()
    payload["actions"] = [{"tool": "set_object_rotation", "arguments": "arbitrary python"}]
    with pytest.raises(QwenReasoningError, match="arguments"):
        parse_qwen_reasoning(payload)
