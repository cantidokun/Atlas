"""Deterministic final-answer recovery for controller-owned modifications.

The normal Atlas agent lets Qwen draft the final response and Python validate
it. Controller-owned tasks have a second, safer completion path: once the
controller has completed all writes and independent verification, Python can
build a complete state-aware report directly from the evidence ledger.

This is a recovery path, not a replacement for Qwen reasoning. It exists so a
successful modification cannot fail solely because Qwen omits required before,
target, or after-state fields during its final response.
"""

from typing import Any, Dict, List, Optional


def _successful_relationships(evidence_ledger: List[dict]) -> List[dict]:
    return [
        item["result"]
        for item in evidence_ledger
        if item.get("tool") == "inspect_object_relationship"
        and item.get("successful", True) is not False
        and isinstance(item.get("result"), dict)
        and "error" not in item["result"]
    ]


def _successful_moves(tool_execution_history: List[dict]) -> int:
    return sum(
        1
        for item in tool_execution_history
        if item.get("tool") == "move_object"
        and item.get("successful") is True
        and isinstance(item.get("result"), dict)
        and item["result"].get("status") == "moved"
    )


def _location(result: Dict[str, Any], side: str) -> Optional[List[float]]:
    obj = result.get(side, {})
    value = obj.get("location")
    if not isinstance(value, list) or len(value) != 3:
        return None
    return value


def _fmt_vector(values: List[float]) -> str:
    """Format a 3D vector and prevent negative zero after rounding."""
    normalized = []
    for value in values:
        numeric = float(value)
        rounded = round(numeric, 3)
        normalized.append(0.0 if rounded == 0 else rounded)
    return "[" + ", ".join(f"{value:.3f}" for value in normalized) + "]"


def build_midpoint_final_answer(
    evidence_ledger: List[dict],
    tool_execution_history: List[dict],
) -> Optional[str]:
    """Build a complete final report when a midpoint controller is complete.

    Returns ``None`` unless the evidence contains a complete BEFORE snapshot,
    a calculated target can be derived from it, successful writes, and a
    complete FINAL VERIFIED relationship snapshot at the required midpoint.
    """
    relationships = _successful_relationships(evidence_ledger)
    if not relationships or _successful_moves(tool_execution_history) == 0:
        return None

    before = relationships[0]
    after = relationships[-1]

    before_a = _location(before, "object_a")
    before_b = _location(before, "object_b")
    midpoint_before = before.get("midpoint")

    after_a = _location(after, "object_a")
    after_b = _location(after, "object_b")
    midpoint_after = after.get("midpoint")

    if any(
        not isinstance(value, list) or len(value) != 3
        for value in (before_a, before_b, midpoint_before, after_a, after_b, midpoint_after)
    ):
        return None

    if midpoint_after != [0.0, 0.0, 0.0]:
        return None

    target_a = [before_a[i] - midpoint_before[i] for i in range(3)]
    target_b = [before_b[i] - midpoint_before[i] for i in range(3)]
    adjustment = [-midpoint_before[i] for i in range(3)]

    object_a_name = before.get("object_a", {}).get("name", "Object A")
    object_b_name = before.get("object_b", {}).get("name", "Object B")
    distance_after = after.get("distance")
    symmetric_after = after.get("symmetric_about_origin")

    distance_line = (
        f"- Distance: {float(distance_after):.3f} units\n"
        if isinstance(distance_after, (int, float))
        else ""
    )
    symmetry_line = (
        f"- Symmetric about origin: {str(symmetric_after).lower()}\n"
        if isinstance(symmetric_after, bool)
        else ""
    )

    return (
        "The authorized midpoint modification is complete and independently verified.\n\n"
        "INITIAL MEASURED STATE\n"
        f"- {object_a_name}: {_fmt_vector(before_a)}\n"
        f"- {object_b_name}: {_fmt_vector(before_b)}\n"
        f"- Midpoint: {_fmt_vector(midpoint_before)}\n\n"
        "CALCULATED TARGET STATE\n"
        f"- {object_a_name}: {_fmt_vector(target_a)}\n"
        f"- {object_b_name}: {_fmt_vector(target_b)}\n"
        f"- Positional adjustment: {_fmt_vector(adjustment)}\n\n"
        "FINAL VERIFIED STATE\n"
        f"- {object_a_name}: {_fmt_vector(after_a)}\n"
        f"- {object_b_name}: {_fmt_vector(after_b)}\n"
        f"- Midpoint: {_fmt_vector(midpoint_after)}\n"
        f"{distance_line}"
        f"{symmetry_line}"
        "- Independent post-modification relationship inspection: verified"
    )
