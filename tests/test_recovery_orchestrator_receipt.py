from planning.recovery_orchestrator import RecoveryOrchestrator, RecoveryState


def make():
    return RecoveryOrchestrator(lambda: True, lambda: True, lambda: True)


def test_recovery_requires_receipt_identities():
    assert make().recover().state == RecoveryState.BLOCKED


def test_recovery_creates_authoritative_receipt():
    r = make()
    assert r.recover("e1", "p1", "a1").state == RecoveryState.READY_TO_RESUME
    assert r.receipt is not None
    assert r.receipt.matches("e1", "p1", "a1")


def test_recovery_resume_requires_matching_receipt():
    r = make()
    r.recover("e1", "p1", "a1")
    assert r.resume("e1", "p1", "a1").state == RecoveryState.RESUMED


def test_changed_identity_blocks_and_invalidates_receipt():
    r = make()
    r.recover("e1", "p1", "a1")
    assert r.resume("e2", "p1", "a1").state == RecoveryState.BLOCKED
    assert r.receipt is None


def test_failed_retry_cannot_reuse_previous_receipt():
    calls = [True, False]
    r = RecoveryOrchestrator(lambda: calls.pop(0), lambda: True, lambda: True)
    assert r.recover("e1", "p1", "a1").state == RecoveryState.READY_TO_RESUME
    assert r.recover("e2", "p2", "a2").state == RecoveryState.BLOCKED
    assert r.receipt is None
    assert r.resume("e1", "p1", "a1").state == RecoveryState.BLOCKED


def test_blocked_recovery_cannot_resume():
    r = RecoveryOrchestrator(lambda: False, lambda: True, lambda: True)
    r.recover("e1", "p1", "a1")
    assert r.resume("e1", "p1", "a1").state == RecoveryState.BLOCKED
