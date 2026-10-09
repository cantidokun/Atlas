"""A-REF pure graph / projection / mutator-mirror tests (R4F 4.A, 4.C, 5, 6, 25)."""

import copy

import pytest

from tests.aref.aref_fixture import validate_fixture
from tests.aref.aref_pure import (EnvelopeRefusal, build_graph, fresh_graph,
                                  make_pure_extractor, make_pure_mutator)
from tests.aref.fixtures import SPECS, load_case


def _validated(fixture_id):
    return load_case(fixture_id)


def test_projection_uses_object_label_as_mesh_id_and_name_sorted_order():
    spec = _validated("AREF-TEST-FX-AL-C1")
    graph = build_graph(spec)
    payload = graph.project_payload(spec.scene["scene_id"], spec.scene["unit_system"])
    names = [o["object_id"] for o in payload["objects"]]
    assert names == ["atlas-target", "atlas-unrelated"]  # global ascending name order
    for o in payload["objects"]:
        assert o["mesh"]["mesh_id"] == o["object_id"]  # mesh_id is the OBJECT label


def test_shared_datablock_is_shared_identity_and_mutation_visible_to_all():
    spec = _validated("AREF-TEST-FX-AL-C1")
    graph = fresh_graph(spec)
    assert graph.objects["atlas-target"].db_key == graph.objects["atlas-unrelated"].db_key
    db = graph.datablocks["DB1"]
    mutator = make_pure_mutator("REMOVE_DUPLICATE_FACE")
    mutator(graph, object_id="atlas-target", mesh_id="atlas-target",
            selected_face_index=2, expected_face_tuple=(4, 5, 6))
    assert db.faces == [[4, 5, 6], [0, 1, 2]]  # one shared record; both objects observe it
    extractor = make_pure_extractor(spec)
    scene, _ = extractor(graph)
    for obj in scene.objects:
        assert tuple(tuple(f) for f in obj.mesh.faces) == ((4, 5, 6), (0, 1, 2))


def test_mirror_refuses_target_mismatch():
    spec = _validated("AREF-TEST-FX-MM-C1")
    graph = fresh_graph(spec)
    mutator = make_pure_mutator("REMOVE_DUPLICATE_FACE")
    with pytest.raises(EnvelopeRefusal) as excinfo:
        mutator(graph, object_id="atlas-target", mesh_id="atlas-target",
                selected_face_index=2, expected_face_tuple=(4, 5, 6))
    assert excinfo.value.code == "RC-TARGET-MISMATCH"


def test_mirror_duplicate_exact_index_and_tuple_rules():
    spec = _validated("AREF-TEST-FX-C1-PAIR")
    graph = fresh_graph(spec)
    mutator = make_pure_mutator("REMOVE_DUPLICATE_FACE")
    with pytest.raises(EnvelopeRefusal) as e1:
        mutator(graph, object_id="atlas-target", mesh_id="atlas-target",
                selected_face_index=True, expected_face_tuple=(4, 5, 6))
    assert e1.value.code == "RC-EXACT-INDEX"  # bool is rejected (not an exact int)
    with pytest.raises(EnvelopeRefusal) as e2:
        mutator(graph, object_id="atlas-target", mesh_id="atlas-target",
                selected_face_index=9, expected_face_tuple=(4, 5, 6))
    assert e2.value.code == "RC-INDEX-RANGE"
    with pytest.raises(EnvelopeRefusal) as e3:
        mutator(graph, object_id="atlas-target", mesh_id="atlas-target",
                selected_face_index=2, expected_face_tuple=(0, 1, 2))
    assert e3.value.code == "RC-TUPLE-MISMATCH"
    mutator(graph, object_id="atlas-target", mesh_id="atlas-target",
            selected_face_index=2, expected_face_tuple=(4, 5, 6))
    assert graph.datablocks["DB1"].faces == [[4, 5, 6], [0, 1, 2]]


def test_mirror_degenerate_has_no_tuple_comparison():
    spec = _validated("AREF-TEST-FX-C2-DEGEN")
    graph = fresh_graph(spec)
    mutator = make_pure_mutator("REMOVE_DEGENERATE_FACE")
    # the live branch performs no tuple comparison: a wrong recorded tuple must NOT refuse
    mutator(graph, object_id="atlas-target", mesh_id="atlas-target",
            face_id=0, face_tuple=[9, 9, 9])
    assert graph.datablocks["DB1"].faces == [[0, 1, 3]]


def test_mirror_winding_and_merge_transitions():
    spec = _validated("AREF-TEST-FX-C3-POS")
    graph = fresh_graph(spec)
    winding = make_pure_mutator("REPAIR_FACE_WINDING")
    faces0 = list(graph.datablocks["DB1"].faces)
    with pytest.raises(EnvelopeRefusal) as e1:
        winding(graph, object_id="atlas-target", mesh_id="atlas-target",
                face_index=0, face_tuple=[7, 8, 9])
    assert e1.value.code == "RC-TUPLE-MISMATCH"
    winding(graph, object_id="atlas-target", mesh_id="atlas-target",
            face_index=0, face_tuple=faces0[0])
    assert graph.datablocks["DB1"].faces[0] == list(reversed(faces0[0]))

    merge = make_pure_mutator("REPAIR_MERGE_VERTEX")
    merge(graph, object_id="atlas-target", mesh_id="atlas-target",
          vertices=[[0.0, 0.0, 0.0]], faces=[[0, 0, 0]], old_to_new_mapping={0: 0})
    assert graph.datablocks["DB1"].vertices == [[0.0, 0.0, 0.0]]


def test_no_rc_slots_branch_exists():
    """R4F 4.C: the pure mirror contains NO RC-SLOTS-CHANGED branch (live-only)."""
    import inspect

    from tests.aref import aref_pure

    source = inspect.getsource(aref_pure)
    assert "RC-SLOTS-CHANGED" not in source.split("NOTE (R4F 4.C")[0]
    assert "RC-SLOTS-CHANGED" in source  # only inside the explanatory NOTE
