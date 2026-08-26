"""Final pre-live gate for one authorized Blender write."""
from typing import Any, Callable, Mapping, Optional, Tuple

from planning.action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_live_write_result import BlenderLiveWriteOutcome
from planning.blender_write_authorization import BlenderWriteAuthorization


AuthoritativeVerifier = Callable[[ActionSpec, Any], Tuple[bool, Mapping[str, Any]]]


class BlenderLiveWriteGate:
    """Execute one authorization-bound Blender write and verify authoritative state."""

    def __init__(self, boundary: BlenderExecutionBoundary, verifier: Optional[AuthoritativeVerifier] = None) -> None:
        self._boundary = boundary
        self._verifier = verifier

    def execute(self, action: ActionSpec, authorization: BlenderWriteAuthorization) -> BlenderLiveWriteOutcome:
        if not authorization.matches(action):
            raise ValueError("Blender write authorization does not match action")
        result, receipt = self._boundary.execute_authorized_write(action, authorization)
        if not receipt.matches_authorization(authorization.authorization_id):
            return BlenderLiveWriteOutcome.blocked({"receipt_authorized": False}, "Blender write receipt is not bound to authorization")
        if not receipt.matches(action.tool, action.arguments, result):
            return BlenderLiveWriteOutcome.blocked(
                {"receipt_authorized": True, "receipt_matches_execution": False},
                "Blender write receipt does not bind the requested action and execution result",
            )
        if not result.ok:
            return BlenderLiveWriteOutcome.blocked(
                {"receipt_authorized": True, "receipt_matches_execution": True, "result": result},
                "Blender executor did not establish a successful write",
            )
        if self._verifier is None:
            return BlenderLiveWriteOutcome.blocked({"receipt_authorized": True, "receipt_matches_execution": True, "result": result}, "No authoritative Blender verifier is configured")
        try:
            verified, verification = self._verifier(action, receipt)
            if not isinstance(verified, bool):
                raise TypeError("authoritative verifier must return a bool verification result")
            if not isinstance(verification, Mapping):
                raise TypeError("authoritative verifier must return a mapping of verification details")
            verification = dict(verification)
        except Exception as exc:
            return BlenderLiveWriteOutcome.blocked(
                {"receipt_authorized": True, "receipt_matches_execution": True, "result": result, "verification_error": type(exc).__name__},
                "Authoritative Blender verification failed closed",
            )
        if not verified:
            return BlenderLiveWriteOutcome.blocked(
                {"receipt_authorized": True, "receipt_matches_execution": True, "result": result, **verification},
                "Authoritative Blender state did not verify the requested write",
            )
        return BlenderLiveWriteOutcome.verified(receipt, {"receipt_authorized": True, "receipt_matches_execution": True, "result": result, **verification})
