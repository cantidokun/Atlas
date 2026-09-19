"""Controlled production bridge from the canonical correction executor to one Blender session.

This module is deliberately narrower than the generic Blender execution stack. It:
- accepts only the four already-live-validated correction operations;
- serializes the existing CorrectionPlan/authorization values;
- starts one disposable Blender process in no-save mode;
- delegates all correction authority to correction_executor inside that process;
- returns typed transport evidence plus the canonical correction receipt.

It does not add planning, authorization, persistence, retry, rollback, or generic Blender tools.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from planning.blender.correction_authorization import (
    AuthorizationOutcome,
    MergePresentedWork,
    PresentedWork,
    parse_authorization,
    resolve_designated_face_index,
    verify_authorization,
    verify_merge_authorization,
)
from planning.blender.correction_contract import CorrectionPlan
from planning.blender.correction_executor import EXECUTOR_VERSION, _EXECUTABLE_TYPES
from planning.blender.correction_values import thaw_jsonable


BRIDGE_VERSION = "1"
START_MARKER = "ATLAS_CORRECTION_BRIDGE_START"
END_MARKER = "ATLAS_CORRECTION_BRIDGE_END"

_EXPECTED_OPERATIONS = frozenset(
    {
        "REMOVE_DUPLICATE_FACE",
        "REMOVE_DEGENERATE_FACE",
        "REPAIR_FACE_WINDING",
        "REPAIR_MERGE_VERTEX",
    }
)


class CorrectionExecutionBridgeError(RuntimeError):
    """Declared correction-bridge transport failure."""


class CorrectionExecutionBridgeValidationError(CorrectionExecutionBridgeError):
    """The bridge request is malformed or violates the closed bridge contract."""


@dataclass(frozen=True)
class CorrectionBridgeRequest:
    operation: str
    plan_id: str
    correction_id: str
    source_report_digest: str
    object_id: Optional[str]
    mesh_id: Optional[str]
    parameters: Mapping[str, Any]
    expected_postcondition_ref: str
    expected_postcondition_digest: str
    plan: Mapping[str, Any]
    authorization: Optional[Mapping[str, Any]]
    source_blend_path: Optional[str] = None
    bridge_version: str = BRIDGE_VERSION
    correction_executor_version: str = EXECUTOR_VERSION
    source_scene_id: Optional[str] = None

    def to_json_compatible(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "plan_id": self.plan_id,
            "correction_id": self.correction_id,
            "source_report_digest": self.source_report_digest,
            "object_id": self.object_id,
            "mesh_id": self.mesh_id,
            "parameters": dict(self.parameters),
            "expected_postcondition_ref": self.expected_postcondition_ref,
            "expected_postcondition_digest": self.expected_postcondition_digest,
            "plan": dict(self.plan),
            "authorization": None if self.authorization is None else dict(self.authorization),
            "source_blend_path": self.source_blend_path,
            "bridge_version": self.bridge_version,
            "correction_executor_version": self.correction_executor_version,
            "source_scene_id": self.source_scene_id,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_json_compatible(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CorrectionBridgeResult:
    transport_ok: bool
    transport_failure_code: Optional[str]
    request_digest: str
    operation: Optional[str]
    correction_id: Optional[str]
    correction_result: Optional[Mapping[str, Any]]
    engine_evidence: Mapping[str, Any]
    stdout_tail: str = ""

    def to_json(self) -> str:
        return json.dumps(
            {
                "transport_ok": self.transport_ok,
                "transport_failure_code": self.transport_failure_code,
                "request_digest": self.request_digest,
                "operation": self.operation,
                "correction_id": self.correction_id,
                "correction_result": self.correction_result,
                "engine_evidence": dict(self.engine_evidence),
                "stdout_tail": self.stdout_tail,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )


def _canonical_postcondition_binding(plan: CorrectionPlan, operation: str) -> tuple[str, str]:
    """Derive transport binding metadata from the existing canonical correction contract."""
    matching = [c for c in plan.corrections if c.correction_type == operation]
    if len(matching) != 1:
        raise CorrectionExecutionBridgeValidationError(
            "the bridge requires exactly one correction of the selected operation"
        )
    correction = matching[0]
    reference = f"correction_executor:{EXECUTOR_VERSION}:{operation}"
    body = {
        "reference": reference,
        "correction_type": correction.correction_type,
        "expected_postcondition": thaw_jsonable(correction.expected_postcondition),
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode(
            "utf-8"
        )
    ).hexdigest()
    return reference, digest


def _validate_closed_operation(operation: str) -> None:
    if type(operation) is not str or not operation:
        raise CorrectionExecutionBridgeValidationError("operation must be a non-empty string")
    if set(_EXECUTABLE_TYPES) != _EXPECTED_OPERATIONS:
        raise CorrectionExecutionBridgeValidationError(
            "executor executable-type allowlist drifted from the four explicitly bridge-authorized operations"
        )
    if operation not in _EXPECTED_OPERATIONS:
        raise CorrectionExecutionBridgeValidationError(
            f"correction operation {operation!r} is not bridge-authorized"
        )


def _find_single_correction(plan: CorrectionPlan, operation: str):
    matches = [c for c in plan.corrections if c.correction_type == operation]
    if len(matches) != 1:
        raise CorrectionExecutionBridgeValidationError(
            f"expected exactly one executable correction of type {operation!r}; found {len(matches)}"
        )
    return matches[0]


def _preflight_review_authorization(
    plan: CorrectionPlan, operation: str, authorization: Optional[Mapping[str, Any]]
) -> None:
    """Run the existing authorization contract before any Blender file/scene contact."""
    correction = _find_single_correction(plan, operation)
    if operation in {"REMOVE_DUPLICATE_FACE", "REMOVE_DEGENERATE_FACE"}:
        if authorization is not None:
            raise CorrectionExecutionBridgeValidationError(
                "W1/W1b bridge calls must not introduce an authorization artifact"
            )
        return

    if authorization is None:
        raise CorrectionExecutionBridgeValidationError(
            f"{operation} requires its existing correction authorization artifact"
        )

    artifact = parse_authorization(dict(authorization))

    if operation == "REPAIR_FACE_WINDING":
        params = thaw_jsonable(correction.parameters)
        designated = params.get("designated_face_index")
        candidate_faces = params.get("candidate_faces")
        selection_mode = "D1" if designated is not None else "D2"
        work = PresentedWork(
            correction_type=correction.correction_type,
            correction_id=correction.correction_id,
            plan_id=plan.plan_id,
            source_report_digest=plan.source_report_digest,
            selection_mode=selection_mode,
            plan_designated_face_index=designated,
            candidate_pair=(tuple(candidate_faces) if candidate_faces is not None else None),
            execution_face_tuple=None,
        )
        verdict = verify_authorization(artifact, work)
        if not verdict.ok and verdict.failure_code != "EXECUTION_FACE_TUPLE_UNAVAILABLE":
            raise CorrectionExecutionBridgeValidationError(
                f"authorization rejected before Blender contact: {verdict.failure_code}"
            )
        designation, designation_failure = resolve_designated_face_index(artifact, work)
        if designation_failure is not None:
            raise CorrectionExecutionBridgeValidationError(
                f"authorization designation rejected before Blender contact: {designation_failure.failure_code}"
            )
        if designation is None:
            raise CorrectionExecutionBridgeValidationError(
                "authorization did not resolve an execution face"
            )
        return

    params = thaw_jsonable(correction.parameters)
    work = MergePresentedWork(
        correction_type=correction.correction_type,
        correction_id=correction.correction_id,
        plan_id=plan.plan_id,
        source_report_digest=plan.source_report_digest,
        target_object_mesh=(correction.object_id or "", correction.mesh_id or ""),
        duplicate_groups=tuple(tuple(group) for group in params["duplicate_groups"]),
        plan_target_object_mesh=(correction.object_id or "", params["mesh_id"]),
        mapping_digest=params["mapping_digest"],
        all_groups_exact=params["all_groups_exact"],
    )
    verdict = verify_merge_authorization(artifact, work)
    if not verdict.ok:
        raise CorrectionExecutionBridgeValidationError(
            f"authorization rejected before Blender contact: {verdict.failure_code}"
        )


def make_bridge_request(
    plan: CorrectionPlan,
    *,
    operation: Optional[str] = None,
    authorization: Optional[Mapping[str, Any]] = None,
    source_blend_path: Optional[str] = None,
) -> CorrectionBridgeRequest:
    """Build the closed language-neutral bridge envelope from a canonical CorrectionPlan."""
    if type(plan) is not CorrectionPlan:
        raise CorrectionExecutionBridgeValidationError("plan must be an exact CorrectionPlan")
    if plan.plan_id != plan._compute_plan_id():
        raise CorrectionExecutionBridgeValidationError("plan_id is not self-consistent")

    executable_types = [c.correction_type for c in plan.corrections if c.correction_type in _EXPECTED_OPERATIONS]
    chosen = operation or (executable_types[0] if len(executable_types) == 1 else None)
    if chosen is None:
        raise CorrectionExecutionBridgeValidationError(
            "operation must be explicit when the plan contains zero or multiple bridge operations"
        )

    _validate_closed_operation(chosen)
    correction = _find_single_correction(plan, chosen)
    reference, digest = _canonical_postcondition_binding(plan, chosen)
    _preflight_review_authorization(plan, chosen, authorization)

    if source_blend_path is not None:
        if type(source_blend_path) is not str or not source_blend_path:
            raise CorrectionExecutionBridgeValidationError("source_blend_path must be a non-empty string")
        if not os.path.isfile(source_blend_path):
            raise CorrectionExecutionBridgeValidationError(
                f"source_blend_path does not exist: {source_blend_path}"
            )

    return CorrectionBridgeRequest(
        operation=chosen,
        plan_id=plan.plan_id,
        correction_id=correction.correction_id,
        source_report_digest=plan.source_report_digest,
        object_id=correction.object_id,
        mesh_id=correction.mesh_id,
        parameters=thaw_jsonable(correction.parameters),
        expected_postcondition_ref=reference,
        expected_postcondition_digest=digest,
        plan=plan.to_json_compatible(),
        authorization=None if authorization is None else dict(authorization),
        source_blend_path=source_blend_path,
    )


class CorrectionExecutionBridge:
    """One correction invocation per disposable Blender process/session."""

    def __init__(self, *, blender_command: str, timeout: int = 120):
        if type(blender_command) is not str or not blender_command.strip():
            raise ValueError("blender_command must be a non-empty string")
        if type(timeout) is not int or timeout <= 0:
            raise ValueError("timeout must be a positive integer")
        self._blender_command = blender_command
        self._timeout = timeout

    def execute(
        self,
        plan: CorrectionPlan,
        *,
        operation: Optional[str] = None,
        authorization: Optional[Mapping[str, Any]] = None,
        source_blend_path: Optional[str] = None,
    ) -> CorrectionBridgeResult:
        request = make_bridge_request(
            plan,
            operation=operation,
            authorization=authorization,
            source_blend_path=source_blend_path,
        )
        encoded = base64.b64encode(request.canonical_json().encode("utf-8")).decode("ascii")
        expression = (
            "import base64; "
            "from planning.blender.correction_execution_bridge_runtime import run_embedded_request; "
            f"run_embedded_request(base64.b64decode('{encoded}').decode('utf-8'))"
        )
        command = [
            self._blender_command,
            "--background",
            "--factory-startup",
            "--python-expr",
            expression,
        ]
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return CorrectionBridgeResult(
                transport_ok=False,
                transport_failure_code="BLENDER_PROCESS_TIMEOUT",
                request_digest=request.digest(),
                operation=request.operation,
                correction_id=request.correction_id,
                correction_result=None,
                engine_evidence={"process_disposed": True},
                stdout_tail=str(exc),
            )
        except OSError as exc:
            return CorrectionBridgeResult(
                transport_ok=False,
                transport_failure_code="BLENDER_PROCESS_START_FAILED",
                request_digest=request.digest(),
                operation=request.operation,
                correction_id=request.correction_id,
                correction_result=None,
                engine_evidence={"process_disposed": True},
                stdout_tail=str(exc),
            )

        stdout = proc.stdout or ""
        if proc.returncode != 0:
            return CorrectionBridgeResult(
                transport_ok=False,
                transport_failure_code="BLENDER_PROCESS_FAILED",
                request_digest=request.digest(),
                operation=request.operation,
                correction_id=request.correction_id,
                correction_result=None,
                engine_evidence={"process_disposed": True},
                stdout_tail=(proc.stderr or stdout)[-4000:],
            )

        start = stdout.find(START_MARKER)
        end = stdout.find(END_MARKER, start + len(START_MARKER))
        if start < 0 or end < 0:
            return CorrectionBridgeResult(
                transport_ok=False,
                transport_failure_code="RESULT_MARKERS_MISSING",
                request_digest=request.digest(),
                operation=request.operation,
                correction_id=request.correction_id,
                correction_result=None,
                engine_evidence={"process_disposed": True, "ambiguous_result": True},
                stdout_tail=stdout[-4000:],
            )

        payload = stdout[start + len(START_MARKER) : end].strip()
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            return CorrectionBridgeResult(
                transport_ok=False,
                transport_failure_code="RESULT_JSON_INVALID",
                request_digest=request.digest(),
                operation=request.operation,
                correction_id=request.correction_id,
                correction_result=None,
                engine_evidence={"process_disposed": True, "ambiguous_result": True},
                stdout_tail=f"{exc}: {stdout[-4000:]}",
            )

        if type(decoded) is not dict:
            return CorrectionBridgeResult(
                transport_ok=False,
                transport_failure_code="RESULT_NOT_OBJECT",
                request_digest=request.digest(),
                operation=request.operation,
                correction_id=request.correction_id,
                correction_result=None,
                engine_evidence={"process_disposed": True, "ambiguous_result": True},
                stdout_tail=stdout[-4000:],
            )

        if decoded.get("request_digest") != request.digest():
            return CorrectionBridgeResult(
                transport_ok=False,
                transport_failure_code="REQUEST_DIGEST_MISMATCH",
                request_digest=request.digest(),
                operation=request.operation,
                correction_id=request.correction_id,
                correction_result=None,
                engine_evidence={"process_disposed": True, "ambiguous_result": True},
                stdout_tail=stdout[-4000:],
            )

        return CorrectionBridgeResult(
            transport_ok=True,
            transport_failure_code=None,
            request_digest=request.digest(),
            operation=request.operation,
            correction_id=request.correction_id,
            correction_result=decoded.get("correction_result"),
            engine_evidence=decoded.get("engine_evidence", {}),
            stdout_tail=stdout[-4000:],
        )
