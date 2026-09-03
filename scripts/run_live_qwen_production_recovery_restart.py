"""Prove Qwen-originated soccer production recovery across a Python restart.

Phase 1 obtains a live Qwen proposal, crosses the normal Atlas handoff and
authorization boundary, executes the first real Blender action, intentionally
fails the later action before Blender is invoked, and persists both the Atlas
continuation and Qwen provenance. Phase 2 starts a fresh Python process,
reconstructs the canonical Qwen handoff from persisted provenance, resumes the
existing Atlas runtime, acquires fresh evidence, explicitly authorizes only the
unfinished replacement action, verifies the final state independently, and
restores the fixture.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from action_plan import ActionSpec
from planning.authorized_task_runtime import start_authorized_task_runtime
from planning.autonomous_task_runtime import AutonomousTaskRuntime
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_process_executor import BlenderProcessExecutor
from planning.blender_tool_requests import BLENDER_PROCESS_REQUEST_BUILDERS
from planning.replan_authorization import ReplanAuthorization
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore
from qwen.ollama_provider import OllamaQwenProvider
from qwen.production_handoff import QwenProductionTaskHandoff
from scripts.run_live_production_task import BlenderProductionExecutor, _object_location, _object_rotation


def _executor(blender_command: str) -> tuple[BlenderExecutionBoundary, BlenderProductionExecutor]:
    transport = BlenderProcessExecutor(BLENDER_PROCESS_REQUEST_BUILDERS, blender_command=blender_command)
    boundary = BlenderExecutionBoundary(transport)
    return boundary, BlenderProductionExecutor(boundary)


def _restore_fixture(
    boundary: BlenderExecutionBoundary,
    path: Path,
    object_name: str,
    original_location: List[float],
    original_rotation: List[float],
) -> tuple[List[float], List[float]]:
    current_location = _object_location(
        boundary.execute_verified("inspect_scene", {"file_name": str(path)}), object_name
    )
    current_rotation = _object_rotation(
        boundary.execute_verified(
            "inspect_object_transform", {"file_name": str(path), "object_name": object_name}
        ),
        object_name,
    )
    if current_location != original_location:
        boundary.execute_with_persistence(
            "move_object",
            {"file_name": str(path), "object_name": object_name, "location": original_location},
            "inspect_scene",
            {"file_name": str(path)},
            {object_name: {"location": original_location}},
            lambda inspection: {object_name: {"location": _object_location(inspection, object_name)}},
        )
    if current_rotation != original_rotation:
        boundary.execute_with_persistence(
            "set_object_rotation",
            {
                "file_name": str(path),
                "object_name": object_name,
                "rotation_degrees": original_rotation,
            },
            "inspect_object_transform",
            {"file_name": str(path), "object_name": object_name},
            {"object_name": object_name, "rotation_degrees": original_rotation},
            lambda inspection: {
                "object_name": object_name,
                "rotation_degrees": _object_rotation(inspection, object_name),
            },
        )
    restored_location = _object_location(
        boundary.execute_verified("inspect_scene", {"file_name": str(path)}), object_name
    )
    restored_rotation = _object_rotation(
        boundary.execute_verified(
            "inspect_object_transform", {"file_name": str(path), "object_name": object_name}
        ),
        object_name,
    )
    return restored_location, restored_rotation


def _proposal_target(handoff: QwenProductionTaskHandoff) -> tuple[List[float], List[float]]:
    parameters = (handoff.semantic_task.metadata or {}).get("workflow_parameters", {})
    location = parameters.get("target_location")
    rotation = parameters.get("target_rotation")
    if not all(isinstance(value, list) and len(value) == 3 for value in (location, rotation)):
        raise RuntimeError("Qwen workflow parameters did not contain valid target transforms")
    return [float(value) for value in location], [float(value) for value in rotation]


def phase_failure(args: argparse.Namespace) -> int:
    path = Path(args.blend)
    state_file = Path(args.state_file)
    boundary, executor = _executor(args.blender)
    original_location = _object_location(
        boundary.execute_verified("inspect_scene", {"file_name": str(path)}), args.object
    )
    original_rotation = _object_rotation(
        boundary.execute_verified(
            "inspect_object_transform", {"file_name": str(path), "object_name": args.object}
        ),
        args.object,
    )
    target_location = [original_location[0] + args.delta_x, original_location[1], original_location[2]]
    target_rotation = [original_rotation[0], original_rotation[1], original_rotation[2] + args.delta_rotation]

    objective = (
        f"Prepare the soccer goal for a broadcast shot using file {path} and object {args.object}. "
        f"Set target_location to {target_location} and target_rotation to {target_rotation}."
    )
    context = (
        f"Verified production inputs: file_name={path}; object_name={args.object}; "
        f"target_location={target_location}; target_rotation={target_rotation}. "
        "Use only the canonical Atlas broadcast-goal-preparation workflow. "
        "Return workflow and numeric version separately."
    )
    provider = OllamaQwenProvider(
        url=args.url or "http://localhost:11434/api/chat",
        model=args.model or "qwen3:8b",
        timeout=args.timeout,
    )

    proposal = provider.propose(objective, context=context)
    handoff = QwenProductionTaskHandoff.from_proposal(proposal)
    handoff.verify_integrity()
    qwen_target_location, qwen_target_rotation = _proposal_target(handoff)
    if qwen_target_location != target_location or qwen_target_rotation != target_rotation:
        raise RuntimeError(
            f"Qwen proposal target drifted from the verified objective: "
            f"proposal_location={qwen_target_location}, proposal_rotation={qwen_target_rotation}"
        )

    _, authorization = handoff.authorize(args.authorization_id)
    runtime = start_authorized_task_runtime(
        handoff.compiled_task,
        FutureRuntimeStateStore(state_file),
        RuntimeContext(
            "Execute and recover the Qwen-proposed soccer production objective through Atlas.",
            {"environment": "local-blender", "file": str(path), "task": handoff.semantic_task.name},
        ),
        executor,
        authorization,
    )
    runtime.runtime.checkpoint_metadata(
        {
            "fixture_original_location": original_location,
            "fixture_original_rotation": original_rotation,
            "fixture_target_location": qwen_target_location,
            "fixture_target_rotation": qwen_target_rotation,
            "qwen_handoff": handoff.snapshot(),
        }
    )

    class FailLaterAction:
        def __init__(self, delegate):
            self.delegate = delegate

        def __call__(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            if tool == "set_object_rotation":
                raise RuntimeError("controlled Qwen-originated later-action failure")
            return self.delegate(tool, arguments)

    runtime.executor = FailLaterAction(runtime.executor)
    failed = runtime.run_until_pause()
    if failed.get("blocked") is not True:
        raise RuntimeError(f"Qwen-originated failure did not block the continuation: {failed}")
    persisted = FutureRuntimeStateStore(state_file).load()
    if not isinstance((persisted.get("metadata") or {}).get("qwen_handoff"), dict):
        raise RuntimeError("Qwen handoff provenance was not persisted with the blocked continuation")

    print("LIVE QWEN PRODUCTION RECOVERY PHASE 1 VERIFIED")
    print(f"object={args.object}")
    print(f"workflow={handoff.semantic_task.metadata['workflow_catalog']['name']}")
    print(f"workflow_version={handoff.semantic_task.metadata['workflow_catalog']['version']}")
    print(f"original_location={original_location}")
    print(f"original_rotation={original_rotation}")
    print(f"target_location={qwen_target_location}")
    print(f"target_rotation={qwen_target_rotation}")
    print("qwen_proposal=verified")
    print("atlas_authorization=verified")
    print("first_action=completed")
    print("later_action=controlled_failure")
    print("qwen_provenance_checkpointed=verified")
    print("durable_partial_progress=verified")
    print("process_restart=ready")
    print(f"state_file={state_file}")
    return 0


def phase_recover(args: argparse.Namespace) -> int:
    path = Path(args.blend)
    state_file = Path(args.state_file)
    boundary, executor = _executor(args.blender)
    store = FutureRuntimeStateStore(state_file)
    metadata = store.load().get("metadata") or {}
    persisted_handoff = metadata.get("qwen_handoff")
    if not isinstance(persisted_handoff, dict):
        raise RuntimeError("persisted Qwen handoff provenance is missing")
    handoff = QwenProductionTaskHandoff.from_snapshot(persisted_handoff)

    original_location = metadata.get("fixture_original_location")
    original_rotation = metadata.get("fixture_original_rotation")
    target_location = metadata.get("fixture_target_location")
    target_rotation = metadata.get("fixture_target_rotation")
    if not all(isinstance(value, list) and len(value) == 3 for value in (
        original_location, original_rotation, target_location, target_rotation
    )):
        raise RuntimeError("persisted Qwen recovery fixture state is incomplete")
    original_location = [float(value) for value in original_location]
    original_rotation = [float(value) for value in original_rotation]
    target_location = [float(value) for value in target_location]
    target_rotation = [float(value) for value in target_rotation]

    parameters = (handoff.semantic_task.metadata or {}).get("workflow_parameters", {})
    if parameters.get("target_location") != target_location or parameters.get("target_rotation") != target_rotation:
        raise RuntimeError("persisted Qwen target provenance does not match the continuation envelope")

    runtime = AutonomousTaskRuntime.resume_from_store(
        handoff.compiled_task,
        store,
        RuntimeContext(
            "Execute and recover the Qwen-proposed soccer production objective through Atlas.",
            {"environment": "local-blender", "file": str(path), "task": handoff.semantic_task.name},
        ),
        executor,
    )
    snapshot = runtime.runtime.snapshot()
    if snapshot.get("blocked") is not True:
        raise RuntimeError(f"fresh process did not recover the blocked Qwen continuation: {snapshot}")
    if runtime.authorization is None or runtime.authorization.authorization_id != args.authorization_id:
        raise RuntimeError("Qwen-originated Atlas authorization was not recovered")

    recovery = runtime.recover_with_fresh_evidence()
    if recovery["decision"]["disposition"] != "REPLAN_REQUIRED":
        raise RuntimeError(f"Qwen-originated recovery did not reach REPLAN_REQUIRED: {recovery}")

    if len(handoff.compiled_task.actions) < 2:
        raise RuntimeError("Qwen production workflow did not compile the expected multi-action task")
    unfinished = handoff.compiled_task.actions[1]
    replacement = [
        ActionSpec(
            unfinished.tool,
            dict(unfinished.arguments),
            "qwen_replanned_rotation",
            unfinished.requires_success,
            unfinished.dependency_names(),
        )
    ]
    receipt = runtime.authorize_replan(replacement, args.replan_authorization_id)
    if not isinstance(receipt, ReplanAuthorization):
        raise RuntimeError("Qwen recovery replan did not produce the expected authorization receipt")
    runtime.install_authorized_replan(receipt, replacement)
    result = runtime.run_until_pause()
    if result.get("complete") is not True or result.get("blocked") is True:
        raise RuntimeError(f"Qwen-originated recovery did not complete: {result}")

    final_location = _object_location(
        boundary.execute_verified("inspect_scene", {"file_name": str(path)}), args.object
    )
    final_rotation = _object_rotation(
        boundary.execute_verified(
            "inspect_object_transform", {"file_name": str(path), "object_name": args.object}
        ),
        args.object,
    )
    if final_location != target_location or final_rotation != target_rotation:
        raise RuntimeError("independent final verification failed after Qwen-originated recovery")

    restored_location, restored_rotation = _restore_fixture(
        boundary,
        path,
        args.object,
        original_location,
        original_rotation,
    )
    if restored_location != original_location or restored_rotation != original_rotation:
        raise RuntimeError("fixture restoration verification failed")
    state_file.unlink(missing_ok=True)

    print("LIVE QWEN PRODUCTION RECOVERY VERIFIED")
    print(f"object={args.object}")
    print(f"workflow={handoff.semantic_task.metadata['workflow_catalog']['name']}")
    print(f"workflow_version={handoff.semantic_task.metadata['workflow_catalog']['version']}")
    print("qwen_provenance_recovered=verified")
    print("initial_authorization_recovered=verified")
    print("process_restart=verified")
    print("fresh_recovery_evidence=verified")
    print("qwen_workflow_target_revalidated=verified")
    print("completed_prerequisite_not_replayed=verified")
    print(f"replan_authorization={args.replan_authorization_id}")
    print("replacement_execution=verified")
    print("independent_final_verification=verified")
    print(f"fixture_restored_location={restored_location}")
    print(f"fixture_restored_rotation={restored_rotation}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("failure", "recover"), required=True)
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--blend", default="atlas_live_mutation.blend")
    parser.add_argument("--object", default="Goal_Left_post")
    parser.add_argument("--delta-x", type=float, default=0.25)
    parser.add_argument("--delta-rotation", type=float, default=15.0)
    parser.add_argument("--authorization-id", default="atlas-qwen-recovery-initial")
    parser.add_argument("--replan-authorization-id", default="atlas-qwen-recovery-replan")
    parser.add_argument("--state-file", default="Saved/atlas-qwen-production-recovery-restart.json")
    parser.add_argument("--url", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    path = Path(args.blend)
    if not path.is_file():
        print(f"LIVE QWEN PRODUCTION RECOVERY FAILED: Blender fixture not found: {path}")
        return 1

    try:
        if args.phase == "failure":
            return phase_failure(args)
        return phase_recover(args)
    except Exception as exc:
        print(f"LIVE QWEN PRODUCTION RECOVERY FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
