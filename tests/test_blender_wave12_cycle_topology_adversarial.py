from __future__ import annotations

import copy

import pytest

from planning.blender.parent_cycle import (
    CYCLE_CORRECTION_TYPE,
    ParentCycleError,
    execute_repair_parent_cycle,
    plan_parent_cycle_correction,
)


_DIGEST = "a" * 64


def _scene(*pairs):
    return {
        "objects": [
            {
                "object_id": object_id,
                "parent_object_id": parent_id,
                "name": f"name-{object_id}",
                "location": [index, 0, 0],
                "rotation": [1, 0, 0, 0],
                "scale": [1, 1, 1],
            }
            for index, (object_id, parent_id) in enumerate(pairs)
        ]
    }


def _auth(plan):
    return {
        "decision": "APPROVED",
        "correction_type": CYCLE_CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": _DIGEST,
        "target_object_id": plan["target_object_id"],
        "expected_parent_id": plan["params"]["expected_parent_id"],
    }


def test_selected_cycle_repair_preserves_preexisting_unrelated_cycle():
    working = _scene(
        ("a", "b"),
        ("b", "a"),
        ("c", "d"),
        ("d", "c"),
        ("tail", "a"),
    )
    plan = plan_parent_cycle_correction(
        working, _DIGEST, target_object_id="a", expected_parent_id="b"
    )
    calls = []

    def mutate(object_id, expected_parent_id, new_parent_id):
        calls.append((object_id, expected_parent_id, new_parent_id))
        for obj in working["objects"]:
            if obj["object_id"] == object_id:
                obj["parent_object_id"] = new_parent_id

    result = execute_repair_parent_cycle(
        plan, _auth(plan), extractor=lambda: (working, _DIGEST), mutator=mutate
    )

    assert result.ok is True
    assert calls == [("a", "b", None)]
    assert working["objects"][0]["parent_object_id"] is None
    assert working["objects"][1]["parent_object_id"] == "a"
    assert working["objects"][2]["parent_object_id"] == "d"
    assert working["objects"][3]["parent_object_id"] == "c"


def test_successfully_applied_plan_cannot_be_replayed():
    working = _scene(("a", "a"))
    plan = plan_parent_cycle_correction(
        working, _DIGEST, target_object_id="a", expected_parent_id="a"
    )
    first = execute_repair_parent_cycle(
        plan,
        _auth(plan),
        extractor=lambda: (working, _DIGEST),
        mutator=lambda object_id, expected_parent_id, new_parent_id: working["objects"][0].update(
            parent_object_id=new_parent_id
        ),
    )
    assert first.ok is True

    calls = []
    second = execute_repair_parent_cycle(
        plan,
        _auth(plan),
        extractor=lambda: (working, _DIGEST),
        mutator=lambda *args: calls.append(args),
    )

    assert second.ok is False
    assert second.outcome == "PLAN_INVALID"
    assert second.failure_code == "EXPECTED_PARENT_MISMATCH"
    assert calls == []


def test_self_cycle_repair_is_exactly_one_edge():
    working = _scene(("a", "a"), ("other", None))
    before = copy.deepcopy(working)
    plan = plan_parent_cycle_correction(
        working, _DIGEST, target_object_id="a", expected_parent_id="a"
    )
    calls = []

    def mutate(object_id, expected_parent_id, new_parent_id):
        calls.append((object_id, expected_parent_id, new_parent_id))
        working["objects"][0]["parent_object_id"] = new_parent_id

    result = execute_repair_parent_cycle(
        plan, _auth(plan), extractor=lambda: (working, _DIGEST), mutator=mutate
    )

    assert result.ok is True
    assert calls == [("a", "a", None)]
    assert working["objects"][0]["parent_object_id"] is None
    assert working["objects"][0]["name"] == before["objects"][0]["name"]
    assert working["objects"][1] == before["objects"][1]


def test_target_tail_into_cycle_is_not_misclassified_as_target_cycle():
    scene = _scene(("tail", "a"), ("a", "b"), ("b", "a"))

    with pytest.raises(ParentCycleError, match="not a member") as exc:
        plan_parent_cycle_correction(
            scene, _DIGEST, target_object_id="tail", expected_parent_id="a"
        )

    assert exc.value.failure_code == "CYCLE_NOT_FOUND"


def test_long_cycle_is_detected_and_repaired_without_reparenting_other_nodes():
    names = ["a", "b", "c", "d", "e", "f", "g", "h"]
    scene = _scene(*[(name, names[(index + 1) % len(names)]) for index, name in enumerate(names)])
    plan = plan_parent_cycle_correction(
        scene, _DIGEST, target_object_id="d", expected_parent_id="e"
    )
    before = copy.deepcopy(scene)

    def mutate(object_id, expected_parent_id, new_parent_id):
        assert (object_id, expected_parent_id, new_parent_id) == ("d", "e", None)
        next(obj for obj in scene["objects"] if obj["object_id"] == object_id)["parent_object_id"] = new_parent_id

    result = execute_repair_parent_cycle(
        plan, _auth(plan), extractor=lambda: (scene, _DIGEST), mutator=mutate
    )

    assert result.ok is True
    assert next(obj for obj in scene["objects"] if obj["object_id"] == "d")["parent_object_id"] is None
    for before_obj, after_obj in zip(before["objects"], scene["objects"]):
        if before_obj["object_id"] != "d":
            assert after_obj == before_obj


def test_dangling_parent_chain_is_not_treated_as_a_cycle():
    scene = _scene(("a", "missing"))

    with pytest.raises(ParentCycleError) as exc:
        plan_parent_cycle_correction(
            scene, _DIGEST, target_object_id="a", expected_parent_id="missing"
        )

    assert exc.value.failure_code == "PARENT_IS_DANGLING"


def test_cycle_signature_is_independent_of_object_storage_order():
    scene_a = _scene(("a", "b"), ("b", "c"), ("c", "a"), ("x", None))
    scene_b = _scene(("x", None), ("c", "a"), ("a", "b"), ("b", "c"))

    plan_a = plan_parent_cycle_correction(
        scene_a, _DIGEST, target_object_id="a", expected_parent_id="b"
    )
    plan_b = plan_parent_cycle_correction(
        scene_b, _DIGEST, target_object_id="a", expected_parent_id="b"
    )

    assert plan_a == plan_b


def test_mutation_that_creates_a_second_cycle_fails_closed():
    scene = _scene(
        ("a", "b"),
        ("b", "a"),
        ("c", None),
        ("d", "c"),
    )
    plan = plan_parent_cycle_correction(
        scene, _DIGEST, target_object_id="a", expected_parent_id="b"
    )
    calls = []

    def mutate(object_id, expected_parent_id, new_parent_id):
        calls.append((object_id, expected_parent_id, new_parent_id))
        next(obj for obj in scene["objects"] if obj["object_id"] == "a")["parent_object_id"] = None
        next(obj for obj in scene["objects"] if obj["object_id"] == "c")["parent_object_id"] = "d"

    result = execute_repair_parent_cycle(
        plan, _auth(plan), extractor=lambda: (scene, _DIGEST), mutator=mutate
    )

    assert result.ok is False
    assert result.outcome == "POSTCONDITION_FAILED"
    assert result.failure_code == "NEW_CYCLE_CREATED"
    assert calls == [("a", "b", None)]
