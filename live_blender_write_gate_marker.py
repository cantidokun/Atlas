"""Direct live probe for the authorization-bound Blender marker write gate."""
import argparse
import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Tuple

from planning.action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_write_authorization import BlenderWriteAuthorization
from planning.marker_task import MARKER_COLLECTION, MARKER_OBJECT
from tools.blender import create_empty_marker, inspect_scene
from tools.blender_collection import inspect_object_collections

FILE_BY_CASE = {
    "incorrect": "marker_task_INCORRECT.blend",
    "already-correct": "marker_task_CORRECT.blend",
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
        tool="create_empty_marker",
        arguments={
            "file_name": file_name,
            "collection_name": MARKER_COLLECTION,
            "object_name": MARKER_OBJECT,
        },
        name="create Atlas_Marker",
    )


def _execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool != "create_empty_marker":
        raise RuntimeError("live probe only permits create_empty_marker")
    raw = create_empty_marker(**arguments)
    status = raw.get("status")
    return {
        "ok": status in {"created", "already_exists"},
        "state": str(status or "unknown"),
        "details": dict(raw),
    }


def _authoritative_state(file_name: str) -> Dict[str, Any]:
    scene = inspect_scene(file_name)
    membership = inspect_object_collections(
        file_name=file_name,
        object_name=MARKER_OBJECT,
    )
    objects = scene.get("objects", [])
    marker = next((obj for obj in objects if obj.get("name") == MARKER_OBJECT), None)
    return {
        "scene": scene,
        "membership": membership,
        "marker": marker,
        "marker_exists": marker is not None,
        "marker_type_empty": isinstance(marker, dict) and marker.get("type") == "EMPTY",
        "marker_in_atlas_collection": (
            MARKER_COLLECTION in membership.get("collections", [])
        ),
    }


def _verifier(action: ActionSpec, receipt: Any) -> Tuple[bool, Dict[str, Any]]:
    state = _authoritative_state(action.arguments["file_name"])
    satisfied = all(
        (
            state["marker_exists"],
            state["marker_type_empty"],
            state["marker_in_atlas_collection"],
        )
    )
    return satisfied, state


def _mismatch_verifier(action: ActionSpec, receipt: Any) -> Tuple[bool, Dict[str, Any]]:
    state = _authoritative_state(action.arguments["file_name"])
    return False, {
        **state,
        "expected_by_adversarial_verifier": "marker_absent",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=tuple(FILE_BY_CASE), default="incorrect")
    parser.add_argument("--adversarial", action="store_true")
    args = parser.parse_args()

    file_name = FILE_BY_CASE[args.case]
    action = _action(file_name)
    authorization = BlenderWriteAuthorization.issue(
        action, f"live-probe:marker:{args.case}"
    )
    boundary = BlenderExecutionBoundary(_execute)
    verifier = _mismatch_verifier if args.adversarial else _verifier
    gate = BlenderLiveWriteGate(boundary, verifier=verifier)
    outcome = gate.execute(action, authorization)

    print("ATLAS BLENDER LIVE MARKER WRITE GATE PROBE")
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
            raise SystemExit("ADVERSARIAL MARKER PROBE FAILED: false success escaped the gate")
        print("ATLAS BLENDER LIVE MARKER ADVERSARIAL GATE: PASS")
    else:
        if outcome.status != "VERIFIED" or outcome.receipt is None:
            raise SystemExit("LIVE MARKER PROBE FAILED: authoritative verification did not confirm the write")
        print("ATLAS BLENDER LIVE MARKER VERIFIED: PASS")


if __name__ == "__main__":
    main()
