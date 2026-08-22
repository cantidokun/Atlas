import pytest

from planning.blender_reasoning_contract import (
    BlenderReasoningContractError,
    normalize_model_reasoning,
)


def payload():
    return {
        "task_id": "qwen-001",
        "objective": "Correct the scene alignment.",
        "observations": [{"object": "Goal_Left_post", "rotation_error": 2.0}],
        "diagnosis": "The goal post rotation is outside tolerance.",
        "confidence": 0.94,
        "proposed_actions": [
            {"tool": "inspect_object_transform", "arguments": {"file_name": "scene.blend", "object_name": "Goal_Left_post"}}
        ],
        "success_criteria": ["rotation is within tolerance"],
    }


def test_normalizes_reasoning_without_granting_execution_authority():
    reasoning = normalize_model_reasoning(payload())
    intent = reasoning.to_intent()

    assert reasoning.confidence == 0.94
    assert intent.objective == "Correct the scene alignment."
    assert intent.actions[0].tool == "inspect_object_transform"
    assert not hasattr(reasoning, "execute")


def test_rejects_missing_structured_fields():
    bad = payload()
    del bad["diagnosis"]
    with pytest.raises(BlenderReasoningContractError, match="diagnosis"):
        normalize_model_reasoning(bad).to_intent()


def test_rejects_non_object_action_arguments():
    bad = payload()
    bad["proposed_actions"][0]["arguments"] = "run arbitrary code"
    with pytest.raises(BlenderReasoningContractError, match="arguments must be an object"):
        normalize_model_reasoning(bad)


def test_rejects_out_of_range_confidence():
    bad = payload()
    bad["confidence"] = 1.5
    with pytest.raises(BlenderReasoningContractError, match="between 0 and 1"):
        normalize_model_reasoning(bad).to_intent()
