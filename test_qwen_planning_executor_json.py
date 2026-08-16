import json

from qwen_planning_executor import execute_read_only_plan


def test_read_only_execution_result_contains_json_safe_data(monkeypatch):
    monkeypatch.setattr(
        "qwen_planning_executor.TOOLS",
        {"inspect_scene": lambda **kwargs: {"scene": "Scene", "total_objects": 6}},
    )

    result = execute_read_only_plan({
        "evidence": [{"tool": "inspect_scene", "arguments": {"file_name": "goalpost_test.blend"}}],
        "actions": [],
    })

    json.dumps(result)
    assert result["results"][0]["result"]["total_objects"] == 6
