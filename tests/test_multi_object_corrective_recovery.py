from action_plan import ActionSpec
from planning.multi_step_corrective_executor import MultiStepCorrectiveExecutor
from planning.blender_execution_boundary import BlenderExecutionBoundary


def _action(tool, name, **arguments):
    return ActionSpec(tool=tool, arguments=arguments, name=name, requires_success=True)


def test_replans_only_the_properties_that_are_wrong_after_interruption():
    state = {
        "A": {"location": [1.0, 0.0, 0.0], "rotation": [0.0, 0.0, 45.0]},
        "B": {"location": [-1.0, 0.0, 0.0], "rotation": [0.0, 0.0, -45.0]},
    }
    target = {
        "A": {"location": [1.0, 0.0, 0.0], "rotation": [0.0, 0.0, 45.0]},
        "B": {"location": [-1.0, 0.0, 0.0], "rotation": [0.0, 0.0, -45.0]},
    }
    writes = []

    def observe():
        return {key: dict(value) for key, value in state.items()}

    def plan(evidence):
        actions = []
        for name in ("A", "B"):
            if evidence[name]["location"] != target[name]["location"]:
                actions.append(_action(
                    "move_object", f"move {name}",
                    file_name="multi_property.blend", object_name=f"Atlas_{name}",
                    location=target[name]["location"],
                ))
            if evidence[name]["rotation"] != target[name]["rotation"]:
                actions.append(_action(
                    "set_object_rotation", f"rotate {name}",
                    file_name="multi_property.blend", object_name=f"Atlas_{name}",
                    rotation_degrees=target[name]["rotation"],
                ))
        return actions

    def execute(tool, arguments):
        writes.append((tool, arguments))
        object_key = arguments["object_name"].split("_")[-1]
        if tool == "move_object":
            state[object_key]["location"] = list(arguments["location"])
        else:
            state[object_key]["rotation"] = list(arguments["rotation_degrees"])
        return {"status": "ok"}

    executor = MultiStepCorrectiveExecutor(
        BlenderExecutionBoundary(execute), observe, plan, "multi-property-test"
    )

    first = executor.execute_all(max_steps=2)
    assert len(first) == 2
    assert len(writes) == 2

    state["B"]["location"] = [99.0, 0.0, 0.0]
    state["B"]["rotation"] = [0.0, 0.0, 99.0]

    rest = executor.execute_all(max_steps=8)
    assert len(rest) == 2
    assert state == target
    assert [entry[0] for entry in writes] == [
        "move_object", "set_object_rotation", "move_object", "set_object_rotation"
    ]


def test_no_actions_when_all_object_properties_are_already_verified():
    state = {"A": {"location": [1.0, 0.0, 0.0], "rotation": [0.0, 0.0, 45.0]}}

    executor = MultiStepCorrectiveExecutor(
        BlenderExecutionBoundary(lambda tool, arguments: {"status": "ok"}),
        lambda: state,
        lambda evidence: [],
        "already-correct",
    )

    assert executor.execute_all(max_steps=4) == []
