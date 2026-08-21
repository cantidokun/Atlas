"""Autonomous verification resolvers for Blender postconditions."""
from __future__ import annotations

from typing import Any, Dict, Tuple

from planning.blender_task_verifier import verify_object_location
from planning.future_generator import FutureStep


def object_location_resolver(
    *,
    file_name: str,
    object_name: str,
    expected_location: Tuple[float, float, float],
    tolerance: float = 1e-4,
):
    """Build a resolver that acquires fresh Blender evidence and evaluates it.

    The resolver intentionally performs inspection through the runtime's
    authorized executor. It never trusts the mutation result as proof of the
    final state.
    """
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
