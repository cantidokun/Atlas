"""Direct live probe for the authorization-bound Blender delete write gate."""
import argparse
import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Tuple

from planning.action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_write_authorization import BlenderWriteAuthorization
from planning.object_delete_task import TARGET_OBJECT
from tools.blender_delete import delete_object
from tools.blender_transform import inspect_object_transform

FILE_BY_CASE = {
    "incorrect": "object_delete_INCORRECT.blend",
    "correct": "object_delete_CORRECT.blend",
}


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _action(file_name: str) -> ActionSpec:
    return ActionSpec(
        tool="delete_object",
        arguments={"file_name": file_name, "object_name": TARGET_OBJECT},
    )


def _execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool != "delete_object":
        raise RuntimeError("live probe only permits delete_object")
    raw = delete_object(**arguments)
    status = raw.get("status")
    return {
        "ok": status in {"ok", "already_absent"},
        "state": str(status or "unknown"),
        "details": dict(raw),
    }


def _verifier(action: ActionSpec, receipt: Any) -> Tuple[bool, Dict[str, Any]]:
    observed = inspect_object_transform(
        file_name=action.arguments["file_name"],
        object_name=action.arguments["object_name"],
    )
    deleted = observed.get("status") == "object_not_found"
    return deleted, {"authoritative": observed, "object_deleted": deleted}


def _mismatch_verifier(action: ActionSpec, receipt: Any) -> Tuple[bool, Dict[str, Any]]:
    observed = inspect_object_transform(
        file_name=action.arguments["file_name"],
        object_name=action.arguments["object_name"],
    )
    wrong_expectation = observed.get("status") == "ok"
    return wrong_expectation, {
        "authoritative": observed,
        "expected_by_adversarial_verifier": "object_not_found",
        "object_deleted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=tuple(FILE_BY_CASE), default="incorrect")
    parser.add_argument("--adversarial", action="store_true")
    args = parser.parse_args()

    file_name = FILE_BY_CASE[args.case]
    action = _action(file_name)
    authorization = BlenderWriteAuthorization.issue(action, f"live-probe:delete:{args.case}")
    boundary = BlenderExecutionBoundary(_execute)
    verifier = _mismatch_verifier if args.adversarial else _verifier
    gate = BlenderLiveWriteGate(boundary, verifier=verifier)
    outcome = gate.execute(action, authorization)

    print("ATLAS BLENDER LIVE DELETE WRITE GATE PROBE")
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
            raise SystemExit("ADVERSARIAL DELETE PROBE FAILED: false success escaped the gate")
        print("ATLAS BLENDER LIVE DELETE ADVERSARIAL GATE: PASS")
    else:
        if outcome.status != "VERIFIED" or outcome.receipt is None:
            raise SystemExit("LIVE DELETE PROBE FAILED: authoritative verification did not confirm the write")
        print("ATLAS BLENDER LIVE DELETE VERIFIED: PASS")


if __name__ == "__main__":
    main()
