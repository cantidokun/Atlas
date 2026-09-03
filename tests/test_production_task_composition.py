import pytest

from action_plan import ActionSpec
from evidence_plan import EvidenceRequest
from planning.production_task_composition import (
    ProductionTaskFragment,
    compose_production_task,
)
from planning.target_state import StateInvariant, TargetStateEvaluator


def _evaluator():
    return TargetStateEvaluator([
        StateInvariant("ready", lambda evidence: evidence["ready"] is True),
    ])


def test_compose_preserves_fragment_and_action_order():
    location = ProductionTaskFragment(
        "position",
        evidence=(EvidenceRequest("inspect_scene", {"file_name": "scene.blend"}, "scene"),),
        actions=(ActionSpec("move_object", {"location": [1, 2, 3]}, "position_goal"),),
    )
    orientation = ProductionTaskFragment(
        "orientation",
        actions=(
            ActionSpec(
                "set_object_rotation",
                {"rotation_degrees": [0, 0, 15]},
                "orient_goal",
                depends_on=("position_goal",),
            ),
        ),
    )

    production = compose_production_task(
        name="prepare-goal",
        objective="Prepare a soccer goal for a broadcast shot.",
        fragments=(location, orientation),
        evaluator=_evaluator(),
        allowed_action_tools=("move_object", "set_object_rotation"),
    )

    assert production.snapshot()["metadata"]["fragments"] == ["position", "orientation"]
    assert [action.name for action in production.actions] == ["position_goal", "orient_goal"]
    assert production.actions[1].dependency_names() == ("position_goal",)
    assert production.compile().actions == production.actions


def test_compose_rejects_duplicate_fragments():
    fragment = ProductionTaskFragment("same")

    with pytest.raises(ValueError, match="duplicate production fragment name"):
        compose_production_task(
            name="duplicate",
            objective="Prepare a soccer production task.",
            fragments=(fragment, fragment),
            evaluator=_evaluator(),
            allowed_action_tools=("move_object",),
        )


def test_compose_validates_dependencies_through_canonical_task_contract():
    fragment = ProductionTaskFragment(
        "broken",
        actions=(ActionSpec("move_object", {}, "orient_goal", depends_on=("missing",)),),
    )

    with pytest.raises(ValueError, match="unknown action"):
        compose_production_task(
            name="broken",
            objective="Prepare a soccer production task.",
            fragments=(fragment,),
            evaluator=_evaluator(),
            allowed_action_tools=("move_object",),
        )
