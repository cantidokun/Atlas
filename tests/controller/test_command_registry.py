import pytest

from controller.command_registry import (
    CommandCapability,
    CommandRegistryError,
    ControllerCommandRegistry,
)
from controller.communication_gateway import CommunicationProtocolError, ControllerCommunicationGateway


def test_registry_is_explicit_and_fail_closed():
    registry = ControllerCommandRegistry([
        CommandCapability("inspect_scene", "scene.read"),
        CommandCapability("rename_object", "scene.write", mutates_state=True),
    ])

    assert registry.names() == ("inspect_scene", "rename_object")
    assert registry.resolve("rename_object").mutates_state is True
    assert registry.resolve("inspect_scene").capability == "scene.read"

    with pytest.raises(CommandRegistryError, match="command is not registered"):
        registry.resolve("delete_everything")


def test_registry_rejects_duplicate_or_invalid_capabilities():
    registry = ControllerCommandRegistry()

    with pytest.raises(CommandRegistryError, match="command name must be non-empty"):
        registry.register(CommandCapability("", "scene.read"))

    with pytest.raises(CommandRegistryError, match="capability name must be non-empty"):
        registry.register(CommandCapability("inspect_scene", ""))

    registry.register(CommandCapability("inspect_scene", "scene.read"))
    with pytest.raises(CommandRegistryError, match="command already registered"):
        registry.register(CommandCapability("inspect_scene", "scene.read"))


def test_gateway_rejects_unregistered_command_before_handler():
    calls = []
    registry = ControllerCommandRegistry([
        CommandCapability("inspect_scene", "scene.read"),
    ])

    def handle_command(*args):
        calls.append(args)
        return {"accepted": True}

    gateway = ControllerCommunicationGateway(handle_command, registry)
    gateway.open_session("atlas-session")

    with pytest.raises(CommunicationProtocolError, match="command is not registered"):
        gateway.handle_message({
            "protocol_version": "1",
            "id": "req-1",
            "type": "command",
            "session_id": "atlas-session",
            "payload": {"command": "delete_everything", "arguments": {}},
        })

    assert calls == []


def test_gateway_dispatches_registered_command_unchanged():
    calls = []
    registry = ControllerCommandRegistry([
        CommandCapability("inspect_scene", "scene.read"),
    ])

    def handle_command(*args):
        calls.append(args)
        return {"accepted": True}

    gateway = ControllerCommunicationGateway(handle_command, registry)
    gateway.open_session("atlas-session")

    response = gateway.handle_message({
        "protocol_version": "1",
        "id": "req-1",
        "type": "command",
        "session_id": "atlas-session",
        "payload": {"command": "inspect_scene", "arguments": {"file": "scene.blend"}},
    })

    assert response["status"] == "ok"
    assert calls == [
        (
            "atlas-session",
            "req-1",
            {"command": "inspect_scene", "arguments": {"file": "scene.blend"}},
        )
    ]
