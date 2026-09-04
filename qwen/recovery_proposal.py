"""Intent-only Qwen proposals for Atlas production recovery.

Qwen may suggest the canonical workflow/version/parameters to re-establish after
an Atlas failure. Atlas remains responsible for validating whether that intent
can become a concrete replacement plan and for authorizing any writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from qwen.production_proposal import (
    QwenProductionProposal,
    QwenProductionProposalError,
    validate_qwen_production_proposal,
)


@dataclass(frozen=True)
class QwenRecoveryProposal:
    """Validated recovery intent with no executable authority."""

    production: QwenProductionProposal
    reason: str

    def snapshot(self) -> Dict[str, Any]:
        return {
            "production": self.production.snapshot(),
            "reason": self.reason,
        }


def validate_qwen_recovery_proposal(proposal: Any) -> QwenRecoveryProposal:
    if not isinstance(proposal, dict):
        raise QwenProductionProposalError("Qwen recovery proposal must be an object.")
    allowed_keys = {"workflow", "version", "parameters", "reason"}
    unexpected = sorted(set(proposal) - allowed_keys)
    if unexpected:
        raise QwenProductionProposalError(
            f"Qwen recovery proposal contains unexpected fields: {unexpected}"
        )
    reason = proposal.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise QwenProductionProposalError("Qwen recovery proposal reason must be a non-empty string.")
    production = validate_qwen_production_proposal(
        {key: proposal[key] for key in ("workflow", "version", "parameters") if key in proposal}
    )
    return QwenRecoveryProposal(production=production, reason=reason.strip())


__all__ = ["QwenRecoveryProposal", "validate_qwen_recovery_proposal"]
