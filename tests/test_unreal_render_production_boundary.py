import pytest

from planning.unreal_agent import UnrealCapability, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_task_planner import UnrealTaskPlanner


def _intent():
    return UnrealTaskIntent(
        intent_id="render-production-test",
        description="configure a real Unreal render",
        target_entity_ids=("ATLAS_RENDER_TEST",),
    )


def _config():
    return {
        "width": 1920,
        "height": 1080,
        "start_frame": 1,
        "end_frame": 120,
        "output_directory": "Saved/AtlasRenderOutput",
        "output_format": "png",
    }


def test_render_planner_builds_read_write_verify_sequence():
    plan = UnrealTaskPlanner().plan_render_configuration(_intent(), _config())
    assert [operation.name for operation in plan.operations] == [
        "inspect_render_state",
        "configure_render",
        "verify_render_state",
    ]
    assert [operation.kind for operation in plan.operations] == [
        UnrealOperationKind.READ,
        UnrealOperationKind.WRITE,
        UnrealOperationKind.VERIFY,
    ]
    assert all(operation.capability is UnrealCapability.RENDER for operation in plan.operations)
    assert plan.operations[1].arguments["width"] == 1920
    assert plan.operations[2].arguments["output_format"] == "png"


def test_render_planner_rejects_invalid_contract():
    value = _config()
    value["end_frame"] = 0
    with pytest.raises(ValueError):
        UnrealTaskPlanner().plan_render_configuration(_intent(), value)
