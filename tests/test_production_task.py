import pytest

from action_plan import ActionSpec
from evidence_plan import EvidenceRequest
from planning.production_task import ProductionTaskDefinition
from planning.target_state import StateInvariant, TargetStateEvaluator


def _production_task():
    evaluator = TargetStateEvaluator([
        StateInvariant("ready", lambda evidence: evidence["ready"] is True),
    ])
    return ProductionTaskDefinition(
        name="prepare-broadcast-goal",
        objective="Prepare the soccer goal for a broadcast shot.",
        evidence=(EvidenceRequest("inspect_scene", {"file_name": "scene.blend"}, "scene"),),
        actions=(
            ActionSpec("move_object", {"location": [1, 2, 3]}, "position_goal"),
            ActionSpec(
                "set_object_rotation",
                {"rotation_degrees": [0, 0, 15]},
                "orient_goal",
                depends_on=("position_goal",),
            ),
        ),
        evaluator=evaluator,
        allowed_action_tools=("move_object", "set_object_rotation"),
        metadata={"domain": "soccer-production"},
    )


def test_production_task_compiles_to_existing_task_contract():
    task = _production_task().compile()

    assert task.name == "prepare-broadcast-goal"
    assert task.allow_writes is True
    assert task.actions[1].dependency_names() == ("position_goal",)
    assert task.allowed_action_tools == {"move_object", "set_object_rotation"}
    assert task.metadata["production_task"] == "prepare-broadcast-goal"
    assert task.metadata["objective"] == "Prepare the soccer goal for a broadcast shot."


def test_production_task_rejects_empty_objective():
    task = _production_task()
    with pytest.raises(ValueError, match="objective"):
        ProductionTaskDefinition(
            name=task.name,
            objective="",
            evidence=task.evidence,
            actions=task.actions,
            evaluator=task.evaluator,
            allowed_action_tools=task.allowed_action_tools,
        )


def test_production_task_preserves_dependency_metadata_in_snapshot():
    snapshot = _production_task().snapshot()

    assert snapshot["actions"][1]["depends_on"] == ["position_goal"]
    assert snapshot["metadata"] == {"domain": "soccer-production"}
