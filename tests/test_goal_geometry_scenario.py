"""Tests for the reusable centered-goal soccer scenario."""

import pytest

from scenarios.goal_geometry import centered_goal_condition, goal_center_alignment


def centered_relationship():
    return {
        "object_a": {"location": [0.0, 5.233, 0.0]},
        "object_b": {"location": [0.0, -5.233, 0.0]},
        "midpoint": [0.0, 0.0, 0.0],
        "symmetric_about_origin": True,
        "distance": 10.466,
    }


def test_centered_goal_condition_accepts_valid_geometry():
    evidence = centered_relationship()
    assert goal_center_alignment(evidence) is True
    assert centered_goal_condition().matches(evidence) is True


def test_centered_goal_condition_rejects_wrong_midpoint():
    evidence = centered_relationship()
    evidence["midpoint"] = [0.0, 0.25, 0.0]
    assert goal_center_alignment(evidence) is False
    assert centered_goal_condition().matches(evidence) is False


def test_centered_goal_condition_rejects_wrong_distance():
    evidence = centered_relationship()
    evidence["distance"] = 10.0
    assert centered_goal_condition().matches(evidence) is False


def test_centered_goal_condition_requires_authoritative_fields():
    with pytest.raises(KeyError):
        centered_goal_condition().matches({"midpoint": [0.0, 0.0, 0.0]})
