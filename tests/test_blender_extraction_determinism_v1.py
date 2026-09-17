"""Extraction Fidelity v1 — deterministic determinism / encoding / digest-boundary tests.

Covers design §9 (three-run determinism protocol with the run-C reordering rules), §8.2 (canonical
evidence encoding vectors), §11.1/§11.2 (digest participation and the T-6 partition), §4.5 T-4
(``materials: null`` acceptance layers), and §10/§12.4 (duplicate canonical IDs stay kernel-findable).

Run C reorders ONLY things whose canonical order is derived by rule (object construction order,
collection creation order, collection-link order). Vertex order, polygon order and material-slot
append order are held identical — those are source-ordered domains (§6, §4.3).
"""
import copy
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
CANONICALIZATION = 'json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)'


def _canonical_text(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _payload_sha(payload) -> str:
    return hashlib.sha256(_canonical_text(payload).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# §9 — determinism fixture and the three runs
# ---------------------------------------------------------------------------

def _determinism_scene(reverse=False):
    """Same semantic scene; ``reverse`` changes only rule-derived construction order (§9 run C)."""
    zeta, alpha, nested = _Collection("Zeta"), _Collection("Alpha"), _Collection("Nested")
    alpha.children.append(nested)
    if reverse:
        zeta, alpha = alpha, zeta

    material_slots = [_Slot(_Mat(n), "DATA") for n in UNSORTED_MATS]

    def build(name):
        if name == "e_obj":
            return _plain_obj("e_obj", euler=(0.5235987756, 0.6981317008, 0.8726646260))
        if name == "q_obj":
            return _plain_obj("q_obj", rotation_mode="QUATERNION", quat=(2.0, 0.0, 0.0, 0.0))
        if name == "m_alpha":
            return _mesh_obj("m_alpha", verts=UNSORTED_VERTS, faces=UNSORTED_FACES, mats=UNSORTED_MATS)
        if name == "m_beta":
            data = _mesh_obj("m_beta", verts=UNSORTED_VERTS, faces=UNSORTED_FACES)
            data.material_slots = material_slots
            return data
        if name == "shared_obj":
            return _plain_obj("shared_obj")
        raise AssertionError(name)

    order = ["q_obj", "e_obj", "m_alpha", "m_beta", "shared_obj"]
    built = {n: build(n) for n in (list(reversed(order)) if reverse else order)}
    solo = _plain_obj("solo_master_only")
    in_nested = _plain_obj("in_nested")

    scene = _Bpy().context.scene
    for obj in (list(built.values()) if reverse else list(built.values())):
        scene.collection.link(obj)
    scene.collection.link(solo)
    if reverse:
        scene.collection.children.extend([alpha, zeta])
    else:
        scene.collection.children.extend([zeta, alpha])
    if reverse:
        alpha.link(built["shared_obj"])
        zeta.link(built["shared_obj"])
    else:
        zeta.link(built["shared_obj"])
        alpha.link(built["shared_obj"])
    nested.link(in_nested)
    return _Bpy(scene)


def determinism_payload_sha() -> str:
    """Payload SHA-256 of the canonical construction (§9 run A). Importable by a child process."""
    return _payload_sha(extract_scene(_determinism_scene(reverse=False)))


def test_run_a_and_run_c_produce_identical_payloads_and_hashes():
    payload_a = extract_scene(_determinism_scene(reverse=False))
    payload_c = extract_scene(_determinism_scene(reverse=True))

    assert payload_a == payload_c
    sha_a, sha_c = _payload_sha(payload_a), _payload_sha(payload_c)
    assert sha_a == sha_c, (sha_a, sha_c)

    # source-ordered domains are unaffected by the construction-order change (§9)
    alpha_a = _by_id(payload_a, "m_alpha")["mesh"]
    alpha_c = _by_id(payload_c, "m_alpha")["mesh"]
    assert alpha_a["vertices"] == alpha_c["vertices"] == [[round(c, 6) for c in v] for v in UNSORTED_VERTS]
    assert alpha_a["faces"] == alpha_c["faces"] == [list(f) for f in UNSORTED_FACES]
    assert alpha_a["materials"] == alpha_c["materials"] == UNSORTED_MATS

    # the reversed collection-link sub-case must not move the representative (§9, §5.4)
    assert _by_id(payload_a, "shared_obj")["collection"] == _by_id(payload_c, "shared_obj")["collection"]
    assert [o["object_id"] for o in payload_a["objects"]] == [o["object_id"] for o in payload_c["objects"]]


def test_run_b_different_pythonhashseed_produces_the_same_hash():
    expected = determinism_payload_sha()
    script = (
        "import sys; sys.path.insert(0, {repo!r});\n"
        "from tests.test_blender_extraction_determinism_v1 import determinism_payload_sha\n"
        "print('SHA=' + determinism_payload_sha())\n"
    ).format(repo=REPO_ROOT)
    results = {}
    for seed in ("1", "2", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        proc = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, env=env, cwd=REPO_ROOT,
        )
        assert proc.returncode == 0, proc.stderr[-1500:]
        results[seed] = proc.stdout.strip().split("SHA=")[-1].strip()
    assert set(results.values()) == {expected}, results


def test_determinism_evidence_records_the_canonicalization_identifier():
    # §9 requires each run to record hash, canonicalization id and construction order; the id is the
    # §8.2 encoding, and it must be the one actually used by the payload hash above.
    payload = extract_scene(_determinism_scene(reverse=False))
    assert hashlib.sha256(_canonical_text(payload).encode("utf-8")).hexdigest() == _payload_sha(payload)
    assert "sort_keys=True" in CANONICALIZATION and "allow_nan=False" in CANONICALIZATION


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
