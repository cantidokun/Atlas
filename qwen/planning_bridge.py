"""Bridge structured Qwen output into inert Atlas planning proposals."""
import json, re
from typing import Any, Dict, Optional
from task_planner import TaskPlanProposal, build_task_plan
PLAN_MARKER = "ATLAS_TASK_PLAN:"
REQUIRED_PLAN_KEYS = {"evidence", "actions"}

def _valid_plan_envelope(parsed: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(parsed, dict) or not REQUIRED_PLAN_KEYS.issubset(parsed): return None
    return parsed

def _legacy_flat_plan(parsed: Any) -> Optional[Dict[str, Any]]:
    """Normalize the strict three-item flat form emitted by some local Qwen runs.

    Only the exact conditional shape is accepted: one evidence request followed
    by two move_object actions. This preserves the inert Python validation path
    while tolerating a model serialization quirk.
    """
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

def extract_task_plan_proposal(content: str) -> Optional[Dict[str, Any]]:
    if not content: return None
    match = re.search(r"ATLAS_TASK_PLAN\s*:\s*(\{[\s\S]*\})", content, re.IGNORECASE)
    if match:
        try: return _valid_plan_envelope(json.loads(match.group(1)))
        except (TypeError, ValueError): return None
    stripped = content.strip()
    try:
        parsed = json.loads(stripped)
    except (TypeError, ValueError):
        return None
    envelope = _valid_plan_envelope(parsed)
    if envelope is not None:
        return envelope
    return _legacy_flat_plan(parsed)

def build_proposal_from_qwen(content: str, allowed_tools=None) -> Optional[TaskPlanProposal]:
    raw = extract_task_plan_proposal(content)
    if raw is None: return None
    return build_task_plan(raw, allowed_tools=allowed_tools)
