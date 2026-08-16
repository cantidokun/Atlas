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


def extract_task_plan_proposal(content: str) -> Optional[Dict[str, Any]]:
    """Extract one JSON object following the Atlas task-plan marker."""
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

    return parsed if isinstance(parsed, dict) else None


def build_proposal_from_qwen(
    content: str,
    allowed_tools=None,
) -> Optional[TaskPlanProposal]:
    """Extract and validate a Qwen proposal without authorizing execution."""
    raw = extract_task_plan_proposal(content)
    if raw is None:
        return None
    return build_task_plan(raw, allowed_tools=allowed_tools)
