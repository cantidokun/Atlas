"""M11.1 deterministic tests: evidence gate (design §8) + escalation packet (§10)."""

import json

import pytest

from planning.m11_router.evidence_gate import (
    EvidenceGate,
    EvidenceGateResultKind,
)
from planning.m11_router.escalation_packet import EscalationPacket
from planning.m11_router.risk import RISK_DIMENSIONS, classify_task
from planning.m11_router.model_profile import ModelTier


# ---- evidence gate ----

def test_passing_evidence_accepted():
    gate = EvidenceGate(require_tests=True, require_build=True)
    r = gate.evaluate(tests_passed=10, tests_failed=0, build_result="PASS")
    assert r.is_sufficient is True
    assert r.outcome == EvidenceGateResultKind.SUFFICIENT


def test_failing_test_rejected():
    gate = EvidenceGate(require_tests=True)
    r = gate.evaluate(tests_passed=9, tests_failed=1)
    assert r.is_sufficient is False
    assert r.outcome == EvidenceGateResultKind.INSUFFICIENT


def test_failed_build_escalates():
    gate = EvidenceGate(require_tests=True, require_build=True)
    r = gate.evaluate(tests_passed=10, tests_failed=0, build_result="FAIL")
    assert r.requires_escalation is True
    assert r.outcome == EvidenceGateResultKind.INSUFFICIENT


def test_missing_build_signal_insufficient():
    gate = EvidenceGate(require_build=True)
    r = gate.evaluate(tests_passed=10, tests_failed=0, build_result=None)
    assert r.outcome == EvidenceGateResultKind.INSUFFICIENT


def test_model_confidence_cannot_pass_gate():
    gate = EvidenceGate(require_tests=True)
    # No test results at all (None) -> not sufficient even with a "confidence".
    r = gate.evaluate(tests_passed=None, tests_failed=0)
    assert r.is_sufficient is False
    # The gate does not even accept a confidence parameter.
    with pytest.raises(TypeError):
        gate.evaluate(tests_passed=10, tests_failed=0, confidence=0.99)


def test_multiple_blockers_lead_to_terminal_human_review():
    gate = EvidenceGate(require_tests=True, require_build=True, require_contract=True,
                        max_blockers_to_terminal=2)
    r = gate.evaluate(tests_passed=None, build_result="FAIL", contract_result="UNKNOWN")
    assert r.is_terminal_human_review is True
    assert r.outcome == EvidenceGateResultKind.TERMINAL_HUMAN_REVIEW


def test_diff_check_failure_escalates():
    gate = EvidenceGate(require_diff=True)
    r = gate.evaluate(tests_passed=10, tests_failed=0, diff_checks={"no_production_touch": False})
    assert r.requires_escalation is True


# ---- escalation packet ----

def _risk():
    z = {d: 0 for d in RISK_DIMENSIONS}
    z["cryptography"] = 3
    return classify_task("t", z, task_classes=["security-crypto"])


def test_packet_identity_propagation():
    pkt = EscalationPacket.build(
        task_id="t",
        task_statement="fix attestation",
        risk=_risk(),
        current_tier=ModelTier.L2,
        attempt_ids=["a1"],
        escalation_ids=["e1"],
        failures=["evidence gate red"],
        corrections=["corrected HMAC canonical payload"],
        contract_references=["docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md #M8"],
    )
    assert pkt.task_id == "t"
    assert pkt.attempt_ids == ("a1",)
    assert pkt.escalation_ids == ("e1",)
    assert pkt.from_attempt == "a1"
    assert "evidence gate red" in pkt.failures


def test_packet_serialization_roundtrip():
    pkt = EscalationPacket.build(
        task_id="t", task_statement="recover coordinator",
        risk=_risk(), current_tier=ModelTier.L3,
        failures=["torn state misclassified"], attempt_ids=["a1", "a2"],
        escalation_ids=["e1"],
    )
    json_str = pkt.to_json()
    reparsed = dict(json.loads(json_str))
    assert reparsed["task_id"] == "t"
    assert isinstance(json_str, str)


def test_packet_evidence_preserved():
    gate = EvidenceGate(require_tests=True)
    ev = gate.evaluate(tests_passed=0, tests_failed=1)
    pkt = EscalationPacket.build(task_id="t", task_statement="s", evidence=[ev])
    assert len(pkt.evidence) == 1
    assert pkt.evidence[0].outcome == EvidenceGateResultKind.INSUFFICIENT


def test_packet_prior_attempt_preserved():
    pkt = EscalationPacket.build(task_id="t", task_statement="s", prior_result="prior outcome X")
    assert pkt.prior_result == "prior outcome X"


def test_packet_is_immutable():
    pkt = EscalationPacket.build(task_id="t", task_statement="s")
    with pytest.raises(AttributeError):
        pkt.failures = ("attempt_nonce=abc",)  # immutable -> cannot inject