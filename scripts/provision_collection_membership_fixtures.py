"""Provision deterministic Blender fixtures for collection-membership tasks."""
from pathlib import Path
import os
import shutil
import subprocess

PROJECT_DIR = Path(os.path.abspath(os.path.expandvars(r"%USERPROFILE%\Desktop\Atlas")))
BASE = PROJECT_DIR / "goalpost_test.blend"
CORRECT = PROJECT_DIR / "collection_membership_CORRECT.blend"
INCORRECT = PROJECT_DIR / "collection_membership_INCORRECT.blend"
TARGET_COLLECTION = "Atlas_Test"
TARGET_OBJECT = "Atlas_Marker"


def blender_path() -> str:
    blender = shutil.which("blender")
    if blender:
        return blender
    for candidate in (
        r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
    ):
        if Path(candidate).exists():
            return candidate
    raise SystemExit("Blender executable not found on PATH or known install locations.")


def provision(output: Path, correct: bool) -> None:
    script = f'''import bpy\nfrom pathlib import Path\nimport sys\n\noutput = Path(sys.argv[-1])\ntarget_name = {TARGET_COLLECTION!r}\nobject_name = {TARGET_OBJECT!r}\ncollection = bpy.data.collections.get(target_name)\nif collection is None:\n    collection = bpy.data.collections.new(target_name)\n    bpy.context.scene.collection.children.link(collection)\n\nobj = bpy.data.objects.get(object_name)\nif obj is None:\n    obj = bpy.data.objects.new(object_name, None)\n\nfor linked in list(obj.users_collection):\n    linked.objects.unlink(obj)\n\nif {correct!r}:\n    collection.objects.link(obj)\nelse:\n    bpy.context.scene.collection.objects.link(obj)\n\nbpy.ops.wm.save_as_mainfile(filepath=str(output))\n'''
    temp = PROJECT_DIR / "_atlas_collection_membership_fixture.py"
    temp.write_text(script, encoding="utf-8")
    try:
        subprocess.run([blender_path(), "-b", str(BASE), "--python", str(temp), "--", str(output)], check=True)
    finally:
        temp.unlink(missing_ok=True)


def main() -> int:
    if not BASE.exists():
        raise SystemExit(f"Base Blender fixture not found: {BASE}")
    provision(CORRECT, True)
    provision(INCORRECT, False)
    print(f"Provisioned correct membership fixture: {CORRECT}")
    print(f"Provisioned incorrect membership fixture: {INCORRECT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
