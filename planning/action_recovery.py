"""Safety-first recovery decisions for failed Atlas actions."""
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass(frozen=True)
class RecoveryDecision:
    recoverable: bool
    require_fresh_evidence: bool
    retry_authorized: bool
    reason: str

def assess_action_failure(*, action_index: int, action_result: Optional[Dict[str, Any]], remaining_actions: int) -> RecoveryDecision:
    if action_index < 0:
        raise ValueError("action_index must be non-negative")
    if remaining_actions < 0:
        raise ValueError("remaining_actions must be non-negative")
    if not isinstance(action_result, dict):
        return RecoveryDecision(False, True, False, "Action failure result is missing or malformed.")
    return RecoveryDecision(True, True, False, "Execution state may have changed; obtain fresh read-only evidence and require a new validated and explicitly authorized plan before retrying.")
