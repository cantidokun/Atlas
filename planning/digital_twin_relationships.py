"""Explicit semantic relationships between Atlas Digital Twin entities."""

from dataclasses import dataclass
from enum import Enum


class RelationshipType(str, Enum):
    PART_OF = "part_of"
    CONTAINS = "contains"
    ADJACENT_TO = "adjacent_to"
    ATTACHED_TO = "attached_to"
    ALIGNED_WITH = "aligned_with"
    ABOVE = "above"
    BELOW = "below"
    INSIDE = "inside"
    OUTSIDE = "outside"
    RELATED_TO = "related_to"


@dataclass(frozen=True)
class EntityRelationship:
    source_entity_id: str
    relationship: RelationshipType
    target_entity_id: str

    def __post_init__(self) -> None:
        if not self.source_entity_id.strip() or not self.target_entity_id.strip():
            raise ValueError("relationship entity ids must not be empty")
        if self.source_entity_id == self.target_entity_id:
            raise ValueError("entity relationship cannot target itself")
