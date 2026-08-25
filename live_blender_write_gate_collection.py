"""Direct live probe for the collection-membership write gate."""
import argparse
import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Tuple

from planning.action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_write_authorization import BlenderWriteAuthorization
from planning.collection_membership_task import TARGET_COLLECTION, TARGET_OBJECT
from tools.blender_collection import inspect_object_collections, move_object_to_collection

FILE_BY_CASE = {
    "incorrect": "collection_membership_INCORRECT.blend",
    "correct": "collection_membership_CORRECT.blend",
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
        tool="move_object_to_collection",
        arguments={
            "file_name": file_name,
            "object_name": TARGET_OBJECT,
            "collection_name": TARGET_COLLECTION,
        },
    )


def _execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool != "move_object_to_collection":
        raise RuntimeError("live probe only permits move_object_to_collection")
    raw = move_object_to_collection(**arguments)
    status = raw.get("status")
    return {
        "ok": status in {"moved", "already_member"},
        "state": str(status or "unknown"),
        "details": dict(raw),
    }


def _verify(action: ActionSpec, receipt: Any) -> Tuple[bool, Dict[str, Any]]:
    observed = inspect_object_collections(
        file_name=action.arguments["file_name"],
        object_name=action.arguments["object_name"],
    )
    satisfied = (
        observed.get("object_name") == TARGET_OBJECT
        and observed.get("exists") is True
        and observed.get("collections") == [TARGET_COLLECTION]
    )
    return satisfied, {"authoritative": observed, "collection_membership_verified": satisfied}


def _mismatch_verifier(action: ActionSpec, receipt: Any) -> Tuple[bool, Dict[str, Any]]:
    observed = inspect_object_collections(
        file_name=action.arguments["file_name"],
        object_name=action.arguments["object_name"],
    )
    wrong_expectation = observed.get("collections") != [TARGET_COLLECTION]
    return wrong_expectation, {
        "authoritative": observed,
        "expected_by_adversarial_verifier": [TARGET_COLLECTION],
        "collection_membership_verified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=tuple(FILE_BY_CASE), default="incorrect")
    parser.add_argument("--adversarial", action="store_true")
    args = parser.parse_args()

    file_name = FILE_BY_CASE[args.case]
    action = _action(file_name)
    authorization = BlenderWriteAuthorization.issue(action, f"live-probe:collection:{args.case}")
    boundary = BlenderExecutionBoundary(_execute)
    verifier = _mismatch_verifier if args.adversarial else _verify
    gate = BlenderLiveWriteGate(boundary, verifier=verifier)
    outcome = gate.execute(action, authorization)

    print("ATLAS BLENDER LIVE COLLECTION WRITE GATE PROBE")
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
            raise SystemExit("ADVERSARIAL COLLECTION PROBE FAILED: false success escaped the gate")
        print("ATLAS BLENDER LIVE COLLECTION ADVERSARIAL GATE: PASS")
    else:
        if outcome.status != "VERIFIED" or outcome.receipt is None:
            raise SystemExit("LIVE COLLECTION PROBE FAILED: authoritative verification did not confirm the write")
        print("ATLAS BLENDER LIVE COLLECTION VERIFIED: PASS")


if __name__ == "__main__":
    main()
