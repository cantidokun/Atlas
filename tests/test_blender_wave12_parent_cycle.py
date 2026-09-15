from __future__ import annotations

import copy

import pytest

from planning.blender.parent_cycle import (
    CYCLE_CORRECTION_TYPE,
    ParentCycleError,
    execute_repair_parent_cycle,
    plan_parent_cycle_correction,
    target_is_in_parent_cycle,
)


def scene(*parents):
    return {
        "objects": [
            {"object_id": oid, "parent_object_id": parent, "location": [i, 0, 0], "rotation": [1, 0, 0, 0], "scale": [1, 1, 1]}
            for i, (oid, parent) in enumerate(parents)
        ]
    }


def test_self_cycle_detected():
    s = scene(("a", "a"))
    assert target_is_in_parent_cycle(s, "a") is True


def test_two_node_cycle_detected():
    s = scene(("a", "b"), ("b", "a"))
    assert target_is_in_parent_cycle(s, "a") is True
    assert target_is_in_parent_cycle(s, "b") is True


def test_multi_node_cycle_detected_without_touching_tail():
    s = scene(("a", "b"), ("b", "c"), ("c", "a"), ("tail", "a"))
    assert target_is_in_parent_cycle(s, "a") is True
    assert target_is_in_parent_cycle(s, "tail") is False


def test_non_cycle_is_rejected():
    s = scene(("a", "b"), ("b", None))
    assert target_is_in_parent_cycle(s, "a") is False


def test_dangling_parent_is_not_wave12():
    s = scene(("a", "missing"))
    with pytest.raises(ParentCycleError) as exc:
        plan_parent_cycle_correction(s, "a" * 64, target_object_id="a", expected_parent_id="missing")
    assert exc.value.failure_code == "PARENT_IS_DANGLING"


def test_planner_binds_exact_target_and_parent():
    s = scene(("a", "b"), ("b", "a"), ("unrelated", None))
    plan = plan_parent_cycle_correction(s, "a" * 64, target_object_id="a", expected_parent_id="b")
    assert plan["correction_type"] == CYCLE_CORRECTION_TYPE
    assert plan["target_object_id"] == "a"
    assert plan["params"] == {"expected_parent_id": "b"}
    assert plan["source_report_digest"] == "a" * 64


def test_planner_rejects_wrong_parent():
    s = scene(("a", "b"), ("b", "a"))
    with pytest.raises(ParentCycleError) as exc:
        plan_parent_cycle_correction(s, "a" * 64, target_object_id="a", expected_parent_id="a")
    assert exc.value.failure_code == "EXPECTED_PARENT_MISMATCH"


def test_duplicate_object_ids_fail_closed():
    s = {"objects": [{"object_id": "a", "parent_object_id": "a"}, {"object_id": "a", "parent_object_id": "a"}]}
    with pytest.raises(ParentCycleError) as exc:
        target_is_in_parent_cycle(s, "a")
    assert exc.value.failure_code == "DUPLICATE_OBJECT_ID"


def test_authorization_is_closed():
    s = scene(("a", "b"), ("b", "a"))
    plan = plan_parent_cycle_correction(s, "a" * 64, target_object_id="a", expected_parent_id="b")
    auth = {
        "decision": "APPROVED",
        "correction_type": CYCLE_CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": "a" * 64,
        "target_object_id": "a",
        "expected_parent_id": "b",
    }

    working = copy.deepcopy(s)

    def extract():
        return working, "a" * 64

    calls = []

    def mutate(object_id, expected_parent_id, new_parent_id):
        calls.append((object_id, expected_parent_id, new_parent_id))
        for obj in working["objects"]:
            if obj["object_id"] == object_id:
                obj["parent_object_id"] = new_parent_id

    result = execute_repair_parent_cycle(plan, auth, extractor=extract, mutator=mutate)
    assert result.ok is True
    assert calls == [("a", "b", None)]
    assert working["objects"][0]["parent_object_id"] is None
    assert working["objects"][1]["parent_object_id"] == "a"


def test_wrong_authorization_target_refused_without_mutation():
    s = scene(("a", "b"), ("b", "a"))
    plan = plan_parent_cycle_correction(s, "a" * 64, target_object_id="a", expected_parent_id="b")
    auth = {
        "decision": "APPROVED",
        "correction_type": CYCLE_CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": "a" * 64,
        "target_object_id": "b",
        "expected_parent_id": "b",
    }
    calls = []
    result = execute_repair_parent_cycle(plan, auth, extractor=lambda: (s, "a" * 64), mutator=lambda *args: calls.append(args))
    assert result.ok is False
    assert result.outcome == "AUTHORIZATION_REFUSED"
    assert calls == []


def test_stale_source_digest_refused_without_mutation():
    s = scene(("a", "b"), ("b", "a"))
    plan = plan_parent_cycle_correction(s, "a" * 64, target_object_id="a", expected_parent_id="b")
    auth = {
        "decision": "APPROVED",
        "correction_type": CYCLE_CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": "a" * 64,
        "target_object_id": "a",
        "expected_parent_id": "b",
    }
    calls = []
    result = execute_repair_parent_cycle(plan, auth, extractor=lambda: (s, "b" * 64), mutator=lambda *args: calls.append(args))
    assert result.ok is False
    assert result.failure_code == "SOURCE_DIGEST_MISMATCH"
    assert calls == []


def test_cycle_disappears_before_mutation_refused():
    s = scene(("a", "b"), ("b", None))
    plan_source = scene(("a", "b"), ("b", "a"))
    plan = plan_parent_cycle_correction(plan_source, "a" * 64, target_object_id="a", expected_parent_id="b")
    auth = {
        "decision": "APPROVED",
        "correction_type": CYCLE_CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": "a" * 64,
        "target_object_id": "a",
        "expected_parent_id": "b",
    }
    calls = []
    result = execute_repair_parent_cycle(plan, auth, extractor=lambda: (s, "a" * 64), mutator=lambda *args: calls.append(args))
    assert result.ok is False
    assert result.failure_code == "CYCLE_NOT_FOUND"
    assert calls == []


def test_plan_shape_extra_params_rejected():
    s = scene(("a", "b"), ("b", "a"))
    plan = dict(plan_parent_cycle_correction(s, "a" * 64, target_object_id="a", expected_parent_id="b"))
    plan["params"] = {"expected_parent_id": "b", "detach_to": None}
    auth = {
        "decision": "APPROVED",
        "correction_type": CYCLE_CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": "a" * 64,
        "target_object_id": "a",
        "expected_parent_id": "b",
    }
    result = execute_repair_parent_cycle(plan, auth, extractor=lambda: (s, "a" * 64), mutator=lambda *args: None)
    assert result.failure_code == "PARAMS_INVALID"


def test_non_target_state_must_remain_unchanged():
    s = scene(("a", "b"), ("b", "a"), ("other", None))
    plan = plan_parent_cycle_correction(s, "a" * 64, target_object_id="a", expected_parent_id="b")
    auth = {
        "decision": "APPROVED",
        "correction_type": CYCLE_CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": "a" * 64,
        "target_object_id": "a",
        "expected_parent_id": "b",
    }
    working = copy.deepcopy(s)

    def extract():
        return working, "a" * 64

    def mutate(object_id, expected_parent_id, new_parent_id):
        for obj in working["objects"]:
            if obj["object_id"] == object_id:
                obj["parent_object_id"] = new_parent_id
            if obj["object_id"] == "other":
                obj["location"][0] = 99

    result = execute_repair_parent_cycle(plan, auth, extractor=extract, mutator=mutate)
    assert result.ok is False
    assert result.failure_code == "UNRELATED_OBJECT_CHANGED"


def test_local_transform_must_remain_unchanged():
    s = scene(("a", "b"), ("b", "a"))
    plan = plan_parent_cycle_correction(s, "a" * 64, target_object_id="a", expected_parent_id="b")
    auth = {
        "decision": "APPROVED",
        "correction_type": CYCLE_CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": "a" * 64,
        "target_object_id": "a",
        "expected_parent_id": "b",
    }
    working = copy.deepcopy(s)

    def extract():
        return working, "a" * 64

    def mutate(object_id, expected_parent_id, new_parent_id):
        working["objects"][0]["parent_object_id"] = new_parent_id
        working["objects"][0]["location"][0] = 9

    result = execute_repair_parent_cycle(plan, auth, extractor=extract, mutator=mutate)
    assert result.ok is False
    assert result.failure_code == "TARGET_LOCAL_TRANSFORM_CHANGED"
