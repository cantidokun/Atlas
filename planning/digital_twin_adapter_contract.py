"""Validation helpers for Atlas-to-tool representation boundaries."""

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
