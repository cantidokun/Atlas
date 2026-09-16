from __future__ import annotations

import copy

from planning.blender.parent_cycle import (
    CYCLE_CORRECTION_TYPE,
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
    assert second.failure_code == "CYCLE_NOT_FOUND"
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
