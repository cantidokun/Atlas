"""Live Blender gate for multi-object, multi-property corrective recovery."""
from __future__ import annotations

import argparse
import json
from typing import Any

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.multi_step_corrective_executor import MultiStepCorrectiveExecutor
from planning.transform_correction_plan import TransformTarget, plan_transform_correction
from tools.blender import create_empty_marker, inspect_object_transform, move_object
from tools.blender_transform import set_object_rotation

FILE_NAME = "marker_task_INCORRECT.blend"
COLLECTION = "Atlas_Test"
OBJECT_A = "Atlas_Correction_A"
OBJECT_B = "Atlas_Correction_B"
TARGETS = (
    TransformTarget(OBJECT_A, (1.0, 0.0, 0.0), (0.0, 0.0, 45.0)),
    TransformTarget(OBJECT_B, (-1.0, 0.0, 0.0), (0.0, 0.0, -45.0)),
)
TARGET = {
    target.object_name: {
        "location": list(target.location),
        "rotation": list(target.rotation_degrees),
    }
    for target in TARGETS
}


def _ensure_marker(name: str) -> None:
    result = create_empty_marker(FILE_NAME, COLLECTION, name)
    if result.get("status") not in {"created", "already_exists"}:
        raise RuntimeError(f"failed to establish {name}: {result}")


def _set_transform(name: str, location: list[float], rotation: list[float]) -> None:
    moved = move_object(FILE_NAME, name, location)
    if moved.get("status") not in {"ok", "already_at_location"}:
        raise RuntimeError(f"failed to set location for {name}: {moved}")
    rotated = set_object_rotation(FILE_NAME, name, rotation)
    if rotated.get("status") not in {"ok", "already_rotated"}:
        raise RuntimeError(f"failed to set rotation for {name}: {rotated}")


def establish_fixture() -> None:
    _ensure_marker(OBJECT_A)
    _ensure_marker(OBJECT_B)
    _set_transform(OBJECT_A, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
    _set_transform(OBJECT_B, TARGET[OBJECT_B]["location"], TARGET[OBJECT_B]["rotation"])


def observe() -> dict[str, Any]:
    result = {}
    for name in (OBJECT_A, OBJECT_B):
        evidence = inspect_object_transform(FILE_NAME, name)
        if evidence.get("status") != "ok":
            raise RuntimeError(f"fresh inspection failed for {name}: {evidence}")
        result[name] = {
            "location": [float(value) for value in evidence["location"]],
            "rotation": [float(value) for value in evidence["rotation_degrees"]],
        }
    return result


def plan(evidence: dict[str, Any]):
    return plan_transform_correction(evidence, TARGETS, FILE_NAME)


def make_executor() -> MultiStepCorrectiveExecutor:
    def execute(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool == "move_object":
            raw = move_object(**arguments)
        elif tool == "set_object_rotation":
            raw = set_object_rotation(**arguments)
        else:
            raise RuntimeError(f"unexpected live corrective tool: {tool}")
        status = raw.get("status")
        return {"ok": status in {"ok", "already_at_location", "already_rotated"}, "state": str(status), "details": dict(raw)}

    return MultiStepCorrectiveExecutor(
        BlenderExecutionBoundary(execute), observe, plan, "live:multi-object-corrective"
    )


def inject_external_change() -> None:
    moved = move_object(FILE_NAME, OBJECT_B, [99.0, 0.0, 0.0])
    if moved.get("status") not in {"ok", "already_at_location"}:
        raise RuntimeError(f"external location mutation failed: {moved}")
    rotated = set_object_rotation(FILE_NAME, OBJECT_B, [0.0, 0.0, 99.0])
    if rotated.get("status") not in {"ok", "already_rotated"}:
        raise RuntimeError(f"external rotation mutation failed: {rotated}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inject-external-change", action="store_true")
    args = parser.parse_args()

    establish_fixture()
    executor = make_executor()

    first = executor.execute_all(max_steps=2)
    if len(first) != 2:
        raise RuntimeError(f"expected two corrective steps for object A, got {len(first)}")

    if args.inject_external_change:
        inject_external_change()

    second = executor.execute_all(max_steps=8)
    if len(second) != 2:
        raise RuntimeError(f"expected two corrective steps for object B, got {len(second)}")

    final = observe()
    if plan(final):
        raise RuntimeError(f"independent final observation failed: {final}")

    print("ATLAS MULTI-OBJECT MULTI-PROPERTY GATE: PASS")
    print(json.dumps({
        "first_receipts": len(first),
        "second_receipts": len(second),
        "external_change_injected": args.inject_external_change,
        "final_state": final,
    }, indent=2))


if __name__ == "__main__":
    main()
