"""Provision deterministic fixtures for the live Blender object-delete task."""
from pathlib import Path
import os
import shutil
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.blender import validate_blend_file, run_blender

PROJECT_DIR = Path(os.path.abspath(os.path.expandvars(r"%USERPROFILE%\Desktop\Atlas")))
BASE_FILE = PROJECT_DIR / "goalpost_test.blend"
CORRECT_FILE = PROJECT_DIR / "object_delete_CORRECT.blend"
INCORRECT_FILE = PROJECT_DIR / "object_delete_INCORRECT.blend"
TARGET_OBJECT = "Atlas_Delete_Candidate"


def add_candidate(file_name: str) -> None:
    blend_path = validate_blend_file(file_name)
    script = f"""
import bpy
obj = bpy.data.objects.get({TARGET_OBJECT!r})
if obj is None:
    obj = bpy.data.objects.new({TARGET_OBJECT!r}, None)
    bpy.context.scene.collection.objects.link(obj)
bpy.ops.wm.save_as_mainfile(filepath={str(blend_path)!r})
print('ATLAS_FIXTURE_READY')
"""
    result = __import__('subprocess').run([
        r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        "--background", str(blend_path), "--python-expr", script,
    ], capture_output=True, text=True, timeout=60)
    if "ATLAS_FIXTURE_READY" not in result.stdout:
        raise RuntimeError(result.stdout[-3000:])


def provision() -> None:
    if not BASE_FILE.is_file():
        raise FileNotFoundError(BASE_FILE)
    shutil.copyfile(BASE_FILE, INCORRECT_FILE)
    shutil.copyfile(BASE_FILE, CORRECT_FILE)
    add_candidate(INCORRECT_FILE.name)
    print(f"Provisioned {CORRECT_FILE.name} and {INCORRECT_FILE.name}")


if __name__ == "__main__":
    provision()
