"""Fail-closed Unreal task decomposition.

This layer converts an Atlas-owned production intent into a deterministic,
ordered proposal. It does not authorize or execute the proposal.
"""

from dataclasses import dataclass
from typing import Mapping, Sequence, Tuple

from planning.unreal_agent import (
    UnrealCapability,
    UnrealOperation,
    UnrealOperationKind,
    UnrealTaskIntent,
)
from planning.unreal_capability_registry import UnrealCapabilityRegistry


@dataclass(frozen=True)
class UnrealTaskPlan:
    intent_id: str
    operations: Tuple[UnrealOperation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.intent_id, str) or not self.intent_id.strip():
            raise ValueError("UnrealTaskPlan intent_id must be a non-empty string")
        if not self.operations:
            raise ValueError("UnrealTaskPlan must contain at least one operation")


class UnrealTaskPlanner:
    def __init__(self, capabilities=None):
        self.capabilities = capabilities or UnrealCapabilityRegistry()

    @staticmethod
    def _validate_intent(intent: UnrealTaskIntent) -> None:
        """Fail-closed validation of the intent before any planning work."""
        if not isinstance(intent, UnrealTaskIntent):
            raise TypeError("intent must be an UnrealTaskIntent instance")
        if not intent.target_entity_ids:
            raise ValueError("Unreal task intents require explicit target entity IDs")
        for eid in intent.target_entity_ids:
            if not isinstance(eid, str) or not eid.strip():
                raise ValueError("target_entity_ids must contain only non-empty strings")

    def plan_inspection(self, intent: UnrealTaskIntent) -> UnrealTaskPlan:
        self._validate_intent(intent)
        return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_inspection(intent))

    def plan_material_variant(self, intent: UnrealTaskIntent) -> UnrealTaskPlan:
        self._validate_intent(intent)
        return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_material_variant(intent))

    def plan_actor_location_write(self, intent: UnrealTaskIntent, location: Mapping[str, float]) -> UnrealTaskPlan:
        """Plan one actor-location change with independent post-write inspection."""
        self._validate_intent(intent)
        return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_actor_location_write(intent, location))

    def plan_actor_location_sequence(self, intent: UnrealTaskIntent, locations: Sequence[Mapping[str, float]]) -> UnrealTaskPlan:
        """Plan ordered actor-location writes with proof after every mutation."""
        self._validate_intent(intent)
        return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_actor_location_sequence(intent, locations))


class UnrealAgentPlanBuilder:
    def __init__(self, capabilities: UnrealCapabilityRegistry):
        self.capabilities = capabilities

    @staticmethod
    def _require_targets(intent: UnrealTaskIntent) -> Tuple[str, ...]:
        targets = tuple(intent.target_entity_ids)
        if not targets:
            raise ValueError("Unreal task intents require explicit target entity IDs.")
        return targets

    @staticmethod
    def _validate_location(location: Mapping[str, float]) -> Mapping[str, float]:
        if not isinstance(location, Mapping):
            raise TypeError("location must be a mapping")
        if set(location.keys()) != {"x", "y", "z"}:
            raise ValueError("location must contain exactly x, y, and z")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in location.values()):
            raise TypeError("location coordinates must be numeric")
        return dict(location)

    def _operation(self, capability, kind, name, entity_ids, arguments=None):
        self.capabilities.validate(capability, kind)
        operation_arguments = {"entity_ids": entity_ids}
        if arguments:
            operation_arguments.update(arguments)
        operation = UnrealOperation(
            capability=capability,
            kind=kind,
            name=name,
            arguments=operation_arguments,
            entity_ids=entity_ids,
        )
        return self.capabilities.validate_operation(operation)

    def for_inspection(self, intent):
        entity_ids = self._require_targets(intent)
        return (
            self._operation(UnrealCapability.INSPECT_ACTOR, UnrealOperationKind.READ, "inspect_target_actors", entity_ids),
            self._operation(UnrealCapability.INSPECT_ACTOR, UnrealOperationKind.VERIFY, "verify_target_actor_mapping", entity_ids),
        )

    def for_material_variant(self, intent):
        entity_ids = self._require_targets(intent)
        return (
            self._operation(UnrealCapability.INSPECT_ACTOR, UnrealOperationKind.READ, "inspect_target_actors", entity_ids),
            self._operation(UnrealCapability.MATERIAL, UnrealOperationKind.READ, "inspect_material_state", entity_ids),
            self._operation(UnrealCapability.MATERIAL, UnrealOperationKind.WRITE, "apply_material_variant", entity_ids),
            self._operation(UnrealCapability.MATERIAL, UnrealOperationKind.VERIFY, "verify_material_variant", entity_ids),
        )

    def for_actor_location_write(self, intent, location: Mapping[str, float]):
        entity_ids = self._require_targets(intent)
        location = self._validate_location(location)
        return (
            self._operation(UnrealCapability.INSPECT_ACTOR, UnrealOperationKind.READ, "inspect_target_actors", entity_ids),
            self._operation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE, "set_actor_location", entity_ids, {"location": location}),
            self._operation(UnrealCapability.INSPECT_ACTOR, UnrealOperationKind.VERIFY, "verify_target_actor_mapping", entity_ids),
        )

    def for_actor_location_sequence(self, intent, locations: Sequence[Mapping[str, float]]):
        entity_ids = self._require_targets(intent)
        if isinstance(locations, (str, bytes)) or not isinstance(locations, Sequence):
            raise TypeError("locations must be a sequence of mappings")
        if not locations:
            raise ValueError("locations must contain at least one location")

        operations = [
            self._operation(UnrealCapability.INSPECT_ACTOR, UnrealOperationKind.READ, "inspect_target_actors", entity_ids)
        ]
        for location in locations:
            location = self._validate_location(location)
            operations.extend((
                self._operation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE, "set_actor_location", entity_ids, {"location": location}),
                self._operation(UnrealCapability.INSPECT_ACTOR, UnrealOperationKind.VERIFY, "verify_target_actor_mapping", entity_ids),
            ))
        return tuple(operations)
