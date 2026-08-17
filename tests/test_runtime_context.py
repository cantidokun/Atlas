import pytest

from planning.runtime_context import RuntimeContext, build_runtime_context


def test_stable_prefix_is_separate_from_dynamic_state():
    ctx = build_runtime_context(
        "ATLAS RULES",
        observation={"value": 1},
        plan_digest="abc",
        current_step={"sequence": 2},
    )
    rendered = ctx.render()
    assert rendered["stable_instructions"] == "ATLAS RULES"
    assert rendered["dynamic_state"] == {
        "observation": {"value": 1},
        "plan_digest": "abc",
        "current_step": {"sequence": 2},
    }


def test_dynamic_state_does_not_mutate_context():
    source = {"value": 1}
    ctx = RuntimeContext("RULES", source)
    payload = ctx.dynamic_payload()
    payload["value"] = 99
    assert ctx.dynamic_state["value"] == 1
    assert source["value"] == 1


def test_stable_instructions_are_required():
    with pytest.raises(ValueError):
        RuntimeContext(" ", {})


def test_dynamic_state_must_be_mapping():
    with pytest.raises(TypeError):
        RuntimeContext("RULES", [])


def test_live_state_is_not_embedded_in_cacheable_prefix():
    ctx = build_runtime_context(
        "STATIC ATLAS INSTRUCTIONS",
        observation={"secret": "live"},
        runtime_state={"current_index": 4},
    )
    assert "live" not in ctx.cacheable_prefix()
    assert "current_index" not in ctx.cacheable_prefix()
