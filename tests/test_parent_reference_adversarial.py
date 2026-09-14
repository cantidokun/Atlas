"""Permanent deterministic hostile corpus for Wave-4 parent-reference execution.

This is deliberately separate from the ordinary unit tests.  It exercises a
fixed 500-case corpus of malformed plans/authorizations and proves the critical
fail-closed invariant: no hostile case reaches the mutation seam.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from planning.blender.parent_reference import (
    execute_repair_parent_reference,
    plan_parent_reference_correction,
)


TARGET = "object:child"
MISSING_PARENT = "parent:missing"
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


def auth_for(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": "APPROVED",
        "correction_type": "REPAIR_PARENT_REFERENCE",
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": plan["source_report_digest"],
        "target_object_id": plan["target_object_id"],
        "expected_parent_id": plan["params"]["expected_parent_id"],
    }


def _base_plan() -> dict[str, Any]:
    return dict(
        plan_parent_reference_correction(
            make_scene(), SOURCE,
            target_object_id=TARGET,
            expected_parent_id=MISSING_PARENT,
        )
    )


def _hostile_cases() -> list[tuple[str, Callable[[dict[str, Any], dict[str, Any], int], None]]]:
    """Return 25 deterministic mutation families, expanded to 500 cases."""

    def plan_field(field: str, value_factory: Callable[[int], Any]):
        def mutate(plan: dict[str, Any], auth: dict[str, Any], i: int) -> None:
            plan[field] = value_factory(i)
        return mutate

    def auth_field(field: str, value_factory: Callable[[int], Any]):
        def mutate(plan: dict[str, Any], auth: dict[str, Any], i: int) -> None:
            auth[field] = value_factory(i)
        return mutate

    families = [
        ("plan-type", plan_field("correction_type", lambda i: f"HOSTILE_TYPE_{i}")),
        ("plan-id", plan_field("plan_id", lambda i: f"{i:064x}"[-64:])),
        ("correction-id", plan_field("correction_id", lambda i: f"{i + 1:064x}"[-64:])),
        ("source-digest", plan_field("source_report_digest", lambda i: (f"{i + 1:064x}"[-64:]))),
        ("target-id", plan_field("target_object_id", lambda i: f"object:hostile:{i}")),
        ("params-extra", plan_field("params", lambda i: {"expected_parent_id": MISSING_PARENT, "detach_to": None, "extra": i})),
        ("params-missing", plan_field("params", lambda i: {"expected_parent_id": MISSING_PARENT})),
        ("params-empty", plan_field("params", lambda i: {})),
        ("detach-nonnull", plan_field("params", lambda i: {"expected_parent_id": MISSING_PARENT, "detach_to": f"parent:hostile:{i}"})),
        ("expected-parent", plan_field("params", lambda i: {"expected_parent_id": f"parent:hostile:{i}", "detach_to": None})),
        ("params-list", plan_field("params", lambda i: [i])),
        ("params-null", plan_field("params", lambda i: None)),
        ("auth-decision", auth_field("decision", lambda i: "REJECTED" if i % 2 else "PENDING")),
        ("auth-type", auth_field("correction_type", lambda i: f"HOSTILE_AUTH_TYPE_{i}")),
        ("auth-correction-id", auth_field("correction_id", lambda i: f"{i + 1000:064x}"[-64:])),
        ("auth-plan-id", auth_field("plan_id", lambda i: f"{i + 2000:064x}"[-64:])),
        ("auth-source", auth_field("source_report_digest", lambda i: f"{i + 3000:064x}"[-64:])),
        ("auth-target", auth_field("target_object_id", lambda i: f"object:hostile-auth:{i}")),
        ("auth-parent", auth_field("expected_parent_id", lambda i: f"parent:hostile-auth:{i}")),
        ("auth-extra", auth_field("unexpected", lambda i: i)),
        ("auth-empty-type", auth_field("correction_type", lambda i: "")),
        ("auth-empty-plan", auth_field("plan_id", lambda i: "")),
        ("auth-empty-correction", auth_field("correction_id", lambda i: "")),
        ("auth-empty-source", auth_field("source_report_digest", lambda i: "")),
        ("auth-empty-target", auth_field("target_object_id", lambda i: "")),
    ]
    return families


def test_500_case_deterministic_hostile_corpus_is_fail_closed():
    families = _hostile_cases()
    assert len(families) == 25

    total = 0
    for family_name, mutate in families:
        for i in range(20):
            scene = make_scene()
            plan = _base_plan()
            auth = auth_for(plan)
            mutate(plan, auth, i)

            mutations: list[tuple[str, None]] = []

            def extractor() -> tuple[Scene, str]:
                return scene, SOURCE

            def mutator(target_id: str, detach_to: None) -> None:
                mutations.append((target_id, detach_to))
                scene.objects[0].parent_id = None

            try:
                outcome = execute_repair_parent_reference(
                    plan,
                    auth,
                    extractor=extractor,
                    mutator=mutator,
                )
            except Exception as exc:  # hostile corpus must not escape raw exceptions
                raise AssertionError(f"raw exception in {family_name}[{i}]: {exc!r}") from exc

            assert outcome.ok is False, f"hostile case unexpectedly applied: {family_name}[{i}]"
            assert mutations == [], f"mutation reached seam: {family_name}[{i}]"
            assert scene.objects[0].parent_id == MISSING_PARENT
            total += 1

    assert total == 500
