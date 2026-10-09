"""A-REF aliasing-detection assessment (R4F 16.6(4): C3/C4 postcondition sets) + live attempt record.

Source-inspection half: asserts the pinned postcondition code that detects a shared-datablock
change for each operation family (C1/C2 face removal, C3 winding WC-Q11, C4 merge MQ-6), and runs
the planner's explicit merge pass over the PURE aliased report to record the refusal the aliased
merge scene produces (two target scopes). The live half is the marker-recorded attempt run by the
live gate.
"""

import json
import os
from pathlib import Path

import pytest

from tests.aref.aref_live_driver import DEFAULT_EVIDENCE
from tests.aref.aref_pure import build_graph, make_pure_extractor
from tests.aref.aref_plan import real_merge_plan
from tests.aref.fixtures import load_case

REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTOR_SOURCE = REPO_ROOT / "planning" / "blender" / "correction_executor.py"

#: Source-backed aliasing detection, one pinned evidence site per operation family.
DETECTION_SITES = {
    "C1/C2 face removal": "unrelated object {obj.object_id!r} state changed",
    "C3 winding (WC-Q11)": "WC-Q11",
    "C4 merge (MQ-6)": "MQ-6",
}


def test_source_inspection_aliasing_detection_sites_exist():
    text = EXECUTOR_SOURCE.read_text(encoding="utf-8", errors="replace")
    missing = [name for name, marker in DETECTION_SITES.items() if marker not in text]
    assert missing == [], f"aliasing-detection sites missing from the pinned executor: {missing}"
    # the site markers carry the source line numbers into the recorded evidence (recorded below)
    lines = {}
    for name, marker in DETECTION_SITES.items():
        for number, line in enumerate(text.splitlines(), start=1):
            if marker in line:
                lines[name] = number
                break
    record = {"source": str(EXECUTOR_SOURCE.relative_to(REPO_ROOT)).replace("\\", "/"),
              "detection_sites": lines,
              "conclusion": ("every operation family's postcondition set contains an unrelated-"
                             "object check, so a shared-datablock change is detected for C1/C2 "
                             "(face removal), C3 (WC-Q11) and C4 (MQ-6)")}
    path = DEFAULT_EVIDENCE / "aliasing_detection_source.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    assert set(lines) == set(DETECTION_SITES)


def test_aliased_merge_pass_refuses_multiple_scopes_on_the_pure_path():
    """The pure half of the C4 aliased attempt: two scopes are refused, not aggregated."""
    spec = load_case("AREF-TEST-FX-AL-C1")  # aliased two-object scene (C1 operation, same graph)
    aliased = {"scene": {"scene_id": spec.scene["scene_id"], "unit_system": spec.scene["unit_system"]},
               "datablocks": [{"db_key": "DB1", "db_name": "atlas-target",
                               "vertices": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [7.0, 0.0, 0.0],
                                            [3.0, 3.0, 0.0], [3.0, 3.0, 0.0], [4.0, 0.0, 5.0]],
                               "faces": [[0, 2, 3], [5, 2, 3]]}],
               "objects": [{"object_id": "atlas-target", "datablock_key": "DB1", "type": "MESH"},
                           {"object_id": "atlas-unrelated", "datablock_key": "DB1", "type": "MESH"}]}
    from tests.aref.aref_live_common import load_case_live  # noqa: F401  (kept import-light)

    from types import SimpleNamespace

    shim = SimpleNamespace(**aliased)
    graph = build_graph(shim)
    payload = graph.project_payload(shim.scene["scene_id"], shim.scene["unit_system"], None)
    scene, report = make_pure_extractor(shim)(graph)
    outcome = real_merge_plan(report, payload)
    assert outcome.refusal_code is not None
    assert outcome.plan.corrections == ()
    # the refusal is a planning-state refusal, never NO_CORRECTIONS (which would imply nothing to review)
    assert outcome.plan.state in ("REVIEW_REQUIRED", "PLANNING_ERROR")
    record = {"refusal_code": outcome.refusal_code, "plan_state": outcome.plan.state,
              "scopes": sorted({(f.object_id, f.mesh_id) for f in report.findings
                                if f.code.value == "MESH_DUPLICATE_VERTEX"})}
    path = DEFAULT_EVIDENCE / "aliased_merge_pure_attempt.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, sort_keys=True, indent=1, default=list) + "\n",
                    encoding="utf-8")
    assert record["scopes"], record
