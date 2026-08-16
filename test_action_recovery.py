from action_recovery import assess_action_failure


def test_failed_action_requires_fresh_evidence_and_forbids_direct_retry():
    decision = assess_action_failure(
        action_index=1,
        action_result={"status": "error", "error": "simulated failure"},
        remaining_actions=1,
    )

    assert decision.recoverable is True
    assert decision.require_fresh_evidence is True
    assert decision.retry_authorized is False


def test_missing_failure_result_is_not_retryable():
    decision = assess_action_failure(
        action_index=0,
        action_result=None,
        remaining_actions=2,
    )

    assert decision.recoverable is False
    assert decision.require_fresh_evidence is True
    assert decision.retry_authorized is False


def test_invalid_indexes_are_rejected():
    try:
        assess_action_failure(
            action_index=-1,
            action_result={"status": "error"},
            remaining_actions=0,
        )
    except ValueError as exc:
        assert "action_index" in str(exc)
    else:
        raise AssertionError("negative action index must be rejected")

    try:
        assess_action_failure(
            action_index=0,
            action_result={"status": "error"},
            remaining_actions=-1,
        )
    except ValueError as exc:
        assert "remaining_actions" in str(exc)
    else:
        raise AssertionError("negative remaining action count must be rejected")
