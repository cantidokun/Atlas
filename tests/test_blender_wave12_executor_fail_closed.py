from __future__ import annotations

from planning.blender.parent_cycle import (
    CYCLE_CORRECTION_TYPE,
    execute_repair_parent_cycle,
    plan_parent_cycle_correction,
)


def _scene():
    return {
        "objects": [
            {"object_id": "a", "parent_object_id": "b", "name": "a"},
            {"object_id": "b", "parent_object_id": "a", "name": "b"},
        ]
    }


def _auth(plan):
    return {
        "decision": "APPROVED",
        "correction_type": CYCLE_CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": "a" * 64,
        "target_object_id": "a",
        "expected_parent_id": "b",
    }


def test_mutator_exception_is_explicit_non_success():
    scene = _scene()
    plan = plan_parent_cycle_correction(
        scene, "a" * 64, target_object_id="a", expected_parent_id="b"
    )
    calls = []

    def mutate(*args):
        calls.append(args)
        raise RuntimeError("simulated mutator failure")

    result = execute_repair_parent_cycle(
        plan,
        _auth(plan),
        extractor=lambda: (scene, "a" * 64),
        mutator=mutate,
    )

    assert result.ok is False
    assert result.outcome == "MUTATION_FAILED"
    assert result.failure_code == "MUTATOR_EXCEPTION"
    assert calls == [("a", "b", None)]
    assert scene["objects"][0]["parent_object_id"] == "b"
