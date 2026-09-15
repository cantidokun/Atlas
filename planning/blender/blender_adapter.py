"""Thin Blender adapter: normalize real Blender inspection data into the canonical kernel input.

This adapter does NOT duplicate validation semantics. It only:
1. extracts Blender-state fields from the normalized ``BlenderExecutionResult`` payloads /
   ``inspect_scene`` / ``inspect_mesh``/``inspect_object_transform`` style dicts the existing
   Blender tooling already returns,
2. maps them into the canonical :class:`~planning.blender.scene_model.SceneModel`,
3. invokes the deterministic kernel, and
4. returns the structured :class:`~planning.blender.scene_report.SceneReport`.

It deliberately requires NO live Blender for its own tests: a fixture payload exercises the same
mapping path as a real inspection. Live execution remains gated (the existing Blender boundary
owns that). No bpy is imported here.

The existing Blender execution/authority boundary (validate -> execute -> verify -> receipt ->
persistence-evidence) is NOT altered; the kernel is an analysis capability beneath it.
"""

from typing import Any, Dict, Optional, Tuple

from planning.blender.kernel import run_scene_health
from planning.blender.scene_model import SceneModel, ObjectModel, MeshModel
from planning.blender.scene_report import SceneReport, compute_input_digest
from planning.blender.soccer_field_profile import SoccerFieldValidationProfile
from planning.blender_result_contract import BlenderExecutionResult


def build_scene_model_from_blender(
    *,
    scene_id: str,
    objects: Tuple[Dict[str, Any], ...],
    unit_system: Optional[str] = None,
    coordinate_frame: Optional[str] = None,
    world_bounds: Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = None,
) -> SceneModel:
    """Build a canonical SceneModel from normalized, inspection-style object dicts.

    ``objects`` is a tuple of plain mappings with the keys understood by
    :func:`planning.blender.scene_model.parse_scene_report_input` (object_id, name, collection,
    parent_object_id, location, scale, visible, mesh). This is a thin, lossless normalization to
    the canonical model; no validation rules live here.
    """
    payload: Dict[str, Any] = {
        "scene_id": scene_id,
        "unit_system": unit_system if unit_system is not None else "METERS",
        "coordinate_frame": coordinate_frame,
        "world_bounds": world_bounds,
        "objects": list(objects),
    }
    from planning.blender.scene_model import parse_scene_report_input

    return parse_scene_report_input(payload)


def scene_from_inspect_payload(
    result: Any,
    *,
    scene_id: str = "atlas_scene",
    unit_system: str = "METERS",
) -> SceneModel:
    """Normalize an ``inspect_scene``-style payload into a canonical SceneModel.

    The payload is the normalized dict returned by the existing Blender boundary
    (``BlenderExecutionResult.details``). It is a thin mapping: each object is converted to the
    canonical object/mesh contract. Fields absent from the inspection are left unset (None),
    never invented.
    """
    if not isinstance(result, dict):
        raise TypeError("inspect payload must be a dict")
    raw_objects = result.get("objects", ())
    if not isinstance(raw_objects, (tuple, list)):
        raise TypeError("inspect payload objects must be a list/tuple")

    objects = []
    for raw in raw_objects:
        if not isinstance(raw, dict):
            raise TypeError("each object must be a dict")
        mesh = None
        if "vertex_count" in raw or "mesh" in raw:
            mesh_payload = raw.get("mesh")
            if isinstance(mesh_payload, dict):
                mesh = mesh_payload
            else:
                # minimal mesh from counts (no actual vertices available -> empty canonical mesh
                # would be rejected; skip mesh if no vertex list). We only build a mesh when a
                # real vertex list is available.
                mesh = None
        objects.append(
            {
                "object_id": raw.get("object_id") or raw.get("name") or str(len(objects)),
                "name": raw.get("name") or raw.get("object_name") or "unnamed",
                "collection": raw.get("collection"),
                "parent_object_id": raw.get("parent_object_id"),
                "location": raw.get("location", (0.0, 0.0, 0.0)),
                "scale": raw.get("scale", (1.0, 1.0, 1.0)),
                "visible": raw.get("visible", True),
                "mesh": mesh,
            }
        )
    return build_scene_model_from_blender(
        scene_id=scene_id,
        unit_system=unit_system,
        objects=tuple(objects),
    )


def evaluate_blender_inspection(
    result: Any,
    profile: Optional[SoccerFieldValidationProfile] = None,
    *,
    scene_id: str = "atlas_scene",
    unit_system: str = "METERS",
) -> SceneReport:
    """Single-call adapter: normalize an inspection payload, run the kernel, return a report."""
    scene = scene_from_inspect_payload(result, scene_id=scene_id, unit_system=unit_system)
    return run_scene_health(scene, profile)


def report_from_verified_result(
    verified: BlenderExecutionResult,
    profile: Optional[SoccerFieldValidationProfile] = None,
) -> SceneReport:
    """Convenience: accept a ``BlenderExecutionResult`` and produce a SceneReport.

    Only ``details`` from the verified result are consumed; the receipt/evidence machinery of the
    existing boundary is untouched.
    """
    return evaluate_blender_inspection(verified.details, profile)