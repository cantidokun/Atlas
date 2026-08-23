"""Live Blender gate for multi-object, multi-property corrective recovery."""
from __future__ import annotations

import argparse
import json
from typing import Any

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.multi_step_corrective_executor import MultiStepCorrectiveExecutor
from planning.transform_correction_plan import TransformTarget, plan_transform_correction
from tools.blender_transform import inspect_object_transform, set_object_rotation
from tools.blender import move_object
from tools.blender_test_fixture import set_test_transform

FILE_NAME = "marker_task_INCORRECT.blend"
OBJECT_A = "Goal_Left_post"
OBJECT_B = "Goal_Right_Post"
TARGETS = (
    TransformTarget(OBJECT_A, (1.0, 0.0, 0.0), (0.0, 0.0, 45.0)),
    TransformTarget(OBJECT_B, (-1.0, 0.0, 0.0), (0.0, 0.0, -45.0)),
)
TARGET = {t.object_name: {"location": list(t.location), "rotation": list(t.rotation_degrees)} for t in TARGETS}


def establish_fixture() -> None:
    for name in (OBJECT_A, OBJECT_B):
        result = set_test_transform(FILE_NAME, name, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        if result.get("status") != "ok":
            raise RuntimeError(f"failed to reset fixture {name}: {result}")
    result = set_test_transform(FILE_NAME, OBJECT_B, TARGET[OBJECT_B]["location"], TARGET[OBJECT_B]["rotation"])
    if result.get("status") != "ok":
        raise RuntimeError(f"failed to establish target state for {OBJECT_B}: {result}")


def observe() -> dict[str, Any]:
    result = {}
    for name in (OBJECT_A, OBJECT_B):
        evidence = inspect_object_transform(FILE_NAME, name)
        if evidence.get("status") != "ok":
            raise RuntimeError(f"fresh inspection failed for {name}: {evidence}")
        result[name] = {"location": [float(v) for v in evidence["location"]], "rotation": [float(v) for v in evidence["rotation_degrees"]]}
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
        return {"ok": status in {"ok", "moved", "already_at_location", "already_rotated"}, "state": str(status), "details": dict(raw)}
    return MultiStepCorrectiveExecutor(BlenderExecutionBoundary(execute), observe, plan, "live:multi-object-corrective")


def inject_external_change() -> None:
    result = set_test_transform(FILE_NAME, OBJECT_B, [99.0, 0.0, 0.0], [0.0, 0.0, 99.0])
    if result.get("status") != "ok":
        raise RuntimeError(f"external fixture mutation failed: {result}")


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
    print(json.dumps({"first_receipts": len(first), "second_receipts": len(second), "external_change_injected": args.inject_external_change, "final_state": final}, indent=2))


if __name__ == "__main__":
    main()
