import json

from qwen_planning_executor import execute_read_only_plan
from task_planner import build_task_plan


def test_executor_accepts_validated_task_plan_proposal(monkeypatch):
    monkeypatch.setattr(
        "qwen_planning_executor.TOOLS",
        {"inspect_scene": lambda **kwargs: {"scene": "Scene", "total_objects": 6}},
    )

    proposal = build_task_plan({
        "evidence": [{"tool": "inspect_scene", "arguments": {"file_name": "goalpost_test.blend"}}],
        "actions": [],
    }, allowed_tools={"inspect_scene"})

    result = execute_read_only_plan(proposal)
    json.dumps(result)
    assert result["execution_authorized"] is False
    assert result["results"][0]["result"]["total_objects"] == 6
