import pytest

from qwen_planning_executor import execute_read_only_plan


def test_read_only_executor_runs_inspection(monkeypatch):
    seen = []

    monkeypatch.setattr(
        "qwen_planning_executor.TOOLS",
        {"inspect_scene": lambda **kwargs: seen.append(kwargs) or {"ok": True}},
    )

    result = execute_read_only_plan({
        "evidence": [{"tool": "inspect_scene", "arguments": {"file_name": "x.blend"}}],
        "actions": [],
    })

    assert result["read_only"] is True
    assert result["execution_authorized"] is False
    assert seen == [{"file_name": "x.blend"}]
    assert result["results"][0]["result"] == {"ok": True}


def test_read_only_executor_rejects_actions():
    with pytest.raises(PermissionError):
        execute_read_only_plan({
            "evidence": [],
            "actions": [{"tool": "move_object", "arguments": {}}],
        })


def test_read_only_executor_rejects_write_tool():
    with pytest.raises(PermissionError):
        execute_read_only_plan({
            "evidence": [{"tool": "move_object", "arguments": {}}],
            "actions": [],
        })


def test_read_only_executor_rejects_unknown_tool():
    with pytest.raises(PermissionError):
        execute_read_only_plan({
            "evidence": [{"tool": "not_a_tool", "arguments": {}}],
            "actions": [],
        })
