"""Authoritative post-write verification for the controlled Blender live gate."""
from typing import Any, Callable, Dict, Mapping, Tuple

from planning.action_plan import ActionSpec
from planning.blender_execution_receipt import BlenderExecutionReceipt


Verification = Callable[[ActionSpec], Mapping[str, Any]]


def verify_authoritative_write(
    action: ActionSpec,
    receipt: BlenderExecutionReceipt,
    verifier: Verification,
) -> Tuple[bool, Dict[str, Any]]:
    """Verify final authoritative state independently of executor success."""
    if not isinstance(action, ActionSpec):
        raise TypeError("action must be an ActionSpec")
    if not isinstance(receipt, BlenderExecutionReceipt):
        raise TypeError("receipt must be a BlenderExecutionReceipt")
    state = dict(verifier(action))
    if state.get("ok") is not True:
        return False, state
    expected = dict(action.arguments)
    if "state" in state and isinstance(state["state"], Mapping):
        for key, value in expected.items():
            if key in state["state"] and state["state"][key] != value:
                return False, state
    return True, state
