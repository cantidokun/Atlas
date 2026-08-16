import pytest

from live_qwen_conditional_loop import target_is_satisfied


def _relationship():
    return {
        "object_a": {"location": [0.0, 5.233, 0.0]},
        "object_b": {"location": [0.0, -5.233, 0.0]},
        "midpoint": [0.0, 0.0, 0.0],
        "symmetric_about_origin": True,
        "distance": 10.466,
    }


def test_target_is_satisfied_requires_all_invariants():
    assert target_is_satisfied(_relationship()) is True


@pytest.mark.parametrize(
    "field,value",
    [
        ("midpoint", [0.0, 0.001, 0.0]),
        ("symmetric_about_origin", False),
        ("distance", 10.467),
    ],
)
def test_target_is_satisfied_rejects_inconsistent_evidence(field, value):
    relationship = _relationship()
    relationship[field] = value
    assert target_is_satisfied(relationship) is False


def test_target_is_satisfied_rejects_wrong_post_location():
    relationship = _relationship()
    relationship["object_a"]["location"] = [0.0, 5.234, 0.0]
    assert target_is_satisfied(relationship) is False
