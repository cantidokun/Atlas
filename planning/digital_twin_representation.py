"""Engine-independent contracts for Atlas Digital Twin representations.

Atlas owns the canonical Digital Twin. Production tools such as Blender and
Unreal expose representations of a specific Atlas revision through adapters.
This module defines the metadata boundary without importing either tool.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ProductionTool(str, Enum):
    BLENDER = "blender"
    UNREAL = "unreal"
    PHOTOGRAMMETRY = "photogrammetry"
    OTHER = "other"


class RepresentationState(str, Enum):
    CREATED = "created"
    SYNCED = "synced"
    MODIFIED = "modified"
    VERIFIED = "verified"
    STALE = "stale"
    INVALID = "invalid"


@dataclass(frozen=True)
class TwinRepresentation:
    """A production-side representation derived from one Atlas revision."""

    twin_id: str
    representation_id: str
    source_revision_id: str
    production_tool: ProductionTool
    external_id: str
    state: RepresentationState = RepresentationState.CREATED
    source_fingerprint: Optional[str] = None

    def __post_init__(self) -> None:
        for name, value in (
            ("twin_id", self.twin_id),
            ("representation_id", self.representation_id),
            ("source_revision_id", self.source_revision_id),
            ("external_id", self.external_id),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")


def create_representation_contract(
    twin_id: str,
    representation_id: str,
    source_revision_id: str,
    production_tool: ProductionTool,
    external_id: str,
    source_fingerprint: Optional[str] = None,
) -> TwinRepresentation:
    """Create metadata describing a tool-side representation.

    This does not create or modify anything in the production tool. The adapter
    is responsible for the actual import/export or scene operation.
    """
    return TwinRepresentation(
        twin_id=twin_id,
        representation_id=representation_id,
        source_revision_id=source_revision_id,
        production_tool=production_tool,
        external_id=external_id,
        source_fingerprint=source_fingerprint,
    )


def mark_representation_state(
    representation: TwinRepresentation,
    state: RepresentationState,
) -> TwinRepresentation:
    """Return a new immutable representation record with updated state."""
    return TwinRepresentation(
        twin_id=representation.twin_id,
        representation_id=representation.representation_id,
        source_revision_id=representation.source_revision_id,
        production_tool=representation.production_tool,
        external_id=representation.external_id,
        state=state,
        source_fingerprint=representation.source_fingerprint,
    )
