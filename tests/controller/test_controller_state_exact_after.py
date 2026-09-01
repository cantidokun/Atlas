import pytest

from controller_state import ControllerState, record_after, record_before, record_write


BEFORE = {
    "object_a": {"name": "Goal_Left_post", "location": [0.0, 5.44, 0.0]},
    "object_b": {"name": "Goal_Right_Post", "location": [0.0, -5.164, 0.0]},
    "midpoint": [0.0, 0.138, 0.0],
}


def _state():
    state = ControllerState("goalpost_test.blend", "Goal_Left_post", "Goal_Right_Post")
    record_before(state, BEFORE)
    record_write(state, "Goal_Left_post", [0.0, 5.302, 0.0], {"status": "moved"})
    record_write(state, "Goal_Right_Post", [0.0, -5.302, 0.0], {"status": "moved"})
    return state


def _after(**overrides):
    result = {
        "object_a": {"name": "Goal_Left_post", "location": [0.0, 5.302, 0.0]},
        "object_b": {"name": "Goal_Right_Post", "location": [0.0, -5.302, 0.0]},
        "midpoint": [0.0, 0.0, 0.0],
    }
    result.update(overrides)
    return result


def test_after_rejects_wrong_object_a_location():
    with pytest.raises(ValueError, match="AFTER evidence"):
        record_after(_state(), _after(object_a={"name": "Goal_Left_post", "location": [0.0, 5.3, 0.0]}))


def test_after_rejects_wrong_object_b_location():
    with pytest.raises(ValueError, match="AFTER evidence"):
        record_after(_state(), _after(object_b={"name": "Goal_Right_Post", "location": [0.0, -5.3, 0.0]}))


def test_after_rejects_wrong_midpoint():
    with pytest.raises(ValueError, match="AFTER evidence"):
        record_after(_state(), _after(midpoint=[0.0, 0.001, 0.0]))


def test_after_requires_authorized_object_names():
    with pytest.raises(ValueError, match="AFTER evidence"):
        record_after(_state(), _after(object_a={"name": "Other", "location": [0.0, 5.302, 0.0]}))
