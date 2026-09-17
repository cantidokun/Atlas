"""Engine-neutral composition of heterogeneous Unreal production operations.

This module is deliberately above the Unreal transport. It composes existing
capability-specific task plans into one deterministic production plan while
leaving execution, evidence, verification, authorization, and recovery to the
existing Atlas boundaries.
"""

from dataclasses import dataclass
from typing import Optional

from planning.unreal_composite_operation import CompositeActorProductionOperation
from planning.unreal_render_contract import UnrealRenderConfig, normalize_render_config
from planning.unreal_shot_continuity import UnrealShotContinuity
from planning.unreal_task_planner import UnrealTaskIntent, UnrealTaskPlan, UnrealTaskPlanner


@dataclass(frozen=True)
class UnrealProductionSpec:
    """Declarative inputs for one heterogeneous Unreal production transaction."""

    composite: CompositeActorProductionOperation
    start_frame: int
    end_frame: int
    render_config: UnrealRenderConfig
    sequence_asset_path: str
    blueprint_asset_path: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.composite, CompositeActorProductionOperation):
            raise TypeError("composite must be a CompositeActorProductionOperation")
        if isinstance(self.start_frame, bool) or not isinstance(self.start_frame, int):
            raise TypeError("start_frame must be an integer")
        if isinstance(self.end_frame, bool) or not isinstance(self.end_frame, int):
            raise TypeError("end_frame must be an integer")
        if self.start_frame > self.end_frame:
            raise ValueError("start_frame must not exceed end_frame")
        if not isinstance(self.render_config, UnrealRenderConfig):
            raise TypeError("render_config must be an UnrealRenderConfig instance")
        if self.render_config.start_frame != self.start_frame or self.render_config.end_frame != self.end_frame:
            raise ValueError("render_config frame range must match production frame range")
        if (
            not isinstance(self.sequence_asset_path, str)
            or not self.sequence_asset_path
            or self.sequence_asset_path.strip() != self.sequence_asset_path
            or not self.sequence_asset_path.startswith("/")
        ):
            raise ValueError(
                "sequence_asset_path must be a non-empty canonical Unreal package path"
            )
        if self.blueprint_asset_path is not None:
            if not isinstance(self.blueprint_asset_path, str) or not self.blueprint_asset_path.strip():
                raise ValueError("blueprint_asset_path must be a non-empty Unreal package path")
            if not self.blueprint_asset_path.startswith("/"):
                raise ValueError("blueprint_asset_path must be a non-empty Unreal package path")


@dataclass(frozen=True)
class UnrealProductionPlan:
    """A production plan plus its phase boundaries for audit/recovery."""

    plan: UnrealTaskPlan
    phases: tuple
    continuity: UnrealShotContinuity

    def __post_init__(self) -> None:
        if not isinstance(self.plan, UnrealTaskPlan):
            raise TypeError("plan must be a UnrealTaskPlan instance")
        if not self.phases:
            raise ValueError("phases must not be empty")
        for phase_name, start, end in self.phases:
            if not isinstance(phase_name, str) or not phase_name.strip():
                raise ValueError("phase names must be non-empty strings")
            if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end < start:
                raise ValueError("phase boundaries must be valid operation indexes")
            if end > len(self.plan.operations):
                raise ValueError("phase boundary exceeds production plan")
        if not isinstance(self.continuity, UnrealShotContinuity):
            raise TypeError("continuity must be an UnrealShotContinuity instance")
        _validate_plan_continuity(self.plan, self.continuity)


def _validate_plan_continuity(
    plan: UnrealTaskPlan,
    continuity: UnrealShotContinuity,
) -> None:
    """Require the declared continuity to match this exact plan's own operations.

    The continuity record is declared once and the plan is composed from the
    same declarative inputs, so the two can only disagree through construction
    error or tampering. Both directions fail closed here rather than at the
    render boundary, and no later stage may treat the record as an echo of the
    engine's answer.
    """
    render_operations = tuple(
        operation for operation in plan.operations if operation.name == "configure_render"
    )
    sequencer_operations = tuple(
        operation for operation in plan.operations
        if operation.name == "set_sequencer_playback_range"
    )

    if len(render_operations) > 1 or len(sequencer_operations) > 1:
        raise ValueError("production plan must not configure render or sequencer state twice")

    for operation in render_operations:
        arguments = operation.arguments
        observed = {
            "start_frame": arguments.get("start_frame"),
            "end_frame": arguments.get("end_frame"),
            "output_directory": arguments.get("output_directory"),
            "output_format": arguments.get("output_format"),
        }
        expected = {
            "start_frame": continuity.start_frame,
            "end_frame": continuity.end_frame,
            "output_directory": continuity.output_directory,
            "output_format": continuity.output_format,
        }
        if observed != expected:
            raise ValueError(
                "production plan render configuration does not match the "
                "declared shot continuity"
            )

    for operation in sequencer_operations:
        arguments = operation.arguments
        if (
            arguments.get("start_frame") != continuity.start_frame
            or arguments.get("end_frame") != continuity.end_frame
        ):
            raise ValueError(
                "production plan sequencer range does not match the declared "
                "shot continuity"
            )


def build_unreal_production_plan(
    intent: UnrealTaskIntent,
    spec: UnrealProductionSpec,
    planner: Optional[UnrealTaskPlanner] = None,
) -> UnrealProductionPlan:
    """Compose Blueprint, actor, Sequencer, and render phases deterministically.

    The resulting object contains ordinary ``UnrealOperation`` instances. No
    transport-specific behavior is introduced here, which keeps this boundary
    reusable by the workflow/action-runner layer.
    """
    if not isinstance(intent, UnrealTaskIntent):
        raise TypeError("intent must be a UnrealTaskIntent instance")
    if not isinstance(spec, UnrealProductionSpec):
        raise TypeError("spec must be an UnrealProductionSpec instance")
    if tuple(intent.target_entity_ids) != spec.composite.entity_ids:
        raise ValueError("production intent targets must exactly match composite entity_ids")

    task_planner = planner or UnrealTaskPlanner()
    subplans = []

    if spec.blueprint_asset_path is not None:
        subplans.append(
            ("blueprint", task_planner.plan_blueprint_compile(intent, spec.blueprint_asset_path))
        )

    subplans.append(
        ("actor_composite", task_planner.plan_composite_actor_production(intent, spec.composite))
    )
    subplans.append(
        ("sequencer", task_planner.plan_sequencer_playback_range(intent, spec.start_frame, spec.end_frame))
    )
    subplans.append(
        ("render", task_planner.plan_render_configuration(intent, {
            "width": spec.render_config.width,
            "height": spec.render_config.height,
            "start_frame": spec.render_config.start_frame,
            "end_frame": spec.render_config.end_frame,
            "output_directory": spec.render_config.output_directory,
            "output_format": spec.render_config.output_format,
        }))
    )

    operations = []
    phases = []
    for phase_name, subplan in subplans:
        start = len(operations)
        operations.extend(subplan.operations)
        phases.append((phase_name, start, len(operations)))

    return UnrealProductionPlan(
        plan=UnrealTaskPlan(intent.intent_id, tuple(operations)),
        phases=tuple(phases),
        continuity=UnrealShotContinuity(
            sequence_asset_path=spec.sequence_asset_path,
            start_frame=spec.start_frame,
            end_frame=spec.end_frame,
            output_directory=spec.render_config.output_directory,
            output_format=spec.render_config.output_format,
        ),
    )
