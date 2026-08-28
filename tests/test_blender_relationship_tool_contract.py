from unittest.mock import patch

import pytest

from tools.blender_relationship import inspect_object_parent, parent_object


def test_parent_object_rejects_unauthorized_child_before_blender_call():
    with patch("tools.blender_relationship.run_blender") as run:
        result = parent_object("scene.blend", "Cube", "Goal_Left_post")

    assert result["status"] == "error"
    run.assert_not_called()


def test_parent_object_rejects_unauthorized_parent_before_blender_call():
    with patch("tools.blender_relationship.run_blender") as run:
        result = parent_object("scene.blend", "Atlas_Marker", "Cube")

    assert result["status"] == "error"
    run.assert_not_called()


def test_parent_object_rejects_self_parenting_before_blender_call():
    with patch("tools.blender_relationship.run_blender") as run:
        result = parent_object("scene.blend", "Atlas_Marker", "Atlas_Marker")

    assert result["status"] == "error"
    run.assert_not_called()


def test_parent_inspection_is_read_only():
    with patch("tools.blender_relationship.validate_blend_file", return_value="scene.blend"), patch(
        "tools.blender_relationship.run_blender",
        return_value={"status": "inspected", "object_name": "Atlas_Marker", "parent_name": "Goal_Left_post"},
    ) as run:
        result = inspect_object_parent("scene.blend", "Atlas_Marker")

    assert result["status"] == "inspected"
    run.assert_called_once()
