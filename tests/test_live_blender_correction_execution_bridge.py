"""Operator-gated live Blender test for the production Correction Execution Bridge.

The fixture .blend files are created by a preparatory Blender process and are NOT written by the
correction bridge itself. Each bridge invocation runs one disposable Blender process/session:
pre-state extraction -> canonical correction executor -> real Blender mutation -> fresh extraction.
The source fixture is hash-checked before/after and no .blend/.blend1 artifact may appear.
"""
import base64
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from planning.blender.correction_authorization import mapping_digest
from planning.blender.correction_contract import CorrectionPlan
from planning.blender.correction_execution_bridge import CorrectionExecutionBridge
from planning.blender.correction_values import thaw_jsonable


REPO = Path(__file__).resolve().parents[1]
FROZEN_ASSET = REPO / "tests" / "assets" / "blender" / "atlas_transform_validation.blend"
BLENDER_ENV = os.environ.get("ATLAS_RUN_LIVE_BLENDER", "") == "1"

pytestmark = pytest.mark.skipif(not BLENDER_ENV, reason="live Blender gate off")

PROFILE = {"name": "soccer-field", "version": "1"}
OPS = (
    "REMOVE_DUPLICATE_FACE",
    "REMOVE_DEGENERATE_FACE",
    "REPAIR_FACE_WINDING",
    "REPAIR_MERGE_VERTEX",
)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _blend_inventory(root):
    found = {}
    for path in root.rglob("*"):
        if ".git" in path.parts or ".venv" in path.parts:
            continue
        if path.suffix.lower() in {".blend", ".blend1"} and path.is_file():
            found[str(path)] = (_sha256(path), path.stat().st_size)
    return found


def _run_blender_script(script):
    from tools.blender import BLENDER

    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    expr = (
        "import base64; "
        "exec(compile(base64.b64decode('" + encoded + "').decode('utf-8'), '<atlas-live-gate>', 'exec'))"
    )
    return subprocess.run(
        [BLENDER, "--background", "--factory-startup", "--python-expr", expr],
        capture_output=True,
        text=True,
        timeout=240,
        cwd=REPO,
        env=dict(os.environ, PYTHONPATH=str(REPO)),
        check=False,
    )


def _create_fixture(path, operation):
    script = f"""
import bpy, json, os
path = {str(path)!r}
operation = {operation!r}

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)

if operation == "REMOVE_DUPLICATE_FACE":
    verts = [(0,0,0),(1,0,0),(0,1,0),(2,0,0),(3,0,0),(2,1,0)]
    faces = [(0,1,2),(3,4,5),(3,4,5)]
elif operation == "REMOVE_DEGENERATE_FACE":
    verts = [(0,0,0),(1,0,0),(2,0,0),(0,1,0)]
    faces = [(0,1,2),(0,1,3)]
elif operation == "REPAIR_FACE_WINDING":
    verts = [(0,0,0),(1,0,0),(0,1,0),(0,-1,0)]
    faces = [(0,1,2),(0,1,3)]
elif operation == "REPAIR_MERGE_VERTEX":
    verts = [(0,0,0),(1,0,0),(0,1,0),(5,0,0),(6,0,0),(5,1,0),(0,0,0)]
    faces = [(0,1,2),(3,4,5)]
else:
    raise RuntimeError(operation)

mesh = bpy.data.meshes.new("pitch")
mesh.from_pydata(verts, [], faces)
mesh.update()
obj = bpy.data.objects.new("pitch", mesh)
bpy.context.scene.collection.objects.link(obj)

if operation == "REPAIR_MERGE_VERTEX":
    m1 = bpy.data.materials.new("turf")
    m2 = bpy.data.materials.new("line_markings")
    obj.data.materials.append(m1)
    obj.data.materials.append(m2)
    obj.material_slots[0].link = "DATA"
    obj.material_slots[1].link = "DATA"

bpy.ops.wm.save_as_mainfile(filepath=path)
print("ATLAS_FIXTURE_CREATED")
"""
    proc = _run_blender_script(script)
    assert proc.returncode == 0, proc.stderr[-3000:]
    assert "ATLAS_FIXTURE_CREATED" in proc.stdout


def _plan_from_fixture(path, operation):
    script = f"""
import json
import bpy
from planning.blender.bpy_extraction import extract_scene
from planning.blender.extraction_payload import payload_to_scene_model
from planning.blender.kernel import run_scene_health, soccer_field_profile_default
from planning.blender.correction_planner import plan_scene_report, plan_merge_vertex_correction

bpy.ops.wm.open_mainfile(filepath={str(path)!r}, load_ui=False)
payload = extract_scene(bpy)
scene = payload_to_scene_model(payload)
report = run_scene_health(scene, soccer_field_profile_default())
report_payload = report.to_json_compatible()
report_payload["digest"] = report.digest()
scene_input = dict(payload)
scene_input.pop("schema_version", None)

if {operation!r} == "REPAIR_MERGE_VERTEX":
    outcome = plan_merge_vertex_correction(report_payload, scene_input, profile={"name":"soccer-field","version":"1"})
else:
    outcome = plan_scene_report(report_payload, profile={"name":"soccer-field","version":"1"})

if outcome.plan is None:
    raise RuntimeError("planner returned no plan: " + repr(getattr(outcome, "refusal_code", None)))

print("ATLAS_PLAN_START")
print(json.dumps(outcome.plan.to_json_compatible(), sort_keys=True, separators=(",",":")))
print("ATLAS_PLAN_END")
"""
    proc = _run_blender_script(script)
    assert proc.returncode == 0, proc.stderr[-5000:]
    start = proc.stdout.find("ATLAS_PLAN_START")
    end = proc.stdout.find("ATLAS_PLAN_END", start + 1)
    assert start >= 0 and end >= 0, proc.stdout[-5000:]
    raw = json.loads(proc.stdout[start + len("ATLAS_PLAN_START"):end].strip())
    return raw


def _reconstruct_plan(raw):
    from planning.blender.correction_contract import CorrectionProposal

    corrections = []
    for item in raw["corrections"]:
        corrections.append(CorrectionProposal(
            correction_id=item["correction_id"],
            finding_code=item["finding_code"],
            object_id=item["object_id"],
            mesh_id=item["mesh_id"],
            correction_type=item["correction_type"],
            parameters=item["parameters"],
            rationale=item["rationale"],
            preconditions=tuple(item["preconditions"]),
            expected_postcondition=item["expected_postcondition"],
            risk=item["risk"],
            severity=item["severity"],
            reversibility=item["reversibility"],
            dependencies=tuple(item["dependencies"]),
            determinism=item["determinism"],
            requires_human_review=item["requires_human_review"],
            out_of_scope=item["out_of_scope"],
        ))
    return CorrectionPlan(
        plan_id=raw["plan_id"],
        source_report_digest=raw["source_report_digest"],
        source_revision_id=raw["source_revision_id"],
        planner_version=raw["planner_version"],
        profile=raw["profile"],
        corrections=tuple(corrections),
        dependencies=tuple(tuple(e) for e in raw["dependencies"]),
        summary_metrics=raw["summary_metrics"],
        state=raw["state"],
        planning_errors=tuple(raw["planning_errors"]),
    )


def _authorization_for(plan, operation):
    if operation in {"REMOVE_DUPLICATE_FACE", "REMOVE_DEGENERATE_FACE"}:
        return None
    correction = next(c for c in plan.corrections if c.correction_type == operation)
    auth = {
        "authorization_version": "1",
        "authorization_policy_version": "1",
        "decision": "APPROVED",
        "correction_type": operation,
        "correction_id": correction.correction_id,
        "plan_id": plan.plan_id,
        "source_report_digest": plan.source_report_digest,
        "authorized_by": "live-test-operator",
        "authorized_at_utc": "2026-09-19T22:00:00Z",
    }
    if operation == "REPAIR_FACE_WINDING":
        params = thaw_jsonable(correction.parameters)
        if params.get("designated_face_index") is None:
            auth["designated_face_index"] = 0
    return auth


@pytest.fixture(scope="module")
def live_bridge_results(tmp_path_factory):
    tmp_root = tmp_path_factory.mktemp("atlas_bridge_live")
    before = _blend_inventory(REPO)
    cases = []

    for operation in OPS:
        fixture = tmp_root / f"{operation}.blend"
        _create_fixture(fixture, operation)
        fixture_before = _sha256(fixture)

        raw_plan = _plan_from_fixture(fixture, operation)
        plan = _reconstruct_plan(raw_plan)
        auth = _authorization_for(plan, operation)

        bridge = CorrectionExecutionBridge(blender_command=__import__("tools.blender", fromlist=["BLENDER"]).BLENDER)
        result = bridge.execute(plan, operation=operation, authorization=auth, source_blend_path=str(fixture))

        fixture_after = _sha256(fixture)
        cases.append({
            "operation": operation,
            "result": result,
            "fixture_before": fixture_before,
            "fixture_after": fixture_after,
        })

    after = _blend_inventory(REPO)
    assert before == after, "bridge/test run created or modified repository .blend/.blend1 files"
    return cases


def test_live_bridge_all_four_operations_complete(live_bridge_results):
    for case in live_bridge_results:
        result = case["result"]
        assert result.transport_ok is True
        receipt = result.correction_result
        assert receipt["result"] == "COMPLETED", case
        assert receipt["failure_code"] is None, case
        assert result.engine_evidence["process_disposed"] is True
        assert result.engine_evidence["mutator_invocations"] == 1, case
        assert result.engine_evidence["extraction_invocations"] >= 2, case
        assert result.engine_evidence["saved_anything"] is False, case


def test_live_bridge_source_files_are_unchanged(live_bridge_results):
    for case in live_bridge_results:
        assert case["fixture_before"] == case["fixture_after"], case
        evidence = case["result"].engine_evidence
        assert evidence["filepath_at_end"] == evidence["filepath_after_load"]
        assert evidence["is_dirty_at_end"] in {True, False}


def test_live_bridge_receipt_shapes(live_bridge_results):
    expected_fields = {
        "REMOVE_DUPLICATE_FACE": 17,
        "REMOVE_DEGENERATE_FACE": 17,
        "REPAIR_FACE_WINDING": 27,
        "REPAIR_MERGE_VERTEX": 44,
    }
    for case in live_bridge_results:
        operation = case["operation"]
        receipt = case["result"].correction_result
        assert len(receipt) == expected_fields[operation]
