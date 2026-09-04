"""Live Qwen -> Atlas authorization -> existing runtime -> Blender mutation proof.

This is the first end-to-end Qwen production mutation harness. Qwen only
proposes the catalog workflow and parameters. Atlas validates, authorizes, and
runs the existing task runtime. Final state is independently verified and the
fixture is restored to its observed original state.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from planning.authorized_task_runtime import start_authorized_task_runtime
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_process_executor import BlenderProcessExecutor
from planning.blender_tool_requests import BLENDER_PROCESS_REQUEST_BUILDERS
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore
from qwen.ollama_provider import OllamaQwenProvider
from qwen.production_handoff import QwenProductionTaskHandoff
from scripts.run_live_production_task import BlenderProductionExecutor, _object_location, _object_rotation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--blend", default="atlas_live_mutation.blend")
    parser.add_argument("--object", default="Goal_Left_post")
    parser.add_argument("--state-file", default="Saved/atlas-qwen-production-runtime.json")
    parser.add_argument("--url", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    path = Path(args.blend)
    state_file = Path(args.state_file)
    if not path.is_file():
        print(f"LIVE QWEN PRODUCTION RUNTIME FAILED: Blender fixture not found: {path}")
        return 1

    transport = BlenderProcessExecutor(BLENDER_PROCESS_REQUEST_BUILDERS, blender_command=args.blender)
    boundary = BlenderExecutionBoundary(transport)
    executor = BlenderProductionExecutor(boundary)

    original_location: List[float] = _object_location(
        boundary.execute_verified("inspect_scene", {"file_name": str(path)}), args.object
    )
    original_rotation: List[float] = _object_rotation(
        boundary.execute_verified(
            "inspect_object_transform", {"file_name": str(path), "object_name": args.object}
        ),
        args.object,
    )
    target_location = [original_location[0] + 0.25, original_location[1], original_location[2]]
    target_rotation = [original_rotation[0], original_rotation[1], original_rotation[2] + 15.0]

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

    try:
        state_file.unlink(missing_ok=True)
        proposal = provider.propose(objective, context=context)
        handoff = QwenProductionTaskHandoff.from_proposal(proposal)
        handoff.verify_integrity()
        action_plan, authorization = handoff.authorize("atlas-qwen-production-runtime-live")
        runtime = start_authorized_task_runtime(
            handoff.compiled_task,
            FutureRuntimeStateStore(state_file),
            RuntimeContext(
                "Execute the Qwen-proposed soccer production objective through Atlas.",
                {"environment": "local-blender", "file": str(path), "task": handoff.semantic_task.name},
            ),
            executor,
            authorization,
        )

        result = runtime.run_until_pause()
        if result.get("complete") is not True or result.get("blocked") is True:
            raise RuntimeError(f"Qwen-authorized production runtime did not complete: {result}")

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
            raise RuntimeError("independent final verification failed")

        catalog: Dict[str, Any] = (handoff.semantic_task.metadata or {}).get("workflow_catalog", {})
        parameters: Dict[str, Any] = (handoff.semantic_task.metadata or {}).get("workflow_parameters", {})
        print("LIVE QWEN-AUTHORIZED SOCCER PRODUCTION RUNTIME VERIFIED")
        print(f"object={args.object}")
        print(f"workflow={catalog.get('name')}")
        print(f"workflow_version={catalog.get('version')}")
        print("qwen_proposal=verified")
        print("catalog_validation=verified")
        print("semantic_task=verified")
        print("atlas_authorization=verified")
        print(f"authorization_id={authorization.authorization_id}")
        print(f"authorization_digest={authorization.plan_digest}")
        print("existing_task_runtime=verified")
        print("blender_execution=verified")
        print("independent_final_verification=verified")
        print(f"workflow_parameters={parameters}")
        print(f"target_location={target_location}")
        print(f"target_rotation={target_rotation}")
    except Exception as exc:
        print(f"LIVE QWEN-AUTHORIZED SOCCER PRODUCTION RUNTIME FAILED: {exc}")
        return 1
    finally:
        try:
            current_location = _object_location(
                boundary.execute_verified("inspect_scene", {"file_name": str(path)}), args.object
            )
            current_rotation = _object_rotation(
                boundary.execute_verified(
                    "inspect_object_transform", {"file_name": str(path), "object_name": args.object}
                ),
                args.object,
            )
            if current_location != original_location:
                boundary.execute_with_persistence(
                    "move_object",
                    {"file_name": str(path), "object_name": args.object, "location": original_location},
                    "inspect_scene",
                    {"file_name": str(path)},
                    {args.object: {"location": original_location}},
                    lambda inspection: {args.object: {"location": _object_location(inspection, args.object)}},
                )
            if current_rotation != original_rotation:
                boundary.execute_with_persistence(
                    "set_object_rotation",
                    {
                        "file_name": str(path),
                        "object_name": args.object,
                        "rotation_degrees": original_rotation,
                    },
                    "inspect_object_transform",
                    {"file_name": str(path), "object_name": args.object},
                    {"object_name": args.object, "rotation_degrees": original_rotation},
                    lambda inspection: {
                        "object_name": args.object,
                        "rotation_degrees": _object_rotation(inspection, args.object),
                    },
                )
            restored_location = _object_location(
                boundary.execute_verified("inspect_scene", {"file_name": str(path)}), args.object
            )
            restored_rotation = _object_rotation(
                boundary.execute_verified(
                    "inspect_object_transform", {"file_name": str(path), "object_name": args.object}
                ),
                args.object,
            )
            if restored_location == original_location and restored_rotation == original_rotation:
                print(f"fixture_restored_location={restored_location}")
                print(f"fixture_restored_rotation={restored_rotation}")
            else:
                print(f"fixture_restoration_failed_location={restored_location}")
                print(f"fixture_restoration_failed_rotation={restored_rotation}")
        finally:
            state_file.unlink(missing_ok=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
