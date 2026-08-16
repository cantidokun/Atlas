"""Provision deterministic Blender fixtures for the live conditional harness."""
from pathlib import Path
import shutil
import subprocess
import sys

BASE = Path(r"C:\Users\Gavin's PC\Desktop\Atlas\goalpost_test.blend")
CORRECT = BASE.with_name("goalpost_test_CONDITIONAL_CORRECT.blend")
INCORRECT = BASE.with_name("goalpost_test_CONDITIONAL_INCORRECT.blend")
LEFT = (0.0, 5.233, 0.0)
RIGHT = (0.0, -5.233, 0.0)


def main() -> int:
    if not BASE.exists():
        raise SystemExit(f"Base Blender fixture not found: {BASE}")
    blender = shutil.which("blender")
    if not blender:
        raise SystemExit("Blender executable not found on PATH.")

    script = r'''import bpy
from pathlib import Path
import sys

output = Path(sys.argv[-1])
left = bpy.data.objects.get("Goal_Left_post")
right = bpy.data.objects.get("Goal_Right_Post")
if left is None or right is None:
    raise RuntimeError("Required goalpost objects were not found")
left.location = (0.0, 5.233, 0.0)
right.location = (0.0, -5.233, 0.0)
bpy.ops.wm.save_as_mainfile(filepath=str(output))
'''
    tmp = BASE.with_name("_atlas_make_correct.py")
    tmp.write_text(script, encoding="utf-8")
    try:
        subprocess.run([blender, "-b", str(BASE), "--python", str(tmp), "--", str(CORRECT)], check=True)
    finally:
        tmp.unlink(missing_ok=True)

    shutil.copy2(BASE, INCORRECT)
    print(f"Provisioned correct fixture: {CORRECT}")
    print(f"Provisioned incorrect fixture: {INCORRECT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
