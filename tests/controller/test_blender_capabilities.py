import pytest

from controller.blender_capabilities import BLENDER_CAPABILITIES, create_blender_command_registry
from controller.command_registry import CommandCapability
from planning.blender_autonomous_executor import BlenderAutonomousExecutor


def test_blender_capability_catalog_is_explicit_and_classifies_reads_vs_writes():
    registry = create_blender_command_registry()

    assert registry.contains("inspect_scene")
    assert registry.resolve("inspect_scene").mutates_state is False
    assert registry.resolve("inspect_scene").capability == "blender.scene.read"

    assert registry.resolve("create_empty_marker").mutates_state is True
    assert registry.resolve("create_empty_marker").capability == "blender.object.write"
    assert registry.resolve("set_object_rotation").mutates_state is True

    assert len(BLENDER_CAPABILITIES) == len(registry.names())


def test_blender_capability_catalog_contains_no_duplicate_names():
    names = [capability.name for capability in BLENDER_CAPABILITIES]
    assert len(names) == len(set(names))
    assert all(isinstance(capability, CommandCapability) for capability in BLENDER_CAPABILITIES)


def test_blender_autonomous_executor_fails_closed_before_executor_for_unknown_tool():
    calls = []
    executor = BlenderAutonomousExecutor(
        lambda tool, arguments: calls.append((tool, arguments)) or {
            "ok": True,
            "state": "ok",
            "details": {},
        }
    )

    with pytest.raises(ValueError, match="command is not registered"):
        executor("arbitrary_host_command", {})

    assert calls == []


def test_blender_autonomous_executor_exposes_declared_capability():
    executor = BlenderAutonomousExecutor(lambda tool, arguments: {
        "ok": True,
        "state": "inspected",
        "details": {},
    })

    capability = executor.capability_for("inspect_scene")
    assert capability.name == "inspect_scene"
    assert capability.mutates_state is False
