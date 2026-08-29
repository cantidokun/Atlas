"""Provision deterministic fixtures for the live Blender create-collection gate."""
from pathlib import Path
import os
import subprocess

PROJECT_DIR = Path(os.path.abspath(os.path.expandvars(r"%USERPROFILE%\Desktop\Atlas")))
BASE_FILE = PROJECT_DIR / "goalpost_test.blend"
CORRECT_FILE = PROJECT_DIR / "create_collection_CORRECT.blend"
INCORRECT_FILE = PROJECT_DIR / "create_collection_INCORRECT.blend"
TARGET_COLLECTION = "Atlas_Test"


def blender_path() -> str:
    for candidate in (
        r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
    ):
        if Path(candidate).exists():
            return candidate
    raise SystemExit("Blender executable not found in known install locations.")


def provision(output: Path, collection_exists: bool) -> None:
    script = f'''import bpy\nfrom pathlib import Path\nimport sys\n\noutput = Path(sys.argv[-1])\ntarget = {TARGET_COLLECTION!r}\nfor collection in list(bpy.data.collections):\n    if collection.name == target:\n        bpy.data.collections.remove(collection, do_unlink=True)\nif {collection_exists!r}:\n    collection = bpy.data.collections.new(target)\n    bpy.context.scene.collection.children.link(collection)\n\nbpy.ops.wm.save_as_mainfile(filepath=str(output))\n'''
    temp = PROJECT_DIR / "_atlas_create_collection_fixture.py"
    temp.write_text(script, encoding="utf-8")
    try:
        result = subprocess.run(
            [blender_path(), "--background", str(BASE_FILE), "--python", str(temp), "--", str(output)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout)[-3000:])
    finally:
        temp.unlink(missing_ok=True)


def main() -> int:
    if not BASE_FILE.is_file():
        raise SystemExit(f"Base Blender fixture not found: {BASE_FILE}")
    provision(CORRECT_FILE, True)
    provision(INCORRECT_FILE, False)
    print(f"Provisioned {CORRECT_FILE.name} and {INCORRECT_FILE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
