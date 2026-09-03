"""Proposal-only Qwen boundary for Atlas soccer-production workflows.

Qwen may propose a canonical workflow identity, version, and parameters. Atlas
resolves and validates that proposal against the trusted soccer-production
catalog and returns one semantic production task. No tool execution,
authorization, scheduling, or recovery behavior is exposed here.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Optional

from planning.production_task import ProductionTaskDefinition
from planning.soccer_production_catalog import compile_soccer_production_workflow


@dataclass(frozen=True)
class QwenProductionProposal:
    """Validated model proposal containing only semantic workflow intent."""

    workflow: str
    parameters: Dict[str, Any]
    version: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", deepcopy(self.parameters))

    def snapshot(self) -> Dict[str, Any]:
        """Return a detached, JSON-friendly snapshot of the proposal."""
        snapshot = {
            "workflow": self.workflow,
            "version": self.version,
            "parameters": deepcopy(self.parameters),
        }
        for key, value in snapshot["parameters"].items():
            if isinstance(value, tuple):
                snapshot["parameters"][key] = list(value)
        return snapshot


class QwenProductionProposalError(ValueError):
    """Raised when a Qwen production proposal is malformed or unsupported."""


def validate_qwen_production_proposal(proposal: Any) -> QwenProductionProposal:
    """Validate the proposal envelope without executing or authorizing anything."""
    if not isinstance(proposal, dict):
        raise QwenProductionProposalError("Qwen production proposal must be an object.")
    allowed_keys = {"workflow", "version", "parameters"}
    unexpected = sorted(set(proposal) - allowed_keys)
    if unexpected:
        raise QwenProductionProposalError(
            f"Qwen production proposal contains unexpected fields: {unexpected}"
        )
    workflow = proposal.get("workflow")
    if not isinstance(workflow, str) or not workflow.strip():
        raise QwenProductionProposalError(
            "Qwen production proposal workflow must be a non-empty string."
        )
    version = proposal.get("version")
    if version is not None and (
        not isinstance(version, int) or isinstance(version, bool) or version < 1
    ):
        raise QwenProductionProposalError(
            "Qwen production proposal version must be a positive integer."
        )
    parameters = proposal.get("parameters")
    if not isinstance(parameters, dict):
        raise QwenProductionProposalError(
            "Qwen production proposal parameters must be an object."
        )
    return QwenProductionProposal(
        workflow=workflow,
        parameters=parameters,
        version=version,
    )


def compile_qwen_production_proposal(proposal: Any) -> ProductionTaskDefinition:
    """Resolve a validated Qwen proposal into the canonical semantic task contract."""
    validated = validate_qwen_production_proposal(proposal)
    try:
        return compile_soccer_production_workflow(
            validated.workflow,
            validated.parameters,
            version=validated.version,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise QwenProductionProposalError(str(exc)) from exc


__all__ = [
    "QwenProductionProposal",
    "QwenProductionProposalError",
    "compile_qwen_production_proposal",
    "validate_qwen_production_proposal",
]
