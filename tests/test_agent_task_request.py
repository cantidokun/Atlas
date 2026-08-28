from controller.agent_task_request import AgentTaskRequest


def test_request_preserves_explicit_routing_fields():
    request = AgentTaskRequest(
        capability="unreal.production",
        provider="unreal",
        context={"scene": "soccer_field"},
        intent="produce_composite",
    )

    assert request.routing_kwargs() == {
        "capability": "unreal.production",
        "provider": "unreal",
        "context": {"scene": "soccer_field"},
    }
    assert request.intent == "produce_composite"


def test_request_rejects_missing_capability():
    try:
        AgentTaskRequest(capability="")
    except ValueError as exc:
        assert "capability" in str(exc)
    else:
        raise AssertionError("expected empty capability to be rejected")


def test_request_rejects_non_mapping_context():
    try:
        AgentTaskRequest(capability="unreal.production", context=[])
    except TypeError as exc:
        assert "context" in str(exc)
    else:
        raise AssertionError("expected non-dict context to be rejected")
