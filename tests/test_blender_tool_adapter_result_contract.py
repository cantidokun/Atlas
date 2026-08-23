from planning.blender_tool_adapter import BlenderToolAdapter


def test_adapter_normalizes_success_status():
    result = BlenderToolAdapter._normalize_result({
        "status": "moved",
        "object_name": "Goal_Left_post",
        "location": [1.0, 0.0, 0.0],
    })
    assert result["ok"] is True
    assert result["state"] == "moved"
    assert result["details"]["object_name"] == "Goal_Left_post"


def test_adapter_normalizes_error_status():
    result = BlenderToolAdapter._normalize_result({
        "status": "error",
        "error": "Object not found",
    })
    assert result["ok"] is False
    assert result["state"] == "error"
    assert result["details"]["error"] == "Object not found"


def test_adapter_preserves_new_contract_results():
    original = {"ok": True, "state": "moved", "details": {"x": 1}}
    assert BlenderToolAdapter._normalize_result(original) is original
