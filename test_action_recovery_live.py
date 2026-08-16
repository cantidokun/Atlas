"""Controlled local harness for the Atlas action-failure recovery boundary."""

from planning.action_recovery import assess_action_failure


def main() -> None:
    failed_write = {
        "status": "error",
        "object_name": "Goal_Left_post",
        "error": "CONTROLLED_TEST_FAILURE",
    }

    decision = assess_action_failure(
        action_index=0,
        action_result=failed_write,
        remaining_actions=1,
    )

    print("--- CONTROLLED FAILURE ---")
    print(failed_write)
    print("--- RECOVERY DECISION ---")
    print(decision)

    assert decision.recoverable is True
    assert decision.require_fresh_evidence is True
    assert decision.retry_authorized is False

    print("--- ATLAS RECOVERY RESULT ---")
    print("FAILED WRITE: DETECTED")
    print("FRESH EVIDENCE: REQUIRED")
    print("AUTOMATIC RETRY: REFUSED")
    print("ATLAS CONTROLLED FAILURE TEST: PASS")


if __name__ == "__main__":
    main()
