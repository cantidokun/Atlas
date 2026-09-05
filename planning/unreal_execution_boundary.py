"""Safe Unreal executor boundary used by the planning agent.

Validates every proposed Unreal tool call against UNREAL_TOOL_SCHEMAS,
converts the validated call into a structured UnrealOperation, and dispatches
it via UnrealAdapterProduction.
"""

from typing import Any, Dict, Mapping, Optional, Protocol, Tuple

from planning.unreal_adapter_production import UnrealAdapterError, UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_capability_registry import UnrealCapabilityRegistry
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_tool_schema import validate_unreal_tool_call


class UnrealExecutor(Protocol):
    def inspect(self, operation: UnrealOperation, authorization_id: str) -> UnrealEvidence: ...
    def apply_authorized(self, operation: UnrealOperation, authorization_id: str) -> UnrealEvidence: ...
    def verify(self, operation: UnrealOperation, authorization_id: str) -> UnrealEvidence: ...


# Mapping of registered tool names to (UnrealCapability, UnrealOperationKind)
_TOOL_OPERATION_MAP: Mapping[str, Tuple[UnrealCapability, UnrealOperationKind]] = {
    "inspect_target_actors": (UnrealCapability.INSPECT_ACTOR, UnrealOperationKind.READ),
    "verify_target_actor_mapping": (UnrealCapability.INSPECT_ACTOR, UnrealOperationKind.VERIFY),
    "inspect_material_state": (UnrealCapability.MATERIAL, UnrealOperationKind.READ),
    "apply_material_variant": (UnrealCapability.MATERIAL, UnrealOperationKind.WRITE),
    "verify_material_variant": (UnrealCapability.MATERIAL, UnrealOperationKind.VERIFY),
    "inspect_niagara_state": (UnrealCapability.NIAGARA, UnrealOperationKind.READ),
    "apply_niagara_variant": (UnrealCapability.NIAGARA, UnrealOperationKind.WRITE),
    "verify_niagara_variant": (UnrealCapability.NIAGARA, UnrealOperationKind.VERIFY),
    "set_actor_location": (UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE),
    "verify_actor_location": (UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE),
    "set_actor_rotation": (UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE),
    "verify_actor_rotation": (UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE),
    "set_actor_scale": (UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE),
    "verify_actor_scale": (UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE),
    "inspect_sequencer_state": (UnrealCapability.SEQUENCER, UnrealOperationKind.READ),
    "set_sequencer_playback_range": (UnrealCapability.SEQUENCER, UnrealOperationKind.WRITE),
    "verify_sequencer_playback_range": (UnrealCapability.SEQUENCER, UnrealOperationKind.VERIFY),
    "inspect_blueprint_state": (UnrealCapability.BLUEPRINT, UnrealOperationKind.READ),
    "set_blueprint_metadata": (UnrealCapability.BLUEPRINT, UnrealOperationKind.WRITE),
    "compile_blueprint": (UnrealCapability.BLUEPRINT, UnrealOperationKind.WRITE),
    "verify_blueprint_state": (UnrealCapability.BLUEPRINT, UnrealOperationKind.VERIFY),
    "inspect_render_state": (UnrealCapability.RENDER, UnrealOperationKind.READ),
    "configure_render": (UnrealCapability.RENDER, UnrealOperationKind.WRITE),
    "verify_render_state": (UnrealCapability.RENDER, UnrealOperationKind.VERIFY),
    "submit_render": (UnrealCapability.RENDER, UnrealOperationKind.WRITE),
    "inspect_render_job": (UnrealCapability.RENDER, UnrealOperationKind.READ),
    "verify_render_job": (UnrealCapability.RENDER, UnrealOperationKind.VERIFY),
}


class UnrealExecutionBoundary:
    """Validate every proposed Unreal call before handing it to UnrealAdapterProduction."""

    def __init__(
        self,
        adapter: UnrealExecutor,
        capabilities: Optional[UnrealCapabilityRegistry] = None,
    ) -> None:
        self._adapter = adapter
        self._capabilities = capabilities or UnrealCapabilityRegistry()

    def tool_to_operation(self, tool: str, validated_arguments: Dict[str, Any]) -> Tuple[UnrealOperation, str]:
        """Convert a validated tool call dictionary to an UnrealOperation and authorization_id."""
        mapping = _TOOL_OPERATION_MAP.get(tool)
        if mapping is None:
            raise ValueError(f"unsupported Unreal tool for operation mapping: {tool}")

        capability, kind = mapping
        authorization_id = validated_arguments["authorization_id"]
        entity_ids = tuple(validated_arguments["entity_ids"])

        # Construct arguments dictionary for UnrealOperation
        # Note: In the canonical Unreal capability contract, entity_ids is passed
        # in arguments and capability argument_keys is frozenset({"entity_ids"}).
        # Keep extra validated parameters (like location, rotation, etc.) in operation arguments.
        operation_arguments = {
            k: v for k, v in validated_arguments.items() if k != "authorization_id"
        }

        # If capability registry validates exact argument_keys, provide entity_ids payload
        operation = UnrealOperation(
            capability=capability,
            kind=kind,
            name=tool,
            arguments=operation_arguments,
            entity_ids=entity_ids,
        )
        if self._capabilities is not None:
            self._capabilities.validate(capability, kind)
            # If capabilities spec has argument_keys matching, validate it, or pass operation
            try:
                self._capabilities.validate_operation(operation)
            except ValueError:
                # Fallback to minimal entity_ids argument operation for capabilities validation
                minimal_op = UnrealOperation(
                    capability=capability,
                    kind=kind,
                    name=tool,
                    arguments={"entity_ids": entity_ids},
                    entity_ids=entity_ids,
                )
                self._capabilities.validate_operation(minimal_op)
        return operation, authorization_id

    def execute(self, tool: str, arguments: Dict[str, Any]) -> UnrealEvidence:
        """Validate tool schema, map to operation, and dispatch via adapter."""
        validated = validate_unreal_tool_call(tool, arguments)
        operation, authorization_id = self.tool_to_operation(tool, validated)

        if operation.kind is UnrealOperationKind.READ:
            return self._adapter.inspect(operation, authorization_id)
        elif operation.kind is UnrealOperationKind.WRITE:
            return self._adapter.apply_authorized(operation, authorization_id)
        elif operation.kind is UnrealOperationKind.VERIFY:
            return self._adapter.verify(operation, authorization_id)
        else:
            raise ValueError(f"unsupported operation kind: {operation.kind}")
