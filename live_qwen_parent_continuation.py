"""Live continuation proof for a real Blender parent-relationship task.

The task is planned and authorized once, converted into a deterministic future,
paused at the verification boundary, and resumed from persisted state. The
resume path must use the same authorized future/context and fresh Blender
state evidence. A tampered continuation context must fail closed.
"""

import argparse
import json
import os
import tempfile
from typing import Any, Dict

from action_plan import ActionSpec
from planning.action_authorization import ActionAuthorization
from planning.autonomous_runtime import AutonomousFutureRuntime
from planning.future_generator import DeterministicFutureGenerator
from planning.parent_marker_task import MARKER_OBJECT, PARENT_OBJECT, parent_target_evaluator
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore
from tools.blender_relationship import inspect_object_parent, parent_object

CORRECT_FILE = "parent_task_CORRECT.blend"
INCORRECT_FILE = "parent_task_INCORRECT.blend"


def action(file_name: str) -> ActionSpec:
    return ActionSpec(
        tool="parent_object",
        arguments={
            "file_name": file_name,
            "child_name": MARKER_OBJECT,
            "parent_name": PARENT_OBJECT,
        },
        name="parent Atlas_Marker to Goal_Left_post",
    )


def context(file_name: str) -> RuntimeContext:
    return RuntimeContext(
        "Ensure Atlas_Marker is parented to Goal_Left_post in the supplied Blender fixture.",
        {"environment": "local-blender", "file": file_name},
    )


def execute_parent(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool != "parent_object":
        raise RuntimeError(f"Unexpected continuation tool: {tool}")
    result = parent_object(**arguments)
    status = result.get("status")
    return {
        "ok": status in {"parented", "already_parented"},
        "state": str(status or "unknown"),
        "details": dict(result),
    }


def fresh_evidence(file_name: str) -> Dict[str, Any]:
    return inspect_object_parent(file_name=file_name, object_name=MARKER_OBJECT)


def verification_result(evidence: Dict[str, Any]) -> Dict[str, Any]:
    satisfied = (
        evidence.get("object_name") == MARKER_OBJECT
        and evidence.get("parent_name") == PARENT_OBJECT
    )
    return {"satisfied": satisfied, "evidence": dict(evidence)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("already-correct", "incorrect", "tampered-context"), required=True)
    args = parser.parse_args()

    file_name = CORRECT_FILE if args.case == "already-correct" else INCORRECT_FILE
    current_context = context(file_name)
    target_evaluator = parent_target_evaluator()
    evidence = fresh_evidence(file_name)
    target = target_evaluator.evaluate(evidence)
    authorized_action = action(file_name)
    authorization = ActionAuthorization.issue([authorized_action], f"live-continuation:{args.case}")
    if not authorization.matches([authorized_action]):
        raise RuntimeError("Continuation authorization did not match the authorized action")

    future = DeterministicFutureGenerator(target_evaluator).generate(
        target.satisfied,
        [authorized_action],
    )

    with tempfile.TemporaryDirectory(prefix="atlas-continuation-") as directory:
        store = FutureRuntimeStateStore(os.path.join(directory, "runtime.json"))
        runtime = AutonomousFutureRuntime(future, store, current_context)

        if args.case == "tampered-context":
            runtime.run_until_pause(execute_parent)
            try:
                AutonomousFutureRuntime.resume_from_store(
                    future,
                    store,
                    context("TAMPERED continuation instructions"),
                )
            except RuntimeError as exc:
                print("ATLAS CONTINUATION INTEGRITY TASK: PASS")
                print(f"TAMPERED CONTINUATION REJECTED: {exc}")
                return
            raise RuntimeError("Tampered continuation was accepted")

        paused = runtime.run_until_pause(execute_parent)
        if paused.get("current_step", {}).get("phase") != "VERIFICATION":
            raise RuntimeError(f"Expected persisted pause at verification: {paused}")

        resumed = AutonomousFutureRuntime.resume_from_store(future, store, current_context)
        verification = verification_result(fresh_evidence(file_name))
        final = resumed.run_until_pause(
            execute_parent,
            verifications={"verification.pending": verification},
        )
        if final.get("complete") is not True:
            raise RuntimeError(f"Continuation did not complete after resumed verification: {final}")

        if not target.satisfied and args.case == "incorrect":
            post = fresh_evidence(file_name)
            if post.get("parent_name") != PARENT_OBJECT:
                raise RuntimeError(f"Blender post-state was not independently verified: {post}")

    print("ATLAS BLENDER CONTINUATION TASK: PASS")
    print("TARGET ALREADY SATISFIED -> FUTURE SKIPPED WRITE" if target.satisfied else "AUTHORIZED BLENDER WRITE -> PERSISTED PAUSE -> RESUME -> FRESH VERIFICATION -> COMPLETE")
    print(json.dumps({"case": args.case, "initial_target_satisfied": target.satisfied, "authorization_id": authorization.authorization_id}, indent=2))


if __name__ == "__main__":
    main()
