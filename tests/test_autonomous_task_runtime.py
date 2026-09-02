from action_plan import ActionSpec

from planning.autonomous_task_runtime import AutonomousTaskRuntime
from planning.evidence_plan import EvidenceRequest
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
            return {"ok": True, "state": "inspected", "details": {"ready": evidence_calls >= 2}}
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
        return {"ok": True, "state": "inspected", "details": {"ready": True}}

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
            return {"ok": True, "state": "inspected", "details": {"ready": evidence_calls == 1}}
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
