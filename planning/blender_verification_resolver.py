"""Autonomous verification resolvers for Blender postconditions."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

from planning.blender_task_verifier import verify_object_location
from planning.future_generator import FutureStep


def object_location_resolver(
    *,
    file_name: str,
    object_name: str,
    expected_location: Tuple[float, float, float],
    tolerance: float = 1e-4,
):
    """Build a resolver that acquires fresh Blender evidence and evaluates it."""
    def resolve(step: FutureStep, execute) -> Dict[str, Any]:
        if step.phase != "VERIFICATION":
            raise ValueError("Blender verification resolver requires a VERIFICATION step.")
        result = execute(
            "inspect_object_transform",
            {"file_name": file_name, "object_name": object_name},
        )
        decision = verify_object_location(
            result,
            object_name=object_name,
            expected_location=expected_location,
            tolerance=tolerance,
        )
        return {
            "satisfied": decision.ok,
            "reason": decision.reason,
            "evidence": dict(decision.evidence),
        }

    return resolve


def object_locations_resolver(
    *,
    file_name: str,
    expected_locations: Mapping[str, Tuple[float, float, float]],
    tolerance: float = 1e-4,
):
    """Build one postcondition resolver for several Blender objects.

    Every object is independently inspected through the authorized executor.
    The aggregate verification passes only when every required object matches
    its expected location.
    """
    expected = dict(expected_locations)

    def resolve(step: FutureStep, execute) -> Dict[str, Any]:
        if step.phase != "VERIFICATION":
            raise ValueError("Blender verification resolver requires a VERIFICATION step.")

        decisions = {}
        for object_name, expected_location in expected.items():
            result = execute(
                "inspect_object_transform",
                {"file_name": file_name, "object_name": object_name},
            )
            decisions[object_name] = verify_object_location(
                result,
                object_name=object_name,
                expected_location=expected_location,
                tolerance=tolerance,
            )

        satisfied = all(decision.ok for decision in decisions.values())
        return {
            "satisfied": satisfied,
            "reason": "all object locations match expected state" if satisfied else "one or more object locations differ from expected state",
            "evidence": {
                object_name: {
                    "ok": decision.ok,
                    "reason": decision.reason,
                    "details": dict(decision.evidence),
                }
                for object_name, decision in decisions.items()
            },
        }

    return resolve
