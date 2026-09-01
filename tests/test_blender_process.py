from unittest.mock import patch

import pytest

from tools.blender_process import BlenderProcessError, run_checked_blender


def _result(stdout="ATLAS_START{\"ok\":true}ATLAS_END", returncode=0, stderr=""):
    return type("Completed", (), {"stdout": stdout, "stderr": stderr, "returncode": returncode})()


def test_nonzero_exit_fails_closed():
    with patch("tools.blender_process.subprocess.run", return_value=_result(returncode=2, stderr="traceback")):
        with pytest.raises(BlenderProcessError, match="exit code 2"):
            run_checked_blender("blender", "scene.blend", "pass", "ATLAS_START", "ATLAS_END")


def test_timeout_fails_closed():
    with patch("tools.blender_process.subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("blender", 60)):
        with pytest.raises(BlenderProcessError, match="timed out"):
            run_checked_blender("blender", "scene.blend", "pass", "ATLAS_START", "ATLAS_END")


def test_startup_failure_fails_closed():
    with patch("tools.blender_process.subprocess.run", side_effect=OSError("missing executable")):
        with pytest.raises(BlenderProcessError, match="Unable to start"):
            run_checked_blender("blender", "scene.blend", "pass", "ATLAS_START", "ATLAS_END")


def test_end_marker_must_follow_start_marker():
    output = "ATLAS_ENDATLAS_START{\"ok\":true}"
    with patch("tools.blender_process.subprocess.run", return_value=_result(stdout=output)):
        with pytest.raises(BlenderProcessError, match="valid result"):
            run_checked_blender("blender", "scene.blend", "pass", "ATLAS_START", "ATLAS_END")


def test_non_object_json_fails_closed():
    output = "ATLAS_START[1,2,3]ATLAS_END"
    with patch("tools.blender_process.subprocess.run", return_value=_result(stdout=output)):
        with pytest.raises(BlenderProcessError, match="JSON object"):
            run_checked_blender("blender", "scene.blend", "pass", "ATLAS_START", "ATLAS_END")
