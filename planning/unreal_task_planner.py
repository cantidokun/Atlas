"""Fail-closed Unreal task decomposition.

This layer converts an Atlas-owned production intent into a deterministic,
ordered proposal. It does not authorize or execute the proposal.
"""

from dataclasses import dataclass
from typing import Tuple

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


class UnrealTaskPlanner:
    def __init__(self, capabilities=None):
        self.capabilities = capabilities or UnrealCapabilityRegistry()

    def plan_inspection(self, intent: UnrealTaskIntent) -> UnrealTaskPlan:
        operations = UnrealAgentPlanBuilder(self.capabilities).for_inspection(intent)
        return UnrealTaskPlan(intent.intent_id, operations)

    def plan_material_variant(self, intent: UnrealTaskIntent) -> UnrealTaskPlan:
        operations = UnrealAgentPlanBuilder(self.capabilities).for_material_variant(intent)
        return UnrealTaskPlan(intent.intent_id, operations)


class UnrealAgentPlanBuilder:
    def __init__(self, capabilities: UnrealCapabilityRegistry):
        self.capabilities = capabilities

    def _operation(self, capability, kind, name, entity_ids):
        self.capabilities.validate(capability, kind)
        return UnrealOperation(
            capability=capability,
            kind=kind,
            name=name,
            arguments={"entity_ids": entity_ids},
            entity_ids=entity_ids,
        )

    def for_inspection(self, intent):
        return (
            self._operation(
                UnrealCapability.INSPECT_ACTOR,
                UnrealOperationKind.READ,
                "inspect_target_actors",
                intent.target_entity_ids,
            ),
            self._operation(
                UnrealCapability.INSPECT_ACTOR,
                UnrealOperationKind.VERIFY,
                "verify_target_actor_mapping",
                intent.target_entity_ids,
            ),
        )

    def for_material_variant(self, intent):
        return (
            self._operation(
                UnrealCapability.INSPECT_ACTOR,
                UnrealOperationKind.READ,
                "inspect_target_actors",
                intent.target_entity_ids,
            ),
            self._operation(
                UnrealCapability.MATERIAL,
                UnrealOperationKind.READ,
                "inspect_material_state",
                intent.target_entity_ids,
            ),
            self._operation(
                UnrealCapability.MATERIAL,
                UnrealOperationKind.WRITE,
                "apply_material_variant",
                intent.target_entity_ids,
            ),
            self._operation(
                UnrealCapability.MATERIAL,
                UnrealOperationKind.VERIFY,
                "verify_material_variant",
                intent.target_entity_ids,
            ),
        )
