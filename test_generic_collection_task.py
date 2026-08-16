from action_plan import ActionSpec
from planning.future_generator import DeterministicFutureGenerator
from planning.target_state import StateInvariant, TargetStateEvaluator


def test_second_task_uses_generic_target_evaluation():
    evaluator = TargetStateEvaluator([
        StateInvariant("target_collection_exists", lambda e: "Atlas_Test" in e.get("collections", [])),
    ])
    satisfied = evaluator.evaluate({"collections": ["Scene", "Atlas_Test"]})
    unsatisfied = evaluator.evaluate({"collections": ["Scene"]})
    assert satisfied.satisfied is True
    assert unsatisfied.satisfied is False


def test_second_task_has_distinct_future_shape():
    evaluator = TargetStateEvaluator([
        StateInvariant("target_collection_exists", lambda e: "Atlas_Test" in e.get("collections", [])),
    ])
    actions = [ActionSpec("create_collection", {"file_name": "collection_task_INCORRECT.blend", "collection_name": "Atlas_Test"}, "create-atlas-test")]
    future = DeterministicFutureGenerator(evaluator).generate(False, actions)
    assert [step.phase for step in future] == ["EVIDENCE", "TARGET", "ACTION", "VERIFICATION", "COMPLETE"]
    assert future[2].action["tool"] == "create_collection"
