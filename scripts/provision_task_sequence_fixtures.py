"""Provision deterministic fixtures for the live two-task sequence proof."""
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
CORRECT_FILE = PROJECT_DIR / "sequence_CORRECT.blend"
INCORRECT_FILE = PROJECT_DIR / "sequence_INCORRECT.blend"
TARGET_OBJECT = "Goal_Left_post"
TARGET_LOCATION = (1.0, 2.0, 0.0)
INCORRECT_LOCATION = (0.0, 0.0, 0.0)
MARKER_OBJECT = "Atlas_Marker"
MARKER_COLLECTION = "Atlas_Test"


def configure_fixture(file_name: str, location: tuple[float, float, float], marker_present: bool) -> None:
    blend_path = validate_blend_file(file_name)
    script = f"""
import bpy
obj = bpy.data.objects.get({TARGET_OBJECT!r})
if obj is None:
    raise RuntimeError({TARGET_OBJECT!r} + ' missing from fixture')
obj.location = {list(location)!r}
marker = bpy.data.objects.get({MARKER_OBJECT!r})
if marker is not None:
    bpy.data.objects.remove(marker, do_unlink=True)
if {marker_present!r}:
    collection = bpy.data.collections.get({MARKER_COLLECTION!r})
    if collection is None:
        collection = bpy.data.collections.new({MARKER_COLLECTION!r})
        bpy.context.scene.collection.children.link(collection)
    marker = bpy.data.objects.new({MARKER_OBJECT!r}, None)
    collection.objects.link(marker)
bpy.ops.wm.save_as_mainfile(filepath={str(blend_path)!r})
print('ATLAS_SEQUENCE_FIXTURE_READY')
"""
    result = subprocess.run([
        r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        "--background", str(blend_path), "--python-expr", script,
    ], capture_output=True, text=True, timeout=60)
    if result.returncode != 0 or "ATLAS_SEQUENCE_FIXTURE_READY" not in result.stdout:
        raise RuntimeError((result.stderr or result.stdout)[-3000:])


def provision() -> None:
    if not BASE_FILE.is_file():
        raise FileNotFoundError(BASE_FILE)
    shutil.copyfile(BASE_FILE, CORRECT_FILE)
    shutil.copyfile(BASE_FILE, INCORRECT_FILE)
    configure_fixture(CORRECT_FILE.name, TARGET_LOCATION, True)
    configure_fixture(INCORRECT_FILE.name, INCORRECT_LOCATION, False)
    print(f"Provisioned {CORRECT_FILE.name} and {INCORRECT_FILE.name}")


if __name__ == "__main__":
    provision()
