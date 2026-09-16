from __future__ import annotations

from collections.abc import Mapping

import pytest

from planning.blender.parent_cycle import (
    CYCLE_CORRECTION_TYPE,
    ParentCycleError,
    _make_plan,
    execute_repair_parent_cycle,
    plan_parent_cycle_correction,
    scene_report_digest,
)


class RaisingGetMapping(Mapping):
    def __init__(self, value=None, message="hostile get"):
        self._value = {} if value is None else dict(value)
        self._message = message

    def __getitem__(self, key):
        raise RuntimeError(self._message)

    def __iter__(self):
        return iter(self._value)

    def __len__(self):
        return len(self._value)

    def get(self, key, default=None):
        raise RuntimeError(self._message)


class RaisingIterMapping(Mapping):
    def __init__(self, value=None, message="hostile iter"):
        self._value = {} if value is None else dict(value)
        self._message = message

    def __getitem__(self, key):
        return self._value[key]

    def __iter__(self):
        raise RuntimeError(self._message)

    def __len__(self):
        return len(self._value)

    def get(self, key, default=None):
        return self._value.get(key, default)


def valid_cycle_scene():
    return {
        "objects": [
            {"object_id": "a", "parent_object_id": "b"},
            {"object_id": "b", "parent_object_id": "a"},
        ]
    }


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


def test_planner_rejects_unhashable_object_id_as_declared_failure():
    scene = {"objects": [{"object_id": [], "parent_object_id": None}]}
    with pytest.raises(ParentCycleError) as exc:
        plan_parent_cycle_correction(
            scene,
            scene_report_digest(scene),
            target_object_id="a",
            expected_parent_id="b",
        )
    assert exc.value.failure_code == "OBJECT_ID_INVALID"


def test_planner_rejects_non_iterable_objects_as_declared_failure():
    scene = {"objects": None}
    with pytest.raises(ParentCycleError) as exc:
        plan_parent_cycle_correction(
            scene,
            scene_report_digest(scene),
            target_object_id="a",
            expected_parent_id="b",
        )
    assert exc.value.failure_code == "SCENE_VALIDATION_FAILED"


def test_planner_rejects_unhashable_parent_id_as_declared_failure():
    scene = {
        "objects": [
            {"object_id": "a", "parent_object_id": []},
            {"object_id": "b", "parent_object_id": "a"},
        ]
    }
    with pytest.raises(ParentCycleError) as exc:
        plan_parent_cycle_correction(
            scene,
            scene_report_digest(scene),
            target_object_id="a",
            expected_parent_id="b",
        )
    assert exc.value.failure_code == "PARENT_ID_INVALID"


def test_executor_contains_malformed_scene_without_mutation():
    malformed = {"objects": [{"object_id": [], "parent_object_id": None}]}
    source_digest = scene_report_digest(malformed)
    plan = _make_plan(
        target_object_id="a",
        expected_parent_id="b",
        source_report_digest=source_digest,
    )
    auth = auth_for(plan)
    calls = []
    result = execute_repair_parent_cycle(
        plan,
        auth,
        extractor=lambda: (malformed, source_digest),
        mutator=lambda *args: calls.append(args),
    )
    assert result.outcome == "PLAN_INVALID"
    assert result.failure_code == "OBJECT_ID_INVALID"
    assert calls == []


def test_executor_contains_hostile_plan_mapping():
    scene = valid_cycle_scene()
    plan = RaisingGetMapping({"correction_type": CYCLE_CORRECTION_TYPE})
    calls = []
    result = execute_repair_parent_cycle(
        plan,
        {},
        extractor=lambda: (scene, scene_report_digest(scene)),
        mutator=lambda *args: calls.append(args),
    )
    assert result.failure_code == "PLAN_ACCESS_FAILED"
    assert calls == []


def test_executor_contains_hostile_authorization_mapping():
    scene = valid_cycle_scene()
    plan = _make_plan(
        target_object_id="a",
        expected_parent_id="b",
        source_report_digest=scene_report_digest(scene),
    )
    auth = RaisingIterMapping()
    calls = []
    result = execute_repair_parent_cycle(
        plan,
        auth,
        extractor=lambda: (scene, scene_report_digest(scene)),
        mutator=lambda *args: calls.append(args),
    )
    assert result.outcome == "AUTHORIZATION_REFUSED"
    assert result.failure_code == "AUTHORIZATION_ACCESS_FAILED"
    assert calls == []


def test_canonical_wave12_scene_digest_is_publicly_available():
    scene = valid_cycle_scene()
    assert scene_report_digest(scene)
    assert len(scene_report_digest(scene)) == 64
