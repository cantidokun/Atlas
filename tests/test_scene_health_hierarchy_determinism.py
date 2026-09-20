"""Regression tests for hierarchy-cycle report determinism across hash seeds."""

import os
import subprocess
import sys
from textwrap import dedent


_SCRIPT = dedent(
    """
    from planning.blender import ObjectModel, SceneModel, run_scene_health, soccer_field_profile

    def obj(oid, parent):
        return ObjectModel(object_id=oid, name=oid, parent_object_id=parent)

    scene = SceneModel(
        scene_id="cycle",
        unit_system="METERS",
        objects=(
            obj("cycle_b", "cycle_c"),
            obj("cycle_a", "cycle_b"),
            obj("cycle_c", "cycle_a"),
        ),
    )
    report = run_scene_health(scene, soccer_field_profile())
    print(report.digest())
    """
)


def test_hierarchy_cycle_report_digest_is_hashseed_deterministic():
    digests = set()
    for seed in ("1", "2", "3", "4", "5", "101", "202"):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = seed
        result = subprocess.run(
            [sys.executable, "-c", _SCRIPT],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        digests.add(result.stdout.strip())

    assert len(digests) == 1
