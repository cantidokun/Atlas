import json

import pytest

from action_plan import ActionSpec
from planning.autonomous_task_runtime import AutonomousTaskRuntime
from planning.evidence_plan import EvidenceRequest
from planning.future_generator import DeterministicFutureGenerator
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
        name="autonomous-runtime-test",
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
        "Make the supplied Blender fixture satisfy the autonomous runtime test.",
        {"environment": "local-blender", "file": "fixture.blend"},
    )


def test_task_runtime_runs_action_then_fresh_verification(tmp_path):
    calls = []
    evidence_calls = 0

    def execute(tool, arguments):
        nonlocal evidence_calls
        calls.append((tool, arguments))
        if tool == "inspect_scene":
            evidence_calls += 1
            return {"ok": True, "state": "inspected", "ready": evidence_calls >= 2}
        return {"ok": True, "state": "moved", "details": {"object_name": arguments["object_name"]}}

    runtime = AutonomousTaskRuntime.start(
        _task(),
        FutureRuntimeStateStore(tmp_path / "runtime.json"),
        _context(),
        execute,
        authorization_id="test-autonomous-runtime",
    )

    result = runtime.run_until_pause()

    assert result["complete"] is True
    assert [tool for tool, _ in calls] == ["inspect_scene", "move_object", "inspect_scene"]
    assert runtime.authorization is not None
    assert runtime.authorization.authorization_id == "test-autonomous-runtime"


def test_task_runtime_skips_write_when_target_is_already_satisfied(tmp_path):
    calls = []

    def execute(tool, arguments):
        calls.append((tool, arguments))
        return {"ok": True, "state": "inspected", "ready": True}

    runtime = AutonomousTaskRuntime.start(
        _task(),
        FutureRuntimeStateStore(tmp_path / "runtime.json"),
        _context(),
        execute,
        authorization_id="unused-for-zero-write",
    )

    result = runtime.run_until_pause()

    assert result["complete"] is True
    assert [tool for tool, _ in calls] == ["inspect_scene", "inspect_scene"]
    assert runtime.authorization is None


def test_task_runtime_blocks_when_fresh_verification_fails(tmp_path):
    calls = []
    evidence_calls = 0

    def execute(tool, arguments):
        nonlocal evidence_calls
        calls.append((tool, arguments))
        if tool == "inspect_scene":
            evidence_calls += 1
            return {"ok": True, "state": "inspected", "ready": False}
        return {"ok": True, "state": "moved", "details": {}}

    runtime = AutonomousTaskRuntime.start(
        _task(),
        FutureRuntimeStateStore(tmp_path / "runtime.json"),
        _context(),
        execute,
        authorization_id="test-verification-failure",
    )

    result = runtime.run_until_pause()

    assert result["blocked"] is True
    assert result["history"][-1]["phase"] == "VERIFICATION"
    assert result["history"][-1]["status"] == "failed"
    assert [tool for tool, _ in calls] == ["inspect_scene", "move_object", "inspect_scene"]


def test_task_runtime_verification_executor_exception_blocks(tmp_path):
    calls = []
    evidence_calls = 0

    def execute(tool, arguments):
        nonlocal evidence_calls
        calls.append((tool, arguments))
        if tool == "inspect_scene":
            evidence_calls += 1
            if evidence_calls == 2:
                raise RuntimeError("verification transport failed")
            return {"ok": True, "state": "inspected", "ready": False}
        return {"ok": True, "state": "moved", "details": {}}

    runtime = AutonomousTaskRuntime.start(
        _task(),
        FutureRuntimeStateStore(tmp_path / "runtime.json"),
        _context(),
        execute,
        authorization_id="test-verification-exception",
    )

    result = runtime.run_until_pause()

    assert result["blocked"] is True
    assert result["failure"]["phase"] == "VERIFICATION"
    assert result["failure"]["result"]["exception_type"] == "RuntimeError"
    assert "verification transport failed" in result["failure"]["result"]["error"]
    assert [tool for tool, _ in calls] == ["inspect_scene", "move_object", "inspect_scene"]


def test_task_runtime_resume_reuses_persisted_authorized_future(tmp_path):
    calls = []
    moved = False
    store = FutureRuntimeStateStore(tmp_path / "runtime.json")
    task = _task()
    context = _context()

    def execute(tool, arguments):
        nonlocal moved
        calls.append((tool, arguments))
        if tool == "inspect_scene":
            return {"ok": True, "state": "inspected", "ready": moved}
        moved = True
        return {"ok": True, "state": "moved", "details": {"object_name": arguments["object_name"]}}

    runtime = AutonomousTaskRuntime.start(
        task,
        store,
        context,
        execute,
        authorization_id="test-resume",
    )

    metadata = store.load()["metadata"]
    assert metadata["target_satisfied"] is False
    assert runtime.runtime.steps[2].phase == "ACTION"
    assert runtime.authorization is not None

    paused = runtime.runtime.run_until_pause(
        runtime._run_executor(),
        acknowledgements={
            "evidence.authoritative": {"source": "test", "task": task.name},
            "target.evaluated": {"satisfied": False},
        },
    )
    assert paused["current_step"]["phase"] == "VERIFICATION"
    assert [tool for tool, _ in calls] == ["inspect_scene", "move_object"]

    reloaded = AutonomousTaskRuntime.resume_from_store(
        task,
        store,
        context,
        execute,
    )
    assert reloaded.authorization is not None
    assert reloaded.authorization.authorization_id == "test-resume"

    result = reloaded.resume_and_run()

    assert result["complete"] is True
    assert [tool for tool, _ in calls] == ["inspect_scene", "move_object", "inspect_scene"]


def test_task_runtime_rejects_persisted_authorization_for_future_shape(tmp_path):
    store = FutureRuntimeStateStore(tmp_path / "runtime.json")
    task = _task()

    runtime = AutonomousTaskRuntime.start(
        task,
        store,
        _context(),
        lambda tool, arguments: {"ready": False},
        authorization_id="test-invalid-binding",
    )
    assert runtime.authorization is not None

    envelope = store.load()
    envelope["metadata"]["action_authorization"]["plan_digest"] = "0" * 64
    store.path.write_text(json.dumps(envelope), encoding="utf-8")

    with pytest.raises(RuntimeError, match="action plan"):
        AutonomousTaskRuntime.resume_from_store(task, store, _context(), lambda tool, arguments: {})


def test_deterministic_future_unsatisfied_branch_contains_action():
    task = _task()
    steps = DeterministicFutureGenerator(task.evaluator).generate(False, [
        ActionSpec(
            "move_object",
            {"file_name": "fixture.blend", "object_name": "Goal_Left_post", "location": [1, 2, 3]},
            "move",
        )
    ])
    assert steps[2].phase == "ACTION"
    assert steps[2].step_id == "action.0"
    assert steps[3].phase == "VERIFICATION"


def test_task_runtime_recovery_requires_fresh_evidence_and_new_authorization(tmp_path):
    calls = []
    move_attempts = 0
    evidence_calls = 0
    store = FutureRuntimeStateStore(tmp_path / "runtime.json")
    task = _task()

    def execute(tool, arguments):
        nonlocal move_attempts, evidence_calls
        calls.append((tool, arguments))
        if tool == "inspect_scene":
            evidence_calls += 1
            return {"ok": True, "state": "inspected", "ready": evidence_calls >= 2}
        move_attempts += 1
        if move_attempts == 1:
            raise RuntimeError("first write failed")
        return {"ok": True, "state": "moved", "details": {"object_name": arguments["object_name"]}}

    runtime = AutonomousTaskRuntime.start(
        task,
        store,
        _context(),
        execute,
        authorization_id="initial-authorization",
    )

    failed = runtime.run_until_pause()
    assert failed["blocked"] is True
    assert runtime.recovery_gate is None

    replacement = [
        ActionSpec(
            "move_object",
            {"file_name": "fixture.blend", "object_name": "Goal_Left_post", "location": [2, 3, 4]},
            "replacement",
        )
    ]
    with pytest.raises(RuntimeError, match="Fresh authoritative"):
        runtime.authorize_replan(replacement, "replacement-authorization")

    recovery = runtime.recover_with_fresh_evidence()
    assert recovery["decision"]["disposition"] == "REPLAN_REQUIRED"

    receipt = runtime.authorize_replan(replacement, "replacement-authorization")
    assert isinstance(receipt, ReplanAuthorization)

    runtime.install_authorized_replan(receipt, replacement)
    assert runtime.runtime.controller.current_step.phase == "ACTION"
    result = runtime.run_until_pause()
    assert result["complete"] is True
    assert [tool for tool, _ in calls] == [
        "inspect_scene",
        "move_object",
        "inspect_scene",
        "move_object",
        "inspect_scene",
    ]


def test_task_runtime_recovery_rejects_unauthorized_tools(tmp_path):
    calls = []

    def execute(tool, arguments):
        calls.append((tool, arguments))
        if tool == "inspect_scene":
            return {"ok": True, "state": "inspected", "ready": False}
        raise RuntimeError("write failed")

    runtime = AutonomousTaskRuntime.start(
        _task(),
        FutureRuntimeStateStore(tmp_path / "runtime.json"),
        _context(),
        execute,
        authorization_id="initial-authorization",
    )
    runtime.run_until_pause()
    runtime.recover_with_fresh_evidence()

    with pytest.raises(RuntimeError, match="unauthorized recovery action tools"):
        runtime.authorize_replan(
            [ActionSpec(
                "delete_object",
                {"file_name": "fixture.blend", "object_name": "Goal_Left_post"},
                "delete",
            )],
            "bad-replan",
        )
