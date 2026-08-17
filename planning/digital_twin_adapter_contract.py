"""Validation and adapter-boundary contracts for Atlas production tools.

Atlas owns canonical Digital Twin state. Tool adapters translate between Atlas
state and a production environment; they do not become the source of truth.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Tuple

from planning.digital_twin_representation import RepresentationState, TwinRepresentation


def is_stale(representation: TwinRepresentation, current_revision_id: str) -> bool:
    """Return whether a representation is derived from an older Atlas revision."""
    if not current_revision_id.strip():
        raise ValueError("current_revision_id must not be empty")
    return representation.source_revision_id != current_revision_id or representation.state is RepresentationState.STALE


def require_current_representation(representation: TwinRepresentation, current_revision_id: str) -> TwinRepresentation:
    """Reject a stale representation before it can be used for production work."""
    if is_stale(representation, current_revision_id):
        raise ValueError("representation is stale relative to the current Atlas revision")
    return representation


@dataclass(frozen=True)
class ToolEvidence:
    """Authoritative evidence returned by a production-tool adapter."""

    representation_id: str
    evidence_id: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.representation_id.strip() or not self.evidence_id.strip():
            raise ValueError("evidence identity fields must not be empty")


@dataclass(frozen=True)
class ToolActionResult:
    """Result metadata returned after an already-authorized tool action."""

    representation_id: str
    action_id: str
    success: bool
    evidence_ids: Tuple[str, ...] = ()


class DigitalTwinToolAdapter(Protocol):
    """Engine-neutral contract for Blender, Unreal, and future tool adapters.

    Implementations must not decide authorization, invent canonical Twin state,
    or silently promote tool state to canonical state. Execution remains behind
    Atlas's existing authorization/action-plan boundary.
    """

    def inspect(self, representation: TwinRepresentation) -> ToolEvidence:
        """Collect authoritative read-only evidence from the production tool."""
        ...

    def apply_authorized_action(
        self,
        representation: TwinRepresentation,
        action_name: str,
        arguments: Mapping[str, Any],
    ) -> ToolActionResult:
        """Execute one action that Atlas has already authorized."""
        ...

    def synchronize(self, representation: TwinRepresentation) -> ToolEvidence:
        """Synchronize/read back tool state into evidence without changing canonical state."""
        ...
