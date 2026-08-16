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


def extract_task_plan_proposal(content: str) -> Optional[Dict[str, Any]]:
    """Extract one JSON object following the Atlas task-plan marker.

    A marked object is not considered an Atlas plan unless it uses the
    expected top-level envelope. This prevents a different JSON schema from
    being silently interpreted as an empty plan.
    """
    if not content:
        return None

    match = re.search(
        r"ATLAS_TASK_PLAN\s*:\s*(\{[\s\S]*\})",
        content,
        re.IGNORECASE,
    )
    if not match:
        return None

    try:
        parsed = json.loads(match.group(1))
    except (TypeError, ValueError):
        return None

    if not isinstance(parsed, dict):
        return None
    if not REQUIRED_PLAN_KEYS.issubset(parsed):
        return None
    return parsed


def build_proposal_from_qwen(
    content: str,
    allowed_tools=None,
) -> Optional[TaskPlanProposal]:
    """Extract and validate a Qwen proposal without authorizing execution."""
    raw = extract_task_plan_proposal(content)
    if raw is None:
        return None
    return build_task_plan(raw, allowed_tools=allowed_tools)
