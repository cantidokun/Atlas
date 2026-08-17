"""Lightweight aggregate for assembling an Atlas Digital Twin state.

The aggregate is intentionally a container and consistency boundary, not an
execution engine. Tool adapters and the existing Atlas control architecture
remain responsible for planning, authorization, execution, and verification.
"""

from dataclasses import dataclass
from typing import Tuple

from planning.digital_twin_entity import DigitalTwinEntity
from planning.digital_twin_relationships import EntityRelationship
from planning.digital_twin_revision import DigitalTwinRevision


@dataclass(frozen=True)
class DigitalTwinAggregate:
    twin_id: str
    revision: DigitalTwinRevision
    entities: Tuple[DigitalTwinEntity, ...] = ()
    relationships: Tuple[EntityRelationship, ...] = ()

    def __post_init__(self) -> None:
        if not self.twin_id.strip():
            raise ValueError("twin_id must not be empty")
        if self.revision.twin_id != self.twin_id:
            raise ValueError("revision belongs to a different Digital Twin")
        for entity in self.entities:
            if entity.twin_id != self.twin_id:
                raise ValueError("entity belongs to a different Digital Twin")

    def entity(self, entity_id: str) -> DigitalTwinEntity:
        normalized = entity_id.strip()
        for entity in self.entities:
            if entity.entity_id == normalized:
                return entity
        raise KeyError(entity_id)
