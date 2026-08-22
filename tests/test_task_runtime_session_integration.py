from planning.marker_task import marker_task_definition
from planning.object_rotation_task import object_rotation_task_definition
from planning.task_runtime import TaskRuntimeSession


def test_rotation_and_marker_use_same_generic_session_contract():
    rotation = TaskRuntimeSession(
        object_rotation_task_definition("rotation.blend"),
        lambda tool, args: {"tool": tool, "rotation_degrees": [0.0, 0.0, 90.0], "object_name": args["object_name"]},
        lambda evidence: evidence[0],
    )
    marker = TaskRuntimeSession(
        marker_task_definition("marker.blend"),
        lambda tool, args: {"tool": tool, "scene": {"objects": []}, "collections": []},
        lambda evidence: {"scene": evidence[0].get("scene", {}), "collections": evidence[1].get("collections", [])},
    )

    assert rotation.task.metadata["operation"] == "rotation"
    assert marker.task.metadata["operation"] == "marker_creation"
    assert rotation.orchestrator is not marker.orchestrator
    assert rotation.task.verify_after_action and marker.task.verify_after_action
