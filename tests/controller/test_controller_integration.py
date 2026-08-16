"""Tests for the live-agent controller integration boundary."""

from controller_integration import AgentControllerIntegration


TASK = (
    "The explicit requirement is that the midpoint between Goal_Left_post "
    "and Goal_Right_Post must be exactly [0.0, 0.0, 0.0]. "
    "You are explicitly authorized to modify the Blender file."
)


BEFORE = {
    "object_a": {"name": "Goal_Left_post", "location": [-3.0, 0.138, 0.0]},
    "object_b": {"name": "Goal_Right_Post", "location": [3.0, 0.138, 0.0]},
    "midpoint": [0.0, 0.138, 0.0],
}


def make_integration():
    evidence = [
        {
            "tool": "inspect_object_relationship",
            "arguments": {
                "file_name": "goalpost_test.blend",
                "object1_name": "Goal_Left_post",
                "object2_name": "Goal_Right_Post",
            },
            "result": BEFORE,
        }
    ]
    history = []
    integration = AgentControllerIntegration(
        "goalpost_test.blend",
        TASK,
        evidence,
        history,
    )
    return integration, evidence, history


def test_python_takes_over_after_before_evidence():
    integration, _, _ = make_integration()

    action = integration.before_model_tool_execution()

    assert action["kind"] == "write"
    assert action["tool"] == "move_object"
    assert action["arguments"]["object_name"] == "Goal_Left_post"


def test_model_is_not_allowed_to_choose_second_move():
    integration, _, _ = make_integration()
    calls = []

    def fake_execute(tool, arguments):
        calls.append((tool, arguments))
        return {"status": "moved"}

    result = integration.execute_forced_action(fake_execute)

    assert result["tool"] == "move_object"
    assert calls[0][1]["object_name"] == "Goal_Left_post"

    next_action = integration.before_model_tool_execution()
    assert next_action["kind"] == "write"
    assert next_action["tool"] == "move_object"
    assert next_action["arguments"]["object_name"] == "Goal_Right_Post"


def test_controller_does_not_complete_after_one_write():
    integration, _, _ = make_integration()

    integration.execute_forced_action(
        lambda tool, arguments: {"status": "moved"}
    )

    assert integration.complete is False


def test_failed_write_does_not_advance_controller():
    integration, _, _ = make_integration()

    result = integration.execute_forced_action(
        lambda tool, arguments: {"error": "write failed"}
    )

    assert result["status"] == "error"
    assert integration.complete is False
