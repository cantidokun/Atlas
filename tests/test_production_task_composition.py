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
        depends_on=("position",),
    )

    production = compose_production_task(
        name="prepare-goal",
        objective="Prepare a soccer goal for a broadcast shot.",
        fragments=(location, orientation),
        evaluator=_evaluator(),
        allowed_action_tools=("move_object", "set_object_rotation"),
    )

    assert production.snapshot()["metadata"]["fragments"] == ["position", "orientation"]
    assert production.snapshot()["metadata"]["fragment_specs"][1]["depends_on"] == ["position"]
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


def test_compose_rejects_unknown_or_later_fragment_dependency():
    first = ProductionTaskFragment("first")
    later = ProductionTaskFragment("later", depends_on=("first",))
    unknown = ProductionTaskFragment("unknown", depends_on=("missing",))

    with pytest.raises(ValueError, match="unknown or later fragment: first"):
        compose_production_task(
            name="later-first",
            objective="Prepare a soccer production task.",
            fragments=(later, first),
            evaluator=_evaluator(),
            allowed_action_tools=("move_object",),
        )

    with pytest.raises(ValueError, match="unknown or later fragment: missing"):
        compose_production_task(
            name="unknown",
            objective="Prepare a soccer production task.",
            fragments=(unknown,),
            evaluator=_evaluator(),
            allowed_action_tools=("move_object",),
        )


def test_fragment_rejects_self_and_duplicate_dependencies():
    with pytest.raises(ValueError, match="cannot depend on itself"):
        ProductionTaskFragment("self", depends_on=("self",))

    with pytest.raises(ValueError, match="dependencies must be unique"):
        ProductionTaskFragment("duplicate", depends_on=("base", "base"))


def test_compose_validates_dependencies_through_canonical_task_contract():
    fragment = ProductionTaskFragment(
        "broken",
        evidence=(EvidenceRequest("inspect_scene", {"file_name": "scene.blend"}, "scene"),),
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


def test_fragment_semantics_survive_composition():
    fragment = ProductionTaskFragment(
        "lighting-prep",
        evidence=(EvidenceRequest("inspect_scene", {"file_name": "scene.blend"}, "scene"),),
        actions=(ActionSpec("move_object", {"location": [1, 2, 3]}, "set_light_anchor"),),
        deliverables=("broadcast lighting anchor",),
        constraints=("preserve field geometry",),
        metadata={"phase": "look-development"},
    )

    production = compose_production_task(
        name="lighting-task",
        objective="Prepare a soccer lighting anchor.",
        fragments=(fragment,),
        evaluator=_evaluator(),
        allowed_action_tools=("move_object",),
        deliverables=("final scene-ready task",),
        constraints=("verify the resulting state",),
        metadata={"department": "cinematography"},
    )

    snapshot = production.snapshot()
    assert production.deliverables == (
        "final scene-ready task",
        "broadcast lighting anchor",
    )
    assert production.constraints == (
        "verify the resulting state",
        "preserve field geometry",
    )
    assert snapshot["metadata"]["department"] == "cinematography"
    assert snapshot["metadata"]["fragments"] == ["lighting-prep"]
    assert snapshot["metadata"]["fragment_specs"] == [fragment.snapshot()]
