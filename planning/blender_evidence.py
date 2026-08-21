"""Normalization of verified Blender tool results into agent evidence."""

from __future__ import annotations

from typing import Any, Dict

from planning.blender_agent_state import BlenderObservation


class BlenderEvidenceError(ValueError):
    """Raised when execution output cannot safely become agent evidence."""


def normalize_blender_result(tool: str, result: Any) -> BlenderObservation:
    """Turn a successful Blender inspection result into immutable agent input."""
    if not isinstance(tool, str) or not tool.strip():
        raise BlenderEvidenceError("tool must be non-empty")
    if not isinstance(result, dict):
        raise BlenderEvidenceError("Blender result must be an object")
    if result.get("status") not in {"ok", "success"}:
        raise BlenderEvidenceError("only successful Blender results may become evidence")

    facts: Dict[str, Any] = dict(result)
    facts.pop("status", None)
    return BlenderObservation(source=tool, facts=facts, verified=True)
