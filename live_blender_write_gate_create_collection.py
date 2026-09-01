"""Direct live probe for the generalized create-collection write gate."""
import argparse
import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Tuple

from planning.action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_write_authorization import BlenderWriteAuthorization
from tools.blender import create_collection, inspect_scene_settings

FILE_BY_CASE = {
    "incorrect": "create_collection_INCORRECT.blend",
    "correct": "create_collection_CORRECT.blend",
}
TARGET_COLLECTION = "Atlas_Test"


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
        tool="create_collection",
        arguments={"file_name": file_name, "collection_name": TARGET_COLLECTION},
    )


def _execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool != "create_collection":
        raise RuntimeError("live probe only permits create_collection")
    raw = create_collection(**arguments)
    status = raw.get("status")
    return {
        "ok": status in {"created", "already_exists"},
        "state": str(status or "unknown"),
        "details": dict(raw),
    }


def _observe(file_name: str) -> Dict[str, Any]:
    return inspect_scene_settings(file_name=file_name)


def _verify(action: ActionSpec, receipt: Any) -> Tuple[bool, Dict[str, Any]]:
    observed = _observe(action.arguments["file_name"])
    collections = observed.get("collections", [])
    satisfied = TARGET_COLLECTION in collections
    return satisfied, {
        "authoritative": observed,
        "collection_created_or_preserved": satisfied,
    }


def _mismatch_verifier(action: ActionSpec, receipt: Any) -> Tuple[bool, Dict[str, Any]]:
    observed = _observe(action.arguments["file_name"])
    return False, {
        "authoritative": observed,
        "expected_by_adversarial_verifier": "collection_absent",
        "collection_created_or_preserved": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=tuple(FILE_BY_CASE), default="incorrect")
    parser.add_argument("--adversarial", action="store_true")
    args = parser.parse_args()

    file_name = FILE_BY_CASE[args.case]
    action = _action(file_name)
    authorization = BlenderWriteAuthorization.issue(action, f"live-probe:create-collection:{args.case}")
    boundary = BlenderExecutionBoundary(_execute)
    verifier = _mismatch_verifier if args.adversarial else _verify
    gate = BlenderLiveWriteGate(boundary, verifier=verifier)
    outcome = gate.execute(action, authorization)

    print("ATLAS BLENDER LIVE CREATE COLLECTION WRITE GATE PROBE")
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
            raise SystemExit("ADVERSARIAL CREATE COLLECTION PROBE FAILED: false success escaped the gate")
        print("ATLAS BLENDER LIVE CREATE COLLECTION ADVERSARIAL GATE: PASS")
    else:
        if outcome.status != "VERIFIED" or outcome.receipt is None:
            raise SystemExit("LIVE CREATE COLLECTION PROBE FAILED: authoritative verification did not confirm the write")
        print("ATLAS BLENDER LIVE CREATE COLLECTION VERIFIED: PASS")


if __name__ == "__main__":
    main()
