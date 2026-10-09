"""A-REF fixture catalog: hand-written FIX specifications (R4F sections 16, 25).

Expected literals (pre-digests, plan identities, authorization literals) are computed ONCE at
fixture-authoring time by tests/aref/authoring/generate_fixtures.py and stored under
tests/aref/expected/ + tests/aref/plan_artifacts/ (never derived at case runtime; R4F 8.2/9.10).

This file is test/conformance scope only.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List

from tests.aref.aref_fixture import FixtureSpec, validate_fixture

#: Shared fixture geometry (the authoring validation record's scenes, validated in tests).
E0_VERTS = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0], [1.0, 1.0, 0.0], [1.0, 0.0, 1.0], [0.0, 1.0, 1.0]]
A = [4, 5, 6]
X = [0, 1, 2]
A_ROT = [5, 6, 4]
W1B_ZERO_AREA_VERTS = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [5.0, 5.0, 0.0]]
W1B_ZERO_AREA_FACES = [[0, 1, 2], [0, 1, 3]]


def _base_spec(fixture_id: str, case: str, operation: str, *,
               datablocks: List[Dict[str, Any]], objects: List[Dict[str, Any]],
               params: Dict[str, Any], plan_construction: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "fixture_id": fixture_id,
        "schema_version": "aref-fix-v1",
        "case": case,
        "operation": operation,
        "scene": {"scene_id": "r4f-aref-scene", "unit_system": "METERS"},
        "datablocks": datablocks,
        "objects": objects,
        "sharing": {db["db_key"]: [o["object_id"] for o in objects if o["datablock_key"] == db["db_key"]]
                    for db in datablocks},
        "params": params,
        "plan_construction": plan_construction,
        "plan_source": "REAL_PLANNER",
        "authorization_fixture": None,
        "expected": {},  # filled from the generated expected file at load time
    }


def _obj(object_id: str, db_key: str, *, type_: str = "MESH") -> Dict[str, Any]:
    return {"object_id": object_id, "datablock_key": db_key, "type": type_}


def _db(db_key: str, db_name: str, vertices: List[List[float]], faces: List[List[int]]) -> Dict[str, Any]:
    return {"db_key": db_key, "db_name": db_name, "vertices": vertices, "faces": faces}


SPECS: Dict[str, Dict[str, Any]] = {}


def _register(spec: Dict[str, Any]) -> None:
    SPECS[spec["fixture_id"]] = spec


# --- C1 duplicate-face cases ------------------------------------------------------------------
_register(_base_spec("AREF-TEST-FX-C1-PAIR", "C1", "REMOVE_DUPLICATE_FACE",
                     datablocks=[_db("DB1", "atlas-target", E0_VERTS, [A, X, A])],
                     objects=[_obj("atlas-target", "DB1")],
                     params={"face_ids": [0, 2], "duplicate_relationship": "exact_duplicate"},
                     plan_construction={"rule": "P1"}))
_register(_base_spec("AREF-TEST-FX-C1-ROTATED", "C1", "REMOVE_DUPLICATE_FACE",
                     datablocks=[_db("DB1", "atlas-target", E0_VERTS, [A, A_ROT, X])],
                     objects=[_obj("atlas-target", "DB1")],
                     params={"face_ids": [0, 1], "duplicate_relationship": "exact_duplicate"},
                     plan_construction={"rule": "P1"}))
_register(_base_spec("AREF-TEST-FX-C1-TRIPLE-S2", "C1", "REMOVE_DUPLICATE_FACE",
                     datablocks=[_db("DB1", "atlas-target", E0_VERTS, [A, X, A, A])],
                     objects=[_obj("atlas-target", "DB1")],
                     params={"face_ids": [0, 2], "duplicate_relationship": "exact_duplicate"},
                     plan_construction={"rule": "P2", "selected_pair": [0, 2]}))
_register(_base_spec("AREF-TEST-FX-C1-TRIPLE-S3", "C1", "REMOVE_DUPLICATE_FACE",
                     datablocks=[_db("DB1", "atlas-target", E0_VERTS, [A, X, A, A])],
                     objects=[_obj("atlas-target", "DB1")],
                     params={"face_ids": [0, 3], "duplicate_relationship": "exact_duplicate"},
                     plan_construction={"rule": "P2", "selected_pair": [0, 3]}))
_register(_base_spec("AREF-TEST-FX-C1-TRIPLE-AMB", "C1", "REMOVE_DUPLICATE_FACE",
                     datablocks=[_db("DB1", "atlas-target", E0_VERTS, [A, X, A, A])],
                     objects=[_obj("atlas-target", "DB1")],
                     params={},
                     plan_construction={"rule": "P1"}))
_register(_base_spec("AREF-TEST-FX-C1-PRECOND", "C1", "REMOVE_DUPLICATE_FACE",
                     datablocks=[_db("DB1", "atlas-target", E0_VERTS, [A, X, A])],
                     objects=[_obj("atlas-target", "DB1")],
                     params={},
                     plan_construction={"rule": "P1", "repoint": {"face_ids": [0, 1]}}))
_register(_base_spec("AREF-TEST-FX-C1-REVERSED", "C1", "REMOVE_DUPLICATE_FACE",
                     datablocks=[_db("DB1", "atlas-target", E0_VERTS, [A, X, A])],
                     objects=[_obj("atlas-target", "DB1")],
                     params={"face_ids": [2, 0], "duplicate_relationship": "exact_duplicate"},
                     plan_construction={"rule": "P1", "repoint": {"face_ids": [2, 0]}}))

# --- C2 degenerate case -----------------------------------------------------------------------
_register(_base_spec("AREF-TEST-FX-C2-DEGEN", "C2", "REMOVE_DEGENERATE_FACE",
                     datablocks=[_db("DB1", "atlas-target", W1B_ZERO_AREA_VERTS, W1B_ZERO_AREA_FACES)],
                     objects=[_obj("atlas-target", "DB1")],
                     params={"face_id": 0, "reason": "degenerate_face"},
                     plan_construction={"rule": "P1"}))

# --- FX-MM naming mismatch (OC3; R4F 16.6(3)) ---------------------------------------------------
_register(_base_spec("AREF-TEST-FX-MM-C1", "C1", "REMOVE_DUPLICATE_FACE",
                     datablocks=[_db("DB1", "atlas-target-mesh", E0_VERTS, [A, X, A])],
                     objects=[_obj("atlas-target", "DB1")],
                     params={"face_ids": [0, 2], "duplicate_relationship": "exact_duplicate"},
                     plan_construction={"rule": "P1"}))

# --- FX-AL aliased cases (OC5; R4F 16.6(4)) ----------------------------------------------------
_register(_base_spec("AREF-TEST-FX-AL-C1", "C1", "REMOVE_DUPLICATE_FACE",
                     datablocks=[_db("DB1", "atlas-target", E0_VERTS, [A, X, A])],
                     objects=[_obj("atlas-target", "DB1"), _obj("atlas-unrelated", "DB1")],
                     params={},
                     plan_construction={"rule": "P1"}))
_register(_base_spec("AREF-TEST-FX-AL-C1-R", "C1", "REMOVE_DUPLICATE_FACE",
                     datablocks=[_db("DB1", "atlas-target", E0_VERTS, [A, X, A])],
                     objects=[_obj("atlas-target", "DB1"), _obj("atlas-unrelated", "DB1")],
                     params={"face_ids": [0, 2], "duplicate_relationship": "exact_duplicate"},
                     plan_construction={"rule": "P3", "keep_only_target": ["atlas-target"]}))

# --- Authorization-negative cases (R4F 16.6(2); null authorization fixture) -------------------
#: pinned merge fixture geometry (merge_vertex_live_script.py:353-355).
B1_VERTS = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [7.0, 0.0, 0.0],
            [3.0, 3.0, 0.0], [3.0, 3.0, 0.0], [4.0, 0.0, 5.0]]
B1_FACES = [[0, 2, 3], [5, 2, 3]]

#: The pinned merge fixture geometry (merge_vertex_live_script.py:353-355) realizes a D2
#: winding proposal under the real planner (candidate_faces (0,1); designated_face_index None),
#: which is the scenario the C3 authorization cases exercise. The real planner emits no
#: REPAIR_MERGE_VERTEX correction for this or comparable simple scenes, so the merge
#: AUTHORIZATION_REQUIRED negative is NOT reachable through the real-planner path and is not
#: claimed (R4F 16.6(2) requires AUTHORIZATION_REQUIRED for C3 **or** C4).
_register(_base_spec("AREF-TEST-FX-C3-AUTHREQ", "C3", "REPAIR_FACE_WINDING",
                     datablocks=[_db("DB1", "atlas-target", B1_VERTS, B1_FACES)],
                     objects=[_obj("atlas-target", "DB1")],
                     params={},
                     plan_construction={"rule": "P1"}))

# --- C3 winding positive (authorization fixture literals generated at authoring time) ---------
_register(_base_spec("AREF-TEST-FX-C3-POS", "C3", "REPAIR_FACE_WINDING",
                     datablocks=[_db("DB1", "atlas-target", B1_VERTS, B1_FACES)],
                     objects=[_obj("atlas-target", "DB1")],
                     params={},
                     plan_construction={"rule": "P1"}))


def load_case(fixture_id: str, *, with_generated: bool = True) -> FixtureSpec:
    """Load + validate one case: spec skeleton merged with generated expected/plan literals."""
    from tests.aref.aref_harness import load_expected

    if fixture_id not in SPECS:
        raise KeyError(f"unknown fixture {fixture_id!r}")
    spec = copy.deepcopy(SPECS[fixture_id])
    if with_generated:
        expected = load_expected(fixture_id)
        spec["expected"] = expected["expected"]
        if expected.get("authorization_fixture") is not None:
            spec["authorization_fixture"] = expected["authorization_fixture"]
    return validate_fixture(spec)


def case_names() -> List[str]:
    return sorted(SPECS)


# --- C4 merge positive (R4F 16.6(1); construction rule PM = the planner's explicit merge pass) --
#: The planner's AUTOMATIC pass emits no merge proposal by design (correction_planner.py:687-694);
#: plan_merge_vertex_correction is the ONLY producer and is the real planner's explicit-request
#: entry point. The fixture geometry is the pinned merge fixture (merge_vertex_live_script.py:353-355)
#: whose live positive case the existing suite already exercises; the authorization fixture is
#: generated at authoring time from the real merge plan.
_register(_base_spec("AREF-TEST-FX-C4-MERGE", "C4", "REPAIR_MERGE_VERTEX",
                     datablocks=[_db("DB1", "atlas-target", B1_VERTS, B1_FACES)],
                     objects=[_obj("atlas-target", "DB1")],
                     params={},
                     plan_construction={"rule": "PM"}))

# --- FX-MM naming mismatch, operations C2/C3/C4 (R4F 16.6(3): MANDATORY, all four operations) ---
_register(_base_spec("AREF-TEST-FX-MM-C2", "C2", "REMOVE_DEGENERATE_FACE",
                     datablocks=[_db("DB1", "atlas-mesh", W1B_ZERO_AREA_VERTS, W1B_ZERO_AREA_FACES)],
                     objects=[_obj("atlas-target", "DB1")],
                     params={"face_id": 0, "reason": "degenerate_face"},
                     plan_construction={"rule": "P1"}))
_register(_base_spec("AREF-TEST-FX-MM-C3", "C3", "REPAIR_FACE_WINDING",
                     datablocks=[_db("DB1", "atlas-mesh", B1_VERTS, B1_FACES)],
                     objects=[_obj("atlas-target", "DB1")],
                     params={},
                     plan_construction={"rule": "P1"}))
_register(_base_spec("AREF-TEST-FX-MM-C4", "C4", "REPAIR_MERGE_VERTEX",
                     datablocks=[_db("DB1", "atlas-mesh", B1_VERTS, B1_FACES)],
                     objects=[_obj("atlas-target", "DB1")],
                     params={},
                     plan_construction={"rule": "PM"}))

# --- FX-AL aliased cases for C2/C3 (R4F 16.6(4); mandatory both variants for C1/C2) ------------
_register(_base_spec("AREF-TEST-FX-AL-C2", "C2", "REMOVE_DEGENERATE_FACE",
                     datablocks=[_db("DB1", "atlas-target", W1B_ZERO_AREA_VERTS, W1B_ZERO_AREA_FACES)],
                     objects=[_obj("atlas-target", "DB1"), _obj("atlas-unrelated", "DB1")],
                     params={},
                     plan_construction={"rule": "P1"}))
_register(_base_spec("AREF-TEST-FX-AL-C2-R", "C2", "REMOVE_DEGENERATE_FACE",
                     datablocks=[_db("DB1", "atlas-target", W1B_ZERO_AREA_VERTS, W1B_ZERO_AREA_FACES)],
                     objects=[_obj("atlas-target", "DB1"), _obj("atlas-unrelated", "DB1")],
                     params={"face_id": 0, "reason": "degenerate_face"},
                     plan_construction={"rule": "P3", "keep_only_target": ["atlas-target"]}))
_register(_base_spec("AREF-TEST-FX-AL-C3", "C3", "REPAIR_FACE_WINDING",
                     datablocks=[_db("DB1", "atlas-target", B1_VERTS, B1_FACES)],
                     objects=[_obj("atlas-target", "DB1"), _obj("atlas-unrelated", "DB1")],
                     params={},
                     plan_construction={"rule": "P1"}))
_register(_base_spec("AREF-TEST-FX-AL-C3-R", "C3", "REPAIR_FACE_WINDING",
                     datablocks=[_db("DB1", "atlas-target", B1_VERTS, B1_FACES)],
                     objects=[_obj("atlas-target", "DB1"), _obj("atlas-unrelated", "DB1")],
                     params={},
                     plan_construction={"rule": "P3", "keep_only_target": ["atlas-target"]}))
