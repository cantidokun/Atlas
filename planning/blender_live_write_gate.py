"""Final pre-live gate for one authorized Blender write."""
from planning.action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_live_write_result import BlenderLiveWriteOutcome
from planning.blender_write_authorization import BlenderWriteAuthorization


class BlenderLiveWriteGate:
    """Execute exactly one authorization-bound Blender write."""

    def __init__(self, boundary: BlenderExecutionBoundary) -> None:
        self._boundary = boundary

    def execute(
        self,
        action: ActionSpec,
        authorization: BlenderWriteAuthorization,
    ) -> BlenderLiveWriteOutcome:
        if not authorization.matches(action):
            raise ValueError("Blender write authorization does not match action")
        result, receipt = self._boundary.execute_authorized_write(action, authorization)
        if not receipt.matches_authorization(authorization.authorization_id):
            return BlenderLiveWriteOutcome.blocked(
                {"receipt_authorized": False},
                "Blender write receipt is not bound to authorization",
            )
        return BlenderLiveWriteOutcome.verified(
            receipt,
            {"receipt_authorized": True, "result": result},
        )
