import pytest

from tool_capabilities import ALL_TOOLS, READ_ONLY_TOOLS, WRITE_TOOLS, requires_write


def test_tool_sets_are_disjoint_and_complete():
    assert READ_ONLY_TOOLS.isdisjoint(WRITE_TOOLS)
    assert ALL_TOOLS == READ_ONLY_TOOLS | WRITE_TOOLS


def test_known_capabilities():
    assert requires_write("inspect_scene") is False
    assert requires_write("move_object") is True


def test_unknown_tools_are_not_silently_classified():
    with pytest.raises(KeyError):
        requires_write("unknown_tool")
