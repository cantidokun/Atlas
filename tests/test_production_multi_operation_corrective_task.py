from action_plan import ActionSpec
from planning.production_multi_operation_corrective_task import ProductionMultiOperationCorrectiveTask


class RecordingExecutor:
    def __init__(self, state):
        self.state = state
        self.calls = []

    def __call__(self, tool, arguments):
        self.calls.append((tool, dict(arguments)))
        if tool == "move_object":
            self.state["location"] = list(arguments["location"])
        elif tool == "set_object_rotation":
            self.state["rotation"] = list(arguments["rotation"])
        return {
            "ok": True,
            "state": "applied",
            "details": dict(arguments),
        }


def test_composes_two_verified_write_capabilities_through_one_runtime():
    state = {"location": [0, 0, 0], "rotation": [0, 0, 0]}
    executor = RecordingExecutor(state)

    def observe():
        return {
            "location": list(state["location"]),
            "rotation": list(state["rotation"]),
        }

    def plan(evidence):
        actions = []
        if evidence["location"] != [1, 2, 3]:
            actions.append(
                ActionSpec(
                    tool="move_object",
                    arguments={
                        "file_name": "scene.blend",
                        "object_name": "Cube",
                        "location": [1, 2, 3],
                    },
                )
            )
        if evidence["rotation"] != [10, 20, 30]:
            actions.append(
                ActionSpec(
                    tool="set_object_rotation",
                    arguments={
                        "file_name": "scene.blend",
                        "object_name": "Cube",
                        "rotation": [10, 20, 30],
                    },
                )
            )
        return actions

    task = ProductionMultiOperationCorrectiveTask(
        observe,
        plan,
        "test:production-composition",
        executor=executor,
    )
    result = task.run(max_steps=4)

    assert result.converged
    assert [tool for tool, _ in executor.calls] == [
        "move_object",
        "set_object_rotation",
    ]
    assert state == {"location": [1, 2, 3], "rotation": [10, 20, 30]}
    assert len(result.receipts) == 2


def test_composition_replans_after_world_interruption_between_operations():
    state = {"location": [0, 0, 0], "rotation": [0, 0, 0]}

    class InterruptingExecutor:
        def __init__(self):
            self.calls = []
            self.authorizations = []

        def execute_authorized_replan(self, replan, evidence):
            action = replan.actions[0]
            self.calls.append(action.tool)
            self.authorizations.append(replan.authorization)
            if action.tool == "move_object":
                state["location"] = list(action.arguments["location"])
                state["rotation"] = [99, 98, 97]
            elif action.tool == "set_object_rotation":
                state["rotation"] = list(action.arguments["rotation"])
            result = {
                "ok": True,
                "state": "applied",
                "details": dict(action.arguments),
            }
            return result, None

    executor = InterruptingExecutor()

    def observe():
        return {
            "location": list(state["location"]),
            "rotation": list(state["rotation"]),
        }

    def plan(evidence):
        if evidence["location"] != [1, 2, 3]:
            return [
                ActionSpec(
                    tool="move_object",
                    arguments={
                        "file_name": "scene.blend",
                        "object_name": "Cube",
                        "location": [1, 2, 3],
                    },
                )
            ]
        if evidence["rotation"] != [10, 20, 30]:
            return [
                ActionSpec(
                    tool="set_object_rotation",
                    arguments={
                        "file_name": "scene.blend",
                        "object_name": "Cube",
                        "rotation": [10, 20, 30],
                    },
                )
            ]
        return []

    task = ProductionMultiOperationCorrectiveTask(
        observe,
        plan,
        "test:production-interruption",
        executor=executor,
    )
    result = task.run(max_steps=4)

    assert result.converged
    assert executor.calls == ["move_object", "set_object_rotation"]
    assert len(executor.authorizations) == 2
    assert executor.authorizations[0].evidence_digest != executor.authorizations[1].evidence_digest
    assert state == {"location": [1, 2, 3], "rotation": [10, 20, 30]}
    assert len(result.receipts) == 2


def test_composition_rejects_non_production_test_capabilities():
    state = {"value": 0}

    def observe():
        return dict(state)

    def plan(_evidence):
        return [ActionSpec(tool="set_value", arguments={"value": 1})]

    task = ProductionMultiOperationCorrectiveTask(
        observe,
        plan,
        "test:production-capability-boundary",
        executor=lambda tool, arguments: {"ok": True, "state": "applied", "details": arguments},
    )

    try:
        task.run(max_steps=1)
    except ValueError as exc:
        assert "verified Blender write capability" in str(exc)
    else:
        raise AssertionError("synthetic set_value must not enter production composition")


def test_composition_rejects_stale_authorization_with_zero_writes():
    from planning.blender_execution_boundary import BlenderExecutionBoundary
    from planning.replan_authorization import ReplanAuthorization

    writes = []
    boundary = BlenderExecutionBoundary(
        lambda tool, arguments: writes.append((tool, dict(arguments))) or {
            "status": "applied",
            "details": dict(arguments),
        }
    )
    evidence_v1 = {"location": [0, 0, 0], "rotation": [0, 0, 0]}
    evidence_v2 = {"location": [1, 2, 3], "rotation": [99, 98, 97]}
    action = ActionSpec(
        tool="set_object_rotation",
        arguments={
            "file_name": "scene.blend",
            "object_name": "Cube",
            "rotation": [10, 20, 30],
        },
    )
    authorization_v1 = ReplanAuthorization.issue(evidence_v1, [action], "test:stale-composition")
    replan = type("Replan", (), {"actions": [action], "authorization": authorization_v1})()

    try:
        boundary.execute_authorized_replan(replan, evidence_v2)
    except RuntimeError as exc:
        assert "stale" in str(exc)
    else:
        raise AssertionError("stale production composition authorization unexpectedly executed")

    assert writes == []
