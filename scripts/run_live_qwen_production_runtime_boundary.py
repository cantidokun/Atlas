"""Live Qwen -> Atlas authorization -> existing runtime boundary proof.

This harness uses the real local Ollama/Qwen provider, the canonical soccer
workflow catalog, Atlas's existing authorization path, and the existing Blender
execution boundary only for authoritative inspection. It intentionally stops
before the ACTION phase so the proof cannot mutate the fixture.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from planning.authorized_task_runtime import start_authorized_task_runtime
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_process_executor import BlenderProcessExecutor
from planning.blender_tool_requests import BLENDER_PROCESS_REQUEST_BUILDERS
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore
from qwen.ollama_provider import OllamaQwenProvider
from qwen.production_handoff import QwenProductionTaskHandoff
from scripts.run_live_production_task import BlenderProductionExecutor, _object_location, _object_rotation


DEFAULT_OBJECT = "Goal_Left_post"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--blend", default="atlas_live_mutation.blend")
    parser.add_argument("--object", default=DEFAULT_OBJECT)
    parser.add_argument("--state-file", default="Saved/atlas-qwen-runtime-boundary.json")
    parser.add_argument("--url", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    path = Path(args.blend)
    state_file = Path(args.state_file)
    if not path.is_file():
        print(f"LIVE QWEN RUNTIME BOUNDARY FAILED: Blender fixture not found: {path}")
        return 1

    transport = BlenderProcessExecutor(BLENDER_PROCESS_REQUEST_BUILDERS, blender_command=args.blender)
    boundary = BlenderExecutionBoundary(transport)
    executor = BlenderProductionExecutor(boundary)

    original_location = _object_location(
        boundary.execute_verified("inspect_scene", {"file_name": str(path)}), args.object
    )
    original_rotation = _object_rotation(
        boundary.execute_verified(
            "inspect_object_transform", {"file_name": str(path), "object_name": args.object}
        ),
        args.object,
    )

    objective = (
        f"Prepare the soccer goal for a broadcast shot using file {path} and object {args.object}. "
        f"Set target_location to [{original_location[0] + 0.25}, {original_location[1]}, {original_location[2]}] "
        f"and target_rotation to [{original_rotation[0]}, {original_rotation[1]}, {original_rotation[2] + 15.0}]."
    )
    context = (
        f"Verified production inputs: file_name={path}; object_name={args.object}; "
        f"original_location={original_location}; original_rotation={original_rotation}. "
        "Apply only the canonical Atlas broadcast-goal-preparation workflow. "
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
        action_plan, authorization = handoff.authorize("atlas-qwen-runtime-boundary-live")
        runtime = start_authorized_task_runtime(
            handoff.compiled_task,
            FutureRuntimeStateStore(state_file),
            RuntimeContext(
                "Execute an authorized soccer production workflow through the existing Atlas runtime.",
                {"environment": "local-blender", "file": str(path), "task": handoff.semantic_task.name},
            ),
            executor,
            authorization,
        )

        after_location = _object_location(
            boundary.execute_verified("inspect_scene", {"file_name": str(path)}), args.object
        )
        after_rotation = _object_rotation(
            boundary.execute_verified(
                "inspect_object_transform", {"file_name": str(path), "object_name": args.object}
            ),
            args.object,
        )
        if after_location != original_location or after_rotation != original_rotation:
            raise RuntimeError("runtime-boundary proof mutated the Blender fixture before ACTION phase")

        snapshot = runtime.runtime.snapshot()
        next_action = snapshot.get("next_action") or {}
        metadata = runtime.runtime.metadata
        catalog = metadata.get("task_metadata", {}).get("workflow_catalog", {})

        print("LIVE QWEN ATLAS RUNTIME BOUNDARY VERIFIED")
        print(f"object={args.object}")
        print(f"workflow={catalog.get('name')}")
        print(f"workflow_version={catalog.get('version')}")
        print("qwen_proposal=verified")
        print("semantic_task=verified")
        print("atlas_authorization=verified")
        print(f"authorization_id={authorization.authorization_id}")
        print(f"authorization_digest={authorization.plan_digest}")
        print("existing_task_runtime=verified")
        print("authoritative_initial_evidence=verified")
        print("authorized_future_constructed=verified")
        print(f"next_action_tool={next_action.get('tool')}")
        print("action_execution=not_attempted")
        print("blender_mutation=not_attempted")
        print(f"fixture_unchanged_location={after_location}")
        print(f"fixture_unchanged_rotation={after_rotation}")
        print(f"authorized_action_count={len(action_plan.actions)}")
    except Exception as exc:
        print(f"LIVE QWEN ATLAS RUNTIME BOUNDARY FAILED: {exc}")
        return 1
    finally:
        state_file.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
