"""LIVE Blender gate for Extraction Fidelity v1 (operator-gated; NOT run in deterministic CI).

Proves the POSITIVE v1 claims against real Blender 4.4.3 on disposable fixtures, exactly as the
design requires (§14 Fixtures A/B/C/E, evidence register L-1 - L-5):

  Fixture A — scoped fidelity positive (deliberately unsorted source orders, non-lexical material
              slots, quaternion objects, an all-three-component XYZ Euler object, nested child
              collections, a two-collection object, a master-only object, hidden/shown objects);
  Fixture B — explicitly unsupported domains (a real UV layer with distinct corner values, an empty
              material slot, an OBJECT-linked slot);
  Fixture C — membership, identity and object classes (nested tree, two-collection object,
              master-only object, nested-only object, an object linked only outside the scene graph,
              an instance-collection Empty, a CURVE object);
  Fixture E — rotation-mode refusal (a non-XYZ Euler mode and AXIS_ANGLE);
  L-1 — the visibility source is `obj.hide_viewport` and collection-level hiding does not move it;
  L-3 — the three-component Euler validation with its wrong-order falsification control;
  L-4 — the material-slot cases, live;
  L-5 — the quaternion layers and the producer fail-closed cases, live.

PROVENANCE (L-2): every positive claim above is proven by these DISPOSABLE fixtures, not by the
frozen asset, which cannot exercise any of them. The frozen asset is a regression anchor only
(covered by tests/test_live_blender_real_asset_gate.py).

Disposable scenes are built with `read_factory_settings(use_empty=True)`; the gate never opens a
.blend, never saves, and never calls a save/export operator.

Run (authorized only)::

    ATLAS_RUN_LIVE_BLENDER=1 python -m pytest tests/test_live_blender_extraction_fidelity_gate.py -s
"""
import hashlib
import json
import os
import subprocess

import pytest

LIVE = os.environ.get("ATLAS_RUN_LIVE_BLENDER", "") == "1"

pytestmark = [pytest.mark.skipif(not LIVE, reason="live Blender gate off (not authorized)")]

FROZEN_ASSET = os.path.join("tests", "assets", "blender", "atlas_transform_validation.blend")
FROZEN_ASSET_SHA256 = "cf618bdc1123734bf49bf6f22677ded3f2e6c3fa2803b97f7a6cf7c7c66f11aa"

MATERIAL_SLOT_NAMES = ["Zebra", "concrete", "AstroTurf"]     # source order != code-point sort
UNSORTED_A_VERTS = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (5.0, 5.0, 5.0), (1.0, 1.0, 0.25)]
UNSORTED_A_FACES = [(2, 0, 1), (0, 1, 3)]
EULER_ANGLES_DEG = (30.0, 40.0, 50.0)


def _blender_command():
    import tools.blender as tb

    return tb.BLENDER


def _file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


_LIVE_SCRIPT = r'''
import bpy, json, math, os, sys

sys.path.insert(0, %(repo)r)

from planning.blender.bpy_extraction import extract_scene
from planning.blender.extraction_payload import payload_to_scene_model
from planning.blender.kernel import run_scene_health, soccer_field_profile_default


def fresh_scene():
    """Disposable in-memory scene: factory settings with NO objects (never a .blend read)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "fidelity_disposable"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    return scene


def child(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def mesh_from(name, verts, faces, material_names=(), empty_slots=0):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    for mname in material_names:
        mat = bpy.data.materials.new(mname)
        me.materials.append(mat)
    for _ in range(empty_slots):
        me.materials.append(None)
    return me


def obj_from(name, data, collection, **kw):
    ob = bpy.data.objects.new(name, data)
    for key, value in kw.items():
        setattr(ob, key, value)
    collection.objects.link(ob)
    return ob


def try_extract():
    record = {}
    try:
        payload = extract_scene(bpy)
        record["raised"] = None
        record["object_ids"] = [o["object_id"] for o in payload["objects"]]
    except Exception as exc:  # noqa: BLE001 - the failure itself is the evidence
        record["raised"] = type(exc).__name__
        record["message"] = str(exc)
    return record


def matrix_quaternion(matrix):
    """Independent 3x3 -> quaternion (trace method), hemisphere-fixed to w >= 0."""
    m = [[matrix[i][j] for j in range(3)] for i in range(3)]
    trace = m[0][0] + m[1][1] + m[2][2]
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        q = (0.25 * s, (m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s)
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2.0
        q = ((m[2][1] - m[1][2]) / s, 0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s)
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2.0
        q = ((m[0][2] - m[2][0]) / s, (m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s)
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2.0
        q = ((m[1][0] - m[0][1]) / s, (m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s)
    if q[0] < 0.0:
        q = tuple(-c for c in q)
    return q


def euler_matrix_zxy_variants(ex_deg, ey_deg, ez_deg):
    ax, ay, az = (math.radians(v) for v in (ex_deg, ey_deg, ez_deg))
    cx, sx = math.cos(ax), math.sin(ax)
    cy, sy = math.cos(ay), math.sin(ay)
    cz, sz = math.cos(az), math.sin(az)
    Rx = ((1, 0, 0), (0, cx, -sx), (0, sx, cx))
    Ry = ((cy, 0, sy), (0, 1, 0), (-sy, 0, cy))
    Rz = ((cz, -sz, 0), (sz, cz, 0), (0, 0, 1))

    def mul(a, b):
        return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))

    return {
        "XYZ": mul(Rz, mul(Ry, Rx)),   # the in-tree convention
        "XZY": mul(Ry, mul(Rz, Rx)),   # rival composition 1
        "ZYX": mul(Rx, mul(Ry, Rz)),   # rival composition 2
    }


def mesh_record(payload, object_id):
    return next(o for o in payload["objects"] if o["object_id"] == object_id)


def materials_of(payload, object_id):
    return mesh_record(payload, object_id)["mesh"].get("materials", "<absent>")


def key_set(payload, object_id):
    return sorted(mesh_record(payload, object_id)["mesh"].keys())


facts = {"blender": {"version": bpy.app.version_string,
                     "build_hash": (bpy.app.build_hash.decode() if isinstance(bpy.app.build_hash, bytes)
                                    else bpy.app.build_hash),
                     "build_commit_date": str(bpy.app.build_commit_date)}}

# ----------------------------------------------------------------- Fixture A (positive)
scene = fresh_scene()
outer = child("Outer")
inner = bpy.data.collections.new("Inner")
outer.children.link(inner)
zeta = child("Zeta")          # created FIRST, so the creation-ordered source view differs
alpha = child("Alpha")        # from the code-point lexical minimum the producer must use

unsorted_mesh = mesh_from("unsorted_mesh", %(verts)r, %(faces)r, %(mats)r)
obj_from("unsorted_mesh", unsorted_mesh, alpha)

euler_obj = bpy.data.objects.new("e_xyz", mesh_from("e_xyz_mesh", [(0.0, 0.0, 0.0)], []))
euler_obj.rotation_mode = "XYZ"
euler_obj.rotation_euler = tuple(math.radians(v) for v in %(euler)r)
alpha.objects.link(euler_obj)

q_unit = bpy.data.objects.new("q_unit", None)
q_unit.rotation_mode = "QUATERNION"
q_unit.rotation_quaternion = (0.5, 0.5, 0.5, 0.5)
alpha.objects.link(q_unit)

q_nonunit = bpy.data.objects.new("q_nonunit", None)
q_nonunit.rotation_mode = "QUATERNION"
q_nonunit.rotation_quaternion = (2.0, 0.0, 0.0, 0.0)
alpha.objects.link(q_nonunit)

two_cols = bpy.data.objects.new("two_cols", None)
zeta.objects.link(two_cols)      # linked FIRST into the lexically-larger collection
alpha.objects.link(two_cols)

master_only = bpy.data.objects.new("master_only", None)
bpy.context.scene.collection.objects.link(master_only)

shown = bpy.data.objects.new("shown_obj", None)
shown.hide_viewport = False
alpha.objects.link(shown)

hidden = bpy.data.objects.new("hidden_obj", None)
hidden.hide_viewport = True
alpha.objects.link(hidden)

collection_hidden = bpy.data.objects.new("collection_hidden_obj", None)
collection_hidden.hide_viewport = False
outer.objects.link(collection_hidden)
outer.hide_viewport = True              # L-1: must NOT move the extracted value

unrelated_empty = bpy.data.objects.new("unrelated_empty", None)
zeta.objects.link(unrelated_empty)

curve = bpy.data.curves.new("curve_data", "CURVE")
curve.dimensions = "3D"
unrelated_curve = bpy.data.objects.new("unrelated_curve", curve)
zeta.objects.link(unrelated_curve)

bpy.context.view_layer.update()
payload_a = extract_scene(bpy)
source_verts = [[round(float(c), 6) for c in v.co] for v in unsorted_mesh.vertices]
source_faces = [list(int(i) for i in p.vertices) for p in unsorted_mesh.polygons]
matrix_quat = matrix_quaternion(euler_obj.matrix_local)
variants = euler_matrix_zxy_variants(*%(euler)r)

facts["A"] = {
    "object_ids": [o["object_id"] for o in payload_a["objects"]],
    "collections": {o["object_id"]: o["collection"] for o in payload_a["objects"]},
    "materials": materials_of(payload_a, "unsorted_mesh"),
    "mesh_key_set": key_set(payload_a, "unsorted_mesh"),
    "source_verts": source_verts,
    "emitted_verts": mesh_record(payload_a, "unsorted_mesh")["mesh"]["vertices"],
    "source_faces": source_faces,
    "emitted_faces": mesh_record(payload_a, "unsorted_mesh")["mesh"]["faces"],
    "visible": {o["object_id"]: o["visible"] for o in payload_a["objects"]},
    "collection_hide_viewport_of_owner": outer.hide_viewport,
    "rotation_euler_object": list(mesh_record(payload_a, "e_xyz")["rotation"]),
    "independent_matrix_quaternion": list(matrix_quat),
    "wrong_order_quaternion": {
        "XZY": list(matrix_quaternion(variants["XZY"])),
        "ZYX": list(matrix_quaternion(variants["ZYX"])),
    },
    "raw_source_euler": [float(v) for v in euler_obj.rotation_euler],
    "q_nonunit_payload_raw": list(mesh_record(payload_a, "q_nonunit")["rotation"]),
    "q_nonunit_source_raw": [float(v) for v in q_nonunit.rotation_quaternion],
    "q_unit_payload_raw": list(mesh_record(payload_a, "q_unit")["rotation"]),
    "two_cols_users_collection": [c.name for c in two_cols.users_collection],
}

# three §7.2.1 layers for the non-unit quaternion object, live
scene_model = payload_to_scene_model(payload_a)
model_obj = next(o for o in scene_model.objects if o.object_id == "q_nonunit")
facts["A"]["q_nonunit_objectmodel_raw"] = list(model_obj.rotation)
facts["A"]["q_nonunit_transform_normalized"] = list(model_obj.transform.rotation)
report_a = run_scene_health(scene_model, soccer_field_profile_default())
facts["A"]["input_digest"] = report_a.input_digest
facts["A"]["report_digest"] = report_a.digest()

# reversed object/collection construction order: same semantic scene, same payload (design §9 run C)
def payload_sha(payload):
    return __import__("hashlib").sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    ).hexdigest()


facts["A"]["payload_sha"] = payload_sha(payload_a)

# §9 run C, live: reverse the two-collection LINK ORDER only, then re-extract. The payload and its
# canonical hash must be byte-identical, because the representative is derived by rule, not by order.
for collection in list(two_cols.users_collection):
    collection.objects.unlink(two_cols)
alpha.objects.link(two_cols)
zeta.objects.link(two_cols)
bpy.context.view_layer.update()
payload_a_reversed = extract_scene(bpy)
facts["A"]["reversed_link_order_users_collection"] = [c.name for c in two_cols.users_collection]
facts["A"]["payload_equal_after_reversed_relink"] = payload_a_reversed == payload_a
facts["A"]["payload_sha_after_reversed_relink"] = payload_sha(payload_a_reversed)
facts["A"]["reversed_link_order_representative"] = next(
    o["collection"] for o in payload_a_reversed["objects"] if o["object_id"] == "two_cols"
)

# ----------------------------------------------------------------- Fixture B (unsupported domains)
fresh_scene()
b_col = child("Field")
uv_mesh = mesh_from("uv_mesh", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])
uv_layer = uv_mesh.uv_layers.new(name="UVMap")
for loop_index, uv in enumerate(((0.0, 0.0), (1.0, 0.0), (0.0, 1.0))):
    uv_layer.data[loop_index].uv = uv
obj_from("uv_mesh", uv_mesh, b_col)

empty_slot_mesh = mesh_from("empty_slot_mesh", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)], empty_slots=1)
obj_from("empty_slot_mesh", empty_slot_mesh, b_col)

object_linked_mesh = mesh_from("object_linked_mesh", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])
object_linked = obj_from("object_linked", object_linked_mesh, b_col)
linked_mat = bpy.data.materials.new("ObjLevelMat")
object_linked.data.materials.append(linked_mat)
slot_links_before = [s.link for s in object_linked.material_slots]
if object_linked.material_slots:
    object_linked.material_slots[len(object_linked.material_slots) - 1].link = "OBJECT"
bpy.context.view_layer.update()

payload_b = extract_scene(bpy)
facts["B"] = {
    "uv_layer_exists": len(uv_mesh.uv_layers) == 1,
    "uv_corner_values": [[float(v) for v in uv_layer.data[i].uv] for i in range(3)],
    "uv_mesh_key_set": key_set(payload_b, "uv_mesh"),
    "empty_slot_len_data_materials": len(empty_slot_mesh.materials),
    "empty_slot_materials": materials_of(payload_b, "empty_slot_mesh"),
    "object_linked_data_slots": len(object_linked.data.materials),
    "object_linked_slot_links_before": slot_links_before,
    "object_linked_slot_links_after": [s.link for s in object_linked.material_slots],
    "object_linked_materials": materials_of(payload_b, "object_linked"),
    "object_linked_mesh_id": mesh_record(payload_b, "object_linked")["mesh"]["mesh_id"],
}

# ----------------------------------------------------------------- Fixture C (membership/classes)
fresh_scene()
c_top = child("Top")
c_nested = bpy.data.collections.new("NestedTop")
c_top.children.link(c_nested)
outside = bpy.data.collections.new("OutsideGraph")     # never linked into the scene graph
in_two_a, in_two_b = child("ColA"), child("ColB")

nested_only = obj_from("nested_only", None, c_nested)
two_way = obj_from("two_way", None, in_two_b)
in_two_a.objects.link(two_way)
master_only_c = bpy.data.objects.new("master_only_c", None)
bpy.context.scene.collection.objects.link(master_only_c)
outside_only = bpy.data.objects.new("outside_only", None)
outside.objects.link(outside_only)

instanced_ref = bpy.data.collections.new("Referenced")
inst_obj_inside = bpy.data.objects.new("instanced_child", None)
instanced_ref.objects.link(inst_obj_inside)
holder = bpy.data.objects.new("instance_holder", None)
holder.instance_collection = instanced_ref
c_top.objects.link(holder)

curve_c = bpy.data.curves.new("curve_c_data", "CURVE")
obj_from("curve_object", curve_c, c_top)
bpy.context.view_layer.update()

payload_c = extract_scene(bpy)
facts["C"] = {
    "object_ids": [o["object_id"] for o in payload_c["objects"]],
    "collections": {o["object_id"]: o["collection"] for o in payload_c["objects"]},
    "mesh_presence": {o["object_id"]: (o["mesh"] is not None) for o in payload_c["objects"]},
    "master_name": bpy.context.scene.collection.name,
    "outside_only_users_collection": [c.name for c in outside_only.users_collection],
    "in_any_scene_tree": outside.name in [c.name for c in bpy.context.scene.collection.children_recursive],
}

# ----------------------------------------------------------------- Fixture E (rotation-mode refusal)
fresh_scene()
e_col = child("Field")
xzy = bpy.data.objects.new("xzy_obj", None)
xzy.rotation_mode = "XZY"
xzy.rotation_euler = (0.1, 0.2, 0.3)
e_col.objects.link(xzy)
bpy.context.view_layer.update()
facts["E_xzy"] = try_extract()

fresh_scene()
e_col = child("Field")
axis = bpy.data.objects.new("axis_obj", None)
axis.rotation_mode = "AXIS_ANGLE"
axis.rotation_axis_angle = (1.0, 0.0, 0.0, 0.5)
e_col.objects.link(axis)
bpy.context.view_layer.update()
facts["E_axis_angle"] = try_extract()

# ----------------------------------------------------------------- L-5 (quaternion fail-closed + layers)
fresh_scene()
l_col = child("Field")
zero = bpy.data.objects.new("zero_quat", None)
zero.rotation_mode = "QUATERNION"
zero.rotation_quaternion = (0.0, 0.0, 0.0, 0.0)
l_col.objects.link(zero)
bpy.context.view_layer.update()
facts["L5_zero"] = try_extract()

fresh_scene()
l_col = child("Field")
nonfinite = bpy.data.objects.new("nonfinite_quat", None)
nonfinite.rotation_mode = "QUATERNION"
nonfinite.rotation_quaternion = (1.0, float("nan"), 0.0, 0.0)
l_col.objects.link(nonfinite)
bpy.context.view_layer.update()
facts["L5_nonfinite"] = try_extract()

print("ATLAS_FID_START")
print(json.dumps(facts, indent=1, sort_keys=True))
print("ATLAS_FID_END")
'''


def _run_gate():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = _LIVE_SCRIPT % {
        "repo": repo,
        "verts": UNSORTED_A_VERTS,
        "faces": UNSORTED_A_FACES,
        "mats": MATERIAL_SLOT_NAMES,
        "euler": EULER_ANGLES_DEG,
    }
    cmd = [_blender_command(), "--background", "--factory-startup", "--python-expr", script]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=repo, env=dict(os.environ))
    if proc.returncode != 0:
        raise AssertionError(
            "live fidelity gate failed rc={}: {}".format(proc.returncode, proc.stderr[-3000:])
        )
    start = proc.stdout.find("ATLAS_FID_START")
    end = proc.stdout.find("ATLAS_FID_END")
    assert start != -1 and end != -1, "live fidelity evidence markers missing" + proc.stdout[-3000:]
    return json.loads(proc.stdout[start + len("ATLAS_FID_START"):end].strip())


def test_live_extraction_fidelity_gate():
    asset = os.path.abspath(FROZEN_ASSET)
    asset_before = _file_sha256(asset)
    assert asset_before == FROZEN_ASSET_SHA256
    assets_dir_before = sorted(os.listdir(os.path.dirname(asset)))

    facts = _run_gate()

    # --- read-only evidence: the frozen asset and its directory are untouched ---
    assert _file_sha256(asset) == asset_before, "READ-ONLY VIOLATION: the frozen asset changed"
    assert sorted(os.listdir(os.path.dirname(asset))) == assets_dir_before, "new file in the asset directory"

    # --- engine identity recorded from inside the run ---
    assert facts["blender"]["version"] == "4.4.3"
    assert facts["blender"]["build_hash"] == "802179c51ccc"

    a = facts["A"]

    # --- Fixture A: membership, ordering, representative collection (§5) ---
    assert set(a["object_ids"]) == {
        "collection_hidden_obj", "e_xyz", "hidden_obj", "master_only", "q_nonunit", "q_unit",
        "shown_obj", "two_cols", "unsorted_mesh", "unrelated_curve", "unrelated_empty",
    }
    assert a["object_ids"] == sorted(a["object_ids"]), "§5.3 code-point object order"
    assert a["collections"]["unsorted_mesh"] == "Alpha"
    assert a["collections"]["two_cols"] == "Alpha", "lexical minimum wins over the source view order"
    assert set(a["two_cols_users_collection"]) == {"Alpha", "Zeta"}, "two reachable collections"
    assert a["payload_equal_after_reversed_relink"] is True, "reversed link order must not move the payload"
    assert a["payload_sha_after_reversed_relink"] == a["payload_sha"]
    assert a["reversed_link_order_representative"] == "Alpha"
    assert a["collections"]["master_only"] is None
    assert a["collections"]["unrelated_curve"] == "Zeta"

    # --- Fixture A: material order is source order and NOT sorted (T-1b) ---
    assert a["materials"] == MATERIAL_SLOT_NAMES
    assert a["materials"] != sorted(MATERIAL_SLOT_NAMES)

    # --- Fixture A: geometry source order preserved (T-7) ---
    assert a["emitted_verts"] == a["source_verts"]
    assert a["emitted_verts"] != sorted(a["emitted_verts"])
    assert a["emitted_faces"] == a["source_faces"]
    assert [tuple(f) for f in a["emitted_faces"]] != sorted(tuple(f) for f in a["source_faces"])

    # --- Fixture A: deferred mesh key set (§3) ---
    assert a["mesh_key_set"] == ["faces", "materials", "mesh_id", "vertices"]

    # --- Fixture A: visibility (L-1) ---
    assert a["visible"]["hidden_obj"] is False
    assert a["visible"]["shown_obj"] is True
    assert a["collection_hide_viewport_of_owner"] is True
    assert a["visible"]["collection_hidden_obj"] is True, "Collection.hide_viewport must not participate"

    # --- Fixture A: the three-component Euler validation and its wrong-order control (L-3) ---
    emitted = a["rotation_euler_object"]
    expected = a["independent_matrix_quaternion"]
    assert all(abs(x - y) <= 1e-6 for x, y in zip(emitted, expected)), (emitted, expected)
    for rival in ("XZY", "ZYX"):
        wrong = a["wrong_order_quaternion"][rival]
        assert not all(abs(x - y) <= 1e-6 for x, y in zip(wrong, expected)), rival

    # --- Fixture A: the three quaternion layers (§7.2.1, L-3/L-5) ---
    assert a["q_nonunit_payload_raw"] == a["q_nonunit_source_raw"] == [2.0, 0.0, 0.0, 0.0]
    assert a["q_nonunit_objectmodel_raw"] == [2.0, 0.0, 0.0, 0.0], "layer 2 is RAW"
    assert a["q_nonunit_transform_normalized"] == [1.0, 0.0, 0.0, 0.0], "layer 3 is NORMALIZED"
    assert a["q_unit_payload_raw"] == [0.5, 0.5, 0.5, 0.5]
    assert isinstance(a["input_digest"], str) and len(a["input_digest"]) == 64
    assert len(a["payload_sha"]) == 64

    # --- Fixture B: unsupported domains (L-4) ---
    b = facts["B"]
    assert b["uv_layer_exists"] is True
    assert b["uv_corner_values"] == [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]], "distinct corner UVs present"
    assert "uvs" not in b["uv_mesh_key_set"]
    assert b["empty_slot_len_data_materials"] == 1
    assert b["empty_slot_materials"] == "<absent>", "an unassigned empty slot omits the key"
    assert b["object_linked_slot_links_after"][-1] == "OBJECT"
    assert b["object_linked_materials"] == "<absent>", "an OBJECT-linked slot omits the key"

    # --- Fixture C: membership and object classes (§5.2/§5.5) ---
    c = facts["C"]
    assert set(c["object_ids"]) == {"curve_object", "instance_holder", "master_only_c", "nested_only", "two_way"}
    assert c["object_ids"] == sorted(c["object_ids"])
    assert c["collections"]["nested_only"] == "NestedTop"
    assert c["collections"]["two_way"] == "ColA"
    assert c["collections"]["master_only_c"] is None
    assert c["mesh_presence"]["instance_holder"] is False
    assert c["mesh_presence"]["curve_object"] is False
    assert "outside_only" not in c["object_ids"], "an object outside the scene graph is excluded"

    # --- Fixture E: rotation-mode refusal ---
    assert facts["E_xzy"]["raised"] is not None
    assert "XZY" in facts["E_xzy"]["message"]
    assert facts["E_axis_angle"]["raised"] is not None
    assert "AXIS_ANGLE" in facts["E_axis_angle"]["message"]

    # --- L-5: producer fail-closed on the quaternion channel ---
    assert facts["L5_zero"]["raised"] is not None
    assert "all-zero" in facts["L5_zero"]["message"]
    assert facts["L5_nonfinite"]["raised"] is not None
    assert "finite" in facts["L5_nonfinite"]["message"]

    print("ATE_FIDELITY_RESULT=" + json.dumps(facts))
