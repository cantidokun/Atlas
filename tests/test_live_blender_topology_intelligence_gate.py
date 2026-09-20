"""Executable gate for the disposable Wave 5 + Read-Only Non-Manifold Blender probe."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

EXPECTED_BLENDER = (4, 4, 3)
MARKER = "ATLAS_READONLY_NON_MANIFOLD_V1_LIVE"

# The live script is intentionally strict: changing/removing evidence checks must require
# changing this expected surface rather than silently shrinking the gate.
EXPECTED_CHECK_NAMES = {
    "repeatable_extraction",
    "scene_report_digest_repeatable",
    "scene_input_digest_repeatable",
    "scene_report_no_unexpected_findings",
    "scene_report_planner_no_correction",
    "scene_report_planner_state",
    "mapping_row_frozen",
    "executor_allowlist_frozen",
    "raw_incidence_independent",
    "independent_v3_incidence",
    "independent_v4_incidence",
    "independent_two_edge_incidence",
    "finding_scope",
    "no_post_validation_mutation",
    "no_save",
    "fixture_count_stable",
    "scene_report_input_digest_matches_model",
}
for _name in (
    "nm_v1_boundary",
    "nm_v2_manifold",
    "nm_v3_edge3",
    "nm_v4_edge4",
    "nm_clean_control",
    "nm_two_nm_edges",
    "nm_quadtri_control",
):
    EXPECTED_CHECK_NAMES.update({
        f"{_name}_raw_faces",
        f"{_name}_canonical_faces",
        f"{_name}_finding",
        f"{_name}_no_extra_findings",
        f"{_name}_metric_coherence",
        f"{_name}_planner_no_correction",
        f"{_name}_planner_state",
    })


def _blender_executable():
    return os.environ.get("ATLAS_BLENDER_EXECUTABLE") or shutil.which("blender")


@pytest.mark.skipif(
    os.environ.get("ATLAS_RUN_LIVE_BLENDER") != "1",
    reason="set ATLAS_RUN_LIVE_BLENDER=1 to run the live Blender gate",
)
def test_live_blender_topology_gate():
    executable = _blender_executable()
    if not executable:
        pytest.fail("Blender executable not found; set ATLAS_BLENDER_EXECUTABLE")

    script = Path(__file__).with_name("topology_intelligence_live_script.py")
    repo_root = script.resolve().parents[1]

    # Make the child hermetic. Do not inherit PYTHONPATH or unrelated ATLAS_* knobs.
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("ATLAS_") and key != "PYTHONPATH"
    }
    completed = subprocess.run(
        [
            executable,
            "--background",
            "--python-exit-code",
            "1",
            "--python",
            str(script),
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = completed.stdout + "\n" + completed.stderr
    assert completed.returncode == 0, combined

    payload = None
    for line in completed.stdout.splitlines():
        line = line.strip()
        if line.startswith("{") and '"marker"' in line:
            payload = json.loads(line)

    assert payload is not None, combined
    assert tuple(payload["blender_version"]) == EXPECTED_BLENDER
    assert payload["failed"] == []
    assert set(payload["checks"]) == EXPECTED_CHECK_NAMES
    assert payload["required_assertions"] == len(EXPECTED_CHECK_NAMES)
    assert payload["passed"] == len(EXPECTED_CHECK_NAMES)
    assert payload["save_attempted"] is False
    assert payload["opened_frozen_asset"] is False
    assert f"{MARKER}_PASS" in completed.stdout
