"""Blender-process runtime for the Correction Execution Bridge.

This module runs inside one disposable Blender process. It does not own planning or authorization;
it reconstructs the canonical CorrectionPlan values, uses the existing correction executor, and
provides only the real Blender mutation/extraction seams.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Mapping, Optional

import bpy

from planning.blender.bpy_extraction import extract_scene
from planning.blender.correction_authorization import parse_authorization
from planning.blender.correction_contract import CorrectionPlan, CorrectionProposal
from planning.blender.correction_executor import (
    ExecutionOutcome,
    execute_merge_vertex,
    execute_remove_degenerate_face,
    execute_remove_duplicate_face,
    execute_repair_face_winding,
)
from planning.blender.extraction_payload import payload_to_scene_model
from planning.blender.kernel import run_scene_health, soccer_field_profile_default


BRIDGE_START = "ATLAS_CORRECTION_BRIDGE_START"
BRIDGE_END = "ATLAS_CORRECTION_BRIDGE_END"


class BridgeRuntimeError(RuntimeError):
    """Declared bridge-runtime failure."""


@dataclass
class LiveEngine:
    bpy: Any


def _reconstruct_plan(raw_plan: Mapping[str, Any]) -> CorrectionPlan:
    if type(raw_plan) is not dict:
        raise BridgeRuntimeError("plan must be an exact object")
    corrections = []
    for raw in raw_plan.get("corrections", []):
        corrections.append(
            CorrectionProposal(
                correction_id=raw["correction_id"],
                finding_code=raw["finding_code"],
                object_id=raw.get("object_id"),
                mesh_id=raw.get("mesh_id"),
                correction_type=raw["correction_type"],
                parameters=raw["parameters"],
                rationale=raw["rationale"],
                preconditions=tuple(raw.get("preconditions", [])),
                expected_postcondition=raw["expected_postcondition"],
                risk=raw["risk"],
                severity=raw["severity"],
                reversibility=raw["reversibility"],
                dependencies=tuple(raw.get("dependencies", [])),
                determinism=raw["determinism"],
                requires_human_review=raw["requires_human_review"],
                out_of_scope=raw["out_of_scope"],
            )
        )
    return CorrectionPlan(
        plan_id=raw_plan["plan_id"],
        source_report_digest=raw_plan["source_report_digest"],
        source_revision_id=raw_plan.get("source_revision_id"),
        planner_version=raw_plan["planner_version"],
        profile=raw_plan["profile"],
        corrections=tuple(corrections),
        dependencies=tuple(tuple(edge) for edge in raw_plan.get("dependencies", [])),
        summary_metrics=raw_plan["summary_metrics"],
        state=raw_plan["state"],
        planning_errors=tuple(raw_plan.get("planning_errors", [])),
    )


def _canonical_postcondition_binding(plan: CorrectionPlan, operation: str) -> tuple[str, str]:
    matches = [c for c in plan.corrections if c.correction_type == operation]
    if len(matches) != 1:
        raise BridgeRuntimeError("expected exactly one selected correction")
    correction = matches[0]
    reference = f"correction_executor:1:{operation}"
    body = {
        "reference": reference,
        "correction_type": correction.correction_type,
        "expected_postcondition": correction.expected_postcondition,
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode(
            "utf-8"
        )
    ).hexdigest()
    return reference, digest


def _extractor(engine_state):
    payload = extract_scene(engine_state.bpy)
    scene = payload_to_scene_model(payload)
    report = run_scene_health(scene, soccer_field_profile_default())
    return scene, report


def _same_datablock_rebuild(obj: Any, vertices: Any, faces: Any) -> None:
    mesh = obj.data
    material_slots = [(slot.link, getattr(slot.material, "name", None)) for slot in obj.material_slots]
    mesh.clear_geometry()
    mesh.from_pydata(
        [tuple(float(c) for c in vertex) for vertex in vertices],
        [],
        [tuple(int(i) for i in face) for face in faces],
    )
    mesh.update()
    observed_slots = [(slot.link, getattr(slot.material, "name", None)) for slot in obj.material_slots]
    if observed_slots != material_slots:
        raise BridgeRuntimeError("same-datablock rebuild changed the material-slot table")


def _target_object(object_id: Optional[str], mesh_id: Optional[str]):
    if type(object_id) is not str or not object_id:
        raise BridgeRuntimeError("bridge requires an explicit target object_id")
    if type(mesh_id) is not str or not mesh_id:
        raise BridgeRuntimeError("bridge requires an explicit target mesh_id")
    obj = bpy.data.objects.get(object_id)
    if obj is None:
        raise BridgeRuntimeError(f"target object {object_id!r} does not exist in Blender")
    if getattr(obj, "type", None) != "MESH":
        raise BridgeRuntimeError(f"target object {object_id!r} is not a mesh object")
    if getattr(obj.data, "name", None) != mesh_id:
        raise BridgeRuntimeError(
            f"target object {object_id!r} data-block is {getattr(obj.data, 'name', None)!r}, not {mesh_id!r}"
        )
    return obj


def _face_removal_mutator(engine_state, *, object_id, mesh_id, face_ids=None, dup_tuple=None, face_id=None, face_tuple=None):
    obj = _target_object(object_id, mesh_id)
    faces = [tuple(int(v) for v in polygon.vertices) for polygon in obj.data.polygons]
    if face_ids is not None:
        ids = [int(value) for value in face_ids]
        if len(ids) != 2:
            raise BridgeRuntimeError("duplicate-face mutation requires exactly two recorded face ids")
        remove_index = max(ids)
    else:
        if type(face_id) is not int:
            raise BridgeRuntimeError("degenerate-face mutation requires an exact face_id")
        remove_index = face_id
    if remove_index < 0 or remove_index >= len(faces):
        raise BridgeRuntimeError("recorded face index is outside the live Blender mesh")
    del faces[remove_index]
    _same_datablock_rebuild(
        obj,
        [tuple(vertex.co) for vertex in obj.data.vertices],
        faces,
    )


def _winding_mutator(engine_state, *, object_id, mesh_id, face_index, face_tuple):
    obj = _target_object(object_id, mesh_id)
    faces = [tuple(int(v) for v in polygon.vertices) for polygon in obj.data.polygons]
    if face_index < 0 or face_index >= len(faces):
        raise BridgeRuntimeError("designated winding face index is outside the live mesh")
    expected = tuple(int(v) for v in face_tuple)
    if faces[face_index] != expected:
        raise BridgeRuntimeError("designated face tuple changed before the engine mutation")
    faces[face_index] = tuple(reversed(faces[face_index]))
    _same_datablock_rebuild(
        obj,
        [tuple(vertex.co) for vertex in obj.data.vertices],
        faces,
    )


def _merge_mutator(engine_state, *, object_id, mesh_id, vertices, faces, old_to_new_mapping):
    obj = _target_object(object_id, mesh_id)
    _same_datablock_rebuild(obj, vertices, faces)


def _run_executor(plan: CorrectionPlan, request: Mapping[str, Any]) -> dict[str, Any]:
    operation = request["operation"]
    authorization = request.get("authorization")
    engine = LiveEngine(bpy)
    mutator_invocations = {"count": 0}

    def counted(mutator):
        def wrapper(engine_state, **kwargs):
            mutator_invocations["count"] += 1
            return mutator(engine_state, **kwargs)
        return wrapper

    if operation == "REMOVE_DUPLICATE_FACE":
        receipt = execute_remove_duplicate_face(
            engine_state=engine,
            plan=plan,
            mutator=counted(_face_removal_mutator),
            extractor=_extractor,
        )
    elif operation == "REMOVE_DEGENERATE_FACE":
        receipt = execute_remove_degenerate_face(
            engine_state=engine,
            plan=plan,
            mutator=counted(_face_removal_mutator),
            extractor=_extractor,
        )
    elif operation == "REPAIR_FACE_WINDING":
        receipt = execute_repair_face_winding(
            engine_state=engine,
            plan=plan,
            authorization=authorization,
            mutator=counted(_winding_mutator),
            extractor=_extractor,
        )
    elif operation == "REPAIR_MERGE_VERTEX":
        receipt = execute_merge_vertex(
            engine_state=engine,
            plan=plan,
            authorization=authorization,
            mutator=counted(_merge_mutator),
            extractor=_extractor,
        )
    else:
        raise BridgeRuntimeError(f"unknown bridge operation: {operation!r}")

    return {
        "receipt": receipt,
        "mutator_invocations": mutator_invocations["count"],
    }


def _load_source(path: Optional[str]) -> None:
    if path is None:
        return
    if type(path) is not str or not path:
        raise BridgeRuntimeError("source_blend_path must be a non-empty string")
    if not os.path.isfile(path):
        raise BridgeRuntimeError(f"source_blend_path does not exist: {path}")
    result = bpy.ops.wm.open_mainfile(filepath=path, load_ui=False)
    if "FINISHED" not in result:
        raise BridgeRuntimeError(f"Blender failed to load source file: {result}")


def run_embedded_request(request_json: str) -> None:
    engine_evidence = {
        "process_disposed": True,
        "ambiguous_result": False,
        "mutator_invocations": 0,
        "source_loaded": False,
        "filepath_before_load": bpy.data.filepath,
        "filepath_after_load": None,
        "filepath_at_end": None,
        "saved_anything": False,
        "is_dirty_at_end": False,
        "extraction_invocations": 0,
    }
    request_digest = None
    try:
        request = json.loads(request_json)
        if type(request) is not dict:
            raise BridgeRuntimeError("embedded request must be an object")
        request_digest = hashlib.sha256(request_json.encode("utf-8")).hexdigest()

        plan = _reconstruct_plan(request["plan"])
        if plan.plan_id != request["plan_id"]:
            raise BridgeRuntimeError("plan_id mismatch between request and plan payload")
        reference, digest = _canonical_postcondition_binding(plan, request["operation"])
        if request["expected_postcondition_ref"] != reference:
            raise BridgeRuntimeError("expected_postcondition_ref mismatch")
        if request["expected_postcondition_digest"] != digest:
            raise BridgeRuntimeError("expected_postcondition_digest mismatch")

        _load_source(request.get("source_blend_path"))
        engine_evidence["source_loaded"] = request.get("source_blend_path") is not None
        engine_evidence["filepath_after_load"] = bpy.data.filepath

        original_extractor = _extractor

        def counted_extractor(engine_state):
            engine_evidence["extraction_invocations"] += 1
            return original_extractor(engine_state)

        globals()["_extractor"] = counted_extractor

        out = _run_executor(plan, request)
        receipt = out["receipt"]
        engine_evidence["mutator_invocations"] = out["mutator_invocations"]
        engine_evidence["filepath_at_end"] = bpy.data.filepath
        engine_evidence["is_dirty_at_end"] = bool(bpy.data.is_dirty)
        engine_evidence["mutator_invocations"] = out["mutator_invocations"]

        payload = {
            "request_digest": hashlib.sha256(request_json.encode("utf-8")).hexdigest(),
            "correction_result": receipt,
            "engine_evidence": engine_evidence,
        }
    except Exception as exc:
        if engine_evidence.get("mutator_invocations", 0) > 0:
            engine_evidence["ambiguous_result"] = True
        engine_evidence["filepath_at_end"] = bpy.data.filepath
        engine_evidence["is_dirty_at_end"] = bool(bpy.data.is_dirty)
        payload = {
            "request_digest": request_digest or hashlib.sha256(request_json.encode("utf-8")).hexdigest(),
            "correction_result": {
                "result": ExecutionOutcome.MUTATION_FAILED,
                "failure_code": "BRIDGE_RUNTIME_ERROR",
                "error": f"{type(exc).__name__}: {exc}",
            },
            "engine_evidence": engine_evidence,
        }

    print(BRIDGE_START)
    print(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False))
    print(BRIDGE_END)
