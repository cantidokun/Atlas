"""Tests for the admitted controller capability execution gateway."""

import pytest

from controller.agent_task_request import AgentTaskRequest
from controller.capability_admission import ControllerCapabilityAdmission
from controller.capability_dispatch import ControllerCapabilityDispatcher
from controller.capability_execution import ControllerCapabilityExecutor


class Handler:
    def __init__(self):
        self.calls = []

    def execute(self, request):
        self.calls.append(request)
        return {"status": "executed", "capability": request.capability}


def _admitted(handler):
    dispatcher = ControllerCapabilityDispatcher()
    dispatcher.register("test", lambda request: request.normalized_capability == "test", handler)
    admission = ControllerCapabilityAdmission(dispatcher)
    return admission.admit(AgentTaskRequest("test"))


def test_execute_invokes_only_admitted_handler():
    handler = Handler()
    admission = _admitted(handler)

    result = ControllerCapabilityExecutor().execute(admission)

    assert result.capability_name == "test"
    assert result.value["status"] == "executed"
    assert handler.calls == [admission.request]


def test_executor_rejects_raw_request_without_admission():
    with pytest.raises(TypeError, match="CapabilityAdmission"):
        ControllerCapabilityExecutor().execute(AgentTaskRequest("test"))


def test_executor_rejects_handler_without_execute_method():
    dispatcher = ControllerCapabilityDispatcher()
    dispatcher.register("bad", lambda request: True, object())
    admission = ControllerCapabilityAdmission(dispatcher).admit(AgentTaskRequest("bad"))

    with pytest.raises(TypeError, match="does not expose execute"):
        ControllerCapabilityExecutor().execute(admission)


def test_execution_does_not_reselect_capability():
    calls = []

    class StableHandler:
        def execute(self, request):
            calls.append("executed")
            return request

    handler = StableHandler()
    admission = _admitted(handler)
    result = ControllerCapabilityExecutor().execute(admission)

    assert result.value is admission.request
    assert calls == ["executed"]
