from planning.recovery_orchestrator import RecoveryOrchestrator, RecoveryState


def make():
    return RecoveryOrchestrator(lambda: True, lambda: True, lambda: True)


def test_recovery_requires_receipt_identities():
    assert make().recover().state == RecoveryState.BLOCKED


def test_recovery_requires_evidence_replan_and_authorization():
    calls = []
    recovery = RecoveryOrchestrator(
        lambda: calls.append("evidence") or True,
        lambda: calls.append("replan") or True,
        lambda: calls.append("authorize") or True,
    )
    assert recovery.recover("e1", "p1", "a1").state == RecoveryState.READY_TO_RESUME
    assert calls == ["evidence", "replan", "authorize"]
    assert recovery.resume("e1", "p1", "a1").state == RecoveryState.RESUMED


def test_recovery_blocks_without_fresh_evidence():
    recovery = RecoveryOrchestrator(lambda: False, lambda: True, lambda: True)
    assert recovery.recover("e1", "p1", "a1").state == RecoveryState.BLOCKED


def test_recovery_blocks_when_replan_fails():
    recovery = RecoveryOrchestrator(lambda: True, lambda: False, lambda: True)
    assert recovery.recover("e1", "p1", "a1").state == RecoveryState.BLOCKED


def test_recovery_blocks_when_authorization_fails():
    recovery = RecoveryOrchestrator(lambda: True, lambda: True, lambda: False)
    assert recovery.recover("e1", "p1", "a1").state == RecoveryState.BLOCKED


def test_resume_cannot_skip_recovery():
    assert make().resume("e1", "p1", "a1").state == RecoveryState.BLOCKED


def test_recovery_gate_exception_blocks_and_clears_receipt():
    recovery = make()
    assert recovery.recover("e1", "p1", "a1").state == RecoveryState.READY_TO_RESUME
    failing = RecoveryOrchestrator(lambda: (_ for _ in ()).throw(RuntimeError("transport unavailable")), lambda: True, lambda: True)
    assert failing.recover("e2", "p2", "a2").state == RecoveryState.BLOCKED
    assert failing.receipt is None
    assert recovery.resume("e1", "p1", "a1").state == RecoveryState.RESUMED


def test_recovery_gate_must_return_true_not_truthy_value():
    recovery = RecoveryOrchestrator(lambda: 1, lambda: True, lambda: True)
    assert recovery.recover("e1", "p1", "a1").state == RecoveryState.BLOCKED


def test_receipt_is_cleared_after_resume_identity_mismatch():
    recovery = make()
    assert recovery.recover("e1", "p1", "a1").state == RecoveryState.READY_TO_RESUME
    assert recovery.resume("e1", "wrong-plan", "a1").state == RecoveryState.BLOCKED
    assert recovery.receipt is None
    assert recovery.resume("e1", "p1", "a1").state == RecoveryState.BLOCKED
