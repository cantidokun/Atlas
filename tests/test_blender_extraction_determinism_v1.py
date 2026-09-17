"""Extraction Fidelity v1 — deterministic determinism / encoding / digest-boundary tests.

The §9 determinism protocol is executed MECHANICALLY: each of the three runs is a separate child
process with an explicitly set ``PYTHONHASHSEED`` (A = 1, B = 2, C = 3) and each run returns a full
evidence record carrying the four §9 obligations —

    * payload SHA-256                       (sha256 of the §8.2 canonical encoding)
    * canonicalization identifier           (the §8.2 encoding string, asserted to be the one used)
    * hash seed                             (read from inside the child, plus a seed probe proving the
                                             seed actually took effect in that process)
    * fixture construction-order identifier (the exact construction orders the run used)

Run C is the prescribed semantic-equivalent construction with **object construction order,
collection creation order and the two-collection link order reversed**, and with vertex order,
polygon order and material-slot append order deliberately UNCHANGED (asserted element-for-element).

Other sections cover §8.2 (canonical encoding vectors), §11.1/§11.2 (digest participation, T-6),
§4.5 T-4 (``materials: null`` acceptance layers) and §10/§12.4 (duplicate canonical IDs stay
kernel-findable).
"""
import copy
import functools
import hashlib
import json
import os
import subprocess
import sys

import pytest

from planning.blender.bpy_extraction import extract_scene
from planning.blender.extraction_payload import payload_to_scene_model, validate_payload_schema
from planning.blender.kernel import (
    run_scene_health,
    scene_input_digest,
    soccer_field_profile_default,
)
from planning.blender.scene_model import SceneReportInputError
from tests.test_blender_extraction_fidelity_v1 import (
    UNSORTED_FACES,
    UNSORTED_MATS,
    UNSORTED_VERTS,
    _Bpy,
    _Collection,
    _Mat,
    _Obj,
    _Slot,
    _bpy_with,
    _by_id,
    _mesh_obj,
    _plain_obj,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# §8.2 — the canonical evidence encoding, normative for every gate hash.
CANONICALIZATION = 'json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False'


def _canonical_text(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _payload_sha(payload) -> str:
    return hashlib.sha256(_canonical_text(payload).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# §9 — the determinism fixture (it records the construction order it used)
# ---------------------------------------------------------------------------

CANONICAL_OBJECT_ORDER = ["q_obj", "e_obj", "m_alpha", "m_beta", "shared_obj"]
CANONICAL_COLLECTION_ORDER = ["Zeta", "Alpha", "Nested"]
CANONICAL_LINK_ORDER = ["Zeta", "Alpha"]          # the two-collection object's link order

_RUN_SEEDS = {"A": "1", "B": "2", "C": "3"}


def _build_determinism_scene(reverse=False):
    """Build the §9 fixture and return ``(bpy, trace)``.

    ``reverse=True`` (run C) reverses ONLY rule-derived construction order: object construction order,
    the order objects are linked into the master collection, collection creation order, the order the
    child collections are linked into the master, and the two-collection link order. The source-ordered
    domains — vertex order, polygon order, material-slot append order — are byte-identical in both
    constructions and are recorded in the trace so that invariance is asserted, not assumed.
    """
    if reverse:
        # collection creation order is itself part of the reversal: create the LAST-created
        # collection first. Nested is created first so Alpha can adopt it.
        nested = _Collection("Nested")
        alpha = _Collection("Alpha")
        zeta = _Collection("Zeta")
        by_name = {"Zeta": zeta, "Alpha": alpha, "Nested": nested}
        created = ["Nested", "Alpha", "Zeta"]
    else:
        zeta = _Collection("Zeta")
        alpha = _Collection("Alpha")
        nested = _Collection("Nested")
        by_name = {"Zeta": zeta, "Alpha": alpha, "Nested": nested}
        created = ["Zeta", "Alpha", "Nested"]
    alpha.children.append(nested)

    material_slots = [_Slot(_Mat(n), "DATA") for n in UNSORTED_MATS]

    def build(name):
        if name == "e_obj":
            return _plain_obj("e_obj", euler=(0.5235987756, 0.6981317008, 0.8726646260))
        if name == "q_obj":
            return _plain_obj("q_obj", rotation_mode="QUATERNION", quat=(2.0, 0.0, 0.0, 0.0))
        if name == "m_alpha":
            return _mesh_obj("m_alpha", verts=UNSORTED_VERTS, faces=UNSORTED_FACES, mats=UNSORTED_MATS)
        if name == "m_beta":
            obj = _mesh_obj("m_beta", verts=UNSORTED_VERTS, faces=UNSORTED_FACES)
            obj.material_slots = material_slots
            return obj
        if name == "shared_obj":
            return _plain_obj("shared_obj")
        raise AssertionError(name)

    object_order = list(reversed(CANONICAL_OBJECT_ORDER)) if reverse else list(CANONICAL_OBJECT_ORDER)
    built = {name: build(name) for name in object_order}       # dict preserves insertion order
    solo = _plain_obj("solo_master_only")
    in_nested = _plain_obj("in_nested")

    scene = _Bpy().context.scene
    for name in object_order:                                  # master object-link order
        scene.collection.link(built[name])
    scene.collection.link(solo)

    children_order = list(reversed(CANONICAL_LINK_ORDER)) if reverse else list(CANONICAL_LINK_ORDER)
    scene.collection.children.extend([by_name[name] for name in children_order])
    link_order = list(reversed(CANONICAL_LINK_ORDER)) if reverse else list(CANONICAL_LINK_ORDER)
    for name in link_order:                                    # two-collection link order
        by_name[name].link(built["shared_obj"])
    nested.link(in_nested)

    source_mesh = built["m_alpha"]
    trace = {
        "object_construction_order": list(object_order),
        "object_master_link_order": list(object_order),
        "collection_creation_order": created,
        "master_children_order": list(children_order),
        "two_collection_link_order": list(link_order),
        # SOURCE-ORDERED domains (§6, §4.3) — identical in both constructions by design.
        "source_domains": {
            "vertices": [[float(v.x), float(v.y), float(v.z)] for v in source_mesh.data.vertices],
            "faces": [list(p.vertices) for p in source_mesh.data.polygons],
            "materials": [m.name for m in source_mesh.data.materials],
        },
    }
    return _Bpy(scene), trace


def _determinism_scene(reverse=False):
    """Backwards-compatible accessor: the fixture scene only."""
    return _build_determinism_scene(reverse=reverse)[0]


def _construction_id(trace) -> str:
    """Deterministic fixture construction-order identifier (recorded by every §9 run)."""
    return "objects[{}]|master_links[{}]|collections[{}]|children[{}]|links[{}]".format(
        ">".join(trace["object_construction_order"]),
        ">".join(trace["object_master_link_order"]),
        ">".join(trace["collection_creation_order"]),
        ">".join(trace["master_children_order"]),
        ">".join(trace["two_collection_link_order"]),
    )


CANONICAL_CONSTRUCTION_ID = (
    "objects[q_obj>e_obj>m_alpha>m_beta>shared_obj]"
    "|master_links[q_obj>e_obj>m_alpha>m_beta>shared_obj]"
    "|collections[Zeta>Alpha>Nested]|children[Zeta>Alpha]|links[Zeta>Alpha]"
)
RUN_C_CONSTRUCTION_ID = (
    "objects[shared_obj>m_beta>m_alpha>e_obj>q_obj]"
    "|master_links[shared_obj>m_beta>m_alpha>e_obj>q_obj]"
    "|collections[Nested>Alpha>Zeta]|children[Alpha>Zeta]|links[Alpha>Zeta]"
)

SEED_PROBE_STRINGS = ("atlas-extraction-fidelity-v1", "determinism-run-probe")


def build_run_evidence(label: str) -> dict:
    """Execute ONE §9 run in THIS process and return its full evidence record.

    Importable by the child processes that the tests spawn with an explicit ``PYTHONHASHSEED``.
    """
    if label not in _RUN_SEEDS:
        raise AssertionError("unknown §9 run label: {!r}".format(label))
    reverse = label == "C"
    bpy, trace = _build_determinism_scene(reverse=reverse)
    payload = extract_scene(bpy)
    canonical = _canonical_text(payload)
    return {
        "run": label,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "hash_randomization_flag": int(sys.flags.hash_randomization),
        "seed_probes": [hash(s) for s in SEED_PROBE_STRINGS],
        "canonicalization": CANONICALIZATION,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "canonical_json": canonical,
        "construction_id": _construction_id(trace),
        "trace": trace,
        "object_ids": [o["object_id"] for o in payload["objects"]],
        "shared_obj_collection": _by_id(payload, "shared_obj")["collection"],
        "emitted_source_domains": {
            "vertices": _by_id(payload, "m_alpha")["mesh"]["vertices"],
            "faces": _by_id(payload, "m_alpha")["mesh"]["faces"],
            "materials": _by_id(payload, "m_alpha")["mesh"].get("materials"),
        },
    }


def determinism_payload_sha() -> str:
    """Payload SHA-256 of the canonical construction (§9 run A). Kept for child-process reuse."""
    return build_run_evidence("A")["payload_sha256"]


# ---------------------------------------------------------------------------
# §9 — the three runs, each in its own process with an explicit hash seed
# ---------------------------------------------------------------------------

_CHILD_SCRIPT = r'''
import json, os, sys
sys.path.insert(0, {repo!r})
from tests.test_blender_extraction_determinism_v1 import build_run_evidence

expected_seed = {seed!r}
observed_seed = os.environ.get("PYTHONHASHSEED")
if observed_seed != expected_seed:
    raise SystemExit("PYTHONHASHSEED not in effect: expected {{}} got {{}}".format(expected_seed, observed_seed))

print("ATLAS_DET_START")
print(json.dumps(build_run_evidence({label!r}), sort_keys=True))
print("ATLAS_DET_END")
'''


@functools.lru_cache(maxsize=None)
def _child_run(label: str) -> dict:
    """Run one §9 run in an isolated process with the prescribed PYTHONHASHSEED."""
    seed = _RUN_SEEDS[label]
    script = _CHILD_SCRIPT.format(repo=REPO_ROOT, seed=seed, label=label)
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    proc = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, env=env, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    start = proc.stdout.find("ATLAS_DET_START")
    end = proc.stdout.find("ATLAS_DET_END")
    assert start != -1 and end != -1, "child run markers missing" + proc.stdout[-2000:]
    return json.loads(proc.stdout[start + len("ATLAS_DET_START"):end].strip())


def _assert_evidence_complete(record: dict, label: str, expected_seed: str) -> None:
    """Every §9 run must record hash, canonicalization id, seed and construction order (§9)."""
    assert record["run"] == label
    assert record["pythonhashseed"] == expected_seed, record["pythonhashseed"]
    assert len(record["payload_sha256"]) == 64
    assert all(c in "0123456789abcdef" for c in record["payload_sha256"])
    assert record["canonicalization"] == CANONICALIZATION
    assert record["construction_id"]
    assert record["trace"]["object_construction_order"]
    assert record["trace"]["collection_creation_order"]
    assert record["trace"]["two_collection_link_order"]
    # the recorded hash must be the §8.2 encoding of the recorded payload
    recomputed = hashlib.sha256(record["canonical_json"].encode("utf-8")).hexdigest()
    assert recomputed == record["payload_sha256"]
    # an isomorph of §8.2, applied to the recorded payload values
    assert hashlib.sha256(
        json.dumps(json.loads(record["canonical_json"]), sort_keys=True,
                   separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    ).hexdigest() == record["payload_sha256"]


def test_run_a_isolated_seed_1_records_full_evidence():
    a = _child_run("A")
    _assert_evidence_complete(a, "A", "1")
    assert a["construction_id"] == CANONICAL_CONSTRUCTION_ID
    assert a["trace"]["object_construction_order"] == CANONICAL_OBJECT_ORDER
    assert a["trace"]["object_master_link_order"] == CANONICAL_OBJECT_ORDER
    assert a["trace"]["collection_creation_order"] == CANONICAL_COLLECTION_ORDER
    assert a["trace"]["master_children_order"] == CANONICAL_LINK_ORDER
    assert a["trace"]["two_collection_link_order"] == CANONICAL_LINK_ORDER


def test_run_b_isolated_seed_2_records_full_evidence():
    b = _child_run("B")
    _assert_evidence_complete(b, "B", "2")
    assert b["construction_id"] == CANONICAL_CONSTRUCTION_ID


def test_run_c_isolated_seed_3_records_the_prescribed_reversal():
    c = _child_run("C")
    _assert_evidence_complete(c, "C", "3")
    assert c["construction_id"] == RUN_C_CONSTRUCTION_ID
    # construction order really is reversed relative to A (this is what run C must demonstrate)
    a = _child_run("A")
    for key in ("object_construction_order", "object_master_link_order", "collection_creation_order",
                "master_children_order", "two_collection_link_order"):
        assert c["trace"][key] == list(reversed(a["trace"][key])), key
    assert c["trace"]["two_collection_link_order"] == ["Alpha", "Zeta"]
    assert a["trace"]["two_collection_link_order"] == ["Zeta", "Alpha"]


def test_runs_a_b_c_produce_identical_payload_values_and_identical_hashes():
    a, b, c = _child_run("A"), _child_run("B"), _child_run("C")

    # identical VALUES: the canonical encoding is byte-identical, so the payloads are equal
    assert a["canonical_json"] == b["canonical_json"] == c["canonical_json"]
    assert json.loads(a["canonical_json"]) == json.loads(b["canonical_json"]) == json.loads(c["canonical_json"])
    # identical HASHES (§9)
    assert a["payload_sha256"] == b["payload_sha256"] == c["payload_sha256"]
    # identical object order and representative under every construction order (§5.3, §5.4)
    assert a["object_ids"] == b["object_ids"] == c["object_ids"]
    assert a["shared_obj_collection"] == b["shared_obj_collection"] == c["shared_obj_collection"] == "Alpha"


def test_run_c_keeps_vertex_polygon_and_material_slot_order_unchanged():
    a, b, c = _child_run("A"), _child_run("B"), _child_run("C")
    for run in (a, b, c):
        assert run["trace"]["source_domains"]["vertices"] == [
            [float(x) for x in v] for v in UNSORTED_VERTS
        ]
        assert run["trace"]["source_domains"]["faces"] == [list(f) for f in UNSORTED_FACES]
        assert run["trace"]["source_domains"]["materials"] == UNSORTED_MATS
        assert run["emitted_source_domains"]["materials"] == UNSORTED_MATS
        assert run["emitted_source_domains"]["faces"] == [list(f) for f in UNSORTED_FACES]
    assert a["trace"]["source_domains"] == b["trace"]["source_domains"] == c["trace"]["source_domains"]
    assert (a["emitted_source_domains"] == b["emitted_source_domains"]
            == c["emitted_source_domains"])


def test_the_hash_seed_actually_took_effect_in_each_run():
    """Mechanical proof that A and B ran under DIFFERENT seeds while producing the same payload."""
    a, b, c = _child_run("A"), _child_run("B"), _child_run("C")
    assert a["pythonhashseed"] == "1" and b["pythonhashseed"] == "2" and c["pythonhashseed"] == "3"
    # a str-hash probe is seed-dependent; at least one probe must differ between any two seeds
    for left, right, labels in ((a, b, "AB"), (a, c, "AC"), (b, c, "BC")):
        assert any(x != y for x, y in zip(left["seed_probes"], right["seed_probes"])), labels
    # ...while the payload hash does not depend on the seed
    assert len({a["payload_sha256"], b["payload_sha256"], c["payload_sha256"]}) == 1


def test_in_process_run_matches_the_child_runs():
    """The in-process path (used by other tests) agrees with the isolated §9 runs."""
    a = _child_run("A")
    local = build_run_evidence("A")
    assert local["payload_sha256"] == a["payload_sha256"]
    assert local["canonical_json"] == a["canonical_json"]
    assert local["construction_id"] == CANONICAL_CONSTRUCTION_ID
    assert determinism_payload_sha() == a["payload_sha256"]


# ---------------------------------------------------------------------------
# §8.2 — canonical encoding vectors
# ---------------------------------------------------------------------------

def test_integral_floats_keep_a_float_form():
    obj = _mesh_obj("m", verts=[(2.0, 0.0, 0.0)], faces=[])
    text = _canonical_text(extract_scene(_bpy_with(master_objects=[obj])))
    assert '"vertices":[[2.0,0.0,0.0]]' in text


def test_negative_zero_keeps_its_sign_and_short_decimals_stay_short():
    obj = _mesh_obj("m", verts=[(-0.0, 0.1, 0.0)], faces=[])
    text = _canonical_text(extract_scene(_bpy_with(master_objects=[obj])))
    assert '"vertices":[[-0.0,0.1,0.0]]' in text


def test_exponent_form_values_encode_as_1e07():
    obj = _plain_obj("m", location=(1e-07, 0.0, 0.0))
    text = _canonical_text(extract_scene(_bpy_with(master_objects=[obj])))
    assert '"location":[1e-07,0.0,0.0]' in text


def test_face_indices_are_json_integers_never_floats():
    obj = _mesh_obj("m", faces=[(2, 0, 1), (0, 1, 3)])
    text = _canonical_text(extract_scene(_bpy_with(master_objects=[obj])))
    assert '"faces":[[2,0,1],[0,1,3]]' in text


def test_non_ascii_strings_are_escaped():
    obj = _plain_obj("\u00e9")
    text = _canonical_text(extract_scene(_bpy_with(master_objects=[obj])))
    assert "\\u00e9" in text


def test_non_finite_numbers_are_refused_by_the_canonical_encoding():
    payload = extract_scene(_bpy_with(master_objects=[_plain_obj("x")]))
    payload["objects"][0]["location"] = [float("nan"), 0.0, 0.0]
    with pytest.raises(ValueError, match="NaN|Out of range|out of range"):
        _canonical_text(payload)


# ---------------------------------------------------------------------------
# §11.1 / §11.2 — digest participation (T-6) and the mechanical key sets
# ---------------------------------------------------------------------------

def _digest_fixture_payload():
    obj = _mesh_obj("m", mats=["A", "B"])
    return extract_scene(_bpy_with(master_objects=[obj]))


def _object_with_mesh(payload):
    return next(o for o in payload["objects"] if o.get("mesh") is not None)


def test_representation_state_fields_do_not_move_the_scene_input_digest():
    base = _digest_fixture_payload()
    base_digest = scene_input_digest(payload_to_scene_model(base))
    faces = len(_object_with_mesh(base)["mesh"]["faces"])
    variants = {
        "materials": ["Zed"],
        "normals": [[0.0, 0.0, 1.0]] * faces,
        "uvs": [[0.0, 0.0]] * faces,
        "local_frame_id": "frame-1",
    }
    for field, value in variants.items():
        variant = copy.deepcopy(base)
        _object_with_mesh(variant)["mesh"][field] = value
        assert scene_input_digest(payload_to_scene_model(variant)) == base_digest, field


@pytest.mark.parametrize(
    "field,value",
    [("collection", "Zeta"), ("visible", False), ("rotation", [0.5, 0.5, 0.5, 0.5])],
)
def test_corrected_producer_fields_do_move_the_scene_input_digest(field, value):
    base = _digest_fixture_payload()
    base_digest = scene_input_digest(payload_to_scene_model(base))
    variant = copy.deepcopy(base)
    variant["objects"][0][field] = value
    assert scene_input_digest(payload_to_scene_model(variant)) != base_digest


def test_digest_input_key_sets_are_exactly_the_documented_ones(monkeypatch):
    import planning.blender.kernel as kernel

    captured = {}
    real = kernel.compute_input_digest

    def spy(values):
        captured["values"] = copy.deepcopy(values)
        return real(values)

    monkeypatch.setattr(kernel, "compute_input_digest", spy)
    payload = _digest_fixture_payload()
    scene_input_digest(payload_to_scene_model(payload))

    values = captured["values"]
    assert set(values) == {"scene_id", "unit_system", "coordinate_frame", "objects"}
    for obj in values["objects"]:
        assert set(obj) == {
            "object_id", "name", "collection", "parent", "location", "scale", "rotation",
            "visible", "mesh",
        }
    for obj in values["objects"]:
        if obj["mesh"] is not None:
            assert set(obj["mesh"]) == {"mesh_id", "vertices", "faces"}


# ---------------------------------------------------------------------------
# §4.5 / T-4 — `materials: null` acceptance layers (unchanged behaviour)
# ---------------------------------------------------------------------------

def test_validator_accepts_materials_null_but_model_construction_rejects_it():
    payload = _digest_fixture_payload()
    _object_with_mesh(payload)["mesh"]["materials"] = None
    validate_payload_schema(payload)                     # the payload validator never inspects materials
    with pytest.raises(SceneReportInputError, match="materials"):
        payload_to_scene_model(payload)


def test_producer_never_emits_materials_null():
    payload = _digest_fixture_payload()
    assert _object_with_mesh(payload)["mesh"]["materials"] == ["A", "B"]
    omitted = extract_scene(_bpy_with(master_objects=[_mesh_obj("m", mats=[None])]))
    assert "materials" not in _object_with_mesh(omitted)["mesh"]


# ---------------------------------------------------------------------------
# §10 / §12.4 — duplicate canonical IDs stay kernel-findable
# ---------------------------------------------------------------------------

def test_hand_built_payload_with_duplicate_object_ids_is_kernel_findable():
    payload = _digest_fixture_payload()
    duplicate = copy.deepcopy(payload["objects"][0])
    payload["objects"].append(duplicate)
    report = run_scene_health(payload_to_scene_model(payload), soccer_field_profile_default())
    codes = {f.code.value for f in report.findings}
    assert "OBJECT_ID_DUPLICATE" in codes
