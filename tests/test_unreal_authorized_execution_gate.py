"""Retired Unreal-specific authorization-gate tests.

Authorization for Unreal now uses the generic Atlas ActionPlan /
ActionAuthorization infrastructure plus UnrealPlanExecutor. The former
UnrealAuthorizedExecutionGate module intentionally raises when imported.
This stub keeps the historical test path collectible without importing the
deprecated module.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="Deprecated UnrealAuthorizedExecutionGate coverage; use generic authorization and UnrealPlanExecutor tests."
)


def test_legacy_unreal_authorized_execution_gate_coverage_retired():
    pytest.skip("Retired in favor of generic Atlas authorization coverage")
