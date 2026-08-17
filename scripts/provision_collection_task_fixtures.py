"""Provision deterministic Blender fixtures for the generic collection task."""
from pathlib import Path
import shutil
import subprocess

BASE = Path(r"C:\Users\Gavin's PC\Desktop\Atlas\goalpost_test.blend")
CORRECT = BASE.with_name("collection_task_CORRECT.blend")
INCORRECT = BASE.with_name("collection_task_INCORRECT.blend")
COLLECTION = "Atlas_Test"


def main() -> int:
    if not BASE.exists():
        raise SystemExit(f"Base Blender fixture not found: {BASE}")
    blender = shutil.which("blender")
    if not blender:
        candidates = [
            r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
        ]
        blender = next((p for p in candidates if Path(p).exists()), None)
    if not blender:
        raise SystemExit("Blender executable not found on PATH or known install locations.")

    script = r'''import bpy
from pathlib import Path
import sys

output = Path(sys.argv[-1])
name = "Atlas_Test"
existing = bpy.data.collections.get(name)
if existing is None:
    existing = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(existing)
bpy.ops.wm.save_as_mainfile(filepath=str(output))
'''
    tmp_correct = BASE.with_name("_atlas_make_collection_correct.py")
    tmp_correct.write_text(script, encoding="utf-8")
    try:
        subprocess.run(
            [blender, "-b", str(BASE), "--python", str(tmp_correct), "--", str(CORRECT)],
            check=True,
        )
    finally:
        tmp_correct.unlink(missing_ok=True)

    remove_script = r'''import bpy
from pathlib import Path
import sys

output = Path(sys.argv[-1])
name = "Atlas_Test"
existing = bpy.data.collections.get(name)
if existing is not None:
    for scene_collection in list(bpy.context.scene.collection.children):
        if scene_collection.name == name:
            bpy.context.scene.collection.children.unlink(scene_collection)
    for obj in list(existing.objects):
        existing.objects.unlink(obj)
    bpy.data.collections.remove(existing)
bpy.ops.wm.save_as_mainfile(filepath=str(output))
'''
    tmp_incorrect = BASE.with_name("_atlas_make_collection_incorrect.py")
    tmp_incorrect.write_text(remove_script, encoding="utf-8")
    try:
        subprocess.run(
            [blender, "-b", str(BASE), "--python", str(tmp_incorrect), "--", str(INCORRECT)],
            check=True,
        )
    finally:
        tmp_incorrect.unlink(missing_ok=True)

    print(f"Provisioned correct collection fixture: {CORRECT}")
    print(f"Provisioned incorrect collection fixture: {INCORRECT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
