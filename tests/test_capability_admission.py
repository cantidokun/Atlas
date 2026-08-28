from controller.agent_task_request import AgentTaskRequest
from controller.capability_admission import ControllerCapabilityAdmission
from controller.capability_dispatch import ControllerCapabilityDispatcher


def test_admission_converts_and_resolves_without_invoking_handler():
    calls = []
    dispatcher = ControllerCapabilityDispatcher()

    def predicate(request):
        return request.normalized_capability == "production"

    def handler(*args, **kwargs):
        calls.append((args, kwargs))

    dispatcher.register("test_production", predicate, handler)
    admission = ControllerCapabilityAdmission(dispatcher)

    result = admission.admit(
        AgentTaskRequest(
            capability=" Production ",
            provider="Unreal",
            context={"production": True},
            intent="create composite",
        )
    )

    assert result.name == "test_production"
    assert result.request.normalized_capability == "production"
    assert result.request.normalized_provider == "unreal"
    assert result.request.context == {"production": True}
    assert result.handler is handler
    assert calls == []


def test_admission_rejects_unmatched_request():
    dispatcher = ControllerCapabilityDispatcher()
    dispatcher.register("other", lambda request: False, object())
    admission = ControllerCapabilityAdmission(dispatcher)

    try:
        admission.admit(AgentTaskRequest(capability="production"))
    except LookupError as exc:
        assert "no controller capability matched" in str(exc)
    else:
        raise AssertionError("unmatched requests must not be admitted")


def test_admission_requires_normalized_agent_request():
    dispatcher = ControllerCapabilityDispatcher()
    admission = ControllerCapabilityAdmission(dispatcher)

    try:
        admission.admit("production")
    except TypeError as exc:
        assert "AgentTaskRequest" in str(exc)
    else:
        raise AssertionError("raw strings must not cross the admission boundary")
