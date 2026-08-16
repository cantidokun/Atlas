"""Bounded iterative Qwen evidence loop for Atlas.

Qwen may request read-only evidence. Python validates and executes those
requests, then sends only returned evidence back to Qwen. No write action is
authorized by this loop.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from evidence_plan import EvidencePlan, EvidenceRequest
from qwen_evidence_feedback import build_evidence_message
from qwen_planning_executor import execute_read_only_plan
from qwen_planning_runtime import TaskPlanProposal, parse_qwen_plan


@dataclass
class EvidenceLoopState:
    """State accumulated across bounded evidence rounds."""

    evidence: List[Dict[str, Any]]
    rounds: int = 0
    complete: bool = False


def proposal_to_evidence_plan(
    proposal: TaskPlanProposal,
    allowed_tools: Set[str],
) -> EvidencePlan:
    """Convert a validated model proposal into a deterministic evidence plan."""
    if proposal.actions:
        raise ValueError("Evidence loop refuses proposals containing actions")

    requests = []
    for item in proposal.evidence:
        if item.tool not in allowed_tools:
            raise ValueError(f"Evidence tool is not allowed: {item.tool}")
        requests.append(
            EvidenceRequest(
                tool=item.tool,
                arguments=dict(item.arguments),
                name=item.name or item.tool,
            )
        )
    return EvidencePlan(requests=requests)


def execute_evidence_proposal(
    proposal: TaskPlanProposal,
    allowed_tools: Set[str],
) -> Dict[str, Any]:
    """Execute one validated evidence proposal and return its evidence."""
    plan = proposal_to_evidence_plan(proposal, allowed_tools)
    collected = []

    while not plan.complete:
        request = plan.next_request
        assert request is not None
        single = TaskPlanProposal(
            evidence=[request],
            actions=[],
        )
        execution = execute_read_only_plan(single)
        result = execution["results"][0]
        plan.record_result(result, True)
        collected.append(result)

    return {
        "read_only": True,
        "execution_authorized": False,
        "results": collected,
        "plan": plan.snapshot(),
    }


def build_next_qwen_messages(
    prior_messages: List[Dict[str, str]],
    execution: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Append bounded verified evidence to the existing Qwen conversation."""
    messages = list(prior_messages)
    messages.append(build_evidence_message(execution["results"]))
    return messages


def parse_evidence_proposal(
    content: str,
    allowed_tools: Set[str],
) -> Optional[TaskPlanProposal]:
    """Parse only evidence-only Qwen proposals for this loop."""
    proposal = parse_qwen_plan(content, allowed_tools=allowed_tools)
    if proposal is None or proposal.actions:
        return None
    return proposal
