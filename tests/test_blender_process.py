import json

import pytest

from tools.blender_process import run_checked_blender


class Completed:
    def __init__(self, returncode, stdout, stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_checked_blender_rejects_nonzero_process(monkeypatch):
    monkeypatch.setattr(
        "tools.blender_process.subprocess.run",
        lambda *args, **kwargs: Completed(
            1,
            "ATLAS_START\n{\"ok\":true}\nATLAS_END",
            "Blender crash",
        ),
    )

    with pytest.raises(RuntimeError, match="exit code 1"):
        run_checked_blender("blender", "scene.blend", "", "ATLAS_START", "ATLAS_END")


def test_checked_blender_rejects_invalid_json(monkeypatch):
    monkeypatch.setattr(
        "tools.blender_process.subprocess.run",
        lambda *args, **kwargs: Completed(
            0,
            "ATLAS_START\nnot-json\nATLAS_END",
        ),
    )

    with pytest.raises(RuntimeError, match="invalid JSON"):
        run_checked_blender("blender", "scene.blend", "", "ATLAS_START", "ATLAS_END")


def test_checked_blender_requires_object_result(monkeypatch):
    monkeypatch.setattr(
        "tools.blender_process.subprocess.run",
        lambda *args, **kwargs: Completed(
            0,
            "ATLAS_START\n[1, 2, 3]\nATLAS_END",
        ),
    )

    with pytest.raises(RuntimeError, match="JSON object"):
        run_checked_blender("blender", "scene.blend", "", "ATLAS_START", "ATLAS_END")


def test_checked_blender_rejects_missing_end_marker(monkeypatch):
    monkeypatch.setattr(
        "tools.blender_process.subprocess.run",
        lambda *args, **kwargs: Completed(
            0,
            "ATLAS_START\n{\"ok\":true}",
        ),
    )

    with pytest.raises(RuntimeError, match="end marker missing"):
        run_checked_blender("blender", "scene.blend", "", "ATLAS_START", "ATLAS_END")


def test_checked_blender_rejects_timeout(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise TimeoutError("runner timeout")

    monkeypatch.setattr(
        "tools.blender_process.subprocess.run",
        raise_timeout,
    )

    with pytest.raises(TimeoutError, match="runner timeout"):
        run_checked_blender("blender", "scene.blend", "", "ATLAS_START", "ATLAS_END")


def test_checked_blender_returns_valid_object(monkeypatch):
    payload = {"status": "ok", "persisted": True}
    monkeypatch.setattr(
        "tools.blender_process.subprocess.run",
        lambda *args, **kwargs: Completed(
            0,
            f"noise\nATLAS_START\n{json.dumps(payload)}\nATLAS_END\n",
        ),
    )

    assert (
        run_checked_blender("blender", "scene.blend", "", "ATLAS_START", "ATLAS_END")
        == payload
    )
