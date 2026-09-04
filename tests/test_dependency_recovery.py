import pytest

from action_plan import ActionSpec
from planning.action_dependencies import ActionDependencyError
from planning.future_execution import FutureExecutionController
from planning.future_generator import DeterministicFutureGenerator
from planning.target_state import StateInvariant, TargetStateEvaluator


def _generator():
    return DeterministicFutureGenerator(
        TargetStateEvaluator([StateInvariant("ready", lambda evidence: evidence["ready"] is True)])
    )


def _steps(actions, inherited=()):
    return _generator().generate(False, actions, satisfied_dependencies=inherited)


def test_inherited_dependency_is_accepted_only_when_explicitly_proven():
    actions = [ActionSpec("rotate", {}, "prepare_rotation", depends_on=("prepare_location",))]
    with pytest.raises(ActionDependencyError, match="unknown action"):
        _steps(actions)
    steps = _steps(actions, ("prepare_location",))
    controller = FutureExecutionController(steps, inherited_dependencies=("prepare_location",))
    controller.acknowledge({"evidence": True})
    controller.acknowledge({"satisfied": False})
    result = controller.execute_current(lambda tool, args: {"ok": True})
    assert result["ok"] is True


def test_inherited_dependency_is_part_of_future_integrity():
    dependent_actions = [ActionSpec("rotate", {}, "prepare_rotation", depends_on=("prepare_location",))]
    independent_actions = [ActionSpec("rotate", {}, "prepare_rotation")]
    first = FutureExecutionController(
        _steps(dependent_actions, ("prepare_location",)),
        inherited_dependencies=("prepare_location",),
    )
    second = FutureExecutionController(
        _steps(independent_actions),
        inherited_dependencies=(),
    )
    assert first.plan_digest != second.plan_digest


def test_inherited_dependency_cannot_be_mutated_after_construction():
    actions = [ActionSpec("rotate", {}, "prepare_rotation", depends_on=("prepare_location",))]
    controller = FutureExecutionController(
        _steps(actions, ("prepare_location",)),
        inherited_dependencies=("prepare_location",),
    )
    controller.inherited_dependencies = ("other",)
    with pytest.raises(RuntimeError, match="Future plan integrity check failed"):
        controller.snapshot()
