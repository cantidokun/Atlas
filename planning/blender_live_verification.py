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
    """Verify final authoritative state independently of executor success.

    A successful verification must contain every requested action argument in
    the authoritative state. Missing fields are not treated as "not checked";
    they are insufficient evidence and therefore fail closed.
    """
    if not isinstance(action, ActionSpec):
        raise TypeError("action must be an ActionSpec")
    if not isinstance(receipt, BlenderExecutionReceipt):
        raise TypeError("receipt must be a BlenderExecutionReceipt")
    state = dict(verifier(action))
    if state.get("ok") is not True:
        return False, state
    authoritative = state.get("state")
    if not isinstance(authoritative, Mapping):
        return False, state
    expected = dict(action.arguments)
    missing = [key for key in expected if key not in authoritative]
    if missing:
        state["verification_error"] = "missing_authoritative_fields"
        state["missing_fields"] = missing
        return False, state
    for key, value in expected.items():
        if authoritative[key] != value:
            return False, state
    return True, state
