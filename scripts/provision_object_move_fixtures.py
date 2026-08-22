"""Provision deterministic fixtures for the live Blender object-movement task."""
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
CORRECT_FILE = PROJECT_DIR / "object_move_CORRECT.blend"
INCORRECT_FILE = PROJECT_DIR / "object_move_INCORRECT.blend"
TARGET_OBJECT = "Goal_Left_post"
TARGET_LOCATION = (1.0, 2.0, 0.0)
INCORRECT_LOCATION = (0.0, 0.0, 0.0)


def set_fixture(file_name: str, location: tuple[float, float, float]) -> None:
    blend_path = validate_blend_file(file_name)
    script = f"""
import bpy
obj = bpy.data.objects.get({TARGET_OBJECT!r})
if obj is None:
    raise RuntimeError({TARGET_OBJECT!r} + ' missing from fixture')
obj.location = {list(location)!r}
bpy.ops.wm.save_as_mainfile(filepath={str(blend_path)!r})
print('ATLAS_MOVE_FIXTURE_READY')
"""
    result = subprocess.run([
        r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        "--background", str(blend_path), "--python-expr", script,
    ], capture_output=True, text=True, timeout=60)
    if result.returncode != 0 or "ATLAS_MOVE_FIXTURE_READY" not in result.stdout:
        raise RuntimeError((result.stderr or result.stdout)[-3000:])


def provision() -> None:
    if not BASE_FILE.is_file():
        raise FileNotFoundError(BASE_FILE)
    shutil.copyfile(BASE_FILE, CORRECT_FILE)
    shutil.copyfile(BASE_FILE, INCORRECT_FILE)
    set_fixture(CORRECT_FILE.name, TARGET_LOCATION)
    set_fixture(INCORRECT_FILE.name, INCORRECT_LOCATION)
    print(f"Provisioned {CORRECT_FILE.name} and {INCORRECT_FILE.name}")


if __name__ == "__main__":
    provision()
