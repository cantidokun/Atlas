from action_plan import ActionSpec
from planning.autonomous_task_runtime import AutonomousTaskRuntime
from planning.evidence_plan import EvidenceRequest
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition


def test_multiple_evidence_requests_are_bound_as_named_bundle(tmp_path):
    evaluator = TargetStateEvaluator(
        [
            StateInvariant("location_ready", lambda evidence: evidence["location"]["location_ready"] is True),
            StateInvariant("rotation_ready", lambda evidence: evidence["rotation"]["rotation_ready"] is True),
        ]
    )
    task = AtlasTaskDefinition(
        name="multi-evidence-task",
        evidence=(
            EvidenceRequest("inspect_location", {"file_name": "fixture.blend"}, "location"),
            EvidenceRequest("inspect_rotation", {"file_name": "fixture.blend"}, "rotation"),
        ),
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
    context = RuntimeContext(
        "Evaluate a multi-evidence Atlas task.",
        {"environment": "test", "file": "fixture.blend"},
    )
    calls = []

    def execute(tool, arguments):
        calls.append(tool)
        if tool == "inspect_location":
            return {"location_ready": True}
        if tool == "inspect_rotation":
            return {"rotation_ready": True}
        return {"ok": True}

    runtime = AutonomousTaskRuntime.start(
        task,
        FutureRuntimeStateStore(tmp_path / "runtime.json"),
        context,
        execute,
        authorization_id="multi-evidence-authorization",
    )

    result = runtime.run_until_pause()

    assert result["complete"] is True
    assert calls == ["inspect_location", "inspect_rotation", "inspect_location", "inspect_rotation"]
