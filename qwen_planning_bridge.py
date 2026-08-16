"""Bridge structured Qwen output into inert Atlas planning proposals.

This module is deliberately small. It only extracts a JSON task-plan proposal
from model text and validates it through ``task_planner``. It never executes a
tool and never grants write authorization.
"""

import json
import re
from typing import Any, Dict, Optional

from task_planner import TaskPlanProposal, build_task_plan


PLAN_MARKER = "ATLAS_TASK_PLAN:"
REQUIRED_PLAN_KEYS = {"evidence", "actions"}


def _valid_plan_envelope(parsed: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(parsed, dict):
        return None
    if not REQUIRED_PLAN_KEYS.issubset(parsed):
        return None
    return parsed


def extract_task_plan_proposal(content: str) -> Optional[Dict[str, Any]]:
    """Extract one JSON task-plan proposal from model text.

    The preferred format is ``ATLAS_TASK_PLAN: { ... }``. For robustness,
    Qwen may also return the JSON object by itself when it follows the
    instruction to output only the plan. In either case the strict Atlas
    top-level envelope is still required, so unrelated JSON is not accepted.
    """
    if not content:
        return None

    match = re.search(
        r"ATLAS_TASK_PLAN\s*:\s*(\{[\s\S]*\})",
        content,
        re.IGNORECASE,
    )
    if match:
        try:
            return _valid_plan_envelope(json.loads(match.group(1)))
        except (TypeError, ValueError):
            return None

    stripped = content.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return None

    try:
        return _valid_plan_envelope(json.loads(stripped))
    except (TypeError, ValueError):
        return None


def build_proposal_from_qwen(
    content: str,
    allowed_tools=None,
) -> Optional[TaskPlanProposal]:
    """Extract and validate a Qwen proposal without authorizing execution."""
    raw = extract_task_plan_proposal(content)
    if raw is None:
        return None
    return build_task_plan(raw, allowed_tools=allowed_tools)
