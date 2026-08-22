"""Retired Unreal-specific determinism tests.

The deprecated Unreal authorization gate is no longer part of the supported
path. Current planner determinism and validation coverage lives in
``tests/test_unreal_task_planner.py`` and the generic Atlas authorization
coverage.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="Deprecated Unreal authorization dependency; use current planner and generic authorization tests."
)


def test_legacy_unreal_task_planner_determinism_coverage_retired():
    pytest.skip("Retired in favor of current planner/generic authorization coverage")
