"""Registration helper for the Unreal production controller capability."""

from controller.capability_dispatch import ControllerCapabilityDispatcher
from controller.capability_request import CapabilityRequest
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration
from planning.unreal_production_planning_boundary import UnrealAuthorizedProductionPlan


def unreal_production_task(request: CapabilityRequest) -> bool:
    """Match only explicitly requested production backed by trusted authorization."""
    if not isinstance(request, CapabilityRequest):
        raise TypeError("request must be a CapabilityRequest")
    return (
        request.normalized_provider == "unreal"
        and request.normalized_capability == "production"
        and request.context.get("production") is True
        and isinstance(
            request.context.get("authorized_production"),
            UnrealAuthorizedProductionPlan,
        )
    )


def register_unreal_production_capability(
    dispatcher: ControllerCapabilityDispatcher,
    integration: UnrealProductionControllerIntegration,
) -> None:
    """Register the Unreal production integration without changing generic dispatch."""
    if not isinstance(dispatcher, ControllerCapabilityDispatcher):
        raise TypeError("dispatcher must be a ControllerCapabilityDispatcher instance")
    if not isinstance(integration, UnrealProductionControllerIntegration):
        raise TypeError(
            "integration must be a UnrealProductionControllerIntegration instance"
        )
    dispatcher.register("unreal_production", unreal_production_task, integration)
