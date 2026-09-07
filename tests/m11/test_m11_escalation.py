"""M11.1 deterministic tests: finite escalation policy (design §6.1)."""

import pytest

from planning.m11_router.escalation import (
    EscalationController,
    EscalationPolicyError,
    MAX_ESCALATIONS_PER_TASK,
    MAX_TIER,
    next_tier_of,
)
from planning.m11_router.model_profile import ModelTier


def test_next_tier_progression():
    assert next_tier_of(ModelTier.L0) == ModelTier.L1
    assert next_tier_of(ModelTier.L1) == ModelTier.L2
    assert next_tier_of(ModelTier.L2) == ModelTier.L3
    assert next_tier_of(ModelTier.L3) is None


def test_constants():
    assert MAX_ESCALATIONS_PER_TASK == 3
    assert MAX_TIER == ModelTier.L3


def test_escalation_0_to_1_to_2_to_3():
    ctrl = EscalationController()
    st = ctrl.initial("t", ModelTier.L0, "a0")
    tiers = [st.current_tier]
    for i in range(1, 4):
        st = ctrl.escalate(st, reason=f"ev{i}", new_attempt_id=f"a{i}", new_escalation_id=f"e{i}")
        tiers.append(st.current_tier)
    assert [t.value for t in tiers] == ["L0", "L1", "L2", "L3"]
    assert st.escalation_count == 3


def test_maximum_3_escalations_then_terminal():
    ctrl = EscalationController()
    st = ctrl.initial("t", ModelTier.L0, "a0")
    for i in range(1, 4):
        st = ctrl.escalate(st, reason=f"ev{i}", new_attempt_id=f"a{i}", new_escalation_id=f"e{i}")
    assert st.terminal is False and st.escalation_count == 3 and st.current_tier == ModelTier.L3
    # 4th escalation exceeds budget -> terminal NEEDS_HUMAN_REVIEW (no raise).
    st = ctrl.escalate(st, reason="ev4", new_attempt_id="a4", new_escalation_id="e4")
    assert st.terminal is True
    assert st.terminal_outcome == "NEEDS_HUMAN_REVIEW"


def test_l3_failure_is_terminal():
    ctrl = EscalationController()
    st = ctrl.initial("t3", ModelTier.L3, "a0")
    st = ctrl.l3_failure(st, reason="L3 could not establish invariant", new_attempt_id="a1", new_escalation_id="e1")
    assert st.terminal is True
    assert st.terminal_outcome == "NEEDS_HUMAN_REVIEW"


def test_insufficient_evidence_at_max_tier_is_terminal():
    ctrl = EscalationController()
    st = ctrl.initial("tx", ModelTier.L3, "a0")
    st = ctrl.escalate(st, insufficient_evidence=True, reason="evidence insufficient",
                       new_attempt_id="a1", new_escalation_id="e1")
    assert st.terminal is True
    assert st.terminal_outcome == "NEEDS_HUMAN_REVIEW"


def test_no_downgrade_monotonic():
    ctrl = EscalationController()
    st = ctrl.initial("t", ModelTier.L0, "a0")
    prev = st.current_tier
    for i in range(1, 6):
        if st.terminal:
            break
        st = ctrl.escalate(st, reason=f"ev{i}", new_attempt_id=f"a{i}", new_escalation_id=f"e{i}")
        # tier must never decrease (monotonicity by construction)
        assert int(st.current_tier.value[1]) >= int(prev.value[1])
        prev = st.current_tier

def test_no_blind_rerun_same_tier_detected():
    ctrl = EscalationController()
    st = ctrl.initial("t", ModelTier.L3, "a0")  # at max -> next None
    # escalate at max-tier with evidence => terminal, not a rerun same tier.
    st2 = ctrl.escalate(st, reason="try again", new_attempt_id="a1", new_escalation_id="e1",
                        insufficient_evidence=True)
    assert st2.terminal is True and st2.terminal_outcome == "NEEDS_HUMAN_REVIEW"


def test_no_infinite_loop_max_escalations_capped():
    ctrl = EscalationController()
    st = ctrl.initial("t", ModelTier.L0, "a0")
    for i in range(1, 20):
        if st.terminal:
            break
        st = ctrl.escalate(st, reason=f"ev{i}", new_attempt_id=f"a{i}", new_escalation_id=f"e{i}")
    assert st.terminal is True
    assert st.escalation_count <= MAX_ESCALATIONS_PER_TASK


def test_terminal_prevents_further_escalation():
    ctrl = EscalationController()
    st = ctrl.initial("t", ModelTier.L3, "a0")
    st = ctrl.escalate(st, reason="max", new_attempt_id="a1", new_escalation_id="e1", insufficient_evidence=True)
    assert st.terminal is True
    with pytest.raises(Exception):  # EscalationTerminal
        ctrl.escalate(st, reason="again", new_attempt_id="a2", new_escalation_id="e2")


def test_escalation_state_tracks_identity():
    ctrl = EscalationController()
    st = ctrl.initial("task-9", ModelTier.L0, "attempt-init")
    st = ctrl.escalate(st, reason="gate failed", new_attempt_id="attempt-1", new_escalation_id="esc-1")
    assert st.task_id == "task-9"
    assert st.attempt_id == "attempt-1"
    assert st.escalation_id == "esc-1"
    assert st.escalation_reason == "gate failed"
    assert st.escalation_count == 1