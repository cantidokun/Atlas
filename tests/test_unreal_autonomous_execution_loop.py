"""Retired Unreal-specific autonomous-loop tests.

Autonomous orchestration is now provided by the generic Atlas planning and
future/recovery infrastructure. The former UnrealAutonomousExecutionLoop
module depends on deprecated Unreal gate/evaluator/recovery components and is
no longer a supported execution path.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="Deprecated Unreal autonomous-loop coverage; use generic orchestrator/future/recovery tests."
)


def test_legacy_unreal_autonomous_execution_loop_coverage_retired():
    pytest.skip("Retired in favor of generic Atlas orchestration coverage")
