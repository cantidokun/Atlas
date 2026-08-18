"""Provision deterministic fixtures for the live Blender object-rename task."""
from pathlib import Path
import os
import shutil
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.blender_object import rename_object

PROJECT_DIR = Path(os.path.abspath(os.path.expandvars(r"%USERPROFILE%\Desktop\Atlas")))
BASE_FILE = PROJECT_DIR / "goalpost_test.blend"
CORRECT_FILE = PROJECT_DIR / "object_rename_CORRECT.blend"
INCORRECT_FILE = PROJECT_DIR / "object_rename_INCORRECT.blend"


def provision() -> None:
    if not BASE_FILE.is_file():
        raise FileNotFoundError(BASE_FILE)
    shutil.copyfile(BASE_FILE, INCORRECT_FILE)
    shutil.copyfile(BASE_FILE, CORRECT_FILE)
    result = rename_object(CORRECT_FILE.name, "Goal_Left_post", "Goal_Left_Post")
    if result.get("status") not in {"renamed", "already_named"}:
        raise RuntimeError(result)
    print(f"Provisioned {CORRECT_FILE.name} and {INCORRECT_FILE.name}")


if __name__ == "__main__":
    provision()
