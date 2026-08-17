from planning.action_plan import ActionPlan, ActionSpec


def test_authorize_with_id_installs_receipt_and_exposes_id():
    plan = ActionPlan([ActionSpec("write", {"value": 1}, "write")])

    receipt = plan.authorize_with_id("integration-test-1")

    assert plan.authorized
    assert plan.authorization_id == "integration-test-1"
    assert receipt.snapshot()["authorization_id"] == "integration-test-1"


def test_authorize_with_id_rejects_blank_identifier():
    plan = ActionPlan([ActionSpec("write", {}, "write")])

    try:
        plan.authorize_with_id("   ")
    except ValueError as exc:
        assert str(exc) == "authorization_id must be a non-empty string."
    else:
        raise AssertionError("expected blank authorization id to be rejected")


def test_authorize_with_id_cannot_reauthorize_after_execution():
    plan = ActionPlan([ActionSpec("write", {}, "write")])
    plan.authorize_with_id("first")
    plan.record_result({"ok": True}, True)

    try:
        plan.authorize_with_id("second")
    except RuntimeError as exc:
        assert str(exc) == "Action plan can only be authorized before execution begins."
    else:
        raise AssertionError("expected reauthorization to be rejected")
