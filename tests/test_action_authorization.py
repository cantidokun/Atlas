from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionSpec


def _actions():
    return [
        ActionSpec(
            tool="move_object",
            arguments={"file_name": "scene.blend", "object_name": "A", "location": [1, 2, 3]},
            name="move A",
        ),
        ActionSpec(
            tool="move_object",
            arguments={"file_name": "scene.blend", "object_name": "B", "location": [4, 5, 6]},
            name="move B",
        ),
    ]


def test_authorization_binds_exact_action_plan():
    actions = _actions()
    receipt = ActionAuthorization.issue(actions, "approval-001")

    assert receipt.matches(actions)
    assert receipt.authorization_id == "approval-001"
    assert receipt.snapshot()["plan_digest"]


def test_authorization_rejects_changed_arguments():
    receipt = ActionAuthorization.issue(_actions(), "approval-002")
    changed = list(_actions())
    changed[0] = ActionSpec(
        tool="move_object",
        arguments={"file_name": "scene.blend", "object_name": "A", "location": [9, 9, 9]},
        name="move A",
    )

    assert not receipt.matches(changed)


def test_authorization_rejects_changed_order():
    actions = _actions()
    receipt = ActionAuthorization.issue(actions, "approval-003")

    assert not receipt.matches(list(reversed(actions)))


def test_authorization_rejects_fabricated_or_invalid_inputs():
    try:
        ActionAuthorization.issue([], "")
    except ValueError:
        pass
    else:
        raise AssertionError("blank authorization id must be rejected")

    try:
        ActionAuthorization.issue([object()], "approval-004")
    except TypeError:
        pass
    else:
        raise AssertionError("non-ActionSpec entries must be rejected")
