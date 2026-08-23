"""Live Blender gate for multi-step corrective recovery with an injected world change."""
from __future__ import annotations

import argparse
import json
from typing import Any

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.multi_step_corrective_executor import MultiStepCorrectiveExecutor
from tools.blender import inspect_scene, create_empty_marker
from tools.blender_delete import delete_object

FILE_NAME = "marker_task_INCORRECT.blend"
MARKER_COLLECTION = "Atlas_Test"
MARKER_OBJECT = "Atlas_Marker"


def observe() -> dict[str, Any]:
    scene = inspect_scene(FILE_NAME)
    names = {item["name"] for item in scene.get("objects", [])}
    return {"marker_present": MARKER_OBJECT in names, "object_names": sorted(names)}


def plan(evidence: dict[str, Any]):
    from action_plan import ActionSpec

    if evidence["marker_present"]:
        return []
    return [ActionSpec(
        tool="create_empty_marker",
        arguments={
            "file_name": FILE_NAME,
            "collection_name": MARKER_COLLECTION,
            "object_name": MARKER_OBJECT,
        },
        name="restore Atlas_Marker",
        requires_success=True,
    )]


def make_executor() -> MultiStepCorrectiveExecutor:
    def execute(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool != "create_empty_marker":
            raise RuntimeError(f"Unexpected live corrective tool: {tool}")
        raw = create_empty_marker(**arguments)
        status = raw.get("status")
        return {
            "ok": status in {"created", "already_exists"},
            "state": str(status or "unknown"),
            "details": dict(raw),
        }

    return MultiStepCorrectiveExecutor(
        BlenderExecutionBoundary(execute),
        observe,
        plan,
        "live:multi-step-corrective",
    )


def establish_precondition() -> None:
    """Make the controlled fixture deterministically require one correction."""
    current = observe()
    if current["marker_present"]:
        deletion = delete_object(FILE_NAME, MARKER_OBJECT)
        if deletion.get("status") != "ok":
            raise RuntimeError(f"Failed to establish missing-marker precondition: {deletion}")
    current = observe()
    if current["marker_present"]:
        raise RuntimeError(f"Live gate precondition was not established: {current}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inject-external-change", action="store_true")
    args = parser.parse_args()

    establish_precondition()
    executor = make_executor()
    first = executor.execute_all(max_steps=1)
    if not first:
        raise RuntimeError("First corrective step did not execute")

    if args.inject_external_change:
        deletion = delete_object(FILE_NAME, MARKER_OBJECT)
        if deletion.get("status") != "ok":
            raise RuntimeError(f"External Blender mutation failed: {deletion}")

    second = executor.execute_all(max_steps=1)
    if not second:
        raise RuntimeError("Fresh-state corrective step did not execute after world change")

    final = observe()
    if not final["marker_present"]:
        raise RuntimeError(f"Independent final observation failed: {final}")

    print("ATLAS MULTI-STEP CORRECTIVE GATE: PASS")
    print(json.dumps({
        "first_receipts": len(first),
        "second_receipts": len(second),
        "external_change_injected": args.inject_external_change,
        "final_state": final,
    }, indent=2))


if __name__ == "__main__":
    main()
