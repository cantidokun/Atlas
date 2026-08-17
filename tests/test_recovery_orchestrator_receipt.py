from planning.recovery_orchestrator import RecoveryOrchestrator, RecoveryState


def make():
    return RecoveryOrchestrator(lambda: True, lambda: True, lambda: True)


def test_recovery_requires_receipt_identities():
    r = make()
    assert r.recover().state == RecoveryState.BLOCKED


def test_recovery_resume_requires_matching_receipt():
    r = make()
    assert r.recover("e1", "p1", "a1").state == RecoveryState.READY_TO_RESUME
    assert r.resume("e1", "p1", "a1").state == RecoveryState.RESUMED


def test_changed_identity_blocks_resume():
    r = make()
    r.recover("e1", "p1", "a1")
    assert r.resume("e2", "p1", "a1").state == RecoveryState.BLOCKED


def test_blocked_recovery_cannot_resume():
    r = RecoveryOrchestrator(lambda: False, lambda: True, lambda: True)
    r.recover("e1", "p1", "a1")
    assert r.resume("e1", "p1", "a1").state == RecoveryState.BLOCKED
