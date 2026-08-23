"""Live proof that generalized BlenderCorrectiveRuntime handles external interruption."""
from __future__ import annotations

import argparse
import json
from typing import Any

from planning.blender_corrective_runtime import BlenderCorrectiveRuntime
from planning.transform_correction_plan import TransformTarget, plan_transform_correction
from tools.blender import move_object
from tools.blender_test_fixture import set_test_transform
from tools.blender_transform import inspect_object_transform, set_object_rotation

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
            raise RuntimeError(f"fixture reset failed for {name}: {result}")
    result = set_test_transform(FILE_NAME, OBJECT_B, TARGET[OBJECT_B]["location"], TARGET[OBJECT_B]["rotation"])
    if result.get("status") != "ok":
        raise RuntimeError(f"fixture setup failed for {OBJECT_B}: {result}")


def observe() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in (OBJECT_A, OBJECT_B):
        evidence = inspect_object_transform(FILE_NAME, name)
        if evidence.get("status") != "ok":
            raise RuntimeError(f"inspection failed for {name}: {evidence}")
        result[name] = {"location": [float(v) for v in evidence["location"]], "rotation": [float(v) for v in evidence["rotation_degrees"]]}
    return result


def plan(evidence: dict[str, Any]):
    return plan_transform_correction(evidence, TARGETS, FILE_NAME)


def inject_external_change() -> None:
    result = set_test_transform(FILE_NAME, OBJECT_B, [99.0, 0.0, 0.0], [0.0, 0.0, 99.0])
    if result.get("status") != "ok":
        raise RuntimeError(f"external change failed: {result}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inject-external-change", action="store_true")
    args = parser.parse_args()
    establish_fixture()

    runtime = BlenderCorrectiveRuntime(observe, plan, "live:generalized-corrective-runtime")
    first = runtime.run(max_steps=2)
    if not first.converged:
        raise RuntimeError("generalized runtime failed to converge first phase")
    if len(first.receipts) != 2:
        raise RuntimeError(f"expected two first-phase receipts, got {len(first.receipts)}")

    if args.inject_external_change:
        inject_external_change()

    second = runtime.run(max_steps=8)
    if not second.converged:
        raise RuntimeError("generalized runtime failed to recover after external change")
    final = observe()
    if plan(final):
        raise RuntimeError(f"independent final verification failed: {final}")

    print("ATLAS GENERALIZED BLENDER CORRECTIVE RUNTIME GATE: PASS")
    print(json.dumps({"first_receipts": len(first.receipts), "second_receipts": len(second.receipts), "external_change_injected": args.inject_external_change, "final_state": final}, indent=2))


if __name__ == "__main__":
    main()
