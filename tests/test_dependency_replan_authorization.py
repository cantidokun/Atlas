import pytest

from action_plan import ActionSpec
from planning.replan_authorization import ReplanAuthorization


def test_replan_authorization_binds_dependency_metadata():
    evidence = {"location": [0.0, 5.3, 0.0]}
    original = [
        ActionSpec("prepare_geometry", {}, "prepare_geometry"),
        ActionSpec("configure_render", {}, "configure_render", depends_on=("prepare_geometry",)),
    ]
    changed = [
        ActionSpec("prepare_geometry", {}, "prepare_geometry"),
        ActionSpec("configure_render", {}, "configure_render", depends_on=()),
    ]

    authorization = ReplanAuthorization.issue(evidence, original, "replan-dependency-test")
    assert authorization.matches(evidence, original)
    assert not authorization.matches(evidence, changed)


def test_replan_authorization_rejects_invalid_dependency_graph():
    evidence = {"ready": True}
    invalid = [
        ActionSpec("prepare_geometry", {}, "prepare_geometry"),
        ActionSpec("configure_render", {}, "configure_render", depends_on=("missing",)),
    ]
    with pytest.raises(ValueError, match="unknown action"):
        ReplanAuthorization.issue(evidence, invalid, "invalid-replan")
