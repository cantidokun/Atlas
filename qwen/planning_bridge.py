"""Bridge structured Qwen output into inert Atlas planning proposals."""

import json
import re
from typing import Any, Dict, Optional

from task_planner import TaskPlanProposal, build_task_plan

PLAN_MARKER = "ATLAS_TASK_PLAN:"
REQUIRED_PLAN_KEYS = {"evidence", "actions"}


def _valid_plan_envelope(parsed: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(parsed, dict) or not REQUIRED_PLAN_KEYS.issubset(parsed):
        return None
    return parsed


def _legacy_flat_plan(parsed: Any) -> Optional[Dict[str, Any]]:
    """Normalize the strict three-item flat form emitted by local Qwen runs."""
    if not isinstance(parsed, list) or len(parsed) != 3:
        return None
    if not all(isinstance(item, dict) for item in parsed):
        return None
    if parsed[0].get("tool") != "inspect_object_relationship":
        return None
    if any(item.get("tool") != "move_object" for item in parsed[1:]):
        return None
    if not all({"tool", "arguments", "name"}.issubset(item) for item in parsed):
        return None
    return {"evidence": [parsed[0]], "actions": parsed[1:]}


def _json_candidates(content: str) -> list[str]:
    """Return only explicitly JSON-shaped payloads from a model response.

    Qwen occasionally wraps otherwise valid JSON in a markdown code fence. We
    tolerate that serialization quirk, but do not broadly scrape arbitrary text
    for JSON because that could hide malformed model output.
    """
    stripped = content.strip()
    candidates = [stripped]

    fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", stripped, re.IGNORECASE)
    if fenced:
        candidates.append(fenced.group(1).strip())

    return list(dict.fromkeys(candidates))


def _decode_json_candidates(content: str) -> list[Any]:
    parsed_values: list[Any] = []
    for candidate in _json_candidates(content):
        try:
            parsed_values.append(json.loads(candidate))
        except (TypeError, ValueError):
            continue
    return parsed_values


def extract_task_plan_proposal(content: str) -> Optional[Dict[str, Any]]:
    if not content:
        return None

    match = re.search(
        r"ATLAS_TASK_PLAN\s*:\s*(\{[\s\S]*\})\s*$",
        content,
        re.IGNORECASE,
    )
    if match:
        try:
            return _valid_plan_envelope(json.loads(match.group(1)))
        except (TypeError, ValueError):
            return None

    for parsed in _decode_json_candidates(content):
        envelope = _valid_plan_envelope(parsed)
        if envelope is not None:
            return envelope

        legacy = _legacy_flat_plan(parsed)
        if legacy is not None:
            return legacy

    return None


def build_proposal_from_qwen(content: str, allowed_tools=None) -> Optional[TaskPlanProposal]:
    raw = extract_task_plan_proposal(content)
    if raw is None:
        return None
    return build_task_plan(raw, allowed_tools=allowed_tools)
