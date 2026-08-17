from planning.recovery_orchestrator import RecoveryOrchestrator, RecoveryState


def test_recovery_requires_evidence_replan_and_authorization():
    calls = []
    recovery = RecoveryOrchestrator(
        lambda: calls.append("evidence") or True,
        lambda: calls.append("replan") or True,
        lambda: calls.append("authorize") or True,
    )
    assert recovery.recover().state == RecoveryState.READY_TO_RESUME
    assert calls == ["evidence", "replan", "authorize"]
    assert recovery.resume().state == RecoveryState.RESUMED


def test_recovery_blocks_without_fresh_evidence():
    recovery = RecoveryOrchestrator(lambda: False, lambda: True, lambda: True)
    assert recovery.recover().state == RecoveryState.BLOCKED


def test_recovery_blocks_when_replan_fails():
    recovery = RecoveryOrchestrator(lambda: True, lambda: False, lambda: True)
    assert recovery.recover().state == RecoveryState.BLOCKED


def test_recovery_blocks_when_authorization_fails():
    recovery = RecoveryOrchestrator(lambda: True, lambda: True, lambda: False)
    assert recovery.recover().state == RecoveryState.BLOCKED


def test_resume_cannot_skip_recovery():
    recovery = RecoveryOrchestrator(lambda: True, lambda: True, lambda: True)
    assert recovery.resume().state == RecoveryState.BLOCKED
