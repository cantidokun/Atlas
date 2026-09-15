"""Deterministic mesh/scene health kernel orchestrator.

Combines the generic mesh-health checks, the generic scene-health checks, the profile envelope
(scale) check, and the readiness gate into a single :class:`SceneReport`. This is the entry point
the thin Blender adapter and tests call.

Analysis-only: this module never executes Blender, authorizes anything, issues receipts, or
mutates assets. It is purely a deterministic function from a canonical ``SceneModel`` + profile to
a ``SceneReport``.
"""

from typing import Any, Dict, List, Mapping, Optional, Tuple

from planning.blender.digital_twin_readiness import evaluate_readiness
from planning.blender.finding_codes import FindingCode
from planning.blender.mesh_health import check_mesh, check_mesh_in_envelope
from planning.blender.scene_health import check_scene, _object_world_points
from planning.blender.transforms import world_points
from planning.blender.scene_model import SceneModel
from planning.blender.scene_report import Finding, SceneReport, build_report, compute_input_digest
from planning.blender.soccer_field_profile import SoccerFieldValidationProfile


def run_scene_health(
    scene: SceneModel,
    profile: Optional[SoccerFieldValidationProfile] = None,
    *,
    include_envelope: bool = True,
    input_digest: Optional[str] = None,
    source_revision_id: Optional[str] = None,
) -> SceneReport:
    """Run the full deterministic kernel over a canonical scene and produce a SceneReport."""
    if not isinstance(scene, SceneModel):
        raise TypeError("run_scene_health requires a SceneModel")
    if profile is None:
        profile = soccer_field_profile_default()

    findings: List[Finding] = []
    scene_metrics: Dict[str, Any] = {}

    mesh_metrics: Dict[str, Any] = {}
    for obj in scene.objects:
        if obj.mesh is not None:
            mesh = obj.mesh
            f_mesh = check_mesh(mesh)
            findings.extend(f_mesh)
            if include_envelope:
                obj_world = _object_world_points(scene, obj)
                if obj_world is not None:
                    f_env = check_mesh_in_envelope(
                        mesh,
                        profile.envelope_min,
                        profile.envelope_max,
                        world_vertices=obj_world,
                        tolerance=profile.tolerance_bounds_metres,
                    )
                    findings.extend(f_env)
                # else: pose unresolved (missing/cyclic parent) -> the scene-health hierarchy check
                # already emitted OBJECT_HIERARCHY_INVALID; do not evaluate envelope on a mis-posed mesh.
            mesh_metrics[mesh.mesh_id] = {
                "vertices": len(mesh.vertices),
                "faces": len(mesh.faces),
            }

    f_scene = check_scene(scene, profile)
    # Tag scene-level findings with the object they concern (already set by scene_health).
    findings.extend(f_scene)

    scene_metrics = _compute_scene_metrics(scene, mesh_metrics, findings)

    state, reason = evaluate_readiness(scene, findings, profile)
    scene_metrics["readiness_reason"] = reason

    if input_digest is None:
        input_digest = _scene_input_digest(scene)

    return build_report(
        scene_id=scene.scene_id,
        validation_state=state,
        findings=findings,
        scene_metrics=scene_metrics,
        profile_name=profile.name,
        input_digest=input_digest,
        source_revision_id=source_revision_id,
    )


def scene_input_digest(scene: SceneModel) -> str:
    """Deterministic digest of the canonical scene input for provenance. Public wrapper."""
    return _scene_input_digest(scene)


def _scene_input_digest(scene: SceneModel) -> str:
    payload: Dict[str, Any] = {
        "scene_id": scene.scene_id,
        "unit_system": scene.unit_system,
        "coordinate_frame": scene.coordinate_frame,
        "objects": [
            {
                "object_id": o.object_id,
                "name": o.name,
                "collection": o.collection,
                "parent": o.parent_object_id,
                "location": list(o.location),
                "scale": list(o.scale),
                "rotation": list(o.rotation),
                "visible": o.visible,
                "mesh": (
                    {
                        "mesh_id": o.mesh.mesh_id,
                        "vertices": o.mesh.vertices,
                        "faces": o.mesh.faces,
                    }
                    if o.mesh is not None
                    else None
                ),
            }
            for o in scene.objects
        ],
    }
    return compute_input_digest(payload)


def _compute_scene_metrics(scene: SceneModel, mesh_metrics: Dict[str, Any], findings: List[Finding]) -> Dict[str, Any]:
    total_vertices = sum(m["vertices"] for m in mesh_metrics.values())
    total_faces = sum(m["faces"] for m in mesh_metrics.values())
    error_count = sum(1 for f in findings if f.severity.value == "error")
    warning_count = sum(1 for f in findings if f.severity.value == "warning")
    code_counts: Dict[str, int] = {}
    for f in findings:
        code_counts[f.code.value] = code_counts.get(f.code.value, 0) + 1
    return {
        "object_count": len(scene.objects),
        "mesh_object_count": len(mesh_metrics),
        "total_vertices": total_vertices,
        "total_faces": total_faces,
        "finding_error_count": error_count,
        "finding_warning_count": warning_count,
        "finding_codes": code_counts,
        "mesh_metrics": mesh_metrics,
    }


def soccer_field_profile_default() -> SoccerFieldValidationProfile:
    """Re-export the default profile for convenience (avoids deep import at call sites)."""
    from planning.blender.soccer_field_profile import soccer_field_profile

    return soccer_field_profile()