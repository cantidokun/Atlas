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


def test_receipt_rejects_whitespace_only_identity():
    with pytest.raises(ValueError):
        RecoveryReceipt("e1", " ", "a1")


def test_receipt_digest_is_unambiguous_for_delimiter_characters():
    first = RecoveryReceipt("a|b", "c", "d")
    second = RecoveryReceipt("a", "b|c", "d")
    assert first.receipt_digest != second.receipt_digest


def test_receipt_is_immutable():
    receipt = RecoveryReceipt("e1", "p1", "a1")
    with pytest.raises(AttributeError):
        receipt.plan_digest = "p2"
