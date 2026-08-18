"""Provision deterministic fixtures for the live Blender object-rotation task."""
from pathlib import Path
import os
import shutil
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.blender import validate_blend_file

PROJECT_DIR = Path(os.path.abspath(os.path.expandvars(r"%USERPROFILE%\Desktop\Atlas")))
BASE_FILE = PROJECT_DIR / "goalpost_test.blend"
CORRECT_FILE = PROJECT_DIR / "object_rotation_CORRECT.blend"
INCORRECT_FILE = PROJECT_DIR / "object_rotation_INCORRECT.blend"
TARGET_OBJECT = "Atlas_Rotation_Candidate"


def set_fixture(file_name: str, rotation: tuple[float, float, float]) -> None:
    blend_path = validate_blend_file(file_name)
    script = f"""
import bpy
obj = bpy.data.objects.get({TARGET_OBJECT!r})
if obj is None:
    obj = bpy.data.objects.new({TARGET_OBJECT!r}, None)
    bpy.context.scene.collection.objects.link(obj)
obj.rotation_mode = 'XYZ'
obj.rotation_euler = tuple(__import__('math').radians(value) for value in {list(rotation)!r})
bpy.ops.wm.save_as_mainfile(filepath={str(blend_path)!r})
print('ATLAS_ROTATION_FIXTURE_READY')
"""
    result = subprocess.run([
        r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        "--background", str(blend_path), "--python-expr", script,
    ], capture_output=True, text=True, timeout=60)
    if "ATLAS_ROTATION_FIXTURE_READY" not in result.stdout:
        raise RuntimeError(result.stdout[-3000:])


def provision() -> None:
    if not BASE_FILE.is_file():
        raise FileNotFoundError(BASE_FILE)
    shutil.copyfile(BASE_FILE, CORRECT_FILE)
    shutil.copyfile(BASE_FILE, INCORRECT_FILE)
    set_fixture(CORRECT_FILE.name, (0.0, 0.0, 90.0))
    set_fixture(INCORRECT_FILE.name, (0.0, 0.0, 0.0))
    print(f"Provisioned {CORRECT_FILE.name} and {INCORRECT_FILE.name}")


if __name__ == "__main__":
    provision()
