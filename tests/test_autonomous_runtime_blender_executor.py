from action_plan import ActionSpec
from planning.autonomous_runtime import AutonomousFutureRuntime
from planning.blender_autonomous_executor import BlenderAutonomousExecutor
from planning.future_generator import DeterministicFutureGenerator
from planning.parent_marker_task import parent_target_evaluator
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore


def _steps():
    action = ActionSpec(
        "parent_object",
        {
            "file_name": "fixture.blend",
            "child_name": "Atlas_Marker",
            "parent_name": "Goal_Left_post",
        },
        "parent",
    )
    return DeterministicFutureGenerator(parent_target_evaluator()).generate(False, [action])


def _context():
    return RuntimeContext(
        "Ensure Atlas_Marker is parented to Goal_Left_post in the supplied Blender fixture.",
        {"environment": "local-blender", "file": "fixture.blend"},
    )


def test_autonomous_runtime_executes_action_through_verified_blender_executor(tmp_path):
    calls = []

    def fake_blender(tool, arguments):
        calls.append((tool, arguments))
        return {
            "ok": True,
            "state": "parented",
            "details": {
                "child_name": arguments["child_name"],
                "parent_name": arguments["parent_name"],
            },
        }

    executor = BlenderAutonomousExecutor(fake_blender)
    runtime = AutonomousFutureRuntime(
        _steps(),
        FutureRuntimeStateStore(tmp_path / "runtime.json"),
        _context(),
    )

    paused = runtime.run_until_pause(
        executor,
        acknowledgements={
            "evidence.authoritative": {"source": "fresh_blender_evidence"},
            "target.evaluated": {"satisfied": False},
        },
    )

    assert paused["current_step"]["phase"] == "VERIFICATION"
    assert calls == [
        (
            "parent_object",
            {
                "file_name": "fixture.blend",
                "child_name": "Atlas_Marker",
                "parent_name": "Goal_Left_post",
            },
        )
    ]
    assert executor.receipt_matches_last_execution(
        "parent_object",
        {
            "file_name": "fixture.blend",
            "child_name": "Atlas_Marker",
            "parent_name": "Goal_Left_post",
        },
    )
