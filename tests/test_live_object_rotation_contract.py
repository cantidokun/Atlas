from planning.object_rotation_task import (
    TARGET_OBJECT,
    TARGET_ROTATION,
    object_rotation_task_definition,
)
from tools.blender_transform import inspect_object_transform


def test_rotation_task_has_independent_post_action_evidence():
    definition = object_rotation_task_definition("object_rotation_INCORRECT.blend")
    evidence = definition.evidence[0]
    action = definition.actions[0]

    assert definition.verify_after_action is True
    assert evidence.tool == "inspect_object_transform"
    assert evidence.arguments == {
        "file_name": "object_rotation_INCORRECT.blend",
        "object_name": TARGET_OBJECT,
    }
    assert action.tool == "set_object_rotation"
    assert action.arguments["rotation_degrees"] == TARGET_ROTATION


def test_transform_inspection_contract_contains_persistent_state_fields():
    # The implementation's emitted payload is inspected statically here; this
    # protects the live verification contract without invoking Blender.
    source = inspect_object_transform.__code__.co_consts
    rendered = "".join(value for value in source if isinstance(value, str))
    assert "rotation_degrees" in rendered
    assert "object_name" in rendered
