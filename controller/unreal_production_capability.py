"""Registration helper for the Unreal production controller capability."""

from typing import Any, Mapping

from controller.capability_dispatch import ControllerCapabilityDispatcher
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration


def unreal_production_task(
    task_text: str,
    context: Mapping[str, Any],
) -> bool:
    """Identify explicit Unreal production tasks without interpreting them as writes."""
    text = (task_text or "").lower()
    return (
        context.get("provider") == "unreal"
        and context.get("production") is True
        and "production" in text
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
