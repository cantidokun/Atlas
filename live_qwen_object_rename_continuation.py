"""Live continuation proof for a real Blender object-rename task.

The task starts from fresh Blender evidence, builds a deterministic future,
pauses at the independent verification boundary, and resumes from persisted
state. The write path intentionally uses the production autonomous Blender
executor so continuation exercises the same validated/receipt-bound execution
adapter used by the autonomous runtime.
"""

import argparse
import json
import os
import tempfile
from typing import Any, Dict

from action_plan import ActionSpec
from planning.action_authorization import ActionAuthorization
from planning.autonomous_runtime import AutonomousFutureRuntime
from planning.blender_autonomous_executor import BlenderAutonomousExecutor
from planning.future_generator import DeterministicFutureGenerator
from planning.object_rename_task import TARGET_NAME, TARGET_OBJECT, object_rename_target_evaluator
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore
from tools.blender import inspect_scene
from tools.blender_object import rename_object

CORRECT_FILE = "object_rename_CORRECT.blend"
INCORRECT_FILE = "object_rename_INCORRECT.blend"


def action(file_name: str) -> ActionSpec:
    return ActionSpec(
        tool="rename_object",
        arguments={
            "file_name": file_name,
            "object_name": TARGET_OBJECT,
            "new_name": TARGET_NAME,
        },
        name="rename_object",
    )


def context(file_name: str) -> RuntimeContext:
    return RuntimeContext(
        f"Ensure {TARGET_OBJECT} is renamed to {TARGET_NAME} in the supplied Blender fixture.",
        {"environment": "local-blender", "file": file_name},
    )


def fresh_evidence(file_name: str) -> Dict[str, Any]:
    scene = inspect_scene(file_name=file_name)
    scene["object_names"] = [obj["name"] for obj in scene.get("objects", [])]
    return scene


def verification_result(evidence: Dict[str, Any]) -> Dict[str, Any]:
    state = object_rename_target_evaluator().evaluate(evidence)
    return {"satisfied": state.satisfied, "evidence": dict(evidence)}


def acknowledgements(target_satisfied: bool) -> Dict[str, Dict[str, Any]]:
    values = {
        "evidence.authoritative": {"source": "fresh_blender_evidence"},
        "target.evaluated": {"satisfied": target_satisfied},
    }
    if target_satisfied:
        values["writes.skipped"] = {"reason": "target_already_satisfied"}
    return values


def blender_executor() -> BlenderAutonomousExecutor:
    def execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool != "rename_object":
            raise RuntimeError(f"Unexpected continuation tool: {tool}")
        raw = rename_object(**arguments)
        status = raw.get("status")
        return {
            "ok": status in {"renamed", "already_named"},
            "state": str(status or "unknown"),
            "details": dict(raw),
        }

    return BlenderAutonomousExecutor(execute)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("already-correct", "incorrect", "tampered-context"), required=True)
    args = parser.parse_args()

    file_name = CORRECT_FILE if args.case == "already-correct" else INCORRECT_FILE
    current_context = context(file_name)
    target_evaluator = object_rename_target_evaluator()
    initial_evidence = fresh_evidence(file_name)
    target = target_evaluator.evaluate(initial_evidence)
    authorized_action = action(file_name)
    authorization = ActionAuthorization.issue([authorized_action], f"live-rename-continuation:{args.case}")
    if not authorization.matches([authorized_action]):
        raise RuntimeError("Continuation authorization did not match the authorized action")

    future = DeterministicFutureGenerator(target_evaluator).generate(target.satisfied, [authorized_action])

    with tempfile.TemporaryDirectory(prefix="atlas-rename-continuation-") as directory:
        store = FutureRuntimeStateStore(os.path.join(directory, "runtime.json"))
        runtime = AutonomousFutureRuntime(future, store, current_context)
        executor = blender_executor()
        calls = 0

        def execute_once(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            nonlocal calls
            calls += 1
            return executor(tool, arguments)

        ack = acknowledgements(target.satisfied)

        if args.case == "tampered-context":
            paused = runtime.run_until_pause(execute_once, acknowledgements=ack)
            if paused.get("current_step", {}).get("phase") != "VERIFICATION":
                raise RuntimeError(f"Expected persisted pause at verification: {paused}")
            try:
                AutonomousFutureRuntime.resume_from_store(
                    future,
                    store,
                    context("TAMPERED continuation instructions"),
                )
            except RuntimeError as exc:
                print("ATLAS RENAME CONTINUATION INTEGRITY TASK: PASS")
                print(f"TAMPERED CONTINUATION REJECTED: {exc}")
                return
            raise RuntimeError("Tampered continuation was accepted")

        paused = runtime.run_until_pause(execute_once, acknowledgements=ack)
        if paused.get("current_step", {}).get("phase") != "VERIFICATION":
            raise RuntimeError(f"Expected persisted pause at verification: {paused}")

        expected_calls = 0 if target.satisfied else 1
        if calls != expected_calls:
            raise RuntimeError(f"Rename execution count mismatch: expected {expected_calls}, got {calls}")
        if not target.satisfied and not executor.receipt_matches_last_execution(
            authorized_action.tool,
            authorized_action.arguments,
        ):
            raise RuntimeError("Rename execution receipt did not match the authorized action")

        resumed = AutonomousFutureRuntime.resume_from_store(future, store, current_context)
        verification = verification_result(fresh_evidence(file_name))
        final = resumed.run_until_pause(
            execute_once,
            verifications={"verification.pending": verification},
        )
        if final.get("complete") is not True:
            raise RuntimeError(f"Rename continuation did not complete: {final}")

        if not target.satisfied:
            post = fresh_evidence(file_name)
            if TARGET_NAME not in post.get("object_names", []) or TARGET_OBJECT in post.get("object_names", []):
                raise RuntimeError(f"Blender post-state was not independently verified: {post}")

    print("ATLAS BLENDER RENAME CONTINUATION TASK: PASS")
    print(
        "TARGET ALREADY SATISFIED -> FUTURE SKIPPED WRITE"
        if target.satisfied
        else "AUTHORIZED BLENDER WRITE -> RECEIPT -> PERSISTED PAUSE -> RESUME -> FRESH VERIFICATION -> COMPLETE"
    )
    print(json.dumps({"case": args.case, "initial_target_satisfied": target.satisfied}, indent=2))


if __name__ == "__main__":
    main()
