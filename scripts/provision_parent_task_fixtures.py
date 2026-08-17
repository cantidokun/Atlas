"""Provision deterministic Blender fixtures for the parent-relationship task."""
from pathlib import Path
import os
import shutil
import sys

# Running ``python scripts/<file>.py`` places ``scripts/`` on sys.path, not
# the repository root. Make the repo-root import boundary explicit so live
# self-hosted execution behaves the same way as the offline test environment.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.blender import create_collection, create_empty_marker
from tools.blender_relationship import parent_object

PROJECT_DIR = os.path.abspath(os.path.expandvars(r"%USERPROFILE%\Desktop\Atlas"))
BASE_FILE = "goalpost_test.blend"
CORRECT_FILE = "parent_task_CORRECT.blend"
INCORRECT_FILE = "parent_task_INCORRECT.blend"


def provision(target):
    source = os.path.join(PROJECT_DIR, BASE_FILE)
    destination = os.path.join(PROJECT_DIR, target)
    shutil.copyfile(source, destination)
    collection = create_collection(target, "Atlas_Test")
    if collection.get("status") not in {"created", "already_exists"}:
        raise RuntimeError(collection)
    marker = create_empty_marker(target, "Atlas_Test", "Atlas_Marker")
    if marker.get("status") not in {"created", "already_exists"}:
        raise RuntimeError(marker)
    return target


if __name__ == "__main__":
    incorrect = provision(INCORRECT_FILE)
    correct = provision(CORRECT_FILE)
    result = parent_object(correct, "Atlas_Marker", "Goal_Left_post")
    if result.get("status") not in {"parented", "already_parented"}:
        raise RuntimeError(result)
    print(f"Provisioned {incorrect} and {correct}")
