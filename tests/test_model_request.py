import pytest

from planning.model_request import build_model_request


def test_model_request_preserves_cache_boundary():
    req = build_model_request(
        "STATIC ATLAS RULES",
        request={"intent": "evaluate"},
        observation={"target": "A"},
        plan_digest="digest-1",
        current_step={"sequence": 3},
        runtime_state={"current_index": 3},
    )
    rendered = req.render()
    assert rendered["stable_instructions"] == "STATIC ATLAS RULES"
    assert rendered["dynamic_state"]["plan_digest"] == "digest-1"
    assert rendered["dynamic_state"]["current_step"]["sequence"] == 3
    assert rendered["dynamic_state"]["runtime_state"]["current_index"] == 3
    assert "digest-1" not in rendered["stable_instructions"]
    assert "current_index" not in rendered["stable_instructions"]


def test_request_is_copied():
    source = {"intent": "evaluate"}
    req = build_model_request("RULES", request=source)
    source["intent"] = "mutated"
    assert req.request["intent"] == "evaluate"


def test_request_requires_mapping():
    with pytest.raises(TypeError):
        build_model_request("RULES", request=[])
