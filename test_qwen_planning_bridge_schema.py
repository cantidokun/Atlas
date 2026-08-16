from qwen_planning_bridge import extract_task_plan_proposal


def test_rejects_different_json_schema_as_plan():
    content = (
        'ATLAS_TASK_PLAN: '
        '{"request_type":"evidence_request","tool":"inspect_scene",'
        '"parameters":{}}'
    )
    assert extract_task_plan_proposal(content) is None


def test_accepts_atlas_plan_envelope():
    content = (
        'ATLAS_TASK_PLAN: '
        '{"evidence":[{"tool":"inspect_scene","arguments":{},"name":"scene"}],'
        '"actions":[]}'
    )
    parsed = extract_task_plan_proposal(content)
    assert parsed is not None
    assert len(parsed["evidence"]) == 1
    assert parsed["actions"] == []
