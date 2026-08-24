"""Final pre-live gate for one authorized Blender write."""
from typing import Any, Mapping

from action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_write_authorization import BlenderWriteAuthorization


class BlenderLiveWriteGate:
    """Execute exactly one authorization-bound Blender write."""

    def __init__(self, boundary: BlenderExecutionBoundary) -> None:
        self._boundary = boundary

    def execute(
        self,
        action: ActionSpec,
        authorization: BlenderWriteAuthorization,
    ) -> BlenderExecutionReceipt:
        if not authorization.matches(action):
            raise ValueError("Blender write authorization does not match action")
        receipt = self._boundary.execute_authorized_write(action, authorization)
        if not receipt.matches_authorization(authorization.authorization_id):
            raise RuntimeError("Blender write receipt is not bound to authorization")
        return receipt
