"""Atlas Blender Agent — deterministic mesh/scene health kernel.

A pure-Python, language-agnostic scene/mesh health analysis foundation, downstream of
photogrammetry and upstream of digital-twin cleanup/preparation. It does NOT depend on ``bpy``,
does NOT execute or authorize Blender, and is analysis-only.

See ``BLENDER_MESH_SCENE_HEALTH_KERNEL.md`` for the full architecture, finding codes, validation
rules, profiles, readiness criteria, complexity, and C++-replacement seams.
"""

# Python 3.9 compatibility: some canonical value contracts use ``slots=True`` when the
# interpreter supports it. Keep those contracts importable on Atlas's supported 3.9 runtime
# without changing their semantic frozen-value behavior. The shim is restored before this
# package import completes so it does not permanently monkeypatch the process-wide dataclasses
# module.
import dataclasses as _dataclasses
import sys as _sys

_native_dataclass = None
if _sys.version_info < (3, 10):
    _native_dataclass = _dataclasses.dataclass

    def _dataclass_compat(cls=None, **kwargs):
        kwargs.pop("slots", None)
        if cls is None:
            return lambda target: _native_dataclass(target, **kwargs)
        return _native_dataclass(cls, **kwargs)

    _dataclasses.dataclass = _dataclass_compat

from planning.blender.blender_adapter import (
    build_scene_model_from_blender,
    evaluate_blender_inspection,
    report_from_verified_result,
    scene_from_inspect_payload,
)
from planning.blender.blender_units import UnitMappingError, is_meters_like, map_unit_system
from planning.blender.bpy_extraction import SceneMembershipError
from planning.blender.digital_twin_readiness import evaluate_readiness
from planning.blender.extraction_payload import (
    PAYLOAD_SCHEMA_VERSION,
    payload_to_scene_model,
    validate_payload_schema,
)
from planning.blender.finding_codes import (
    DEFAULT_READY_BLOCKING_CODES,
    FindingCode,
    FindingSeverity,
    severity_of,
)
from planning.blender.kernel import run_scene_health, scene_input_digest
from planning.blender.mesh_health import check_mesh, check_mesh_in_envelope
from planning.blender.scene_health import check_scene
from planning.blender.scene_model import (
    MeshModel,
    ObjectModel,
    SceneModel,
    SceneReportInputError,
    parse_scene_report_input,
)
from planning.blender.scene_report import (
    Finding,
    REPORT_FORMAT_VERSION,
    VALIDATOR_VERSION,
    SceneReport,
    compute_input_digest,
)
from planning.blender.soccer_field_profile import SoccerFieldValidationProfile, soccer_field_profile
from planning.blender.correction_codes import (
    CorrectionDeterminism,
    CorrectionReversibility,
    CorrectionRiskClass,
    PlannerState,
)
from planning.blender.correction_contract import (
    CorrectionPlan as CorrectionPlanContract,
    CorrectionProposal as CorrectionProposalContract,
)
from planning.blender.correction_mapping import classify as classify_correction
from planning.blender.correction_planner import PLANNER_VERSION, plan_scene_report
from planning.blender.correction_executor import (
    EXECUTOR_VERSION,
    ExecutionOutcome,
    WindingPostconditionError,
    WindingPredicateError,
    execute_remove_duplicate_face,
    execute_remove_degenerate_face,
    execute_repair_face_winding,
)
from planning.blender.correction_authorization import (
    ACCEPTED_AUTHORIZATION_POLICY_VERSIONS,
    AUTHORIZATION_VERSION,
    WINDING_CORRECTION_TYPE,
    AuthorizationArtifact,
    AuthorizationContractError,
    AuthorizationError,
    AuthorizationFailureCode,
    AuthorizationInputError,
    AuthorizationOutcome,
    AuthorizationVerdict,
    PresentedWork,
    parse_authorization,
    resolve_designated_face_index,
    validate_recorded_edges,
    verify_authorization,
    verify_recorded_set_agreement,
)
from planning.blender.transforms import (
    TransformChain,
    TransformError,
    TransformModel,
    compose_stages,
    euler_xyz_degrees_to_quaternion,
    world_points,
    world_pose_for,
)

if _native_dataclass is not None:
    _dataclasses.dataclass = _native_dataclass

# NOTE: bpy_extraction is intentionally NOT imported at package load — it imports ``bpy`` lazily
# from within a Blender process only, so deterministic (non-Blender) import of ``planning.blender``
# never triggers a Blender availability error.

__all__ = [
    "ACCEPTED_AUTHORIZATION_POLICY_VERSIONS",
    "AUTHORIZATION_VERSION",
    "WINDING_CORRECTION_TYPE",
    "AuthorizationArtifact",
    "AuthorizationContractError",
    "AuthorizationError",
    "AuthorizationFailureCode",
    "AuthorizationInputError",
    "AuthorizationOutcome",
    "AuthorizationVerdict",
    "PresentedWork",
    "parse_authorization",
    "resolve_designated_face_index",
    "validate_recorded_edges",
    "verify_authorization",
    "verify_recorded_set_agreement",
    "DEFAULT_READY_BLOCKING_CODES",
    "FindingCode",
    "FindingSeverity",
    "Finding",
    "MeshModel",
    "ObjectModel",
    "REPORT_FORMAT_VERSION",
    "SceneMembershipError",
    "SceneModel",
    "SceneReport",
    "SceneReportInputError",
    "SoccerFieldValidationProfile",
    "UnitMappingError",
    "VALIDATOR_VERSION",
    "check_mesh",
    "check_mesh_in_envelope",
    "check_scene",
    "compute_input_digest",
    "EXECUTOR_VERSION",
    "ExecutionOutcome",
    "execute_remove_duplicate_face",
    "execute_remove_degenerate_face",
    "evaluate_readiness",
    "is_meters_like",
    "map_unit_system",
    "parse_scene_report_input",
    "run_scene_health",
    "scene_input_digest",
    "severity_of",
    "soccer_field_profile",
    "compose_stages",
    "euler_xyz_degrees_to_quaternion",
    "TransformChain",
    "TransformError",
    "TransformModel",
    "world_points",
    "world_pose_for",
    "execute_repair_face_winding",
    "WindingPredicateError",
    "WindingPostconditionError",
]