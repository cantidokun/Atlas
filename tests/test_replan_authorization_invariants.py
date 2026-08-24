import hashlib

import pytest

from action_plan import ActionSpec
from planning.replan_authorization import ReplanAuthorization


def test_replan_authorization_rejects_malformed_digests():
    with pytest.raises(ValueError, match="evidence_digest"):
        ReplanAuthorization("not-a-digest", hashlib.sha256(b"actions").hexdigest(), "auth-1")

    with pytest.raises(ValueError, match="actions_digest"):
        ReplanAuthorization(hashlib.sha256(b"evidence").hexdigest(), "not-a-digest", "auth-1")


def test_replan_authorization_rejects_blank_authorization_id():
    evidence = {"objects": []}
    actions = [ActionSpec("inspect_scene", {"file_name": "scene.blend"})]
    authorization = ReplanAuthorization.issue(evidence, actions, "auth-1")

    with pytest.raises(ValueError, match="authorization_id"):
        ReplanAuthorization(authorization.evidence_digest, authorization.actions_digest, "   ")


def test_replan_authorization_remains_bound_to_mutated_action_arguments():
    evidence = {"objects": [{"name": "Cube"}]}
    action = ActionSpec("move_object", {"object_name": "Cube", "location": [1, 2, 3]})
    authorization = ReplanAuthorization.issue(evidence, [action], "auth-1")

    assert authorization.matches(evidence, [action])

    action.arguments["location"] = [9, 9, 9]
    assert not authorization.matches(evidence, [action])


def test_replan_authorization_remains_bound_to_fresh_evidence():
    actions = [ActionSpec("move_object", {"object_name": "Cube", "location": [1, 2, 3]})]
    original = {"objects": [{"name": "Cube", "location": [0, 0, 0]}]}
    changed = {"objects": [{"name": "Cube", "location": [4, 0, 0]}]}
    authorization = ReplanAuthorization.issue(original, actions, "auth-1")

    assert authorization.matches(original, actions)
    assert not authorization.matches(changed, actions)
