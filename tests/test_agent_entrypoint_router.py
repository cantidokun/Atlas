"""Tests for the pure Atlas agent entrypoint routing facade."""

from controller.agent_capability_runtime import AgentCapabilityRuntime
from controller.agent_entrypoint_router import AgentEntrypointRouter
from controller.atlas_controller_runtime import AtlasControllerRuntime
from controller.capability_registry import ControllerCapabilityRegistry
from controller.capability_request import CapabilityRequest


def _runtime():
    runtime = AtlasControllerRuntime(ControllerCapabilityRegistry())
    runtime.registry.dispatcher.register(
        "test_capability",
        lambda request: (
            isinstance(request, CapabilityRequest)
            and request.normalized_provider == "unreal"
            and request.normalized_capability == "production"
            and request.context.get("production") is True
        ),
        object(),
    )
    return runtime


def test_router_selects_controller_path_for_explicit_capability():
    router = AgentEntrypointRouter(_runtime())

    route = router.route(
        "production",
        provider="unreal",
        context={"production": True},
    )

    assert route.route == "controller"
    assert route.controller_owned is True
    assert route.selection.matched is True
    assert route.selection.name == "test_capability"


def test_router_leaves_unmatched_request_on_agent_path():
    router = AgentEntrypointRouter(_runtime())

    route = router.route("production", provider="unreal")

    assert route.route == "agent"
    assert route.controller_owned is False
    assert route.selection.matched is False


def test_router_never_executes_selected_handler():
    calls = []
    runtime = AtlasControllerRuntime()
    runtime.registry.dispatcher.register(
        "side_effect_probe",
        lambda request: True,
        lambda: calls.append("executed"),
    )

    route = AgentEntrypointRouter(runtime).route("probe")

    assert route.selection.matched is True
    assert calls == []


def test_router_rejects_wrong_runtime_dependency():
    try:
        AgentEntrypointRouter(AgentCapabilityRuntime)  # type: ignore[arg-type]
    except TypeError as exc:
        assert "AtlasControllerRuntime" in str(exc)
    else:
        raise AssertionError("router accepted invalid runtime dependency")
