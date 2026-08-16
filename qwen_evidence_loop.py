"""Compatibility layer for qwen.evidence_loop.

Preserves the legacy root import path and its pytest monkeypatch seams.
"""
from qwen import evidence_loop as _impl
from qwen.evidence_loop import *


# Keep the legacy patch point working for callers/tests that patch
# qwen_evidence_loop.execute_read_only_plan.
execute_read_only_plan = _impl.execute_read_only_plan


def execute_evidence_proposal(proposal, allowed_tools):
    _impl.execute_read_only_plan = execute_read_only_plan
    return _impl.execute_evidence_proposal(proposal, allowed_tools)
