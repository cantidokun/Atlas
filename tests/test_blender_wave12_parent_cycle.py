from __future__ import annotations

import copy

import pytest

from planning.blender.parent_cycle import (
    CYCLE_CORRECTION_TYPE,
    ParentCycleError,
    _scene_digest,
    execute_repair_parent_cycle,
    plan_parent_cycle_correction,
    target_is_in_parent_cycle,
)


def scene(*parents):
    return {
        "objects": [
            {
                "object_id": oid,
                "parent_object_id": parent,
                "name": f"name-{oid}",
                "mesh_id": f"mesh-{oid}",
                "collection_id": f"collection-{oid}",
                "metadata": {"role": oid},
                "location": [i, 0, 0],
                "rotation": [1, 0, 0, 0],
                "scale": [1, 1, 1],
            }
            for i, (oid, parent) in enumerate(parents)
        ]
    }


def digest(value):
    return _scene_digest(value)


def plan_for(value, target="a", parent="b"):
    return plan_parent_cycle_correction(value, digest(value), target_object_id=target, expected_parent_id=parent)


def auth_for(plan):
    return {
        "decision": "APPROVED",
        "correction_type": CYCLE_CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": plan["source_report_digest"],
        "target_object_id": plan["target_object_id"],
        "expected_parent_id": plan["params"]["expected_parent_id"],
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
        plan_parent_cycle_correction(s, digest(s), target_object_id="a", expected_parent_id="missing")
    assert exc.value.failure_code == "PARENT_IS_DANGLING"


def test_planner_binds_exact_target_and_parent():
    s = scene(("a", "b"), ("b", "a"), ("unrelated", None))
    plan = plan_for(s)
    assert plan["correction_type"] == CYCLE_CORRECTION_TYPE
    assert plan["target_object_id"] == "a"
    assert plan["params"] == {"expected_parent_id": "b"}
    assert plan["source_report_digest"] == digest(s)


def test_planner_rejects_wrong_parent():
    s = scene(("a", "b"), ("b", "a"))
    with pytest.raises(ParentCycleError) as exc:
        plan_parent_cycle_correction(s, digest(s), target_object_id="a", expected_parent_id="a")
    assert exc.value.failure_code == "EXPECTED_PARENT_MISMATCH"


def test_duplicate_object_ids_fail_closed():
    s = {"objects": [{"object_id": "a", "parent_object_id": "a"}, {"object_id": "a", "parent_object_id": "a"}]}
    with pytest.raises(ParentCycleError) as exc:
        target_is_in_parent_cycle(s, "a")
    assert exc.value.failure_code == "DUPLICATE_OBJECT_ID"


def test_authorization_is_closed():
    s = scene(("a", "b"), ("b", "a"))
    plan = plan_for(s)
    auth = auth_for(plan)
    working = copy.deepcopy(s)
    calls = []

    def extract():
        return working, digest(working)

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


def test_extra_authorization_field_refused_without_mutation():
    s = scene(("a", "b"), ("b", "a"))
    plan = plan_for(s)
    auth = auth_for(plan)
    auth["unexpected"] = True
    calls = []
    result = execute_repair_parent_cycle(plan, auth, extractor=lambda: (s, digest(s)), mutator=lambda *args: calls.append(args))
    assert result.outcome == "AUTHORIZATION_REFUSED"
    assert result.failure_code == "FIELDS_NOT_CLOSED"
    assert calls == []


@pytest.mark.parametrize(("field", "value", "code"), [
    ("target_object_id", "b", "TARGET_OBJECT_MISMATCH"),
    ("expected_parent_id", "c", "EXPECTED_PARENT_MISMATCH"),
    ("correction_type", "OTHER", "CORRECTION_TYPE_MISMATCH"),
])
def test_authorization_substitutions_refused_without_mutation(field, value, code):
    s = scene(("a", "b"), ("b", "a"))
    plan = plan_for(s)
    auth = auth_for(plan)
    auth[field] = value
    calls = []
    result = execute_repair_parent_cycle(plan, auth, extractor=lambda: (s, digest(s)), mutator=lambda *args: calls.append(args))
    assert result.ok is False
    assert result.failure_code == code
    assert calls == []


def test_stale_source_digest_refused_without_mutation():
    old = scene(("a", "b"), ("b", "a"))
    current = copy.deepcopy(old)
    current["objects"][1]["name"] = "changed"
    plan = plan_for(old)
    auth = auth_for(plan)
    calls = []
    result = execute_repair_parent_cycle(plan, auth, extractor=lambda: (current, digest(current)), mutator=lambda *args: calls.append(args))
    assert result.ok is False
    assert result.failure_code == "SOURCE_DIGEST_MISMATCH"
    assert calls == []


def test_echoed_stale_digest_cannot_reach_mutator():
    old = scene(("a", "b"), ("b", "a"))
    current = copy.deepcopy(old)
    current["objects"][1]["name"] = "changed-after-extraction"
    plan = plan_for(old)
    auth = auth_for(plan)
    calls = []
    result = execute_repair_parent_cycle(plan, auth, extractor=lambda: (current, plan["source_report_digest"]), mutator=lambda *args: calls.append(args))
    assert result.ok is False
    assert result.failure_code == "SOURCE_DIGEST_INVALID"
    assert calls == []


def test_cycle_disappears_before_mutation_refused():
    old = scene(("a", "b"), ("b", "a"))
    current = scene(("a", "b"), ("b", None))
    plan = plan_for(old)
    auth = auth_for(plan)
    calls = []
    result = execute_repair_parent_cycle(plan, auth, extractor=lambda: (current, digest(current)), mutator=lambda *args: calls.append(args))
    assert result.ok is False
    assert result.failure_code == "SOURCE_DIGEST_MISMATCH"
    assert calls == []


def test_plan_shape_extra_params_rejected():
    s = scene(("a", "b"), ("b", "a"))
    plan = dict(plan_for(s))
    plan["params"] = {"expected_parent_id": "b", "detach_to": None}
    auth = auth_for({**plan, "params": {"expected_parent_id": "b"}})
    result = execute_repair_parent_cycle(plan, auth, extractor=lambda: (s, digest(s)), mutator=lambda *args: None)
    assert result.failure_code == "PARAMS_INVALID"


def test_non_target_state_must_remain_unchanged():
    s = scene(("a", "b"), ("b", "a"), ("other", None))
    plan = plan_for(s)
    auth = auth_for(plan)
    working = copy.deepcopy(s)

    def extract():
        return working, digest(working)

    def mutate(object_id, expected_parent_id, new_parent_id):
        for obj in working["objects"]:
            if obj["object_id"] == object_id:
                obj["parent_object_id"] = new_parent_id
            if obj["object_id"] == "other":
                obj["location"][0] = 99

    result = execute_repair_parent_cycle(plan, auth, extractor=extract, mutator=mutate)
    assert result.failure_code == "UNRELATED_OBJECT_CHANGED"


def test_local_transform_must_remain_unchanged():
    s = scene(("a", "b"), ("b", "a"))
    plan = plan_for(s)
    auth = auth_for(plan)
    working = copy.deepcopy(s)

    def extract():
        return working, digest(working)

    def mutate(object_id, expected_parent_id, new_parent_id):
        working["objects"][0]["parent_object_id"] = new_parent_id
        working["objects"][0]["location"][0] = 9

    result = execute_repair_parent_cycle(plan, auth, extractor=extract, mutator=mutate)
    assert result.failure_code == "TARGET_NON_PARENT_CHANGED"


@pytest.mark.parametrize("field", ["name", "mesh_id", "collection_id", "metadata"])
def test_target_canonical_state_must_remain_unchanged(field):
    s = scene(("a", "b"), ("b", "a"))
    plan = plan_for(s)
    auth = auth_for(plan)
    working = copy.deepcopy(s)

    def extract():
        return working, digest(working)

    def mutate(object_id, expected_parent_id, new_parent_id):
        working["objects"][0]["parent_object_id"] = new_parent_id
        if field == "metadata":
            working["objects"][0][field]["role"] = "forged"
        else:
            working["objects"][0][field] = "forged"

    result = execute_repair_parent_cycle(plan, auth, extractor=extract, mutator=mutate)
    assert result.failure_code == "TARGET_NON_PARENT_CHANGED"


def test_target_identity_mutation_must_fail_closed():
    s = scene(("a", "b"), ("b", "a"))
    plan = plan_for(s)
    auth = auth_for(plan)
    working = copy.deepcopy(s)

    def extract():
        return working, digest(working)

    def mutate(object_id, expected_parent_id, new_parent_id):
        working["objects"][0]["object_id"] = "forged-target"
        working["objects"][0]["parent_object_id"] = new_parent_id

    result = execute_repair_parent_cycle(plan, auth, extractor=extract, mutator=mutate)
    assert result.failure_code in {"TARGET_OBJECT_MISSING", "OBJECT_IDENTITY_CHANGED", "UNRELATED_OBJECT_CHANGED", "OUTPUT_DIGEST_INVALID"}


def test_new_unrelated_cycle_must_fail_closed():
    s = scene(("a", "b"), ("b", "a"), ("c", None), ("d", "c"))
    plan = plan_for(s)
    auth = auth_for(plan)
    working = copy.deepcopy(s)

    def extract():
        return working, digest(working)

    def mutate(object_id, expected_parent_id, new_parent_id):
        working["objects"][0]["parent_object_id"] = new_parent_id
        working["objects"][2]["parent_object_id"] = "d"

    result = execute_repair_parent_cycle(plan, auth, extractor=extract, mutator=mutate)
    assert result.failure_code == "NEW_CYCLE_CREATED"


def test_forged_correction_id_rejected_before_mutation():
    s = scene(("a", "b"), ("b", "a"))
    plan = dict(plan_for(s))
    plan["correction_id"] = "f" * 64
    auth = auth_for({**plan, "correction_id": "f" * 64})
    calls = []
    result = execute_repair_parent_cycle(plan, auth, extractor=lambda: (s, digest(s)), mutator=lambda *args: calls.append(args))
    assert result.failure_code == "CORRECTION_ID_INVALID"
    assert calls == []


def test_forged_plan_id_rejected_before_mutation():
    s = scene(("a", "b"), ("b", "a"))
    plan = dict(plan_for(s))
    plan["plan_id"] = "f" * 64
    auth = auth_for({**plan, "plan_id": "f" * 64})
    calls = []
    result = execute_repair_parent_cycle(plan, auth, extractor=lambda: (s, digest(s)), mutator=lambda *args: calls.append(args))
    assert result.failure_code == "PLAN_ID_INVALID"
    assert calls == []


def test_pre_mutation_structural_validation_exception_is_contained():
    source = scene(("a", "b"), ("b", "a"))
    plan = plan_for(source)
    auth = auth_for(plan)
    malformed = {"objects": [{"object_id": "a", "parent_object_id": "b"}, {"object_id": "a", "parent_object_id": "a"}]}
    calls = []
    result = execute_repair_parent_cycle(plan, auth, extractor=lambda: (malformed, digest(malformed)), mutator=lambda *args: calls.append(args))
    assert result.failure_code == "DUPLICATE_OBJECT_ID"
    assert calls == []


def test_post_mutation_structural_validation_exception_is_contained():
    source = scene(("a", "b"), ("b", "a"))
    plan = plan_for(source)
    auth = auth_for(plan)
    working = copy.deepcopy(source)
    malformed = {"objects": [{"object_id": "a", "parent_object_id": None}, {"object_id": "a", "parent_object_id": "a"}]}
    extract_count = 0
    calls = []

    def extract():
        nonlocal extract_count
        extract_count += 1
        if extract_count == 1:
            return working, digest(working)
        return malformed, digest(malformed)

    def mutate(object_id, expected_parent_id, new_parent_id):
        calls.append((object_id, expected_parent_id, new_parent_id))
        working["objects"][0]["parent_object_id"] = new_parent_id

    result = execute_repair_parent_cycle(plan, auth, extractor=extract, mutator=mutate)
    assert result.failure_code == "DUPLICATE_OBJECT_ID"
    assert calls == [("a", "b", None)]


def test_successfully_applied_plan_cannot_be_replayed():
    working = scene(("a", "a"))
    plan = plan_for(working, target="a", parent="a")
    auth = auth_for(plan)

    def mutate(object_id, expected_parent_id, new_parent_id):
        working["objects"][0]["parent_object_id"] = new_parent_id

    first = execute_repair_parent_cycle(plan, auth, extractor=lambda: (working, digest(working)), mutator=mutate)
    assert first.ok is True
    calls = []
    second = execute_repair_parent_cycle(plan, auth, extractor=lambda: (working, digest(working)), mutator=lambda *args: calls.append(args))
    assert second.failure_code == "SOURCE_DIGEST_MISMATCH"
    assert calls == []


def test_extractor_shape_failure_is_contained():
    s = scene(("a", "b"), ("b", "a"))
    plan = plan_for(s)
    auth = auth_for(plan)
    calls = []
    result = execute_repair_parent_cycle(plan, auth, extractor=lambda: s, mutator=lambda *args: calls.append(args))
    assert result.failure_code == "EXTRACTION_FAILED"
    assert calls == []
