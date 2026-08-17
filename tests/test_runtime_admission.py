import pytest

from planning.runtime_admission import RuntimeAdmissionError, admit_runtime_continuation
from planning.runtime_context import build_runtime_context


def _ctx():
    return build_runtime_context("ATLAS STATIC RULES", plan_digest="plan-a")


def test_matching_runtime_identities_are_admitted():
    ctx = _ctx()
    fp = ctx.stable_fingerprint()
    admission = admit_runtime_continuation(
        ctx,
        authorized_plan_digest="plan-a",
        persisted_state={"cursor": 2},
        persisted_stable_fingerprint=fp,
        persisted_plan_digest="plan-a",
        persisted_state_digest="state-a",
        expected_state_digest="state-a",
    )
    assert admission.stable_fingerprint == fp
    assert admission.plan_digest == "plan-a"
    assert admission.state_digest == "state-a"


def test_stale_stable_context_is_rejected():
    ctx = _ctx()
    with pytest.raises(RuntimeAdmissionError, match="stable runtime context"):
        admit_runtime_continuation(
            ctx,
            authorized_plan_digest="plan-a",
            persisted_state={},
            persisted_stable_fingerprint="stale",
            persisted_plan_digest="plan-a",
            persisted_state_digest="state-a",
            expected_state_digest="state-a",
        )


def test_plan_identity_mismatch_is_rejected():
    ctx = _ctx()
    with pytest.raises(RuntimeAdmissionError, match="authorized plan"):
        admit_runtime_continuation(
            ctx,
            authorized_plan_digest="plan-b",
            persisted_state={},
            persisted_stable_fingerprint=ctx.stable_fingerprint(),
            persisted_plan_digest="plan-a",
            persisted_state_digest="state-a",
            expected_state_digest="state-a",
        )


def test_state_identity_mismatch_is_rejected():
    ctx = _ctx()
    with pytest.raises(RuntimeAdmissionError, match="runtime state"):
        admit_runtime_continuation(
            ctx,
            authorized_plan_digest="plan-a",
            persisted_state={},
            persisted_stable_fingerprint=ctx.stable_fingerprint(),
            persisted_plan_digest="plan-a",
            persisted_state_digest="state-old",
            expected_state_digest="state-new",
        )


def test_invalid_persisted_state_is_rejected():
    ctx = _ctx()
    with pytest.raises(RuntimeAdmissionError, match="persisted runtime state"):
        admit_runtime_continuation(
            ctx,
            authorized_plan_digest="plan-a",
            persisted_state=None,
            persisted_stable_fingerprint=ctx.stable_fingerprint(),
            persisted_plan_digest="plan-a",
            persisted_state_digest="state-a",
            expected_state_digest="state-a",
        )
