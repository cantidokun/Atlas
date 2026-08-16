"""Compatibility layer for qwen.planning_executor.

Preserves the legacy root import path and its pytest monkeypatch seams.
"""
from qwen import planning_executor as _impl
from qwen.planning_executor import *


# Keep the legacy patch point working for callers/tests that patch
# qwen_planning_executor.TOOLS.
TOOLS = _impl.TOOLS


def execute_read_only_plan(proposal):
    _impl.TOOLS = TOOLS
    return _impl.execute_read_only_plan(proposal)
