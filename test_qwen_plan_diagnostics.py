import pytest

from qwen_plan_diagnostics import diagnose_qwen_plan


def test_valid_plan_is_classified_valid():
    content = 'ATLAS_TASK_PLAN: {"evidence":[{"tool":"inspect_scene","arguments":{"file_name":"scene.blend"}}],"actions":[]}'
    result = diagnose_qwen_plan(content, allowed_tools={"inspect_scene"})
    assert result.status == "valid"
    assert result.proposal is not None


def test_empty_output_is_malformed():
    result = diagnose_qwen_plan("", allowed_tools={"inspect_scene"})
    assert result.status == "malformed"


def test_wrong_schema_is_malformed():
    content = 'ATLAS_TASK_PLAN: {"request_type":"evidence_request","tool":"inspect_scene"}'
    result = diagnose_qwen_plan(content, allowed_tools={"inspect_scene"})
    assert result.status == "malformed"


def test_disallowed_tool_is_unsupported():
    content = 'ATLAS_TASK_PLAN: {"evidence":[{"tool":"delete_object","arguments":{}}],"actions":[]}'
    result = diagnose_qwen_plan(content, allowed_tools={"inspect_scene"})
    assert result.status == "unsupported"
    assert result.proposal is None
