"""Engine-neutral Unreal Agent architecture primitives.

The Unreal Agent is a domain-specific planner/translator for Unreal production.
It does not own Atlas state, authorize actions, or bypass the generic Atlas
execution/verification architecture.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Tuple


class UnrealCapability(str, Enum):
    INSPECT_WORLD = "inspect_world"
    INSPECT_ACTOR = "inspect_actor"
    MODIFY_ACTOR = "modify_actor"
    INSPECT_ASSET = "inspect_asset"
    MODIFY_ASSET = "modify_asset"
    MATERIAL = "material"
    NIAGARA = "niagara"
    BLUEPRINT = "blueprint"
    SEQUENCER = "sequencer"
    RENDER = "render"


class UnrealOperationKind(str, Enum):
    READ = "read"
    WRITE = "write"
    VERIFY = "verify"


@dataclass(frozen=True)
class UnrealOperation:
    """One structured Unreal operation proposed for Atlas authorization."""

    capability: UnrealCapability
    kind: UnrealOperationKind
    name: str
    arguments: Mapping[str, Any]
    entity_ids: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("operation name must not be empty")
        for entity_id in self.entity_ids:
            if not entity_id.strip():
                raise ValueError("entity_ids must not contain empty values")


@dataclass(frozen=True)
class UnrealTaskIntent:
    """Atlas-owned task intent translated into Unreal-domain operations."""

    intent_id: str
    description: str
    target_entity_ids: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.intent_id.strip():
            raise ValueError("intent_id must not be empty")
        if not self.description.strip():
            raise ValueError("description must not be empty")


class UnrealAgent:
    """Translate a validated intent into structured Unreal operations.

    This class intentionally does not execute operations. Authorization and
    execution remain in Atlas's existing planning/action/adapter layers.
    """

    def propose_operations(self, intent: UnrealTaskIntent) -> Tuple[UnrealOperation, ...]:
        if not intent.target_entity_ids:
            raise ValueError("Unreal intent requires explicit Atlas target entities")
        return (
            UnrealOperation(
                capability=UnrealCapability.INSPECT_ACTOR,
                kind=UnrealOperationKind.READ,
                name="inspect_target_actors",
                arguments={"entity_ids": intent.target_entity_ids},
                entity_ids=intent.target_entity_ids,
            ),
        )
