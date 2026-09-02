from action_plan import ActionSpec
from planning.autonomous_task_runtime import AutonomousTaskRuntime
from planning.evidence_plan import EvidenceRequest
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore
from planning.replan_authorization import ReplanAuthorization
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition


def _task():
    evaluator = TargetStateEvaluator(
        [StateInvariant("ready", lambda evidence: bool(evidence.get("ready")))]
    )
    return AtlasTaskDefinition(
        name="autonomous-runtime-restart-test",
        evidence=(EvidenceRequest("inspect_scene", {"file_name": "fixture.blend"}, "scene"),),
        actions=(
            ActionSpec(
                "move_object",
                {"file_name": "fixture.blend", "object_name": "Goal_Left_post", "location": [1, 2, 3]},
                "move",
            ),
        ),
        evaluator=evaluator,
        allowed_action_tools={"move_object"},
        allow_writes=True,
        verify_after_action=True,
    )


def _context():
    return RuntimeContext(
        "Recover a failed autonomous runtime operation across a process restart.",
        {"environment": "test", "file": "fixture.blend"},
    )


def test_recovery_reconstructs_blocked_gate_and_authorization_after_restart(tmp_path):
    store = FutureRuntimeStateStore(tmp_path / "runtime.json")
    task = _task()

    def first_process_execute(tool, arguments):
        if tool == "inspect_scene":
            return {"ok": True, "ready": False}
        raise RuntimeError("write failed before process restart")

    first = AutonomousTaskRuntime.start(
        task,
        store,
        _context(),
        first_process_execute,
        authorization_id="restart-initial-authorization",
    )
    failed = first.run_until_pause()

    assert failed["blocked"] is True
    assert failed["failure"]["phase"] == "ACTION"
    assert store.load()["snapshot"]["blocked"] is True

    calls = []
    replacement_attempts = 0
    verification_calls = 0

    def second_process_execute(tool, arguments):
        nonlocal replacement_attempts, verification_calls
        calls.append(tool)
        if tool == "inspect_scene":
            verification_calls += 1
            return {"ok": True, "ready": verification_calls >= 2}
        replacement_attempts += 1
        return {"ok": True, "state": "moved"}

    restarted = AutonomousTaskRuntime.resume_from_store(
        task,
        store,
        _context(),
        second_process_execute,
    )

    assert restarted.runtime.controller.blocked is True
    assert restarted.recovery_gate is not None
    assert restarted.authorization is not None
    assert restarted.authorization.authorization_id == "restart-initial-authorization"

    recovery = restarted.recover_with_fresh_evidence()
    assert recovery["decision"]["disposition"] == "REPLAN_REQUIRED"

    replacement = [
        ActionSpec(
            "move_object",
            {"file_name": "fixture.blend", "object_name": "Goal_Left_post", "location": [2, 3, 4]},
            "restart-replacement",
        )
    ]
    receipt = restarted.authorize_replan(replacement, "restart-replan-authorization")
    assert isinstance(receipt, ReplanAuthorization)
    restarted.install_authorized_replan(receipt, replacement)

    result = restarted.run_until_pause()

    assert result["complete"] is True
    assert replacement_attempts == 1
    assert calls == ["inspect_scene", "move_object", "inspect_scene"]
