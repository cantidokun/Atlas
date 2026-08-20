from controller_bridge import ControllerBridge
from controller_session import make_instruction


BEFORE = {
    "object_a": {
        "name": "Goal_Left_post",
        "location": [0.0, 5.44, 0.0],
    },
    "object_b": {
        "name": "Goal_Right_Post",
        "location": [0.0, -5.164, 0.0],
    },
    "midpoint": [0.0, 0.138, 0.0],
}

AFTER = {
    "object_a": {
        "name": "Goal_Left_post",
        "location": [0.0, 5.302, 0.0],
    },
    "object_b": {
        "name": "Goal_Right_Post",
        "location": [0.0, -5.302, 0.0],
    },
    "midpoint": [0.0, 0.0, 0.0],
}


def test_bridge_drives_authorized_workflow_without_human_relay():
    calls = []

    def execute(tool, arguments):
        calls.append((tool, arguments))
        if tool == "inspect_object_relationship":
            return BEFORE if len(calls) == 1 else AFTER
        if tool == "move_object":
            return {
                "status": "moved",
                "object_name": arguments["object_name"],
                "location": arguments["location"],
            }
        raise AssertionError(tool)

    bridge = ControllerBridge(execute)
    response = bridge.receive(make_instruction({"file_name": "goalpost_test.blend"}))

    assert response["status"] == "complete"
    assert response["phase"] == "COMPLETE"
    assert len(calls) == 4
    assert [call[0] for call in calls] == [
        "inspect_object_relationship",
        "move_object",
        "move_object",
        "inspect_object_relationship",
    ]


def test_bridge_rejects_missing_file_name():
    bridge = ControllerBridge(lambda tool, arguments: {})
    instruction = make_instruction({})

    response = bridge.receive(instruction)

    assert response["status"] == "error"
    assert response["error"]["code"] == "invalid_payload"


def test_bridge_has_bounded_execution():
    def never_finish(tool, arguments):
        if tool == "inspect_object_relationship":
            return BEFORE
        return {"status": "moved", "object_name": arguments["object_name"], "location": arguments["location"]}

    bridge = ControllerBridge(never_finish, max_steps=1)
    response = bridge.receive(make_instruction({"file_name": "goalpost_test.blend"}))

    assert response["status"] == "error"
    assert response["error"]["code"] == "step_limit_exceeded"
