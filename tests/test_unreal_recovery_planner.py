"""Retired Unreal-specific recovery-planner tests.

Recovery is now handled by the generic Atlas FutureRecoveryGate and the
Unreal-specific fail-closed recovery policy. The former UnrealRecoveryPlanner
module intentionally raises when imported. Keep this historical path
collectible without importing the deprecated implementation.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="Deprecated UnrealRecoveryPlanner coverage; use generic FutureRecoveryGate and Unreal recovery-policy tests."
)


def test_legacy_unreal_recovery_planner_coverage_retired():
    pytest.skip("Retired in favor of generic Atlas recovery coverage")
