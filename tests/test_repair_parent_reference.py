from __future__ import annotations

from dataclasses import dataclass

from planning.blender.parent_reference import (
    ParentPresentedWork,
    execute_repair_parent_reference,
    plan_parent_reference_correction,
    verify_parent_authorization,
)


MISSING_PARENT = "parent:missing"
TARGET = "object:child"
SOURCE = "a" * 64


@dataclass
class Obj:
    object_id: str
    parent_id: str | None = None
    name: str = "child"
    location: tuple[float, float, float] = (1.0, 2.0, 3.0)
    rotation: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)


@dataclass
class Scene:
    objects: tuple[Obj, ...]


def make_scene() -> Scene:
    return Scene((Obj(TARGET, MISSING_PARENT),))


def auth_for(plan: dict) -> dict:
    return {
        "decision": "APPROVED",
        "correction_type": "REPAIR_PARENT_REFERENCE",
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": plan["source_report_digest"],
        "target_object_id": plan["target_object_id"],
        "expected_parent_id": plan["params"]["expected_parent_id"],
    }


def test_plan_positive():
    plan = plan_parent_reference_correction(
        make_scene(),
        SOURCE,
        target_object_id=TARGET,
        expected_parent_id=MISSING_PARENT,
    )
    assert plan["correction_type"] == "REPAIR_PARENT_REFERENCE"
    assert plan["params"] == {"expected_parent_id": MISSING_PARENT, "detach_to": None}


def test_cycle_refused():
    child = Obj(TARGET, MISSING_PARENT)
    missing = Obj(MISSING_PARENT, TARGET)
    try:
        plan_parent_reference_correction(
            Scene((child, missing)), SOURCE,
            target_object_id=TARGET, expected_parent_id=MISSING_PARENT,
        )
    except Exception as exc:
        assert getattr(exc, "failure_code") == "CYCLE_DETECTED"
    else:
        raise AssertionError("cycle must be refused")


def test_wrong_expected_parent_refused():
    try:
        plan_parent_reference_correction(
            make_scene(), SOURCE,
            target_object_id=TARGET, expected_parent_id="parent:other",
        )
    except Exception as exc:
        assert getattr(exc, "failure_code") == "EXPECTED_PARENT_MISMATCH"
    else:
        raise AssertionError("wrong parent must be refused")


def test_present_parent_refused():
    scene = Scene((Obj(TARGET, MISSING_PARENT), Obj(MISSING_PARENT, None)))
    try:
        plan_parent_reference_correction(
            scene, SOURCE,
            target_object_id=TARGET, expected_parent_id=MISSING_PARENT,
        )
    except Exception as exc:
        assert getattr(exc, "failure_code") == "PARENT_STILL_PRESENT"
    else:
        raise AssertionError("present parent must be refused")


def test_multiple_target_match_refused():
    scene = Scene((Obj(TARGET, MISSING_PARENT), Obj(TARGET, MISSING_PARENT)))
    try:
        plan_parent_reference_correction(
            scene, SOURCE,
            target_object_id=TARGET, expected_parent_id=MISSING_PARENT,
        )
    except Exception as exc:
        assert getattr(exc, "failure_code") == "TARGET_OBJECT_NOT_FOUND"
    else:
        raise AssertionError("ambiguous target must be refused")


def test_authorization_positive():
    plan = plan_parent_reference_correction(
        make_scene(), SOURCE,
        target_object_id=TARGET, expected_parent_id=MISSING_PARENT,
    )
    presented = ParentPresentedWork(
        plan["correction_id"], plan["plan_id"], SOURCE, TARGET, MISSING_PARENT
    )
    verdict = verify_parent_authorization(presented, auth_for(plan))
    assert verdict.verified is True
    assert verdict.outcome == "AUTHORIZATION_VERIFIED"


def test_authorization_cross_plan_refused():
    plan = plan_parent_reference_correction(
        make_scene(), SOURCE,
        target_object_id=TARGET, expected_parent_id=MISSING_PARENT,
    )
    bad = auth_for(plan)
    bad["plan_id"] = "b" * 64
    presented = ParentPresentedWork(
        plan["correction_id"], plan["plan_id"], SOURCE, TARGET, MISSING_PARENT
    )
    verdict = verify_parent_authorization(presented, bad)
    assert verdict.verified is False
    assert verdict.failure_code == "PLAN_ID_MISMATCH"


def test_authorization_wrong_type_refused():
    plan = plan_parent_reference_correction(
        make_scene(), SOURCE,
        target_object_id=TARGET, expected_parent_id=MISSING_PARENT,
    )
    bad = auth_for(plan)
    bad["correction_type"] = "REPAIR_MERGE_VERTEX"
    verdict = verify_parent_authorization(
        ParentPresentedWork(plan["correction_id"], plan["plan_id"], SOURCE, TARGET, MISSING_PARENT),
        bad,
    )
    assert verdict.verified is False
    assert verdict.failure_code == "CORRECTION_TYPE_MISMATCH"


def test_execution_success_and_single_mutation():
    scene = make_scene()
    current_digest = SOURCE
    mutations: list[tuple[str, None]] = []

    def extractor():
        return scene, current_digest

    def mutator(target_id: str, detach_to: None):
        mutations.append((target_id, detach_to))
        for obj in scene.objects:
            if obj.object_id == target_id:
                obj.parent_id = None

    plan = plan_parent_reference_correction(
        scene, SOURCE,
        target_object_id=TARGET, expected_parent_id=MISSING_PARENT,
    )
    outcome = execute_repair_parent_reference(
        plan, auth_for(plan), extractor=extractor, mutator=mutator
    )
    assert outcome.ok is True
    assert outcome.outcome == "CORRECTION_APPLIED"
    assert mutations == [(TARGET, None)]
    assert scene.objects[0].parent_id is None


def test_stale_source_digest_refused_without_mutation():
    scene = make_scene()
    current_digest = "b" * 64
    mutations: list[tuple[str, None]] = []

    def extractor():
        return scene, current_digest

    def mutator(target_id: str, detach_to: None):
        mutations.append((target_id, detach_to))
        scene.objects[0].parent_id = None

    plan = plan_parent_reference_correction(
        scene, SOURCE,
        target_object_id=TARGET, expected_parent_id=MISSING_PARENT,
    )
    outcome = execute_repair_parent_reference(
        plan, auth_for(plan), extractor=extractor, mutator=mutator
    )
    assert outcome.ok is False
    assert outcome.failure_code == "SOURCE_DIGEST_MISMATCH"
    assert mutations == []
    assert scene.objects[0].parent_id == MISSING_PARENT


def test_auth_source_digest_binding_refused():
    plan = plan_parent_reference_correction(
        make_scene(), SOURCE,
        target_object_id=TARGET, expected_parent_id=MISSING_PARENT,
    )
    bad = auth_for(plan)
    bad["source_report_digest"] = "c" * 64
    verdict = verify_parent_authorization(
        ParentPresentedWork(plan["correction_id"], plan["plan_id"], SOURCE, TARGET, MISSING_PARENT),
        bad,
    )
    assert verdict.verified is False
    assert verdict.failure_code == "SOURCE_DIGEST_MISMATCH"


def test_auth_target_binding_refused():
    plan = plan_parent_reference_correction(
        make_scene(), SOURCE,
        target_object_id=TARGET, expected_parent_id=MISSING_PARENT,
    )
    bad = auth_for(plan)
    bad["target_object_id"] = "object:other"
    verdict = verify_parent_authorization(
        ParentPresentedWork(plan["correction_id"], plan["plan_id"], SOURCE, TARGET, MISSING_PARENT),
        bad,
    )
    assert verdict.verified is False
    assert verdict.failure_code == "TARGET_OBJECT_MISMATCH"


def test_non_parent_state_preserved():
    scene = make_scene()
    before = (scene.objects[0].name, scene.objects[0].location, scene.objects[0].rotation, scene.objects[0].scale)
    digest = SOURCE

    def extractor():
        return scene, digest

    def mutator(target_id: str, detach_to: None):
        scene.objects[0].parent_id = None

    plan = plan_parent_reference_correction(scene, SOURCE, target_object_id=TARGET, expected_parent_id=MISSING_PARENT)
    outcome = execute_repair_parent_reference(plan, auth_for(plan), extractor=extractor, mutator=mutator)
    assert outcome.ok
    assert (scene.objects[0].name, scene.objects[0].location, scene.objects[0].rotation, scene.objects[0].scale) == before


def test_authorization_requires_approval():
    plan = plan_parent_reference_correction(make_scene(), SOURCE, target_object_id=TARGET, expected_parent_id=MISSING_PARENT)
    bad = auth_for(plan)
    bad["decision"] = "REJECTED"
    verdict = verify_parent_authorization(
        ParentPresentedWork(plan["correction_id"], plan["plan_id"], SOURCE, TARGET, MISSING_PARENT), bad
    )
    assert verdict.verified is False
    assert verdict.failure_code == "DECISION_NOT_APPROVED"


def test_authorization_expected_parent_binding_refused():
    plan = plan_parent_reference_correction(make_scene(), SOURCE, target_object_id=TARGET, expected_parent_id=MISSING_PARENT)
    bad = auth_for(plan)
    bad["expected_parent_id"] = "parent:other"
    verdict = verify_parent_authorization(
        ParentPresentedWork(plan["correction_id"], plan["plan_id"], SOURCE, TARGET, MISSING_PARENT), bad
    )
    assert verdict.verified is False
    assert verdict.failure_code == "EXPECTED_PARENT_MISMATCH"


def test_invalid_params_refuse_before_mutation():
    plan = dict(plan_parent_reference_correction(make_scene(), SOURCE, target_object_id=TARGET, expected_parent_id=MISSING_PARENT))
    plan["params"] = {"expected_parent_id": MISSING_PARENT, "detach_to": "not-null"}
    mutations: list[tuple[str, None]] = []
    outcome = execute_repair_parent_reference(plan, auth_for(plan), extractor=lambda: (make_scene(), SOURCE), mutator=lambda a, b: mutations.append((a, b)))
    assert outcome.ok is False
    assert outcome.failure_code == "DETACH_TARGET_INVALID"
    assert mutations == []


def test_execution_expected_parent_present_refused_before_mutation():
    plan_scene = make_scene()
    plan = plan_parent_reference_correction(plan_scene, SOURCE, target_object_id=TARGET, expected_parent_id=MISSING_PARENT)
    scene = Scene((Obj(TARGET, MISSING_PARENT), Obj(MISSING_PARENT, None)))
    mutations: list[tuple[str, None]] = []
    outcome = execute_repair_parent_reference(plan, auth_for(plan), extractor=lambda: (scene, SOURCE), mutator=lambda a, b: mutations.append((a, b)))
    assert outcome.ok is False
    assert outcome.failure_code == "PARENT_STILL_PRESENT"
    assert mutations == []
