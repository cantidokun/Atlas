from tools.blender_relationship import ALLOWED_CHILD, ALLOWED_PARENT, parent_object


def test_parent_tool_has_explicit_safety_allowlist():
    assert ALLOWED_CHILD == "Atlas_Marker"
    assert ALLOWED_PARENT == "Goal_Left_post"


def test_parent_tool_rejects_unauthorized_child_before_blender_execution(monkeypatch, tmp_path):
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("Blender should not execute for rejected input")

    monkeypatch.setattr("tools.blender_relationship.run_blender", fake_run)
    result = parent_object(str(tmp_path / "scene.blend"), "Other_Object", ALLOWED_PARENT)

    assert result["status"] == "error"
    assert not called


def test_parent_tool_rejects_unauthorized_parent_before_blender_execution(monkeypatch, tmp_path):
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("Blender should not execute for rejected input")

    monkeypatch.setattr("tools.blender_relationship.run_blender", fake_run)
    result = parent_object(str(tmp_path / "scene.blend"), ALLOWED_CHILD, "Other_Object")

    assert result["status"] == "error"
    assert not called
