from planning.corrective_receipt_guard import require_bound_receipt


class FakeReceipt:
    def __init__(self, matches):
        self.matches_value = matches

    def matches(self, tool, arguments, result):
        return self.matches_value


class FakeExecutor:
    def __init__(self, matches=True, receipt=True):
        self.last_result = object() if receipt else None
        self.last_receipt = FakeReceipt(matches) if receipt else None

    def receipt_matches_last_execution(self, tool, arguments):
        return self.last_receipt is not None and self.last_result is not None and self.last_receipt.matches(tool, arguments, self.last_result)


def test_guard_accepts_bound_receipt():
    receipt = require_bound_receipt(FakeExecutor(), "move_object", {"object_name": "Goal_Left_post"})
    assert isinstance(receipt, FakeReceipt)


def test_guard_rejects_unbound_receipt():
    try:
        require_bound_receipt(FakeExecutor(matches=False), "move_object", {})
    except RuntimeError as exc:
        assert "does not bind" in str(exc)
    else:
        raise AssertionError("unbound receipt was accepted")


def test_guard_rejects_missing_receipt():
    try:
        require_bound_receipt(FakeExecutor(receipt=False), "move_object", {})
    except RuntimeError as exc:
        assert "does not bind the requested action" in str(exc)
    else:
        raise AssertionError("missing receipt was accepted")
