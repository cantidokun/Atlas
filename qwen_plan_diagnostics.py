"""Diagnostics for structured Qwen task-plan proposals.

This layer is read-only. It classifies model output so malformed or
unsupported proposals cannot be confused with an intentional empty plan.
"""

from dataclasses import dataclass
from typing import Any, Optional, Set

from qwen_planning_bridge import extract_task_plan_proposal, build_proposal_from_qwen
from task_planner import TaskPlanProposal, TaskPlanValidationError


@dataclass(frozen=True)
class QwenPlanDiagnostic:
    status: str
    message: str
    proposal: Optional[TaskPlanProposal] = None


def diagnose_qwen_plan(
    content: str,
    allowed_tools: Optional[Set[str]] = None,
) -> QwenPlanDiagnostic:
    """Classify Qwen output without executing or authorizing anything."""
    if not content or not content.strip():
        return QwenPlanDiagnostic("malformed", "Qwen returned no plan text.")

    raw = extract_task_plan_proposal(content)
    if raw is None:
        return QwenPlanDiagnostic(
            "malformed",
            "Qwen output did not contain a valid ATLAS_TASK_PLAN JSON object.",
        )

    if not isinstance(raw.get("evidence", []), list) or not isinstance(raw.get("actions", []), list):
        return QwenPlanDiagnostic(
            "malformed",
            "ATLAS_TASK_PLAN must contain 'evidence' and 'actions' lists.",
        )

    try:
        proposal = build_proposal_from_qwen(content, allowed_tools=allowed_tools)
    except TaskPlanValidationError as error:
        return QwenPlanDiagnostic("unsupported", str(error))

    if proposal is None:
        return QwenPlanDiagnostic("malformed", "Qwen plan could not be parsed.")

    return QwenPlanDiagnostic("valid", "Qwen proposal matches the Atlas plan schema.", proposal)
