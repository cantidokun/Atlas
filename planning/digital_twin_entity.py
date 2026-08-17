"""Engine-independent entity and semantic primitives for Atlas Digital Twins.

An entity is Atlas's canonical semantic handle for something in the twin. It is
not a Blender object or Unreal Actor. Tool-specific representations are linked
later through adapters/representations.
"""

from dataclasses import dataclass, field
from typing import FrozenSet, Optional, Tuple

from planning.digital_twin_spatial import SpatialPose


@dataclass(frozen=True)
class SemanticAttribute:
    """A normalized semantic property attached to a canonical entity."""

    key: str
    value: str

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("semantic attribute key must not be empty")
        if not self.value.strip():
            raise ValueError("semantic attribute value must not be empty")


@dataclass(frozen=True)
class DigitalTwinEntity:
    """Canonical Atlas entity, independent of any production tool."""

    entity_id: str
    entity_type: str
    twin_id: str
    semantic_attributes: Tuple[SemanticAttribute, ...] = ()
    tags: FrozenSet[str] = field(default_factory=frozenset)
    spatial_pose: Optional[SpatialPose] = None
    parent_entity_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.entity_id.strip():
            raise ValueError("entity_id must not be empty")
        if not self.entity_type.strip():
            raise ValueError("entity_type must not be empty")
        if not self.twin_id.strip():
            raise ValueError("twin_id must not be empty")
        if self.parent_entity_id == self.entity_id:
            raise ValueError("entity cannot be its own parent")
        if self.parent_entity_id is not None and not self.parent_entity_id.strip():
            raise ValueError("parent_entity_id must be non-empty when provided")

        normalized_tags = frozenset(tag.strip().lower() for tag in self.tags if tag.strip())
        object.__setattr__(self, "tags", normalized_tags)

        if self.spatial_pose is not None and self.spatial_pose.parent_entity_id not in (None, self.parent_entity_id):
            raise ValueError("spatial pose parent must match entity parent")

    def semantic_value(self, key: str) -> Optional[str]:
        normalized = key.strip().lower()
        for attribute in self.semantic_attributes:
            if attribute.key.strip().lower() == normalized:
                return attribute.value
        return None

    def has_tag(self, tag: str) -> bool:
        return tag.strip().lower() in self.tags


def create_entity(
    twin_id: str,
    entity_id: str,
    entity_type: str,
    *,
    semantic_attributes: Tuple[SemanticAttribute, ...] = (),
    tags: FrozenSet[str] = frozenset(),
    spatial_pose: Optional[SpatialPose] = None,
    parent_entity_id: Optional[str] = None,
) -> DigitalTwinEntity:
    """Create a canonical semantic entity without creating a tool representation."""
    return DigitalTwinEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        twin_id=twin_id,
        semantic_attributes=semantic_attributes,
        tags=tags,
        spatial_pose=spatial_pose,
        parent_entity_id=parent_entity_id,
    )
