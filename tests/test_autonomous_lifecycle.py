import pytest

from planning.autonomous_lifecycle import AutonomousLifecycle, LifecycleState


def test_admission_failure_pauses_without_execution():
    lifecycle = AutonomousLifecycle(lambda: False)
    decision = lifecycle.admit()
    assert decision.state == LifecycleState.PAUSED
    assert lifecycle.state == LifecycleState.PAUSED


def test_admitted_lifecycle_executes_verifies_and_completes():
    lifecycle = AutonomousLifecycle(lambda: True)
    assert lifecycle.admit().state == LifecycleState.CHECKPOINTED
    assert lifecycle.begin_execution().state == LifecycleState.EXECUTING
    assert lifecycle.begin_verification().state == LifecycleState.VERIFYING
    assert lifecycle.finalize(True).state == LifecycleState.COMPLETE


def test_execution_cannot_skip_admission():
    lifecycle = AutonomousLifecycle(lambda: True)
    assert lifecycle.begin_execution().state == LifecycleState.FAILED


def test_verification_cannot_skip_execution():
    lifecycle = AutonomousLifecycle(lambda: True)
    lifecycle.admit()
    assert lifecycle.begin_verification().state == LifecycleState.FAILED


def test_failed_verification_pauses_not_completes():
    lifecycle = AutonomousLifecycle(lambda: True)
    lifecycle.admit()
    lifecycle.begin_execution()
    lifecycle.begin_verification()
    assert lifecycle.finalize(False).state == LifecycleState.PAUSED
