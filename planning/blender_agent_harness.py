"""Deterministic harness for exercising the Blender Agent loop without Blender.

The harness is a test/control shell around the agent: it supplies synthetic
scene evidence, captures proposed actions, and records verified outcomes. It
is deliberately not an execution authority and never bypasses authorization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class BlenderEvidence:
    """A normalized observation produced by inspection or verification."""

    source: str
    facts: Dict[str, Any]


@dataclass
class BlenderAgentHarness:
    """Record agent observations and outcomes for deterministic tests."""

    evidence: List[BlenderEvidence] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    outcomes: List[Dict[str, Any]] = field(default_factory=list)

    def observe(self, source: str, **facts: Any) -> BlenderEvidence:
        evidence = BlenderEvidence(source=source, facts=dict(facts))
        self.evidence.append(evidence)
        return evidence

    def record_action(self, tool: str, arguments: Dict[str, Any]) -> None:
        self.actions.append({"tool": tool, "arguments": dict(arguments)})

    def record_outcome(self, *, tool: str, verified: bool, complete: bool, details: Any = None) -> None:
        self.outcomes.append({
            "tool": tool,
            "verified": verified,
            "complete": complete,
            "details": details,
        })

    def latest_evidence(self) -> BlenderEvidence | None:
        return self.evidence[-1] if self.evidence else None

    def reset(self) -> None:
        self.evidence.clear()
        self.actions.clear()
        self.outcomes.clear()
