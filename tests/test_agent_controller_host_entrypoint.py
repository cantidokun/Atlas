"""Regression coverage for the host-as-entrypoint seam."""

import pytest

from controller.agent_controller_host import AgentControllerHost
from controller.agent_task_request import AgentTaskRequest


def test_host_dispatch_delegates_to_entrypoint_runtime(monkeypatch):
    host = AgentControllerHost()
    request = AgentTaskRequest(
        capability="unregistered-capability",
        provider="blender",
        context={},
    )
    sentinel = object()

    monkeypatch.setattr(
        host.runtime,
        "dispatch",
        lambda incoming: sentinel if incoming is request else None,
    )

    assert host.dispatch(request) is sentinel


def test_host_dispatch_rejects_non_request_values():
    host = AgentControllerHost()

    with pytest.raises(TypeError, match="AgentTaskRequest"):
        host.dispatch({"capability": "production"})
