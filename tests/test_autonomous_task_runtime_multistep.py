from action_plan import ActionSpec
from planning.autonomous_task_runtime import AutonomousTaskRuntime
from planning.evidence_plan import EvidenceRequest
from planning.replan_authorization import ReplanAuthorization
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition


def _task():
    evaluator = TargetStateEvaluator(
        [StateInvariant("ready", lambda evidence: bool(evidence.get("ready")))]
    )
    return AtlasTaskDefinition(
        name="autonomous-multistep-recovery-test",
        evidence=(EvidenceRequest("inspect_scene", {"file_name": "fixture.blend"}, "scene"),),
        actions=(
            ActionSpec(
                "move_object",
                {"file_name": "fixture.blend", "object_name": "Goal_Left_post", "location": [1, 2, 3]},
                "move_goalpost",
            ),
            ActionSpec(
                "set_object_rotation",
                {"file_name": "fixture.blend", "object_name": "Goal_Left_post", "rotation_degrees": [0, 0, 15]},
                "rotate_goalpost",
            ),
        ),
        evaluator=evaluator,
        allowed_action_tools={"move_object", "set_object_rotation"},
        allow_writes=True,
        verify_after_action=True,
    )


def _context():
    return RuntimeContext(
        "Execute a two-step soccer-field object preparation task with recovery.",
        {"environment": "test", "file": "fixture.blend", "task": "autonomous-multistep-recovery-test"},
    )


def test_multistep_recovery_preserves_completed_progress(tmp_path):
    store = FutureRuntimeStateStore(tmp_path / "runtime.json")
    task = _task()
    calls = []
    moved = False
    rotated = False
    rotation_attempts = 0

    def execute(tool, arguments):
        nonlocal moved, rotated, rotation_attempts
        calls.append(tool)
        if tool == "inspect_scene":
            return {"ok": True, "ready": moved and rotated}
        if tool == "move_object":
            moved = True
            return {"ok": True, "state": "moved"}
        if tool == "set_object_rotation":
            rotation_attempts += 1
            if rotation_attempts == 1:
                raise RuntimeError("second action failed")
            rotated = True
            return {"ok": True, "state": "rotated"}
        raise RuntimeError(f"unexpected tool: {tool}")

    runtime = AutonomousTaskRuntime.start(
        task,
        store,
        _context(),
        execute,
        authorization_id="multistep-initial-authorization",
    )

    failed = runtime.run_until_pause()

    assert failed["blocked"] is True
    assert failed["failure"]["phase"] == "ACTION"
    assert failed["failure"]["step_id"] == "action.1"
    assert failed["failure"]["sequence"] == 3
    assert calls == ["inspect_scene", "move_object", "set_object_rotation"]

    recovery = runtime.recover_with_fresh_evidence()
    assert recovery["decision"]["disposition"] == "REPLAN_REQUIRED"

    replacement = [
        ActionSpec(
            "set_object_rotation",
            {"file_name": "fixture.blend", "object_name": "Goal_Left_post", "rotation_degrees": [0, 0, 15]},
            "replanned_rotate_goalpost",
        )
    ]
    receipt = runtime.authorize_replan(replacement, "multistep-replan-authorization")
    assert isinstance(receipt, ReplanAuthorization)
    runtime.install_authorized_replan(receipt, replacement)

    assert runtime.runtime.controller.current_step.phase == "ACTION"
    result = runtime.run_until_pause()

    assert result["complete"] is True
    assert calls == [
        "inspect_scene",
        "move_object",
        "set_object_rotation",
        "inspect_scene",
        "set_object_rotation",
        "inspect_scene",
    ]
    assert calls.count("move_object") == 1
    assert rotation_attempts == 2
    assert moved is True
    assert rotated is True
