"""Direct live probe for the authorization-bound Blender rotation write gate."""
import argparse
import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Tuple

from planning.action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_write_authorization import BlenderWriteAuthorization
from planning.object_rotation_task import TARGET_OBJECT, TARGET_ROTATION
from tools.blender_transform import inspect_object_transform, set_object_rotation


FILE_BY_CASE = {
    "incorrect": "object_rotation_INCORRECT.blend",
    "correct": "object_rotation_CORRECT.blend",
}


def _json_safe(value: Any) -> Any:
    """Convert structured runtime results into JSON-safe probe output."""
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _action(file_name: str) -> ActionSpec:
    return ActionSpec(
        tool="set_object_rotation",
        arguments={
            "file_name": file_name,
            "object_name": TARGET_OBJECT,
            "rotation_degrees": list(TARGET_ROTATION),
        },
    )


def _execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool != "set_object_rotation":
        raise RuntimeError("live probe only permits set_object_rotation")
    raw = set_object_rotation(**arguments)
    status = raw.get("status")
    return {
        "ok": status in {"ok", "already_rotated"},
        "state": str(status or "unknown"),
        "details": dict(raw),
    }


def _verifier(action: ActionSpec, receipt: Any) -> Tuple[bool, Dict[str, Any]]:
    observed = inspect_object_transform(
        file_name=action.arguments["file_name"],
        object_name=action.arguments["object_name"],
    )
    target = [float(value) for value in action.arguments["rotation_degrees"]]
    actual = observed.get("rotation_degrees")
    if observed.get("status") != "ok" or not isinstance(actual, list) or len(actual) != 3:
        return False, {"authoritative": observed}
    matches = all(abs(float(actual[i]) - target[i]) <= 1e-5 for i in range(3))
    return matches, {"authoritative": observed, "rotation_matches": matches}


def _mismatch_verifier(action: ActionSpec, receipt: Any) -> Tuple[bool, Dict[str, Any]]:
    """Read actual Blender state but deliberately require a different target.

    This is an adversarial verification probe: the executor can report success,
    while authoritative verification rejects the requested write without issuing
    another scene mutation.
    """
    observed = inspect_object_transform(
        file_name=action.arguments["file_name"],
        object_name=action.arguments["object_name"],
    )
    wrong_target = [999.0, 999.0, 999.0]
    actual = observed.get("rotation_degrees")
    matches = (
        observed.get("status") == "ok"
        and isinstance(actual, list)
        and len(actual) == 3
        and all(abs(float(actual[i]) - wrong_target[i]) <= 1e-5 for i in range(3))
    )
    return matches, {
        "authoritative": observed,
        "expected_by_adversarial_verifier": wrong_target,
        "rotation_matches": matches,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=tuple(FILE_BY_CASE), default="incorrect")
    parser.add_argument("--adversarial", action="store_true")
    args = parser.parse_args()

    file_name = FILE_BY_CASE[args.case]
    action = _action(file_name)
    authorization = BlenderWriteAuthorization.issue(action, f"live-probe:rotation:{args.case}")
    boundary = BlenderExecutionBoundary(_execute)
    verifier = _mismatch_verifier if args.adversarial else _verifier
    gate = BlenderLiveWriteGate(boundary, verifier=verifier)

    outcome = gate.execute(action, authorization)
    print("ATLAS BLENDER LIVE WRITE GATE PROBE")
    print(json.dumps({
        "case": args.case,
        "adversarial": args.adversarial,
        "status": outcome.status,
        "reason": outcome.reason,
        "verification": _json_safe(outcome.verification),
        "receipt_present": outcome.receipt is not None,
    }, indent=2))

    if args.adversarial:
        if outcome.status != "BLOCKED" or outcome.receipt is not None:
            raise SystemExit("ADVERSARIAL PROBE FAILED: false success escaped the gate")
        print("ATLAS BLENDER LIVE WRITE ADVERSARIAL GATE: PASS")
    else:
        if outcome.status != "VERIFIED" or outcome.receipt is None:
            raise SystemExit("LIVE WRITE PROBE FAILED: authoritative verification did not confirm the write")
        print("ATLAS BLENDER LIVE WRITE VERIFIED: PASS")


if __name__ == "__main__":
    main()
