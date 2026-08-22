from planning.object_move_task import (
    TARGET_LOCATION,
    TARGET_OBJECT,
    object_move_task_definition,
)


def test_object_move_task_is_write_capable_and_verifiable():
    task = object_move_task_definition("move.blend")
    assert task.name == "object_move"
    assert task.allow_writes is True
    assert task.verify_after_action is True
    assert task.allowed_action_tools == {"move_object"}
    assert task.actions[0].arguments == {
        "file_name": "move.blend",
        "object_name": TARGET_OBJECT,
        "location": TARGET_LOCATION,
    }


def test_object_move_target_evaluator_rejects_wrong_location():
    evaluator = object_move_task_definition("move.blend").evaluator
    result = evaluator.evaluate({"object_name": TARGET_OBJECT, "location": [0.0, 0.0, 0.0]})
    assert not result.satisfied


def test_object_move_target_evaluator_accepts_exact_location():
    evaluator = object_move_task_definition("move.blend").evaluator
    result = evaluator.evaluate({"object_name": TARGET_OBJECT, "location": TARGET_LOCATION})
    assert result.satisfied
