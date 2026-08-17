"""Canonical Digital Twin revision and variant primitives.

A revision represents a new authoritative state of the same Digital Twin.
Variants represent derived production representations and must never become
canonical revisions merely because a production tool wrote them.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from planning.digital_twin_identity import DigitalTwinIdentity


class RevisionKind(str, Enum):
    RECONSTRUCTION = "reconstruction"
    CLEANUP = "cleanup"
    CORRECTION = "correction"
    OPTIMIZATION = "optimization"
    OTHER = "other"


class RepresentationKind(str, Enum):
    BLENDER = "blender"
    UNREAL = "unreal"
    RENDER = "render"
    SHOT = "shot"
    OTHER = "other"


@dataclass(frozen=True)
class DigitalTwinRevision:
    twin_id: str
    revision_id: str
    sequence: int
    kind: RevisionKind
    source_revision_id: Optional[str] = None
    source_fingerprint: Optional[str] = None


@dataclass(frozen=True)
class DigitalTwinRepresentation:
    twin_id: str
    representation_id: str
    kind: RepresentationKind
    source_revision_id: str
    production_tool: str
    canonical: bool = False


def create_revision(
    identity: DigitalTwinIdentity,
    revision_id: str,
    sequence: int,
    kind: RevisionKind,
    source_revision: Optional[DigitalTwinRevision] = None,
) -> DigitalTwinRevision:
    """Create a revision while preserving canonical Digital Twin ownership."""
    if sequence < 1:
        raise ValueError("revision sequence must be >= 1")
    if source_revision is not None and source_revision.twin_id != identity.twin_id:
        raise ValueError("source revision belongs to a different Digital Twin")

    return DigitalTwinRevision(
        twin_id=identity.twin_id,
        revision_id=revision_id,
        sequence=sequence,
        kind=kind,
        source_revision_id=source_revision.revision_id if source_revision else None,
        source_fingerprint=identity.stable_fingerprint(),
    )


def create_representation(
    identity: DigitalTwinIdentity,
    representation_id: str,
    kind: RepresentationKind,
    source_revision: DigitalTwinRevision,
    production_tool: str,
) -> DigitalTwinRepresentation:
    """Create a derived production representation; never promote it implicitly."""
    if source_revision.twin_id != identity.twin_id:
        raise ValueError("source revision belongs to a different Digital Twin")
    if not production_tool.strip():
        raise ValueError("production_tool must not be empty")

    return DigitalTwinRepresentation(
        twin_id=identity.twin_id,
        representation_id=representation_id,
        kind=kind,
        source_revision_id=source_revision.revision_id,
        production_tool=production_tool.strip(),
        canonical=False,
    )


def next_revision_sequence(revisions: Tuple[DigitalTwinRevision, ...]) -> int:
    """Return the next canonical revision number."""
    if not revisions:
        return 1
    return max(revision.sequence for revision in revisions) + 1
