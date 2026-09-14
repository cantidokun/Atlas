from __future__ import annotations

from dataclasses import dataclass

from planning.blender.parent_reference import execute_repair_parent_reference, plan_parent_reference_correction

MISSING_PARENT = "parent:missing"
TARGET = "object:child"
OTHER = "object:other"
SOURCE = "a" * 64


@dataclass
class Obj:
    object_id: str
    parent_id: str | None = None
    name: str = "object"
    location: tuple[float, float, float] = (1.0, 2.0, 3.0)
    rotation: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)


@dataclass
class Scene:
    objects: tuple[Obj, ...]


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


def make_scene() -> Scene:
    return Scene((Obj(TARGET, MISSING_PARENT, "child"), Obj(OTHER, None, "other")))


def test_unrelated_object_mutation_fails_closed_after_seam():
    scene = make_scene()
    mutations: list[tuple[str, None]] = []

    def extractor():
        return scene, SOURCE

    def mutator(target_id: str, detach_to: None):
        mutations.append((target_id, detach_to))
        scene.objects[0].parent_id = None
        scene.objects[1].name = "hostile mutation"

    plan = plan_parent_reference_correction(
        scene, SOURCE, target_object_id=TARGET, expected_parent_id=MISSING_PARENT
    )
    outcome = execute_repair_parent_reference(
        plan, auth_for(plan), extractor=extractor, mutator=mutator
    )

    assert outcome.ok is False
    assert outcome.failure_code == "UNRELATED_OBJECT_CHANGED"
    assert mutations == [(TARGET, None)]


def test_object_identity_set_change_fails_closed_after_seam():
    scene = make_scene()

    def extractor():
        return scene, SOURCE

    def mutator(target_id: str, detach_to: None):
        scene.objects[0].parent_id = None
        scene.objects = (scene.objects[0], Obj("object:replacement", None, "replacement"))

    plan = plan_parent_reference_correction(
        scene, SOURCE, target_object_id=TARGET, expected_parent_id=MISSING_PARENT
    )
    outcome = execute_repair_parent_reference(
        plan, auth_for(plan), extractor=extractor, mutator=mutator
    )

    assert outcome.ok is False
    assert outcome.failure_code == "OBJECT_IDENTITY_CHANGED"
