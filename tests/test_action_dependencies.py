import pytest

from action_plan import ActionSpec
from planning.action_authorization import ActionAuthorization
from planning.action_dependencies import ActionDependencyError, validate_action_dependencies
from planning.future_generator import DeterministicFutureGenerator
from planning.target_state import StateInvariant, TargetStateEvaluator


def _generator():
    return DeterministicFutureGenerator(
        TargetStateEvaluator([StateInvariant("ready", lambda evidence: evidence["ready"] is True)])
    )


def _valid_actions():
    return [
        ActionSpec("create_mesh", {}, "create_mesh"),
        ActionSpec("clean_mesh", {}, "clean_mesh", depends_on=("create_mesh",)),
        ActionSpec("prepare_render", {}, "prepare_render", depends_on=("clean_mesh",)),
    ]


def test_dependencies_are_explicit_and_preserve_serial_order():
    actions = _valid_actions()
    validate_action_dependencies(actions)
    steps = _generator().generate(False, actions)
    assert [step.action["name"] for step in steps if step.action] == [
        "create_mesh",
        "clean_mesh",
        "prepare_render",
    ]
    assert steps[3].action["depends_on"] == ["create_mesh"]
    assert steps[4].action["depends_on"] == ["clean_mesh"]


def test_dependency_on_later_action_is_rejected():
    actions = [
        ActionSpec("clean_mesh", {}, "clean_mesh", depends_on=("prepare_render",)),
        ActionSpec("prepare_render", {}, "prepare_render"),
    ]
    with pytest.raises(ActionDependencyError, match="later action"):
        validate_action_dependencies(actions)


def test_unknown_self_and_duplicate_dependencies_are_rejected():
    with pytest.raises(ActionDependencyError, match="unknown action"):
        validate_action_dependencies([
            ActionSpec("a", {}, "a", depends_on=("missing",)),
        ])
    with pytest.raises(ActionDependencyError, match="cannot depend on itself"):
        validate_action_dependencies([
            ActionSpec("a", {}, "a", depends_on=("a",)),
        ])
    with pytest.raises(ActionDependencyError, match="duplicate dependencies"):
        validate_action_dependencies([
            ActionSpec("a", {}, "a"),
            ActionSpec("b", {}, "b", depends_on=("a", "a")),
        ])


def test_dependency_changes_are_bound_into_action_authorization():
    first = [
        ActionSpec("a", {}, "a"),
        ActionSpec("b", {}, "b", depends_on=("a",)),
    ]
    second = [
        ActionSpec("a", {}, "a"),
        ActionSpec("b", {}, "b", depends_on=()),
    ]
    authorization = ActionAuthorization.issue(first, "dependency-auth")
    assert authorization.matches(first)
    assert not authorization.matches(second)
