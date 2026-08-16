"""Safety-first recovery decisions for failed Atlas actions.

A failed or partially completed write must never be retried blindly. Recovery
first requires fresh read-only evidence, and a new action proposal must pass
through the normal authorization gate again.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RecoveryDecision:
    """Describe what the controller may do after an execution failure."""

    recoverable: bool
    require_fresh_evidence: bool
    retry_authorized: bool
    reason: str


def assess_action_failure(
    *,
    action_index: int,
    action_result: Optional[Dict[str, Any]],
    remaining_actions: int,
) -> RecoveryDecision:
    """Return a conservative recovery decision after a failed action.

    Recovery is never authorized directly from a failed write. Fresh evidence
    is mandatory, and the caller must obtain a new validated/authorized plan.
    """
    if action_index < 0:
        raise ValueError("action_index must be non-negative")
    if remaining_actions < 0:
        raise ValueError("remaining_actions must be non-negative")

    if not isinstance(action_result, dict):
        return RecoveryDecision(
            recoverable=False,
            require_fresh_evidence=True,
            retry_authorized=False,
            reason="Action failure result is missing or malformed.",
        )

    return RecoveryDecision(
        recoverable=True,
        require_fresh_evidence=True,
        retry_authorized=False,
        reason=(
            "Execution state may have changed; obtain fresh read-only evidence "
            "and require a new validated and explicitly authorized plan before retrying."
        ),
    )
