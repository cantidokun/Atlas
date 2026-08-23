"""Live proof that generalized BlenderCorrectiveRuntime handles external interruption."""
from __future__ import annotations

import argparse
import json
from typing import Any

from planning.blender_corrective_runtime import BlenderCorrectiveRuntime
from planning.transform_correction_plan import TransformTarget, plan_transform_correction
from tools.blender_test_fixture import set_test_transform
from tools.blender_transform import inspect_object_transform

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


def _observe_raw() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in (OBJECT_A, OBJECT_B):
        evidence = inspect_object_transform(FILE_NAME, name)
        if evidence.get("status") != "ok":
            raise RuntimeError(f"inspection failed for {name}: {evidence}")
        result[name] = {
            "location": [float(v) for v in evidence["location"]],
            "rotation": [float(v) for v in evidence["rotation_degrees"]],
        }
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

    observation_count = 0
    injected = False

    def observe() -> dict[str, Any]:
        nonlocal observation_count, injected
        observation_count += 1
        if args.inject_external_change and observation_count == 3 and not injected:
            inject_external_change()
            injected = True
        return _observe_raw()

    runtime = BlenderCorrectiveRuntime(observe, plan, "live:generalized-corrective-runtime")
    result = runtime.run(max_steps=8)
    if not result.converged:
        raise RuntimeError("generalized runtime failed to converge")
    if args.inject_external_change and not injected:
        raise RuntimeError("external interruption was not injected")

    final = _observe_raw()
    if plan(final):
        raise RuntimeError(f"independent final verification failed: {final}")

    print("ATLAS GENERALIZED BLENDER CORRECTIVE RUNTIME GATE: PASS")
    print(json.dumps({"receipts": len(result.receipts), "external_change_injected": injected, "observations": observation_count, "final_state": final}, indent=2))


if __name__ == "__main__":
    main()
