"""Deterministic composite Unreal production operations.

A composite operation groups already-authorized primitive actor mutations into
one auditable production task. It does not introduce a new Unreal transport
primitive; execution remains delegated to the existing operation executor.
"""
from dataclasses import dataclass
from typing import Any, Mapping, Sequence, Tuple


_ALLOWED = {
    "set_actor_location",
    "set_actor_rotation",
    "set_actor_scale",
    "apply_material_variant",
    "apply_niagara_variant",
}


@dataclass(frozen=True)
class CompositeActorProductionOperation:
    entity_ids: Tuple[str, ...]
    operations: Tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        if not self.entity_ids or any(not isinstance(x, str) or not x.strip() for x in self.entity_ids):
            raise ValueError("entity_ids must contain non-empty strings")
        if not self.operations:
            raise ValueError("operations must not be empty")
        for operation in self.operations:
            if not isinstance(operation, Mapping):
                raise TypeError("each operation must be a mapping")
            name = operation.get("name")
            if name not in _ALLOWED:
                raise ValueError(f"unsupported composite operation: {name!r}")
            ids = tuple(operation.get("entity_ids", self.entity_ids))
            if not ids or any(entity_id not in self.entity_ids for entity_id in ids):
                raise ValueError("operation entity_ids must be contained in composite entity_ids")

    def ordered_operations(self) -> Tuple[Mapping[str, Any], ...]:
        """Return a stable order: transforms, material, then Niagara."""
        order = {
            "set_actor_location": 10,
            "set_actor_rotation": 20,
            "set_actor_scale": 30,
            "apply_material_variant": 40,
            "apply_niagara_variant": 50,
        }
        return tuple(sorted(self.operations, key=lambda op: order[op["name"]]))


def build_composite_actor_operation(
    entity_ids: Sequence[str], operations: Sequence[Mapping[str, Any]]
) -> CompositeActorProductionOperation:
    return CompositeActorProductionOperation(tuple(entity_ids), tuple(operations))
