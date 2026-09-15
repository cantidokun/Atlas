"""Deterministic tests for the extraction payload + thin bpy extraction primitive.

No real Blender is launched: the primitive is exercised with a FAKE ``bpy`` stub that produces the
same canonical payload an in-Blender process would. All conversion/validation is deterministic and
runs in ordinary CI.
"""

import copy

import pytest

from planning.blender import FindingCode
from planning.blender.extraction_payload import (
    PAYLOAD_SCHEMA_VERSION,
    payload_to_scene_model,
    validate_payload_schema,
)
from planning.blender.bpy_extraction import extract_scene
from planning.blender.fixtures import (
    ALL_FIXTURES,
    HEALTHY_SCENE,
    HEALTHY_MESH_WITH_NORMALS,
    report_for_payload,
    scene_report_for_fixture,
)
from planning.blender.blender_units import UnitMappingError, map_unit_system
from planning.blender.scene_model import SceneReportInputError
from planning.blender.kernel import run_scene_health, soccer_field_profile_default


# --------------------------------------------------------------------------- payload schema

def test_payload_schema_version_constants():
    assert PAYLOAD_SCHEMA_VERSION == "1"


def test_payload_schema_valid_healthy():
    validate_payload_schema(HEALTHY_SCENE)
    validate_payload_schema(HEALTHY_MESH_WITH_NORMALS)


def test_payload_schema_rejects_unknown_version():
    with pytest.raises(ValueError, match="schema_version"):
        validate_payload_schema({**HEALTHY_SCENE, "schema_version": "0"})


def test_payload_schema_rejects_unknown_keys():
    bad = {**HEALTHY_SCENE, "bogus": 1}
    with pytest.raises(ValueError, match="unknown scene payload keys"):
        validate_payload_schema(bad)
    obj_bad = copy.deepcopy(HEALTHY_SCENE)
    obj_bad["objects"][0]["extra"] = True
    with pytest.raises(ValueError, match="unknown object payload keys"):
        validate_payload_schema(obj_bad)


def test_payload_schema_rejects_missing_required():
    for drop in ("scene_id", "unit_system", "objects"):
        bad = {k: v for k, v in HEALTHY_SCENE.items() if k != drop}
        with pytest.raises(ValueError, match="missing required"):
            validate_payload_schema(bad)


def test_no_bpy_in_payload():
    import json
    dumped = json.dumps(HEALTHY_SCENE, sort_keys=True)
    assert "bpy" not in dumped


# --------------------------------------------------------------------------- fixture -> report

def test_every_fixture_produces_deterministic_report():
    digests = {}
    for name, fx in ALL_FIXTURES.items():
        r1 = report_for_payload(fx)
        r2 = report_for_payload(fx)
        # same payload -> same report (identical canonical JSON + digest)
        assert r1.canonical_json() == r2.canonical_json()
        assert r1.digest() == r2.digest()
        digests[name] = r1.digest()
    # distinct fixtures produce distinct report identities
    assert len(set(digests.values())) == len(digests)


def test_healthy_fixture_ready_or_warnings():
    r = scene_report_for_fixture("healthy")
    assert r.validation_state in {"production_ready", "analyzed"}
    assert r.has_code(FindingCode.MESH_INVALID_INDEX) is False


def test_invalid_index_fixture_finds_error():
    r = scene_report_for_fixture("invalid_index_mesh")
    assert r.has_code(FindingCode.MESH_INVALID_INDEX)
    assert r.validation_state == "needs_review"


def test_duplicate_degenerate_fixture_finds_errors():
    r = scene_report_for_fixture("duplicate_degenerate_mesh")
    assert r.has_code(FindingCode.MESH_DUPLICATE_VERTEX)
    assert r.validation_state == "needs_review"


def test_hierarchy_fixture_unknown_parent():
    r = scene_report_for_fixture("hierarchy")
    assert r.has_code(FindingCode.OBJECT_HIERARCHY_INVALID)


def test_empty_fixture_not_ready():
    r = scene_report_for_fixture("empty")
    assert r.validation_state == "needs_review"


def test_meshless_fixture_no_mesh_metrics_but_ready_roles():
    r = scene_report_for_fixture("meshless")
    assert r.scene_metrics["mesh_object_count"] == 0
    assert r.validation_state == "production_ready"


# --------------------------------------------------------------------------- fake-bpy primitive

class _Vec:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


class _Angle:
    def __init__(self, *a):
        self.a = tuple(a)


class _Poly:
    def __init__(self, *idx):
        self.vertices = idx


class _MeshData:
    def __init__(self):
        self.vertices = [_Vec(0, 0, 0), _Vec(1, 0, 0), _Vec(0, 1, 0), _Vec(1, 1, 0)]
        self.polygons = [_Poly(0, 1, 2), _Poly(1, 3, 2)]


class _MeshObj:
    def __init__(self, name):
        self.name = name
        self.type = "MESH"
        self.data = _MeshData()
        self.location = _Vec(0, 0, 0)
        self.scale = _Vec(1, 1, 1)
        self.parent = None
        self.users_collection = []


class _Object:
    def __init__(self, name, obj_type="EMPTY"):
        self.name = name
        self.type = obj_type
        self.location = _Vec(0, 0, 0)
        self.scale = _Vec(1, 1, 1)
        self.parent = None
        self.users_collection = []


class _SceneCol:
    """Models Blender's scene.active-collection object membership (scene.collection.objects)."""

    def __init__(self, objs=None):
        self.objects = list(objs) if objs else []


class _Scene:
    def __init__(self):
        self.name = "atlas_scene"
        # Real Blender membership lives on scene.collection.objects, NOT scene.objects.
        self.collection = _SceneCol()
        # Real Blender unit_settings: system is METRIC/IMPERIAL/NONE; length_unit is precise.
        self.unit_settings = type("U", (), {"system": "METRIC", "length_unit": "METERS"})()


class _Context:
    def __init__(self):
        self.scene = _Scene()


class _BpyStub:
    def __init__(self):
        self.context = _Context()


def _bpy_with_soccer_objects():
    bpy = _BpyStub()
    bpy.context.scene.collection.objects = [
        _MeshObj("pitch"),
        _Object("goal_left"),
        _Object("goal_right"),
    ]
    return bpy


def test_fake_bpy_extracts_payload_without_partial_mesh():
    payload = extract_scene(_bpy_with_soccer_objects())
    validate_payload_schema(payload)
    assert payload["scene_id"] == "atlas_scene"
    # the pitch object carries a MESH payload (world-scaled vertices), not count-only
    pitch = next(o for o in payload["objects"] if o["object_id"] == "pitch")
    assert pitch["mesh"] is not None
    assert pitch["mesh"]["vertices"]  # real vertex list present, not a count-only downgrade
    # all objects present, stable (name-sorted) ordering (never Blender pointer order)
    names = [o["name"] for o in payload["objects"]]
    assert names == sorted(names)


def test_fake_bpy_extraction_feeds_kernel_deterministic():
    bpy = _bpy_with_soccer_objects()
    payload = extract_scene(bpy)
    scene = payload_to_scene_model(payload)
    report1 = run_scene_health(scene, soccer_field_profile_default())
    report2 = run_scene_health(scene, soccer_field_profile_default())
    assert report1.canonical_json() == report2.canonical_json()
    assert report1.validation_state in {"production_ready", "analyzed"}


def test_fake_bpy_fails_closed_on_geometryless_mesh():
    bpy = _bpy_with_soccer_objects()
    mesh = bpy.context.scene.collection.objects[0]
    mesh.data.vertices = []  # empty vertex table -> must fail closed, no count-only mesh
    with pytest.raises(ValueError, match="no vertices"):
        extract_scene(bpy)


def test_fake_bpy_fails_closed_mesh_no_data():
    bpy = _bpy_with_soccer_objects()
    bpy.context.scene.collection.objects[0].data = None
    with pytest.raises(ValueError, match="no data"):
        extract_scene(bpy)


# --------------------------------------------------------------------------- Blender 4.4.3 MeshVertex.co
# Real bpy.types.MeshVertex exposes coordinates via ``.co`` (it has NO ``.x/.y/.z``). The adapter
# MUST read ``.co``; a missing/malformed coordinate surface FAILS CLOSED and NEVER manufactures
# zeros (a silent zero would flatten the mesh to the origin and fake degenerate geometry).

class _CoVertex:
    """Real-Bender-4.4.3 MeshVertex shape: a ``.co`` 3-vector, NO ``.x/.y/.z`` axes."""

    def __init__(self, co):
        self.co = list(co)


class _LegacyVertex:
    """Older-Build MeshVertex shape: a COMPLETE ``.x/.y/.z`` axis surface (pre-``.co``)."""

    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


def _scene_single_mesh(vertices):
    bpy = _BpyStub()
    obj = _MeshObj("probe")
    obj.data.vertices = vertices
    obj.data.polygons = [_Poly(0, 1, 2)]
    bpy.context.scene.collection.objects = [obj]
    return bpy


def test_meshvertex_co_primary_extraction():
    # Canonical path: read real 4.4.3 coords from ``.co`` (NOT .x/.y/.z, which do not exist).
    bpy = _scene_single_mesh(
        [_CoVertex((0.0, 0.0, 0.0)), _CoVertex((1.0, 0.5, -2.0)), _CoVertex((-3.0, 0.0, 0.25))]
    )
    mesh = extract_scene(bpy)["objects"][0]["mesh"]
    assert mesh["vertices"] == [
        [0.0, 0.0, 0.0],
        [1.0, 0.5, -2.0],
        [-3.0, 0.0, 0.25],
    ]


def test_meshvertex_vertex_ordering_preserved():
    # The vertex table ORDER is preserved as-read (position i -> coords[i]), which is what keeps
    # face index tuples like (0,1,2) indexing the correct coordinates. Never re-ordered/sorted.
    coords = [(i * 1.0, -i, i / 2.0) for i in range(5)]
    bpy = _scene_single_mesh([_CoVertex(c) for c in coords])
    got = extract_scene(bpy)["objects"][0]["mesh"]["vertices"]
    assert got == [[round(float(c), 6) for c in coord] for coord in coords]


def test_meshvertex_object_local_coordinates_preserved():
    # Vertices are emitted AS READ (OBJECT-LOCAL); the adapter must NOT pre-transform into world
    # space nor bake scale into the coordinates (scale stays an explicit pose field).
    local = [[3.0, 0.0, 0.0], [3.0, 2.0, 0.0], [4.0, 1.0, 0.0]]
    bpy = _scene_single_mesh([_CoVertex(c) for c in local])
    obj = extract_scene(bpy)["objects"][0]
    assert obj["mesh"]["vertices"] == [list(map(float, c)) for c in local]
    assert obj["scale"] == [1.0, 1.0, 1.0]  # scale carried as explicit pose, not baked in


def test_meshvertex_legacy_xyz_fallback():
    # A pre-``.co`` MeshVertex exposing a COMPLETE .x/.y/.z surface is read from those axes.
    bpy = _scene_single_mesh([_LegacyVertex(2.0, 3.0, 4.0)])
    assert extract_scene(bpy)["objects"][0]["mesh"]["vertices"] == [[2.0, 3.0, 4.0]]


def test_meshvertex_no_silent_zero_fallback():
    # A vertex with NEITHER a usable .co NOR a complete .x/.y/.z surface must FAIL CLOSED --
    # never the old `getattr(v, "x", 0.0)` behavior that silently manufactures zeros.

    class _BareVertex:
        pass

    bpy = _scene_single_mesh([_BareVertex()])
    with pytest.raises(ValueError, match="neither a usable .co nor a complete"):
        extract_scene(bpy)

    # A PARTIAL .x/.y/.z surface (missing z) is unsupported -> fail closed, never pad with a zero.
    class _PartialXYZ:
        x = 1.0
        y = 2.0  # no .z

    bpy2 = _scene_single_mesh([_PartialXYZ()])
    with pytest.raises(ValueError, match="neither a usable .co nor a complete"):
        extract_scene(bpy2)


def test_meshvertex_malformed_co_fails_closed():
    # .co present but None / too short -> fail closed (never pad with zeros).
    def _vertex_with_co(co):
        class _V:
            pass

        v = _V()
        v.co = co
        return v

    for bad_co in (None, [1.0], [1.0, 2.0]):
        bpy = _scene_single_mesh([_vertex_with_co(bad_co)])
        with pytest.raises(ValueError, match="malformed|fail closed"):
            extract_scene(bpy)



# --------------------------------------------------------------------------- malformed / no partial

def test_malformed_payload_fails_closed():
    bad = {**HEALTHY_SCENE, "objects": [{"object_id": "x"}]}  # missing name
    with pytest.raises((ValueError, SceneReportInputError, TypeError)):
        payload_to_scene_model(bad)


def test_payload_never_emits_partial_mesh():
    # A mesh with a vertex list too short for its faces IS representable in the kernel contract;
    # the kernel is what reports the malformed topology. The extraction LAYER's "no partial mesh"
    # guarantee is enforced separately (see test_fake_bpy_fails_closed_on_geometryless_mesh).
    # Here we assert the kernel surfaces MESH_INVALID_INDEX rather than dropping the mesh or
    # emitting a count-only success.
    bad = copy.deepcopy(HEALTHY_SCENE)
    bad["objects"][0]["mesh"]["vertices"] = [[0, 0, 0]]  # 1 vertex, faces reference indices >0
    report = report_for_payload(bad)
    assert report.has_code(FindingCode.MESH_INVALID_INDEX)
    assert report.validation_state == "needs_review"
# --------------------------------------------------------------------------- Blocker 1 regression:
# real Blender scene object discovery (scene.collection.objects), never scene.objects / empty.

def test_scene_without_objects_attr_enumerates_via_collection():
    # The OLD failure: a scene lacking `.objects` silently yielded objects=[].
    # Regression: extraction must enumerate through the proper scene representation (the active
    # collection), returning the intended objects, never a silent authoritative-empty scene.
    bpy = _bpy_with_soccer_objects()
    scene = bpy.context.scene
    # Defensive: ensure the buggy surface is truly ABSENT, not just unset.
    if hasattr(scene, "objects"):
        delattr(scene, "objects")
    payload = extract_scene(bpy)
    assert payload["scene_id"] == "atlas_scene"
    assert [o["object_id"] for o in payload["objects"]] == ["goal_left", "goal_right", "pitch"]
    assert len(payload["objects"]) == 3


def test_scene_with_no_collection_fails_closed_never_empty():
    # If scene membership cannot be enumerated (no collection), extraction must FAIL CLOSED,
    # never return a schema-valid objects=[].
    bpy = _bpy_with_soccer_objects()
    bpy.context.scene.collection = None
    with pytest.raises(ValueError, match="scene membership|collection"):
        extract_scene(bpy)


def test_scene_with_collection_but_no_objects_attr_fails_closed():
    # collection present but its .objects is unavailable -> fail closed.
    bpy = _bpy_with_soccer_objects()
    bpy.context.scene.collection = type("C", (), {})()  # no .objects attribute
    with pytest.raises(ValueError, match="scene membership|collection"):
        extract_scene(bpy)


def test_legitimately_empty_scene_membership_is_not_a_failure():
    # A scene that genuinely links ZERO objects yields objects=[] but only because membership IS
    # resolvable (empty collection) — distinct from "cannot enumerate at all".
    bpy = _BpyStub()  # default empty collection, resolvable
    payload = extract_scene(bpy)
    assert payload["objects"] == []


# --------------------------------------------------------------------------- Blocker 2: canonical unit mapping


def _units(system=None, length_unit=None):
    d = {}
    if system is not None:
        d["system"] = system
    if length_unit is not None:
        d["length_unit"] = length_unit
    return type("U", (), d)()


def test_unit_map_length_unit_preferred_over_system():
    # length_unit is authoritative and precise.
    assert map_unit_system(_units(system="IMPERIAL", length_unit="METERS")) == "METERS"


def test_unit_map_metric_system_defaults_to_meters():
    assert map_unit_system(_units(system="METRIC")) == "METERS"


def test_unit_map_imperial_system_defaults_to_inches():
    assert map_unit_system(_units(system="IMPERIAL")) == "INCHES"


def test_unit_map_none_system_maps_to_unspecified():
    assert map_unit_system(_units(system="NONE")) == "UNSPECIFIED"


def test_unit_map_already_canonical_token_passthrough():
    # A producer/test that already supplies a canonical token passes through.
    assert map_unit_system(_units(system="METERS")) == "METERS"


def test_unit_map_undecidable_input_fails_closed():
    # No usable length_unit and no usable system -> declared mapping error (never fabricate).
    with pytest.raises(UnitMappingError):
        map_unit_system(_units())
    with pytest.raises(UnitMappingError):
        map_unit_system(object())


def test_extraction_uses_canonical_unit_mapping():
    # METRIC system + METERS length_unit -> canonical "METERS" in the payload.
    payload = extract_scene(_bpy_with_soccer_objects())
    assert payload["unit_system"] == "METERS"


# --------------------------------------------------------------------------- Hardening 4: host-side file integrity

def test_file_sha256_detects_content_change(tmp_path):
    from tests.test_live_blender_real_asset_gate import _file_sha256

    f = tmp_path / "probe.blend"
    f.write_bytes(b"canonical asset bytes v1")
    h1 = _file_sha256(str(f))
    assert len(h1) == 64 and all(c in "0123456789abcdef" for c in h1)
    f.write_bytes(b"canonical asset bytes v2")  # content changed (same length, still detected)
    h2 = _file_sha256(str(f))
    assert h1 != h2
    # identical content -> identical hash (deterministic / platform-independent)
    assert _file_sha256(str(f)) == h2


# --------------------------------------------------------------------------- Hardening 5: expected-world-coordinate table is
# internally consistent with world_points on a synthetic probe payload matching the designed asset.

def test_expected_probe_world_table_matches_world_points():
    from tests.test_live_blender_real_asset_gate import EXPECTED_PROBE_WORLD, _lazy_obj
    from planning.blender.transforms import world_points

    # Synthetic objects matching the designed asset transform probes.
    def probe(oid, loc=(0.0, 0.0, 0.0), rot=(1.0, 0.0, 0.0, 0.0), sc=(1.0, 1.0, 1.0),
              parent=None):
        return {"object_id": oid, "location": list(loc), "rotation": list(rot),
                "scale": list(sc), "parent_object_id": parent}

    import math
    qz90 = (math.cos(math.pi / 4), 0.0, 0.0, math.sin(math.pi / 4))  # +90deg about Z

    objs = [
        probe("probe_identity", loc=(-20.0, 0.0, 0.0)),
        probe("probe_trans", loc=(-20.0, 10.0, 0.0)),
        probe("probe_rot", loc=(-20.0, -10.0, 0.0), rot=qz90),
        probe("probe_nscale", loc=(-20.0, 20.0, 0.0), sc=(1.0, 3.0, 1.0)),
        probe("probe_combined", loc=(-20.0, -20.0, 0.0), rot=qz90, sc=(2.0, 2.0, 2.0)),
        probe("root", loc=(20.0, 0.0, 0.0)),
        probe("mid", loc=(0.0, 3.0, 0.0), parent="root"),
        probe("leaf", loc=(0.0, 3.0, 0.0), parent="mid"),
    ]
    by_id = {o["object_id"]: _lazy_obj(o) for o in objs}

    cases = {
        "probe_identity": (0.0, 0.0, 0.0),
        "probe_trans": (0.0, 0.0, 0.0),
        "probe_rot": (1.0, 0.0, 0.0),
        "probe_nscale": (0.0, 1.0, 0.0),
        "probe_combined": (1.0, 0.0, 0.0),
        "leaf": (0.0, 0.0, 0.0),
    }
    for oid, local in cases.items():
        chain = world_points(by_id, oid, [list(local)])
        assert chain is not None, f"{oid}: chain unresolved"
        got = tuple(round(float(c), 6) for c in chain[0])
        exp = tuple(round(float(x), 6) for x in EXPECTED_PROBE_WORLD[oid]["world"])
        assert got == exp, f"{oid}: got {got} expected {exp}"

# --------------------------------------------------------------------------- live-script repo import path
# Blender 4.4.3's embedded Python IGNORES a shell PYTHONPATH. The harness must inject the
# repository root via sys.path INSIDE the executed script, BEFORE any `planning.*` import, and the
# import must fail loudly if the repo cannot be established (never a silent skip/empty result).
# This is rendered deterministically (no Blender) here.

def test_live_script_injects_repo_via_syspath_before_planning_import():
    from tests.test_live_blender_real_asset_gate import _LIVE_SCRIPT_TEMPLATE

    fake_asset = r"C:\\tmp\\probe.blend"
    fake_repo = r"C:\\atlas\\repo"
    rendered = _LIVE_SCRIPT_TEMPLATE % {"asset": fake_asset, "repo": fake_repo}

    # repo is injected into sys.path INSIDE the script (repr-encoded string)
    assert ("sys.path.insert(0, " + repr(fake_repo) + ")") in rendered
    # …and that injection PRECEDES every planning import, so the import can only succeed when the
    # repo path is actually importable (ModuleNotFoundError otherwise -> non-zero rc -> fail loud).
    assert rendered.index("sys.path.insert") < rendered.index("from planning.blender")
    # Script must not read the repo path from a shell env var (it comes from sys.path, INSIDE the
    # script). Blender's embedded Python ignores a shell PYTHONPATH, so there must be no env read.
    assert "os.environ" not in rendered
