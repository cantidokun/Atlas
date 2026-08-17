import pytest

from planning.recovery_receipt import RecoveryReceipt


def test_receipt_binds_evidence_plan_and_authorization():
    receipt = RecoveryReceipt("e1", "p1", "a1")
    assert receipt.matches("e1", "p1", "a1")
    assert receipt.receipt_digest


def test_receipt_rejects_changed_evidence():
    receipt = RecoveryReceipt("e1", "p1", "a1")
    assert not receipt.matches("e2", "p1", "a1")


def test_receipt_rejects_changed_plan():
    receipt = RecoveryReceipt("e1", "p1", "a1")
    assert not receipt.matches("e1", "p2", "a1")


def test_receipt_rejects_changed_authorization():
    receipt = RecoveryReceipt("e1", "p1", "a1")
    assert not receipt.matches("e1", "p1", "a2")


def test_receipt_requires_all_digests():
    with pytest.raises(ValueError):
        RecoveryReceipt("", "p1", "a1")
