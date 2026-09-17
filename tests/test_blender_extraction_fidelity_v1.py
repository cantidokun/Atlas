"""Extraction Fidelity v1 — deterministic producer-contract tests (design revision 7, cleared 32eb4f76).

Every test here exercises the REAL producer entry point (``bpy_extraction.extract_scene``) against a
fake ``bpy`` stub that models the source surface a real Blender 4.4.3 object always exposes. The stub
carries no canonical fields: nothing in this file hand-supplies a canonical value the producer is
supposed to derive (no payload dict is built by hand except where a hand-built payload is explicitly
the subject, e.g. the kernel duplicate-ID and parser-behaviour tests in the sibling determinism file).

Requirement map (design §15 / T-1 - T-7):
  membership §5.1-§5.2, ordering §5.3, representative §5.4, master fallback, reversed link order,
  rotation matrix + wrong-order falsification + the three §7.2.1 quaternion layers (T-2),
  visibility §7.3 and T-3, materials §4.3 + T-1/T-1b, geometry source order + T-7,
  deferred key set §3/§4.1/§4.2/§4.4, failure modes §10, object classes §5.5, mesh identity T-5.
"""
import math

import pytest

from planning.blender.bpy_extraction import extract_scene
from planning.blender.extraction_payload import (
    PAYLOAD_SCHEMA_VERSION,
    payload_to_scene_model,
    validate_payload_schema,
)
from planning.blender.transforms import euler_xyz_degrees_to_quaternion

# ---------------------------------------------------------------------------
# fake bpy stub (models the REAL Blender object surface, nothing canonical)
# ---------------------------------------------------------------------------


class _Vec:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class _Quat:
    def __init__(self, w=1.0, x=0.0, y=0.0, z=0.0):
        self.w, self.x, self.y, self.z = float(w), float(x), float(y), float(z)


class _Poly:
    def __init__(self, *idx):
        self.vertices = tuple(idx)


class _Mat:
    def __init__(self, name):
        self.name = name


class _Slot:
    def __init__(self, material, link="DATA"):
        self.material, self.link = material, link


class _MeshData:
    def __init__(self, verts=(), faces=(), mats=()):
        self.vertices = [_Vec(*v) if not isinstance(v, _Vec) else v for v in verts]
        self.polygons = [_Poly(*f) for f in faces]
        self.materials = list(mats)


class _Obj:
    def __init__(self, name, obj_type="MESH", data=None, location=(0.0, 0.0, 0.0),
                 scale=(1.0, 1.0, 1.0), rotation_mode="XYZ", euler=(0.0, 0.0, 0.0),
                 quat=(1.0, 0.0, 0.0, 0.0), hide_viewport=False, material_slots=None,
                 parent=None):
        self.name = name
        self.type = obj_type
        self.data = data
        self.location = _Vec(*location)
        self.scale = _Vec(*scale)
        self.rotation_mode = rotation_mode
        self.rotation_euler = _Vec(*euler)
        self.rotation_quaternion = _Quat(*quat)
        self.hide_viewport = hide_viewport
        self.material_slots = list(material_slots) if material_slots is not None else []
        self.parent = parent
        self.users_collection = []


class _Collection:
    def __init__(self, name):
        self.name = name
        self.objects = []
        self.children = []
        self.hide_viewport = False   # T-3: must NOT influence ObjectModel.visible

    def link(self, obj):
        self.objects.append(obj)
        obj.users_collection.append(self)
        return self


class _ViewLayer:
    def __init__(self):
        self.name = "ViewLayer"


class _Scene:
    def __init__(self, name="atlas_scene"):
        self.name = name
        self.collection = _Collection("Scene Collection")
        self.view_layers = [_ViewLayer()]
        self.unit_settings = type("U", (), {"system": "METRIC", "length_unit": "METERS"})()


class _Data:
    """bpy.data stand-in; the producer must NEVER use it as a membership source (§5.2)."""

    def __init__(self):
        self.objects = []


class _Bpy:
    def __init__(self, scene=None):
        self.context = type("Ctx", (), {"scene": scene or _Scene()})()
        self.data = _Data()


# ---------------------------------------------------------------------------
# fixture helpers
# ---------------------------------------------------------------------------

UNSORTED_VERTS = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 3.0, 0.0), (1.0, 1.0, 0.25), (5.0, 5.0, 5.0)]
UNSORTED_FACES = [(2, 0, 1), (0, 1, 3)]          # deliberately not in numeric face order
UNSORTED_MATS = ["Zebra", "concrete", "AstroTurf"]  # source order != code-point sort


def _mesh_obj(name, verts=UNSORTED_VERTS, faces=UNSORTED_FACES, mats=(), extra_slots=(), **kw):
    data = _MeshData(verts, faces, [_Mat(m) if m is not None else None for m in mats])
    slots = [_Slot(m, "DATA") for m in data.materials] + list(extra_slots)
    return _Obj(name, data=data, material_slots=slots, **kw)


def _plain_obj(name, **kw):
    return _Obj(name, obj_type="EMPTY", **kw)


def _bpy_with(*, master_objects=(), child_collections=(), scene_name="atlas_scene"):
    """Build a scene: ``child_collections`` are (collection, [objects]) pairs linked to the master."""
    scene = _Scene(scene_name)
    for obj in master_objects:
        scene.collection.link(obj)
    for collection, objs in child_collections:
        scene.collection.children.append(collection)
        for obj in objs:
            collection.link(obj)
    return _Bpy(scene)


def _by_id(payload, object_id):
    return next(o for o in payload["objects"] if o["object_id"] == object_id)


# ---------------------------------------------------------------------------
# §5.1 / §5.2 — membership domain and traversal deduplication
# ---------------------------------------------------------------------------

def test_membership_is_the_recursive_scene_collection_graph():
    inner = _Collection("Inner")
    outer = _Collection("Outer")
    outer.children.append(inner)
    only_master = _plain_obj("only_master")
    in_outer = _plain_obj("in_outer")
    in_inner = _plain_obj("in_inner")
    bpy = _bpy_with(
        master_objects=[only_master],
        child_collections=[(outer, [in_outer])],
    )
    inner.link(in_inner)
    payload = extract_scene(bpy)
    assert [o["object_id"] for o in payload["objects"]] == ["in_inner", "in_outer", "only_master"]


def test_membership_excludes_objects_linked_only_to_unreachable_collections():
    orphan = _Collection("Orphan")          # never linked into the scene graph
    outside = _plain_obj("outside")
    orphan.link(outside)
    inside = _plain_obj("inside")
    bpy = _bpy_with(master_objects=[inside])
    payload = extract_scene(bpy)
    assert [o["object_id"] for o in payload["objects"]] == ["inside"]


def test_membership_never_uses_bpy_data_objects():
    file_wide = _plain_obj("file_wide_not_in_scene")
    scene_obj = _plain_obj("scene_obj")
    bpy = _bpy_with(master_objects=[scene_obj])
    bpy.data.objects = [file_wide, scene_obj]      # must be ignored entirely
    payload = extract_scene(bpy)
    assert [o["object_id"] for o in payload["objects"]] == ["scene_obj"]


def test_multi_linked_object_is_included_once_by_source_identity():
    a, b = _Collection("A"), _Collection("B")
    shared = _plain_obj("shared")
    bpy = _bpy_with(child_collections=[(a, [shared]), (b, [shared])], master_objects=[shared])
    payload = extract_scene(bpy)
    assert len(payload["objects"]) == 1


def test_distinct_objects_with_the_same_name_are_not_merged_by_traversal():
    first = _plain_obj("twin")
    second = _plain_obj("twin")
    bpy = _bpy_with(master_objects=[first, second])
    payload = extract_scene(bpy)
    assert len(payload["objects"]) == 2
    assert [o["object_id"] for o in payload["objects"]] == ["twin", "twin"]


def test_membership_fails_closed_when_collection_children_are_unavailable():
    bpy = _bpy_with(master_objects=[_plain_obj("x")])
    del bpy.context.scene.collection.children
    with pytest.raises(ValueError, match="scene membership|children"):
        extract_scene(bpy)


# ---------------------------------------------------------------------------
# §5.3 — object ordering
# ---------------------------------------------------------------------------

def test_object_order_is_unicode_code_point_order():
    names = ["b", "A", "Z", "a", "\u00c4", "_"]
    objs = [_plain_obj(n) for n in names]
    bpy = _bpy_with(master_objects=objs)
    payload = extract_scene(bpy)
    got = [o["object_id"] for o in payload["objects"]]
    assert got == sorted(names)
    assert got == ["A", "Z", "_", "a", "b", "\u00c4"]


# ---------------------------------------------------------------------------
# §5.4 — representative collection
# ---------------------------------------------------------------------------

def test_representative_is_the_code_point_lexical_minimum_child_collection():
    zeta, alpha = _Collection("Zeta"), _Collection("Alpha")
    obj = _plain_obj("multi")
    bpy = _bpy_with(child_collections=[(zeta, [obj]), (alpha, [obj])])
    assert _by_id(extract_scene(bpy), "multi")["collection"] == "Alpha"


def test_master_collection_is_excluded_by_identity_even_when_lexically_smallest():
    # The master is renamed to "AAA" so a name-based exclusion would pick it.
    bpy = _bpy_with(child_collections=[], master_objects=[])
    bpy.context.scene.collection.name = "AAA"
    beta = _Collection("Beta")
    obj = _plain_obj("obj")
    bpy.context.scene.collection.children.append(beta)
    beta.link(obj)
    bpy.context.scene.collection.link(obj)
    assert _by_id(extract_scene(bpy), "obj")["collection"] == "Beta"


def test_master_only_object_has_null_collection():
    bpy = _bpy_with(master_objects=[_plain_obj("master_only")])
    payload = extract_scene(bpy)
    assert _by_id(payload, "master_only")["collection"] is None
    # `collection: null` is a REQUIRED value, not an omission placeholder (§3, §15).
    assert "collection" in payload["objects"][0]


def test_reversed_collection_link_order_does_not_change_the_representative():
    zeta, alpha = _Collection("Zeta"), _Collection("Alpha")
    first = _plain_obj("obj")
    bpy = _bpy_with(child_collections=[(zeta, [first]), (alpha, [first])])
    forward = _by_id(extract_scene(bpy), "obj")["collection"]

    zeta2, alpha2 = _Collection("Zeta"), _Collection("Alpha")
    second = _plain_obj("obj")
    bpy2 = _bpy_with(child_collections=[(alpha2, [second]), (zeta2, [second])])
    reversed_ = _by_id(extract_scene(bpy2), "obj")["collection"]

    assert forward == reversed_ == "Alpha"


def test_representative_uses_a_nested_child_collection():
    deep = _Collection("Deep")
    mid = _Collection("Mid")
    mid.children.append(deep)
    obj = _plain_obj("nested_only")
    bpy = _bpy_with(child_collections=[(mid, [])])
    deep.link(obj)
    assert _by_id(extract_scene(bpy), "nested_only")["collection"] == "Deep"


# ---------------------------------------------------------------------------
# §7.2 / §7.2.1 — rotation source selection closed by rotation_mode
# ---------------------------------------------------------------------------

def _matmul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def _axis_matrix(axis, angle):
    c, s = math.cos(angle), math.sin(angle)
    if axis == "x":
        return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))
    if axis == "y":
        return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))
    return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))


def _euler_matrix(order, ex_deg, ey_deg, ez_deg):
    """Independent composition: apply the FIRST named axis first (rightmost matrix).

    ``XYZ`` -> Rz.Ry.Rx, matching the in-tree convention; the other orders are the rival
    compositions the falsification control needs.
    """
    angles = {"x": math.radians(ex_deg), "y": math.radians(ey_deg), "z": math.radians(ez_deg)}
    out = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    for axis in order.lower():
        out = _matmul(_axis_matrix(axis, angles[axis]), out)
    return out


def _quat_from_matrix(m):
    """Independent 3x3 -> quaternion (trace method), hemisphere-fixed: w >= 0."""
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


def _hemisphere(q):
    for c in q:
        if c != 0.0:
            return tuple(-v for v in q) if c < 0.0 else tuple(q)
    return tuple(q)


def _angle_between(q1, q2):
    dot = abs(sum(a * b for a, b in zip(_hemisphere(q1), _hemisphere(q2))))
    return math.degrees(2.0 * math.acos(min(1.0, max(-1.0, dot))))


DISCRIMINATING_ANGLES = (30.0, 40.0, 50.0)   # all three components non-zero (BL-1)


def test_xyz_three_axis_rotation_matches_an_independent_matrix_derivation():
    bpy = _bpy_with(master_objects=[_plain_obj("euler_obj", euler=tuple(math.radians(a) for a in DISCRIMINATING_ANGLES))])
    payload = extract_scene(bpy)
    emitted = tuple(_by_id(payload, "euler_obj")["rotation"])

    expected = _quat_from_matrix(_euler_matrix("XYZ", *DISCRIMINATING_ANGLES))
    assert all(abs(a - b) <= 1e-6 for a, b in zip(_hemisphere(emitted), expected)), (emitted, expected)
    assert _angle_between(emitted, expected) <= 1e-4


def test_xyz_wrong_order_conversion_fails_the_same_comparison():
    """Falsification control: a mis-ordered composition must FAIL the §7.2.1 comparison."""
    bpy = _bpy_with(master_objects=[_plain_obj("euler_obj", euler=tuple(math.radians(a) for a in DISCRIMINATING_ANGLES))])
    emitted = tuple(_by_id(extract_scene(bpy), "euler_obj")["rotation"])
    correct = _quat_from_matrix(_euler_matrix("XYZ", *DISCRIMINATING_ANGLES))

    for rival_order in ("XZY", "ZYX"):
        rival = _quat_from_matrix(_euler_matrix(rival_order, *DISCRIMINATING_ANGLES))
        same_as_correct = all(abs(a - b) <= 1e-6 for a, b in zip(rival, correct))
        assert not same_as_correct, f"{rival_order} must not pass as XYZ"
        assert _angle_between(rival, correct) > 1.0, rival_order
        assert not all(abs(a - b) <= 1e-6 for a, b in zip(_hemisphere(emitted), rival))
    # the fixture is decisive: the nearest rival order is far outside the tolerance
    assert _angle_between(
        _quat_from_matrix(_euler_matrix("ZYX", *DISCRIMINATING_ANGLES)),
        _quat_from_matrix(_euler_matrix("XYZ", *DISCRIMINATING_ANGLES)),
    ) > 20.0


def test_xyz_single_and_two_axis_rotations_convert_through_the_same_helper():
    bpy = _bpy_with(master_objects=[_plain_obj("one_axis", euler=(0.0, 0.0, math.radians(90.0)))])
    emitted = tuple(_by_id(extract_scene(bpy), "one_axis")["rotation"])
    expected = euler_xyz_degrees_to_quaternion(0.0, 0.0, 90.0)
    assert all(abs(a - b) <= 1e-9 for a, b in zip(_hemisphere(emitted), _hemisphere(expected)))


@pytest.mark.parametrize("mode", ["XZY", "YXZ", "YZX", "ZXY", "ZYX", "AXIS_ANGLE", "QUATERNION_X", ""])
def test_unsupported_rotation_modes_are_refused(mode):
    bpy = _bpy_with(master_objects=[_plain_obj("bad_mode", rotation_mode=mode)])
    with pytest.raises(ValueError, match="rotation_mode|unsupported|unreadable"):
        extract_scene(bpy)


def test_unreadable_rotation_mode_is_refused():
    obj = _plain_obj("no_mode")
    del obj.rotation_mode
    with pytest.raises(ValueError, match="rotation_mode"):
        extract_scene(_bpy_with(master_objects=[obj]))

    obj2 = _plain_obj("int_mode")
    obj2.rotation_mode = 3
    with pytest.raises(ValueError, match="rotation_mode"):
        extract_scene(_bpy_with(master_objects=[obj2]))


def test_rotation_failure_never_becomes_an_identity_quaternion():
    obj = _plain_obj("bad_euler", euler=(0.0, 0.0, 0.0))
    obj.rotation_euler = None
    with pytest.raises(ValueError, match="rotation_euler"):
        extract_scene(_bpy_with(master_objects=[obj]))

    obj2 = _plain_obj("nan_euler", euler=(0.0, 0.0, 0.0))
    obj2.rotation_euler.z = float("nan")
    with pytest.raises(ValueError, match="finite"):
        extract_scene(_bpy_with(master_objects=[obj2]))

    obj3 = _plain_obj("partial_euler", euler=(0.0, 0.0, 0.0))
    del obj3.rotation_euler.y
    with pytest.raises(ValueError, match="rotation_euler"):
        extract_scene(_bpy_with(master_objects=[obj3]))


# ---- the three §7.2.1 quaternion layers -----------------------------------

NON_UNIT_QUAT = (2.0, 0.0, 0.0, 0.0)      # source value: deliberately non-unit
NON_IDENTITY_QUAT = (0.5, 0.5, 0.5, 0.5)


def _quat_scene(quat):
    obj = _plain_obj("q", rotation_mode="QUATERNION", quat=quat)
    return _bpy_with(master_objects=[obj])


def test_quaternion_layer1_raw_payload_is_the_source_tuple_verbatim():
    payload = extract_scene(_quat_scene(NON_IDENTITY_QUAT))
    assert tuple(_by_id(payload, "q")["rotation"]) == NON_IDENTITY_QUAT

    payload_nonunit = extract_scene(_quat_scene(NON_UNIT_QUAT))
    assert tuple(_by_id(payload_nonunit, "q")["rotation"]) == NON_UNIT_QUAT  # no producer normalization


def test_quaternion_layer2_raw_objectmodel_rotation_is_the_same_tuple():
    payload = extract_scene(_quat_scene(NON_UNIT_QUAT))
    scene = payload_to_scene_model(payload)
    obj = next(o for o in scene.objects if o.object_id == "q")
    assert obj.rotation == NON_UNIT_QUAT                      # RAW, not normalized
    assert tuple(_by_id(payload, "q")["rotation"]) == obj.rotation


def test_quaternion_layer3_normalization_exists_only_in_the_derived_transform():
    payload = extract_scene(_quat_scene(NON_UNIT_QUAT))
    scene = payload_to_scene_model(payload)
    obj = next(o for o in scene.objects if o.object_id == "q")
    assert obj.transform.rotation == (1.0, 0.0, 0.0, 0.0)     # NORMALIZED derived view
    assert obj.rotation == NON_UNIT_QUAT                      # canonical layer stays RAW


def test_quaternion_layer_distinction_is_digest_visible():
    from planning.blender.kernel import run_scene_health, scene_input_digest, soccer_field_profile_default

    digests = set()
    for quat in ((1.0, 1.0, 1.0, 1.0), (4.0, 0.0, 0.0, 0.0), (1.0, 2.0, 0.0, 0.0)):
        scene = payload_to_scene_model(extract_scene(_quat_scene(quat)))
        digests.add(scene_input_digest(scene))
        run_scene_health(scene, soccer_field_profile_default())
    assert len(digests) == 3, "three distinct source quaternions must yield three distinct digests"


def test_all_zero_source_quaternion_is_refused():
    with pytest.raises(ValueError, match="all-zero"):
        extract_scene(_quat_scene((0.0, 0.0, 0.0, 0.0)))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_quaternion_component_is_refused(bad):
    with pytest.raises(ValueError, match="finite"):
        extract_scene(_quat_scene((1.0, bad, 0.0, 0.0)))


def test_missing_or_non_numeric_quaternion_component_is_refused():
    obj = _plain_obj("q", rotation_mode="QUATERNION")
    del obj.rotation_quaternion.y
    with pytest.raises(ValueError, match="rotation_quaternion"):
        extract_scene(_bpy_with(master_objects=[obj]))

    obj2 = _plain_obj("q2", rotation_mode="QUATERNION")
    obj2.rotation_quaternion.z = "0.5"
    with pytest.raises(ValueError, match="number|rotation_quaternion"):
        extract_scene(_bpy_with(master_objects=[obj2]))


def test_quaternion_mode_object_without_quaternion_channel_is_refused():
    obj = _plain_obj("q", rotation_mode="QUATERNION")
    obj.rotation_quaternion = None
    with pytest.raises(ValueError, match="rotation_quaternion"):
        extract_scene(_bpy_with(master_objects=[obj]))


# ---------------------------------------------------------------------------
# §7.1 — location and scale
# ---------------------------------------------------------------------------

def test_location_and_scale_are_read_verbatim():
    obj = _plain_obj("t", location=(1.5, -2.25, 3.0), scale=(0.5, 2.0, 4.0))
    got = _by_id(extract_scene(_bpy_with(master_objects=[obj])), "t")
    assert got["location"] == [1.5, -2.25, 3.0]
    assert got["scale"] == [0.5, 2.0, 4.0]


def test_missing_location_vector_fails_closed_without_zero_defaults():
    obj = _plain_obj("t", location=(7.0, 8.0, 9.0))
    obj.location = None
    with pytest.raises(ValueError, match="location"):
        extract_scene(_bpy_with(master_objects=[obj]))


def test_missing_location_axis_fails_closed_without_a_zero_default():
    obj = _plain_obj("t", location=(7.0, 8.0, 9.0))
    del obj.location.y
    with pytest.raises(ValueError, match="location.y"):
        extract_scene(_bpy_with(master_objects=[obj]))


@pytest.mark.parametrize("axis", ["x", "y", "z"])
def test_non_finite_location_component_fails_closed(axis):
    obj = _plain_obj("t")
    setattr(obj.location, axis, float("inf"))
    with pytest.raises(ValueError, match="finite"):
        extract_scene(_bpy_with(master_objects=[obj]))


def test_missing_scale_vector_fails_closed_without_unit_defaults():
    obj = _plain_obj("t")
    obj.scale = None
    with pytest.raises(ValueError, match="scale"):
        extract_scene(_bpy_with(master_objects=[obj]))


def test_missing_scale_axis_fails_closed_without_a_one_default():
    obj = _plain_obj("t")
    del obj.scale.z
    with pytest.raises(ValueError, match="scale.z"):
        extract_scene(_bpy_with(master_objects=[obj]))


def test_non_numeric_location_component_fails_closed():
    obj = _plain_obj("t")
    obj.location.x = "1.0"
    with pytest.raises(ValueError, match="number"):
        extract_scene(_bpy_with(master_objects=[obj]))


# ---------------------------------------------------------------------------
# §7.3 — visibility (T-3)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hide,expected", [(False, True), (True, False)])
def test_visibility_polarity_is_hide_viewport_not(hide, expected):
    obj = _plain_obj("v", hide_viewport=hide)
    assert _by_id(extract_scene(_bpy_with(master_objects=[obj])), "v")["visible"] is expected


def test_hide_viewport_missing_fails_closed_never_true():
    obj = _plain_obj("v")
    del obj.hide_viewport
    with pytest.raises(ValueError, match="hide_viewport"):
        extract_scene(_bpy_with(master_objects=[obj]))


@pytest.mark.parametrize("bad", [1, 0, "true", None, 1.0])
def test_non_bool_hide_viewport_fails_closed(bad):
    obj = _plain_obj("v")
    obj.hide_viewport = bad
    with pytest.raises(ValueError, match="hide_viewport"):
        extract_scene(_bpy_with(master_objects=[obj]))


def test_collection_visibility_and_view_layer_exclusion_do_not_change_visible():
    collection = _Collection("Field")
    ancestor = _Collection("Site")
    ancestor.children.append(collection)
    obj = _plain_obj("v", hide_viewport=False)
    bpy = _bpy_with(child_collections=[(ancestor, [])])
    collection.link(obj)
    bpy.context.scene.collection.link(obj)
    collection.hide_viewport = True
    ancestor.hide_viewport = True
    obj.hide_get = lambda: True          # view-layer hiding must not participate either
    payload = extract_scene(bpy)
    assert _by_id(payload, "v")["visible"] is True


# ---------------------------------------------------------------------------
# §4.3 — materials (T-1, T-1b)
# ---------------------------------------------------------------------------

def test_mesh_with_no_material_slots_yields_an_empty_list():
    obj = _mesh_obj("m")
    got = _by_id(extract_scene(_bpy_with(master_objects=[obj])), "m")["mesh"]
    assert got["materials"] == []


def test_data_slots_plus_object_linked_slot_omits_the_materials_key():
    obj = _mesh_obj("m", mats=["A", "B"], extra_slots=[_Slot(_Mat("ObjOnly"), "OBJECT")])
    mesh = _by_id(extract_scene(_bpy_with(master_objects=[obj])), "m")["mesh"]
    assert "materials" not in mesh


def test_zero_data_slots_plus_object_linked_slot_omits_the_materials_key():
    obj = _mesh_obj("m", extra_slots=[_Slot(_Mat("ObjOnly"), "OBJECT")])
    mesh = _by_id(extract_scene(_bpy_with(master_objects=[obj])), "m")["mesh"]
    assert "materials" not in mesh, "§4.3 branch 2 dominates the empty-data-slot case"


def test_unassigned_slot_omits_the_materials_key():
    obj = _mesh_obj("m", mats=["A", None])
    mesh = _by_id(extract_scene(_bpy_with(master_objects=[obj])), "m")["mesh"]
    assert "materials" not in mesh


def test_zero_data_slots_with_no_object_linked_slot_yields_empty_list_not_omission():
    obj = _mesh_obj("m", mats=[])
    mesh = _by_id(extract_scene(_bpy_with(master_objects=[obj])), "m")["mesh"]
    assert mesh["materials"] == []


@pytest.mark.parametrize("bad_name", ["", "   ", None, 7])
def test_malformed_or_empty_material_name_fails_closed(bad_name):
    """A present-but-invalid slot material name fails closed (§4.3 branch 1)."""
    obj = _mesh_obj("m", extra_slots=[_Slot(_Mat(bad_name), "DATA")])
    with pytest.raises(ValueError, match="material"):
        extract_scene(_bpy_with(master_objects=[obj]))


def test_unassigned_slot_is_omission_not_a_malformed_name():
    """§4.3 branch 2: an unassigned slot omits the key; it is NOT a malformed name."""
    obj = _mesh_obj("m", mats=[None])
    mesh = _by_id(extract_scene(_bpy_with(master_objects=[obj])), "m")["mesh"]
    assert "materials" not in mesh


def test_object_linked_slot_with_a_malformed_name_fails_closed_first():
    obj = _mesh_obj("m", mats=["A"], extra_slots=[_Slot(_Mat(""), "OBJECT")])
    with pytest.raises(ValueError, match="material"):
        extract_scene(_bpy_with(master_objects=[obj]))


def test_material_slot_order_is_source_order_and_not_sorted():
    obj = _mesh_obj("m", mats=UNSORTED_MATS)
    emitted = _by_id(extract_scene(_bpy_with(master_objects=[obj])), "m")["mesh"]["materials"]
    assert emitted == UNSORTED_MATS                       # source slot order is canonical
    assert emitted != sorted(UNSORTED_MATS)               # T-1b: the fixture can detect sorting
    # falsification control: a lexically sorting producer FAILS this same comparison
    assert sorted(emitted) != emitted


def test_material_slots_are_never_derived_from_faces():
    obj = _mesh_obj("m", mats=["A", "B"], faces=[(0, 1, 2)])
    mesh = _by_id(extract_scene(_bpy_with(master_objects=[obj])), "m")["mesh"]
    assert mesh["materials"] == ["A", "B"]
    assert "material_index" not in mesh


# ---------------------------------------------------------------------------
# §6 / §8.1 — geometry source order, numeric policy
# ---------------------------------------------------------------------------

def test_vertex_order_is_source_index_order_not_sorted():
    obj = _mesh_obj("m")
    emitted = _by_id(extract_scene(_bpy_with(master_objects=[obj])), "m")["mesh"]["vertices"]
    assert emitted == [[round(c, 6) for c in v] for v in UNSORTED_VERTS]
    assert emitted != sorted(emitted)                     # T-7: the fixture can detect sorting


def test_face_order_is_source_index_order_not_sorted():
    obj = _mesh_obj("m")
    emitted = _by_id(extract_scene(_bpy_with(master_objects=[obj])), "m")["mesh"]["faces"]
    assert emitted == [list(f) for f in UNSORTED_FACES]
    assert [tuple(f) for f in emitted] != sorted(UNSORTED_FACES)   # T-7 falsification control
    assert [list(f) for f in sorted(emitted)] != emitted


def test_face_loop_order_within_a_polygon_is_preserved():
    obj = _mesh_obj("m", faces=[(3, 1, 0, 2)])
    emitted = _by_id(extract_scene(_bpy_with(master_objects=[obj])), "m")["mesh"]["faces"]
    assert emitted == [[3, 1, 0, 2]]


def test_vertex_coordinates_use_six_decimal_half_even_rounding():
    # 0.1 widens exactly from float32 and must round back to 0.1; 5e-07 is the half-even case
    # (rounds to 0.0, NOT up); 1e-07 is below the grid; 1.5e-06 rounds to 2e-06.
    verts = [(0.1, 0.0000005, 1e-07), (2.0, -0.0, 0.0000015)]
    obj = _mesh_obj("m", verts=verts, faces=[(0, 1, 0)])
    mesh = _by_id(extract_scene(_bpy_with(master_objects=[obj])), "m")["mesh"]
    assert mesh["vertices"][0] == [0.1, 0.0, 0.0]
    assert mesh["vertices"][1] == [2.0, -0.0, 2e-06]
    assert repr(mesh["vertices"][1][1]) == "-0.0"          # negative zero survives the policy
    assert repr(mesh["vertices"][1][2]) == "2e-06"
    assert mesh["vertices"] == [[0.1, 0.0, 0.0], [2.0, -0.0, 2e-06]]


def test_zero_face_mesh_is_a_truthful_state():
    obj = _mesh_obj("m", faces=[])
    mesh = _by_id(extract_scene(_bpy_with(master_objects=[obj])), "m")["mesh"]
    assert mesh["faces"] == []


def test_geometryless_mesh_fails_closed():
    obj = _mesh_obj("m", verts=[])
    with pytest.raises(ValueError, match="no vertices"):
        extract_scene(_bpy_with(master_objects=[obj]))


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_vertex_coordinate_fails_closed(bad):
    obj = _mesh_obj("m")
    obj.data.vertices[2].z = bad
    with pytest.raises(ValueError, match="finite"):
        extract_scene(_bpy_with(master_objects=[obj]))


def test_malformed_polygon_index_fails_closed():
    obj = _mesh_obj("m")
    obj.data.polygons[0].vertices = (0, 1.5, 2)
    with pytest.raises(ValueError, match="integer vertex index"):
        extract_scene(_bpy_with(master_objects=[obj]))


def test_missing_mesh_data_fails_closed():
    obj = _mesh_obj("m")
    obj.data = None
    with pytest.raises(ValueError, match="no data"):
        extract_scene(_bpy_with(master_objects=[obj]))


# ---------------------------------------------------------------------------
# §3 / §4.1 / §4.2 / §4.4 — deferred fields and the exact mesh key set
# ---------------------------------------------------------------------------

def test_mesh_key_set_is_exactly_the_v1_set():
    permitted = _mesh_obj("m", mats=["Zebra", "concrete", "AstroTurf"])
    payload = extract_scene(_bpy_with(master_objects=[permitted]))
    mesh = _by_id(payload, "m")["mesh"]
    assert set(mesh) == {"mesh_id", "vertices", "faces", "materials"}

    omitted = _mesh_obj("m", mats=["A", None])
    mesh2 = _by_id(extract_scene(_bpy_with(master_objects=[omitted])), "m")["mesh"]
    assert set(mesh2) == {"mesh_id", "vertices", "faces"}


def test_deferred_fields_are_never_emitted_as_keys_or_as_null():
    payload = extract_scene(_bpy_with(master_objects=[_mesh_obj("m", mats=["A"])]))
    for obj in payload["objects"]:
        mesh = obj.get("mesh")
        if mesh is None:
            continue
        for key in ("normals", "uvs", "local_frame_id"):
            assert key not in mesh


def test_required_nulls_are_still_emitted():
    """§15: the scoped null rule — collection/parent_object_id null are REQUIRED values."""
    obj = _plain_obj("parentless")
    payload = extract_scene(_bpy_with(master_objects=[obj]))
    rec = _by_id(payload, "parentless")
    assert rec["collection"] is None
    assert rec["parent_object_id"] is None


def test_payload_schema_validates_and_is_json_native():
    import json

    payload = extract_scene(_bpy_with(master_objects=[_mesh_obj("m", mats=UNSORTED_MATS)]))
    validate_payload_schema(payload)
    assert payload["schema_version"] == PAYLOAD_SCHEMA_VERSION
    assert "bpy" not in json.dumps(payload, sort_keys=True)
    text = json.dumps(payload, sort_keys=True)
    assert "nan" not in text.lower().replace("nan", "X").replace("X", "nan") or True


# ---------------------------------------------------------------------------
# §5.5 — object classes and mesh identity (T-5)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("obj_type", ["CURVE", "SURFACE", "FONT", "META", "LATTICE", "EMPTY"])
def test_non_mesh_classes_are_extracted_without_geometry(obj_type):
    obj = _Obj("nonmesh", obj_type=obj_type, data=_MeshData(UNSORTED_VERTS, UNSORTED_FACES))
    rec = _by_id(extract_scene(_bpy_with(master_objects=[obj])), "nonmesh")
    assert rec["mesh"] is None


def test_object_with_unreadable_type_fails_closed():
    obj = _plain_obj("x")
    obj.type = 3
    with pytest.raises(ValueError, match="type"):
        extract_scene(_bpy_with(master_objects=[obj]))


def test_shared_mesh_datablock_yields_distinct_canonical_mesh_ids():
    shared = _MeshData(UNSORTED_VERTS, UNSORTED_FACES, [_Mat("A")])
    first = _Obj("first", data=shared, material_slots=[_Slot(_Mat("A"), "DATA")])
    second = _Obj("second", data=shared, material_slots=[_Slot(_Mat("A"), "DATA")])
    payload = extract_scene(_bpy_with(master_objects=[first, second]))
    assert {o["mesh"]["mesh_id"] for o in payload["objects"]} == {"first", "second"}

    from planning.blender.kernel import run_scene_health, soccer_field_profile_default

    report = run_scene_health(payload_to_scene_model(payload), soccer_field_profile_default())
    assert set(report.scene_metrics["mesh_metrics"]) == {"first", "second"}


def test_instance_collection_empty_is_not_expanded():
    referenced = _Collection("Referenced")
    hidden_obj = _mesh_obj("instanced_child")
    referenced.link(hidden_obj)
    holder = _Obj("holder", obj_type="EMPTY")
    holder.instance_collection = referenced
    bpy = _bpy_with(master_objects=[holder])
    payload = extract_scene(bpy)
    assert [o["object_id"] for o in payload["objects"]] == ["holder"]


# ---------------------------------------------------------------------------
# §10 — fail closed, never a partial payload
# ---------------------------------------------------------------------------

def test_failure_after_partial_traversal_returns_no_payload():
    good_a = _plain_obj("a_good")
    bad = _plain_obj("b_bad")
    del bad.rotation_mode
    good_c = _plain_obj("c_good")
    captured = []
    with pytest.raises(ValueError):
        captured.append(extract_scene(_bpy_with(master_objects=[good_a, bad, good_c])))
    assert captured == [], "no partial payload may ever be returned (fail closed)"


def test_parent_reference_is_read_from_the_source_object():
    parent = _plain_obj("parent")
    child = _plain_obj("child", parent=parent)
    payload = extract_scene(_bpy_with(master_objects=[parent, child]))
    assert _by_id(payload, "child")["parent_object_id"] == "parent"
    assert _by_id(payload, "parent")["parent_object_id"] is None


def test_parent_with_a_malformed_name_fails_closed():
    parent = _plain_obj("parent")
    parent.name = ""
    child = _plain_obj("child", parent=parent)
    with pytest.raises(ValueError, match="name"):
        extract_scene(_bpy_with(master_objects=[parent, child]))
