"""Strict provider-output adapter for Qwen soccer-production proposals.

This module accepts provider responses only as decoded JSON-like values and
routes them through the proposal validator. It never exposes executors,
authorization, persistence, or recovery capabilities.
"""

from __future__ import annotations

import json
from typing import Any

from qwen.production_proposal import (
    QwenProductionProposal,
    QwenProductionProposalError,
    validate_qwen_production_proposal,
)


def parse_qwen_production_output(raw_output: Any) -> QwenProductionProposal:
    """Parse one provider output into a validated proposal-only object."""
    if isinstance(raw_output, (bytes, bytearray)):
        try:
            raw_output = raw_output.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise QwenProductionProposalError("Qwen provider output must be UTF-8 JSON.") from exc
    if isinstance(raw_output, str):
        try:
            raw_output = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise QwenProductionProposalError("Qwen provider output is not valid JSON.") from exc
    return validate_qwen_production_proposal(raw_output)


__all__ = ["parse_qwen_production_output"]
