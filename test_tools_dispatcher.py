"""Tests for the trusted Atlas tool-dispatch boundary."""

import pytest

from tools.dispatcher import (
    ToolDispatchError,
    dispatch_tool,
    tool_requires_write,
    validate_tool_arguments,
)


def test_read_tool_is_trusted_read_only():
    assert tool_requires_write("inspect_scene") is False


def test_write_tool_is_trusted_write():
    assert tool_requires_write("move_object") is True


def test_unknown_tool_is_rejected():
    with pytest.raises(ToolDispatchError, match="not registered"):
        validate_tool_arguments("run_shell", {})


def test_unexpected_arguments_are_rejected():
    with pytest.raises(ToolDispatchError, match="Unexpected arguments"):
        validate_tool_arguments(
            "inspect_scene",
            {"file_name": "scene.blend", "command": "whoami"},
        )


def test_missing_arguments_are_rejected():
    with pytest.raises(ToolDispatchError, match="Missing required arguments"):
        validate_tool_arguments("inspect_mesh", {})


def test_write_tool_is_blocked_without_authorization():
    with pytest.raises(ToolDispatchError, match="explicit Python authorization"):
        dispatch_tool(
            "create_collection",
            {"file_name": "scene.blend", "collection_name": "Atlas_Test"},
            allow_writes=False,
        )
