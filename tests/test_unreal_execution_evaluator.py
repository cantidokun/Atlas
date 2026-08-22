"""Retired Unreal-specific evaluator tests.

Execution evaluation is now provided by the generic Atlas evidence and
TargetStateEvaluator infrastructure. The former UnrealExecutionEvaluator
module intentionally raises when imported. Keep this historical path
collectible without importing the deprecated implementation.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="Deprecated UnrealExecutionEvaluator coverage; use generic evidence/target-state tests."
)


def test_legacy_unreal_execution_evaluator_coverage_retired():
    pytest.skip("Retired in favor of generic Atlas evaluation coverage")
