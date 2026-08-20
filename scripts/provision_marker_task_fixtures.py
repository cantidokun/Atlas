"""Provision deterministic Blender fixtures for the live marker task."""
from pathlib import Path
import shutil
import subprocess

BASE = Path(r"C:\Users\Gavin's PC\Desktop\Atlas\goalpost_test.blend")
CORRECT = BASE.with_name("marker_task_CORRECT.blend")
INCORRECT = BASE.with_name("marker_task_INCORRECT.blend")
COLLECTION = "Atlas_Test"
MARKER = "Atlas_Marker"


def find_blender() -> str:
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


def run(blender: str, script: str, output: Path) -> None:
    script_path = BASE.with_name("_atlas_marker_fixture.py")
    script_path.write_text(script, encoding="utf-8")
    try:
        subprocess.run(
            [blender, "-b", str(BASE), "--python", str(script_path), "--", str(output)],
            check=True,
        )
    finally:
        script_path.unlink(missing_ok=True)


def main() -> int:
    if not BASE.exists():
        raise SystemExit(f"Base Blender fixture not found: {BASE}")
    blender = find_blender()

    correct_script = r'''import bpy
from pathlib import Path
import sys

output = Path(sys.argv[-1])
collection_name = "Atlas_Test"
marker_name = "Atlas_Marker"
collection = bpy.data.collections.get(collection_name)
if collection is None:
    collection = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(collection)
existing = bpy.data.objects.get(marker_name)
if existing is not None:
    bpy.data.objects.remove(existing, do_unlink=True)
marker = bpy.data.objects.new(marker_name, None)
collection.objects.link(marker)
bpy.ops.wm.save_as_mainfile(filepath=str(output))
'''
    run(blender, correct_script, CORRECT)

    incorrect_script = r'''import bpy
from pathlib import Path
import sys

output = Path(sys.argv[-1])
collection_name = "Atlas_Test"
marker_name = "Atlas_Marker"
collection = bpy.data.collections.get(collection_name)
if collection is None:
    collection = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(collection)
existing = bpy.data.objects.get(marker_name)
if existing is not None:
    bpy.data.objects.remove(existing, do_unlink=True)
bpy.ops.wm.save_as_mainfile(filepath=str(output))
'''
    run(blender, incorrect_script, INCORRECT)

    print(f"Provisioned correct marker fixture: {CORRECT}")
    print(f"Provisioned incorrect marker fixture: {INCORRECT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
