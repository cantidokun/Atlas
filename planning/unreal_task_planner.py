"""Fail-closed Unreal task decomposition."""

from dataclasses import dataclass
from typing import Mapping, Sequence, Tuple

from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_capability_registry import UnrealCapabilityRegistry
from planning.unreal_composite_operation import CompositeActorProductionOperation


@dataclass(frozen=True)
class UnrealTaskPlan:
    intent_id: str
    operations: Tuple[UnrealOperation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.intent_id, str) or not self.intent_id.strip(): raise ValueError("UnrealTaskPlan intent_id must be a non-empty string")
        if not self.operations: raise ValueError("UnrealTaskPlan must contain at least one operation")


class UnrealTaskPlanner:
    def __init__(self, capabilities=None): self.capabilities = capabilities or UnrealCapabilityRegistry()
    @staticmethod
    def _validate_intent(intent: UnrealTaskIntent) -> None:
        if not isinstance(intent, UnrealTaskIntent): raise TypeError("intent must be a UnrealTaskIntent instance")
        if not intent.target_entity_ids: raise ValueError("Unreal task intents require explicit target entity IDs")
        for eid in intent.target_entity_ids:
            if not isinstance(eid, str) or not eid.strip(): raise ValueError("target_entity_ids must contain only non-empty strings")
    def plan_inspection(self, intent): self._validate_intent(intent); return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_inspection(intent))
    def plan_material_variant(self, intent, material_variant): self._validate_intent(intent); return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_material_variant(intent, material_variant))
    def plan_niagara_variant(self, intent, niagara_variant): self._validate_intent(intent); return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_niagara_variant(intent, niagara_variant))
    def plan_actor_location_write(self, intent, location): self._validate_intent(intent); return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_actor_location_write(intent, location))
    def plan_actor_rotation_write(self, intent, rotation): self._validate_intent(intent); return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_actor_rotation_write(intent, rotation))
    def plan_actor_scale_write(self, intent, scale): self._validate_intent(intent); return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_actor_scale_write(intent, scale))
    def plan_actor_location_sequence(self, intent, locations): self._validate_intent(intent); return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_actor_location_sequence(intent, locations))
    def plan_sequencer_playback_range(self, intent, start_frame, end_frame): self._validate_intent(intent); return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_sequencer_playback_range(intent, start_frame, end_frame))
    def plan_blueprint_compile(self, intent, asset_path): self._validate_intent(intent); return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_blueprint_compile(intent, asset_path))
    def plan_composite_actor_production(self, intent: UnrealTaskIntent, composite: CompositeActorProductionOperation) -> UnrealTaskPlan:
        self._validate_intent(intent)
        if not isinstance(composite, CompositeActorProductionOperation): raise TypeError("composite must be a CompositeActorProductionOperation")
        if tuple(intent.target_entity_ids) != composite.entity_ids: raise ValueError("composite entity_ids must exactly match intent target_entity_ids")
        return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_composite_actor_production(intent, composite))
    def compose_plans(self, intent, plans):
        self._validate_intent(intent)
        if isinstance(plans, (str, bytes)) or not isinstance(plans, Sequence): raise TypeError("plans must be a sequence of UnrealTaskPlan instances")
        if not plans: raise ValueError("plans must contain at least one UnrealTaskPlan")
        operations=[]
        for index, plan in enumerate(plans):
            if not isinstance(plan, UnrealTaskPlan): raise TypeError(f"plans[{index}] must be a UnrealTaskPlan instance")
            if plan.intent_id != intent.intent_id: raise ValueError("all composed plans must use the same intent_id as the supplied intent")
            operations.extend(plan.operations)
        return UnrealTaskPlan(intent.intent_id, tuple(operations))


class UnrealAgentPlanBuilder:
    def __init__(self, capabilities): self.capabilities = capabilities
    @staticmethod
    def _require_targets(intent):
        targets=tuple(intent.target_entity_ids)
        if not targets: raise ValueError("Unreal task intents require explicit target entity IDs.")
        return targets
    @staticmethod
    def _validate_vector(value, axes, name, error):
        if not isinstance(value, Mapping): raise TypeError(f"{name} must be a mapping")
        if set(value.keys()) != set(axes): raise ValueError(f"{name} must contain exactly {', '.join(axes)}")
        if any(isinstance(v, bool) or not isinstance(v, (int,float)) for v in value.values()): raise TypeError(error)
        return dict(value)
    def _validate_location(self, value): return self._validate_vector(value, ("x","y","z"), "location", "location coordinates must be numeric")
    def _validate_rotation(self, value): return self._validate_vector(value, ("pitch","yaw","roll"), "rotation", "rotation angles must be numeric")
    def _validate_scale(self, value): return self._validate_vector(value, ("x","y","z"), "scale", "scale components must be numeric")
    @staticmethod
    def _validate_named_variant(value, field):
        if not isinstance(value, Mapping): raise TypeError(f"{field} must be a mapping")
        if set(value.keys()) != {"name"}: raise ValueError(f"{field} must contain exactly name")
        if not isinstance(value["name"], str) or not value["name"].strip(): raise ValueError(f"{field}.name must be a non-empty string")
        return {"name": value["name"].strip()}
    @staticmethod
    def _validate_frame(value, name):
        if isinstance(value, bool) or not isinstance(value, int): raise TypeError(f"{name} must be an integer")
        return value
    @staticmethod
    def _validate_asset_path(value):
        if not isinstance(value, str) or not value.strip() or not value.startswith("/"):
            raise ValueError("asset_path must be a non-empty Unreal package path")
        return value.strip()
    def _operation(self, capability, kind, name, entity_ids, arguments=None):
        self.capabilities.validate(capability, kind)
        operation_arguments={"entity_ids": entity_ids}
        if arguments: operation_arguments.update(arguments)
        return self.capabilities.validate_operation(UnrealOperation(capability=capability, kind=kind, name=name, arguments=operation_arguments, entity_ids=entity_ids))
    def for_sequencer_playback_range(self, intent, start_frame, end_frame):
        ids=self._require_targets(intent); start_frame=self._validate_frame(start_frame,"start_frame"); end_frame=self._validate_frame(end_frame,"end_frame")
        if start_frame > end_frame: raise ValueError("start_frame must not exceed end_frame")
        return (self._operation(UnrealCapability.SEQUENCER,UnrealOperationKind.READ,"inspect_sequencer_state",ids),self._operation(UnrealCapability.SEQUENCER,UnrealOperationKind.WRITE,"set_sequencer_playback_range",ids,{"start_frame":start_frame,"end_frame":end_frame}),self._operation(UnrealCapability.SEQUENCER,UnrealOperationKind.VERIFY,"verify_sequencer_playback_range",ids,{"expected_start_frame":start_frame,"expected_end_frame":end_frame}))
    def for_blueprint_compile(self, intent, asset_path):
        ids=self._require_targets(intent); asset_path=self._validate_asset_path(asset_path)
        return (
            self._operation(UnrealCapability.BLUEPRINT, UnrealOperationKind.READ, "inspect_blueprint_state", ids, {"asset_path": asset_path}),
            self._operation(UnrealCapability.BLUEPRINT, UnrealOperationKind.WRITE, "compile_blueprint", ids, {"asset_path": asset_path}),
            self._operation(UnrealCapability.BLUEPRINT, UnrealOperationKind.VERIFY, "verify_blueprint_state", ids, {"asset_path": asset_path, "expected_compile_status": "success"}),
        )
    def for_composite_actor_production(self, intent, composite):
        operations=[self._operation(UnrealCapability.INSPECT_ACTOR, UnrealOperationKind.READ, "inspect_target_actors", composite.entity_ids)]
        for raw in composite.ordered_operations():
            name=raw["name"]; ids=tuple(raw.get("entity_ids", composite.entity_ids)); arguments=dict(raw.get("arguments", {}))
            for field in ("location", "rotation", "scale", "material_variant", "niagara_variant", "variant"):
                if field in raw and field not in arguments: arguments[field]=raw[field]
            if name == "set_actor_location":
                normalized=self._validate_location(arguments["location"]); operations.append(self._operation(UnrealCapability.MODIFY_ACTOR,UnrealOperationKind.WRITE,name,ids,{"location":normalized})); operations.append(self._operation(UnrealCapability.MODIFY_ACTOR,UnrealOperationKind.VERIFY,"verify_actor_location",ids,{"expected_location":normalized}))
            elif name == "set_actor_rotation":
                normalized=self._validate_rotation(arguments["rotation"]); operations.append(self._operation(UnrealCapability.MODIFY_ACTOR,UnrealOperationKind.WRITE,name,ids,{"rotation":normalized})); operations.append(self._operation(UnrealCapability.MODIFY_ACTOR,UnrealOperationKind.VERIFY,"verify_actor_rotation",ids,{"expected_rotation":normalized}))
            elif name == "set_actor_scale":
                normalized=self._validate_scale(arguments["scale"]); operations.append(self._operation(UnrealCapability.MODIFY_ACTOR,UnrealOperationKind.WRITE,name,ids,{"scale":normalized})); operations.append(self._operation(UnrealCapability.MODIFY_ACTOR,UnrealOperationKind.VERIFY,"verify_actor_scale",ids,{"expected_scale":normalized}))
            elif name == "apply_material_variant":
                variant=arguments.get("material_variant", arguments.get("variant")); variant={"name":variant} if isinstance(variant,str) else variant; normalized=self._validate_named_variant(variant,"material_variant")
                operations.append(self._operation(UnrealCapability.MATERIAL,UnrealOperationKind.READ,"inspect_material_state",ids)); operations.append(self._operation(UnrealCapability.MATERIAL,UnrealOperationKind.WRITE,name,ids,{"material_variant":normalized})); operations.append(self._operation(UnrealCapability.MATERIAL,UnrealOperationKind.VERIFY,"verify_material_variant",ids,{"material_variant":normalized}))
            elif name == "apply_niagara_variant":
                variant=arguments.get("niagara_variant", arguments.get("variant")); variant={"name":variant} if isinstance(variant,str) else variant; normalized=self._validate_named_variant(variant,"niagara_variant")
                operations.append(self._operation(UnrealCapability.NIAGARA,UnrealOperationKind.READ,"inspect_niagara_state",ids)); operations.append(self._operation(UnrealCapability.NIAGARA,UnrealOperationKind.WRITE,name,ids,{"niagara_variant":normalized})); operations.append(self._operation(UnrealCapability.NIAGARA,UnrealOperationKind.VERIFY,"verify_niagara_variant",ids,{"niagara_variant":normalized}))
        return tuple(operations)
    def for_inspection(self, intent):
        ids=self._require_targets(intent); return (self._operation(UnrealCapability.INSPECT_ACTOR, UnrealOperationKind.READ, "inspect_target_actors", ids), self._operation(UnrealCapability.INSPECT_ACTOR, UnrealOperationKind.VERIFY, "verify_target_actor_mapping", ids))
    def for_material_variant(self, intent, material_variant):
        ids=self._require_targets(intent); variant=self._validate_named_variant(material_variant,"material_variant")
        return (self._operation(UnrealCapability.INSPECT_ACTOR,UnrealOperationKind.READ,"inspect_target_actors",ids),self._operation(UnrealCapability.MATERIAL,UnrealOperationKind.READ,"inspect_material_state",ids),self._operation(UnrealCapability.MATERIAL,UnrealOperationKind.WRITE,"apply_material_variant",ids,{"material_variant":variant}),self._operation(UnrealCapability.MATERIAL,UnrealOperationKind.VERIFY,"verify_material_variant",ids,{"material_variant":variant}))
    def for_niagara_variant(self, intent, niagara_variant):
        ids=self._require_targets(intent); variant=self._validate_named_variant(niagara_variant,"niagara_variant")
        return (self._operation(UnrealCapability.INSPECT_ACTOR,UnrealOperationKind.READ,"inspect_target_actors",ids),self._operation(UnrealCapability.NIAGARA,UnrealOperationKind.READ,"inspect_niagara_state",ids),self._operation(UnrealCapability.NIAGARA,UnrealOperationKind.WRITE,"apply_niagara_variant",ids,{"niagara_variant":variant}),self._operation(UnrealCapability.NIAGARA,UnrealOperationKind.VERIFY,"verify_niagara_variant",ids,{"niagara_variant":variant}))
    def for_actor_location_write(self,intent,location):
        ids=self._require_targets(intent); location=self._validate_location(location); return (self._operation(UnrealCapability.INSPECT_ACTOR,UnrealOperationKind.READ,"inspect_target_actors",ids),self._operation(UnrealCapability.MODIFY_ACTOR,UnrealOperationKind.WRITE,"set_actor_location",ids,{"location":location}),self._operation(UnrealCapability.MODIFY_ACTOR,UnrealOperationKind.VERIFY,"verify_actor_location",ids,{"expected_location":location}))
    def for_actor_rotation_write(self,intent,rotation):
        ids=self._require_targets(intent); rotation=self._validate_rotation(rotation); return (self._operation(UnrealCapability.INSPECT_ACTOR,UnrealOperationKind.READ,"inspect_target_actors",ids),self._operation(UnrealCapability.MODIFY_ACTOR,UnrealOperationKind.WRITE,"set_actor_rotation",ids,{"rotation":rotation}),self._operation(UnrealCapability.MODIFY_ACTOR,UnrealOperationKind.VERIFY,"verify_actor_rotation",ids,{"expected_rotation":rotation}))
    def for_actor_scale_write(self,intent,scale):
        ids=self._require_targets(intent); scale=self._validate_scale(scale); return (self._operation(UnrealCapability.INSPECT_ACTOR,UnrealOperationKind.READ,"inspect_target_actors",ids),self._operation(UnrealCapability.MODIFY_ACTOR,UnrealOperationKind.WRITE,"set_actor_scale",ids,{"scale":scale}),self._operation(UnrealCapability.MODIFY_ACTOR,UnrealOperationKind.VERIFY,"verify_actor_scale",ids,{"expected_scale":scale}))
    def for_actor_location_sequence(self,intent,locations):
        ids=self._require_targets(intent)
        if isinstance(locations,(str,bytes)) or not isinstance(locations,Sequence): raise TypeError("locations must be a sequence of mappings")
        if not locations: raise ValueError("locations must contain at least one location")
        operations=[self._operation(UnrealCapability.INSPECT_ACTOR,UnrealOperationKind.READ,"inspect_target_actors",ids)]
        for location in locations:
            location=self._validate_location(location); operations.extend((self._operation(UnrealCapability.MODIFY_ACTOR,UnrealOperationKind.WRITE,"set_actor_location",ids,{"location":location}),self._operation(UnrealCapability.MODIFY_ACTOR,UnrealOperationKind.VERIFY,"verify_actor_location",ids,{"expected_location":location})))
        return tuple(operations)
