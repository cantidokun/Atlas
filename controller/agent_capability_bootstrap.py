"""Construct the outer Atlas capability runtime for an agent process.

The bootstrap owns wiring only. It does not infer tasks, authorize plans, or
instantiate provider execution infrastructure unless the caller explicitly
supplies those objects.
"""

from typing import Optional

from controller.atlas_controller_runtime import AtlasControllerRuntime
from controller.capability_registry import ControllerCapabilityRegistry
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration


def build_agent_capability_runtime(
    registry: Optional[ControllerCapabilityRegistry] = None,
    *,
    unreal_production: Optional[UnrealProductionControllerIntegration] = None,
) -> AtlasControllerRuntime:
    """Build one runtime-owned capability resolver with optional Unreal wiring."""
    runtime = AtlasControllerRuntime(registry)
    if unreal_production is not None:
        runtime.register_unreal_production(unreal_production)
    return runtime
