
"""Tests for the explicit model-response controller bridge."""

import pytest

import controller.agent_controller_response_bridge as bridge
from controller.agent_controller_intent import AgentControllerIntent
from controller.agent_trusted_context import AgentTrustedContext
from controller.agent_entrypoint_runtime import AgentEntrypointExecution


class RecordingRuntime:
    pass


class FakeEntrypointRuntime:
    pass


def test_no_controller_marker_does_not_submit(monkeypatch):
    calls = []

    def fake_submit(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(bridge, "submit_agent_task", fake_submit)

    runtime = object()

    with pytest.raises(TypeError, match="AtlasAgentEntrypointRuntime"):
        bridge.submit_controller_request_from_model_output(
            runtime,
            "normal model response",
        )

    assert calls == []


def test_valid_controller_request_submits_parsed_fields(monkeypatch):
    captured = {}

    def fake_submit(runtime, capability, **kwargs):
        captured["runtime"] = runtime
        captured["capability"] = capability
        captured["kwargs"] = kwargs
        return "execution"

    monkeypatch.setattr(bridge, "submit_agent_task", fake_submit)

    runtime = bridge.AtlasAgentEntrypointRuntime.__new__(
        bridge.AtlasAgentEntrypointRuntime
    )

    result = bridge.submit_controller_request_from_model_output(
        runtime,
        """
ATLAS_CONTROLLER_REQUEST:
{
  "capability": "production",
  "provider": "unreal",
  "intent": "render-field-production",
  "context": {
    "production": true,
    "target_entity_ids": ["FIELD_SURFACE"]
  }
}
""",
    )

    assert result == "execution"
    assert captured["runtime"] is runtime
    assert captured["capability"] == "production"
    assert captured["kwargs"] == {
        "provider": "unreal",
        "context": {
            "production": True,
            "target_entity_ids": ["FIELD_SURFACE"],
        },
        "intent": "render-field-production",
    }


def test_absent_marker_returns_none_without_submission(monkeypatch):
    calls = []

    def fake_submit(*args, **kwargs):
        calls.append((args, kwargs))
        return "unexpected"

    monkeypatch.setattr(bridge, "submit_agent_task", fake_submit)

    runtime = bridge.AtlasAgentEntrypointRuntime.__new__(
        bridge.AtlasAgentEntrypointRuntime
    )

    result = bridge.submit_controller_request_from_model_output(
        runtime,
        "The model decided to continue normal reasoning.",
    )

    assert result is None
    assert calls == []


def test_trusted_context_is_added(monkeypatch):
    captured = {}

    def fake_submit(runtime, capability, **kwargs):
        captured["kwargs"] = kwargs
        return "execution"

    monkeypatch.setattr(bridge, "submit_agent_task", fake_submit)

    runtime = bridge.AtlasAgentEntrypointRuntime.__new__(
        bridge.AtlasAgentEntrypointRuntime
    )

    def trusted_context(intent):
        assert isinstance(intent, AgentControllerIntent)
        return AgentTrustedContext.from_values(
            {
                "authorized_production": "TRUSTED_AUTHORIZATION",
                "sequence_asset_path": "/Game/TestSequence",
            }
        )

    bridge.submit_controller_request_from_model_output(
        runtime,
        """
ATLAS_CONTROLLER_REQUEST:
{
  "capability": "production",
  "provider": "unreal",
  "context": {
    "production": true
  }
}
""",
        trusted_context_provider=trusted_context,
    )

    assert captured["kwargs"]["context"] == {
        "production": True,
        "authorized_production": "TRUSTED_AUTHORIZATION",
        "sequence_asset_path": "/Game/TestSequence",
    }


def test_trusted_context_overrides_model_context(monkeypatch):
    captured = {}

    def fake_submit(runtime, capability, **kwargs):
        captured["kwargs"] = kwargs
        return "execution"

    monkeypatch.setattr(bridge, "submit_agent_task", fake_submit)

    runtime = bridge.AtlasAgentEntrypointRuntime.__new__(
        bridge.AtlasAgentEntrypointRuntime
    )

    bridge.submit_controller_request_from_model_output(
        runtime,
        """
ATLAS_CONTROLLER_REQUEST:
{
  "capability": "production",
  "provider": "unreal",
  "context": {
    "production": true,
    "sequence_asset_path": "MODEL_CONTROLLED_PATH"
  }
}
""",
        trusted_context_provider=lambda intent: AgentTrustedContext.from_values(
            {
                "sequence_asset_path": "TRUSTED_PATH"
            }
        ),
    )

    assert captured["kwargs"]["context"]["sequence_asset_path"] == (
        "TRUSTED_PATH"
    )


def test_trusted_context_provider_must_return_agent_trusted_context(monkeypatch):
    monkeypatch.setattr(
        bridge,
        "submit_agent_task",
        lambda *args, **kwargs: "execution",
    )

    runtime = bridge.AtlasAgentEntrypointRuntime.__new__(
        bridge.AtlasAgentEntrypointRuntime
    )

    with pytest.raises(
        TypeError,
        match="must return an AgentTrustedContext",
    ):
        bridge.submit_controller_request_from_model_output(
            runtime,
            """
ATLAS_CONTROLLER_REQUEST:
{
  "capability": "production"
}
""",
            trusted_context_provider=lambda intent: ["not", "a", "mapping"],
        )


def test_parser_errors_propagate_without_submission(monkeypatch):
    calls = []

    def fake_submit(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(bridge, "submit_agent_task", fake_submit)

    runtime = bridge.AtlasAgentEntrypointRuntime.__new__(
        bridge.AtlasAgentEntrypointRuntime
    )

    with pytest.raises(ValueError, match="invalid JSON"):
        bridge.submit_controller_request_from_model_output(
            runtime,
            """
ATLAS_CONTROLLER_REQUEST:
{not valid json}
""",
        )

    assert calls == []


def test_real_unreal_authorization_survives_synthetic_model_response(
    monkeypatch,
):
    from controller.trusted_unreal_context import TrustedUnrealContext
    from planning.unreal_composite_operation import (
        build_composite_actor_operation,
    )
    from planning.unreal_production_operation import (
        UnrealProductionSpec,
        build_unreal_production_plan,
    )
    from planning.unreal_production_planning_boundary import (
        authorize_production_plan,
    )
    from planning.unreal_render_contract import UnrealRenderConfig
    from planning.unreal_task_planner import UnrealTaskIntent

    entity_id = "FIELD_SURFACE"

    trusted_intent = UnrealTaskIntent(
        intent_id="synthetic-real-unreal",
        description="synthetic agent-to-controller production test",
        target_entity_ids=(entity_id,),
    )

    composite = build_composite_actor_operation(
        [entity_id],
        [
            {
                "name": "set_actor_location",
                "location": {
                    "x": 10.0,
                    "y": 20.0,
                    "z": 30.0,
                },
            },
        ],
    )

    production = build_unreal_production_plan(
        trusted_intent,
        UnrealProductionSpec(
            composite=composite,
            start_frame=1,
            end_frame=1,
            render_config=UnrealRenderConfig(
                width=64,
                height=64,
                start_frame=1,
                end_frame=1,
                output_directory="Saved/SyntheticTestOutput",
                output_format="png",
            ),
        ),
    )

    authorized = authorize_production_plan(
        production,
        "synthetic-trusted-authorization",
    )

    trusted_context = TrustedUnrealContext(
        authorized_production=authorized,
        intent=trusted_intent,
        sequence_asset_path="/Game/Trusted/Sequence",
    )

    captured = {}

    def fake_submit(runtime, capability, **kwargs):
        captured["runtime"] = runtime
        captured["capability"] = capability
        captured["context"] = kwargs["context"]
        captured["intent"] = kwargs["intent"]
        return "synthetic-controller-execution"

    monkeypatch.setattr(
        bridge,
        "submit_agent_task",
        fake_submit,
    )

    runtime = bridge.AtlasAgentEntrypointRuntime.__new__(
        bridge.AtlasAgentEntrypointRuntime
    )

    model_response = """
The production capability is required.

ATLAS_CONTROLLER_REQUEST:
{
  "capability": "production",
  "provider": "unreal",
  "intent": "model-forged-intent",
  "context": {
    "production": true,
    "authorized_production": "MODEL_FORGED_AUTHORIZATION",
    "sequence_asset_path": "/Game/Attacker/Sequence"
  }
}
"""

    execution = bridge.submit_controller_request_from_model_output(
        runtime,
        model_response,
        trusted_context_provider=lambda intent: trusted_context.to_trusted_agent_context(),
    )

    assert execution == "synthetic-controller-execution"
    assert captured["runtime"] is runtime
    assert captured["capability"] == "production"

    request_context = captured["context"]

    assert request_context["production"] is True
    assert request_context["authorized_production"] is authorized
    assert request_context["intent"] is trusted_intent
    assert request_context["sequence_asset_path"] == (
        "/Game/Trusted/Sequence"
    )

    assert captured["intent"] == "model-forged-intent"
