import pytest

from planning.blender_live_write_result import BlenderLiveWriteOutcome


def test_verified_outcome_requires_receipt():
    with pytest.raises(TypeError, match="verified outcome requires a BlenderExecutionReceipt"):
        BlenderLiveWriteOutcome.verified(None, {"ok": True})


def test_blocked_outcome_has_no_receipt():
    outcome = BlenderLiveWriteOutcome.blocked({"authoritative": False}, "state mismatch")
    assert outcome.status == "BLOCKED"
    assert outcome.receipt is None
    assert not outcome.is_verified
    assert outcome.reason == "state mismatch"


def test_blocked_outcome_requires_reason():
    with pytest.raises(ValueError, match="requires a reason"):
        BlenderLiveWriteOutcome.blocked({}, "")
