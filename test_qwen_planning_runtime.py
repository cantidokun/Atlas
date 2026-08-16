"""Tests for the read-only Qwen planning runtime adapter."""

from qwen_planning_runtime import parse_qwen_plan, planning_summary


def test_parses_structured_qwen_plan_without_execution():
    content = '''
Some reasoning here.
ATLAS_TASK_PLAN: {
  "evidence": [
    {"tool": "inspect_scene", "arguments": {"file_name": "scene.blend"}, "name": "scene"}
  ],
  "actions": [
    {"tool": "move_object", "arguments": {"object_name": "A", "location": [1, 0, 0]}, "name": "move"}
  ]
}
'''

    proposal = parse_qwen_plan(content, allowed_tools={"inspect_scene", "move_object"})
    assert proposal is not None
    assert proposal.evidence[0].tool == "inspect_scene"
    assert proposal.actions[0].tool == "move_object"


def test_summary_explicitly_reports_no_execution_authorization():
    content = '''ATLAS_TASK_PLAN: {"evidence": [], "actions": []}'''
    proposal = parse_qwen_plan(content)
    summary = planning_summary(proposal)
    assert summary["execution_authorized"] is False
    assert summary["evidence_count"] == 0
    assert summary["action_count"] == 0


def test_missing_plan_marker_returns_none():
    assert parse_qwen_plan("plain Qwen output") is None
