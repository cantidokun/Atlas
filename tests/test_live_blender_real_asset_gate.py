"""REAL-.blend live Blender integration test (operator-gated; NOT run in deterministic CI).

This is the SECOND, clearly-separated live gate for OPERATOR-AUTHORIZED REAL .BLEND VALIDATION
(see planning/blender/BLENDER_REAL_BLEND_VALIDATION.md). It is intentionally distinct from the
existing synthetic in-memory live gate (test_live_blender_extraction_gate.py), which builds a scene
in memory and never loads a saved asset.

ONLY the authorized live run executes this:
    test -f <asset>
    ATLAS_RUN_LIVE_BLENDER=1 ATLAS_BLEND_ASSET=<asset> python -m pytest tests/test_live_blender_real_asset_gate.py -s

In deterministic CI it is always SKIPPED (env gate) and even if the env var is set without the
asset it FAILS clearly rather than silently passing. It never writes a .blend, never saves; a
host-side SHA-256 over the asset asserts contents are unchanged before vs after (content-hash —
never mtime alone). Precise expected-report assertions (object counts, IDs, transforms -> world
coordinates, topology, unit, roles, finding set, ValidationState) replace any "any report passes"
permissiveness. Standard Version begin to be confirmed BEFORE the authorized run.

NOT executed in the preparation/remediation round. M12.5 / M5 untouched. No commit/PR.
"""

import hashlib
import math
import os
import subprocess
import sys

import pytest


def _live_enabled() -> bool:
    # Must be explicitly authorized: ATLAS_RUN_LIVE_BLENDER=1.
    return os.environ.get("ATLAS_RUN_LIVE_BLENDER", "") == "1"


def _asset_path() -> str:
    # Canonical relative path; overridable via ATLAS_BLEND_ASSET.
    return os.environ.get(
        "ATLAS_BLEND_ASSET",
        os.path.join("tests", "assets", "blender", "atlas_transform_validation.blend"),
    )


live = _live_enabled()
asset = _asset_path()

# Disabled by default AND requires the asset to exist. If the env is set but the asset is absent,
# we FAIL (never silently skip) so a misconfigured authorized run is obvious. If the env is unset,
# we SKIP normally (deterministic CI).
if live and not os.path.exists(asset):
    pytest.fail(
        f"ATLAS_RUN_LIVE_BLENDER=1 but asset not found: {asset!r} "
        "(generate per planning/blender/BLENDER_REAL_BLEND_VALIDATION.md)"
    )

pytestmark = [pytest.mark.skipif(not live, reason="real .blend live gate off (not authorized)")]


def _file_sha256(path: str) -> str:
    """Content SHA-256 of a file (platform-independent; NOT mtime)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _blender_command():
    import tools.blender as tb

    return tb.BLENDER  # configured path, e.g. C:\\Program Files\\...\\blender.exe


# ===========================================================================
# EXPECTED REPORT for the designed test asset (see BLENDER_REAL_BLEND_VALIDATION.md §3/§10).
# These are the FINAL, operator-reviewed targets the live run must satisfy. If the asset is
# regenerated the expectations here must be updated in lock-step (never loosened to pass).
#
# Designed scene (11 objects):
#   mesh objects (9): pitch, probe_identity, probe_trans, probe_rot, probe_nscale,
#                     probe_combined, root, mid(parent=root), leaf(parent=mid)
#   role-only empty (2): goal_left, goal_right
# ===========================================================================
EXPECTED_SCENE_ID = "atlas_validation"
EXPECTED_OBJECT_COUNT = 11
EXPECTED_MESH_OBJECT_COUNT = 9
EXPECTED_UNIT = "METERS"
EXPECTED_OBJECT_IDS = sorted(
    ["pitch", "goal_left", "goal_right", "probe_identity", "probe_trans",
     "probe_rot", "probe_nscale", "probe_combined", "root", "mid", "leaf"]
)
EXPECTED_FINDING_CODES = set()  # all probes inside envelope, valid topology, roles present
EXPECTED_VALIDATION_STATE = "production_ready"

# Local probe vertex -> expected WORLD coordinate (Blender -> TransformModel -> world_points).
# Each probe has a DISTINCT base so its world AABB is disjoint from pitch and every sibling
# (=> no OBJECT_BOUNDS_OVERLAP; see generate_asset.py). These are the EXACT pinned world points for
# the generated asset and MUST be updated in lock-step if the asset is regenerated.
EXPECTED_PROBE_WORLD = {
    # identity: base (-20,0,0); world == local + base
    "probe_identity": {"local": (0.0, 0.0, 0.0), "world": (-20.0, 0.0, 0.0)},
    # translation on top of base (-20,10,0)
    "probe_trans": {"local": (0.0, 0.0, 0.0), "world": (-20.0, 10.0, 0.0)},
    # rotation +90deg about Z (active, CCW in right-handed): (1,0,0)->(0,1,0), base (-20,-10,0)
    "probe_rot": {"local": (1.0, 0.0, 0.0), "world": (-20.0, -9.0, 0.0)},
    # non-uniform scale (1,3,1): y scaled; base (-20,20,0)
    "probe_nscale": {"local": (0.0, 1.0, 0.0), "world": (-20.0, 23.0, 0.0)},
    # combined: base(-20,-20,0) + rotZ90 + scale(2,2,2): local(1,0,0)->scale(2,0,0)->rot(0,2,0)->(-20,-18,0)
    "probe_combined": {"local": (1.0, 0.0, 0.0), "world": (-20.0, -18.0, 0.0)},
    # nested parent root(20,0,0)<-mid(0,3,0)<-leaf(0,3,0): leaf origin -> (20,6,0)
    "leaf": {"local": (0.0, 0.0, 0.0), "world": (20.0, 6.0, 0.0)},
}

EXPECTED_PITCH_TOPOLOGY = [3, 4, 5]  # triangle + quad + n-gon per-face cardinalities

# --- Extraction Fidelity v1: the RE-DERIVED frozen-asset anchor (design §11.3 / §21.4). ---
# `collection` is a digested field, so correcting the representative moves the digests: the
# asset's Field/Goals/Structure are ORPHAN collection datablocks (unreachable from
# scene.collection by child links), so no object has an included child collection and the §5.4
# representative is null for all 11 objects.
#
# NAMING NOTE: in the design §11.3 table the two rows' labels are transposed relative to the
# code — `scene_input_digest` IS `report.input_digest` (= `kernel.scene_input_digest`), and the
# other value is `SceneReport.digest()` (which additionally covers metrics and findings). The
# literals are asserted here under their CORRECT names; no design rule depends on the labels.
PRE_V1_SCENE_INPUT_DIGEST = "13bbf29c69449a9c9f825e9fe4212acc3c4c62f519c1aa989d0f2aed1fecf92b"
PRE_V1_REPORT_DIGEST = "8d009d0d8cb7b3ed9604dfca753c998faceb839f1bcf17f7336e3676e54eb331"
EXPECTED_V1_SCENE_INPUT_DIGEST = "d90895bae02e30502cb9077b219b67cc4fbe104f3cbab664850c9346dc60ddfb"
EXPECTED_V1_REPORT_DIGEST = "ee430d6fdc69928b9c91284deda96c14cf3e25d745aa14cfab6c51dabf3a3203"


def _blender_command_ver() -> str:
    return os.environ.get("ATLAS_BLENDER_VERSION_PIN", "<unset: confirm target build before run>")


# Read-only bpy loader + extractor + scene-state digest + payload. Never saves.
_LIVE_SCRIPT_TEMPLATE = r'''
import bpy, json, os, sys

# Repository import path is injected into sys.path INSIDE the script. Blender 4.4.3's embedded
# Python does NOT honor a shell PYTHONPATH (it silently ignores an exported PYTHONPATH), so
# relying on it fails at `import planning.*`. sys.path injection must precede the planning
# imports below; if the repo cannot be importable from here, the import raises a
# ModuleNotFoundError and the subprocess exits non-zero -- the test FAILS LOUDLY (never a
# silent skip) rather than extracting an empty/partial scene.
sys.path.insert(0, %(repo)r)

asset = os.path.abspath(%(asset)r)

# Load the frozen .blend read-only BEFORE any atlas-dependent work runs. The diagnostic
# (planning/blender/BLENDER_REAL_BLEND_GATE_CONTEXT_DIAGNOSTIC.md) proved this call was lost from
# the template during the earlier repo-import splice; without it the script extracted against the
# factory default scene "Scene". This must precede every `planning.*` import, extraction, payload
# construction, and kernel evaluation.
bpy.ops.wm.open_mainfile(filepath=asset)

# Diagnostic/guard (NOT a substitute for the host-side assertions): confirm the loaded scene really
# is the frozen asset's scene before continuing. Fails hereby loudly if the open did not take.
if bpy.context.scene.name != "atlas_validation":
    raise SystemExit(
        "open_mainfile did not activate scene 'atlas_validation' (got '"
        + str(bpy.context.scene.name)
        + "'); aborting before extraction"
    )

def transform_triplets():
    rows = []
    for obj in bpy.data.objects:
        t = obj.rotation_euler if hasattr(obj, "rotation_euler") else (0.0,0.0,0.0)
        s = obj.scale if hasattr(obj, "scale") else (1.0,1.0,1.0)
        rows.append((obj.name,
                     tuple(round(float(getattr(obj.location, a, 0.0)), 6) for a in ("x","y","z")),
                     tuple(round(float(getattr(t, b, 0.0)), 6) for b in ("x","y","z")),
                     tuple(round(float(getattr(s, c, 1.0)), 6) for c in ("x","y","z")),
                     getattr(obj.parent, "name", None) if getattr(obj, "parent", None) else None,
                     len(getattr(getattr(obj, "data", None), "vertices", ())) if getattr(obj,"type","")=="MESH" else None))
    rows.sort(key=lambda r: r[0])
    return rows

snap_before = transform_triplets()

from planning.blender.bpy_extraction import extract_scene
payload = extract_scene(bpy)

from planning.blender.extraction_payload import payload_to_scene_model
from planning.blender.kernel import run_scene_health, soccer_field_profile_default
scene = payload_to_scene_model(payload)
report = run_scene_health(scene, soccer_field_profile_default())

snap_after = transform_triplets()

out = {
    "scene_id": report.scene_id,
    "state": report.validation_state,
    "finding_codes": sorted({f.code.value for f in report.findings}),
    "digest": report.digest(),
    "input_digest": report.input_digest,
    "object_count": len(payload["objects"]),
    "mesh_object_count": sum(1 for o in payload["objects"] if o.get("mesh") is not None),
    "unit_system": payload["unit_system"],
    "object_ids": sorted(o["object_id"] for o in payload["objects"]),
    "collections": {o["object_id"]: o["collection"] for o in payload["objects"]},
    "visibles": {o["object_id"]: o["visible"] for o in payload["objects"]},
    "rotations": {o["object_id"]: list(o["rotation"]) for o in payload["objects"]},
    "mesh_key_sets": {o["object_id"]: sorted(o["mesh"].keys()) for o in payload["objects"]
                      if o.get("mesh") is not None},
    "materials": {o["object_id"]: o["mesh"].get("materials", "<absent>")
                  for o in payload["objects"] if o.get("mesh") is not None},
    "payload": payload,
    "read_only_digest_equal": snap_before == snap_after,
}
print("ATLAS_REAL_START")
print(json.dumps(out))
print("ATLAS_REAL_END")
'''


def test_live_real_blend_validation():
    """Live: load a real .blend read-only -> extract -> payload -> kernel -> precise report."""
    asset_abs = os.path.abspath(asset)
    # --- Host-side file integrity (content hash, not mtime). ---
    pre_hash = _file_sha256(asset_abs)

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = _LIVE_SCRIPT_TEMPLATE % {"asset": asset_abs, "repo": repo}
    cmd = [_blender_command(), "--background", "--python-expr", script]
    env = dict(os.environ)
    # Repository import path is delivered via sys.path INSIDE the Blender script (above), NOT
    # via the shell PYTHONPATH env var -- Blender 4.4.3's embedded Python ignores PYTHONPATH.
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=240, cwd=repo, env=env)
    if proc.returncode != 0:
        raise AssertionError(
            f"real-.blend live extraction failed rc={proc.returncode}: {proc.stderr[-2000:]}"
        )
    start = proc.stdout.find("ATLAS_REAL_START")
    end = proc.stdout.find("ATLAS_REAL_END")
    assert start != -1 and end != -1, "real live payload markers missing" + proc.stdout[-2000:]
    import json as _json

    result = _json.loads(proc.stdout[start + len("ATLAS_REAL_START"):end].strip())

    # --- Hardening 4: no-save / no-mutation file integrity. ---
    post_hash = _file_sha256(asset_abs)
    assert pre_hash == post_hash, (
        "READ-ONLY VIOLATION: .blend content changed during extraction (pre != post SHA-256). "
        "The validation must NEVER save/rewrite the asset. Classify as failure, do not accommodate."
    )
    assert result["read_only_digest_equal"] is True, "read-only scene-state digest CHANGED"

    # --- Blocker 1: object discovery produced the intended, deterministic set. ---
    assert result["scene_id"] == EXPECTED_SCENE_ID
    assert result["object_count"] == EXPECTED_OBJECT_COUNT
    assert result["mesh_object_count"] == EXPECTED_MESH_OBJECT_COUNT
    assert result["object_ids"] == EXPECTED_OBJECT_IDS  # fully deterministic (name-sorted)

    # --- Blocker 2: canonical unit mapping. ---
    assert result["unit_system"] == EXPECTED_UNIT

    # --- Payload contract: JSON-native, no vertices_per_face, name-sorted. ---
    pl = result["payload"]
    assert pl["schema_version"] == "1"
    assert all("vertices_per_face" not in (o.get("mesh") or {}) for o in pl["objects"])

    # --- Topology: pitch mixed per-face cardinalities. ---
    pitch = next(o for o in pl["objects"] if o["object_id"] == "pitch")
    assert [len(f) for f in pitch["mesh"]["faces"]] == EXPECTED_PITCH_TOPOLOGY

    # --- Transform->world coordinates computed HOST-SIDE from the extracted payload. ---
    from planning.blender.transforms import world_points

    by_id = {o["object_id"]: o for o in pl["objects"]}
    for oid, spec in EXPECTED_PROBE_WORLD.items():
        mesh = by_id[oid]["mesh"]
        # find the vertex equal to the expected LOCAL point
        local = tuple(float(x) for x in spec["local"])
        idx = next(i for i, v in enumerate(mesh["vertices"]) if tuple(float(x) for x in v) == local)
        chain = world_points(
            {k: _lazy_obj(v) for k, v in by_id.items()}, oid, [mesh["vertices"][idx]]
        )
        assert chain is not None, f"{oid}: parent chain unresolved (missing/cyclic parent)"
        world = tuple(round(float(c), 6) for c in chain[0])
        assert world == pytest.approx(spec["world"]), (
            f"{oid} world mismatch: local {local} -> {world}, expected {spec['world']}"
        )

    # --- Extraction Fidelity v1: the re-derived frozen-asset anchor (design §11.3 / §21.4). ---
    assert set(result["collections"].values()) == {None}, (
        "every frozen-asset object has no included child collection -> collection: null (§5.4)"
    )
    assert result["input_digest"] == EXPECTED_V1_SCENE_INPUT_DIGEST, (
        "scene_input_digest (= report.input_digest) must be the re-derived v1 value"
    )
    assert result["digest"] == EXPECTED_V1_REPORT_DIGEST, (
        "report.digest() must be the re-derived v1 value"
    )
    # falsification control: neither pre-v1 value may survive the producer correction
    assert result["input_digest"] != PRE_V1_SCENE_INPUT_DIGEST
    assert result["digest"] != PRE_V1_REPORT_DIGEST
    # deferred keys omitted (§4.1/§4.2/§4.4) and materials truthful (§4.3: zero slots -> [])
    assert set(result["mesh_key_sets"]) == {o["object_id"] for o in pl["objects"]
                                            if o.get("mesh") is not None}
    for oid, keys in result["mesh_key_sets"].items():
        assert keys == ["faces", "materials", "mesh_id", "vertices"], (oid, keys)
        assert result["materials"][oid] == [], oid
    # visibility is sourced from obj.hide_viewport (false on every object of this asset)
    assert set(result["visibles"].values()) == {True}
    # the XYZ path is unchanged for this asset: identity everywhere except the two Z-axis probes
    assert result["rotations"]["pitch"] == [1.0, 0.0, 0.0, 0.0]
    # tolerance per the §7.2.1 comparison contract: the asset stores the Euler in float32, so the
    # converted quaternion sits ~1.6e-8 from the exact half-angle value (measured).
    assert result["rotations"]["probe_rot"] == pytest.approx(
        [math.cos(math.pi / 4), 0.0, 0.0, math.sin(math.pi / 4)], abs=1e-6
    )

    # --- Finding set + ValidationState must be EXACT (distinguishes all failure classes). ---
    assert set(result["finding_codes"]) == EXPECTED_FINDING_CODES
    assert result["state"] == EXPECTED_VALIDATION_STATE

    # --- Determinism: report identity reproducible from the captured payload. ---
    from planning.blender.scene_model import parse_scene_report_input
    from planning.blender.kernel import run_scene_health, soccer_field_profile_default

    re_scene = parse_scene_report_input({k: v for k, v in pl.items() if k != "schema_version"})
    re_report = run_scene_health(re_scene, soccer_field_profile_default())
    assert re_report.digest() == result["digest"]

    print("ATE_JSON_RESULT=" + _json.dumps(result))


def _lazy_obj(payload_obj):
    """Build a minimal duck-typed object carrier so ``world_points`` works on a payload dict.

    ``world_points`` only reads ``.object_id``, ``.parent_object_id``, and ``.transform`` (an
    attribute whose absence/malformation surfaces as an unresolved pose). We supply a plain carrier
    with a precomputed ``TransformModel``.
    """
    from planning.blender.transforms import TransformModel

    class _ProbeObj:
        __slots__ = ("object_id", "parent_object_id", "transform")

    o = _ProbeObj()
    o.object_id = payload_obj["object_id"]
    o.parent_object_id = payload_obj.get("parent_object_id")
    o.transform = TransformModel(
        location=tuple(payload_obj.get("location", (0.0, 0.0, 0.0))),
        rotation=tuple(payload_obj.get("rotation", (1.0, 0.0, 0.0, 0.0))),
        scale=tuple(payload_obj.get("scale", (1.0, 1.0, 1.0))),
    )
    return o