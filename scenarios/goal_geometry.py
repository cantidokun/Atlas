"""Reusable soccer-field target predicates for Atlas.

These predicates are application-owned: Qwen may propose evidence and actions,
but it never supplies the predicate that decides whether the target is met.
"""

from typing import Any, Dict

from planning.conditional_action import TargetCondition


EXPECTED_MIDPOINT = [0.0, 0.0, 0.0]
EXPECTED_DISTANCE = 10.466


def goal_center_alignment(evidence: Dict[str, Any]) -> bool:
    """Return True when the goal is centered and symmetrically spaced."""
    return (
        evidence["midpoint"] == EXPECTED_MIDPOINT
        and evidence["symmetric_about_origin"] is True
        and evidence["distance"] == EXPECTED_DISTANCE
    )


def centered_goal_condition() -> TargetCondition:
    """Build the Python-owned condition for the centered-goal scenario."""
    return TargetCondition(
        predicate=goal_center_alignment,
        name="centered_goal_geometry",
    )
