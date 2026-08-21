from planning.autonomous_runtime import AutonomousFutureRuntime
from planning.future_generator import FutureStep
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore


def _steps():
    return [
        FutureStep(0, "evidence.authoritative", "EVIDENCE", "Use fresh evidence."),
        FutureStep(1, "target.evaluated", "TARGET", "Use the resolved target."),
        FutureStep(
            2,
            "action.0",
            "ACTION",
            "Execute the authorized Blender action.",
            {"tool": "move_object", "arguments": {"file_name": "fixture.blend", "object_name": "Goal_Left_post", "location": [0.25, 0.0, 0.0]}},
        ),
        FutureStep(3, "verification.pending", "VERIFICATION", "Verify fresh Blender state."),
        FutureStep(4, "complete", "COMPLETE", "Declare completion only after verification."),
    ]


def _context():
    return RuntimeContext(
        "Move Goal_Left_post and verify its final location.",
        {"environment": "local-blender", "file": "fixture.blend"},
    )


def _acknowledgements():
    return {
        "evidence.authoritative": {"source": "fresh_blender_evidence"},
        "target.evaluated": {"satisfied": False},
    }


def test_verification_resolver_acquires_fresh_evidence_and_allows_continuation(tmp_path):
    calls = []

    def execute(tool, arguments):
        calls.append((tool, arguments))
        if tool == "move_object":
            return {"ok": True, "status": "moved"}
        if tool == "inspect_object_transform":
            return {"ok": True, "object_name": "Goal_Left_post", "location": [0.25, 0.0, 0.0]}
        raise AssertionError(f"unexpected tool: {tool}")

    def resolve(step, executor):
        assert step.step_id == "verification.pending"
        evidence = executor(
            "inspect_object_transform",
            {"file_name": "fixture.blend", "object_name": "Goal_Left_post"},
        )
        assert evidence["ok"] is True
        return {"satisfied": evidence["location"] == [0.25, 0.0, 0.0], "evidence": evidence}

    runtime = AutonomousFutureRuntime(_steps(), FutureRuntimeStateStore(tmp_path / "runtime.json"), _context())
    result = runtime.run_until_pause(execute, acknowledgements=_acknowledgements(), verification_resolver=resolve)

    assert result["complete"] is True
    assert [call[0] for call in calls] == ["move_object", "inspect_object_transform"]


def test_failed_fresh_verification_blocks_runtime(tmp_path):
    calls = []

    def execute(tool, arguments):
        calls.append(tool)
        return {"ok": True, "location": [0.0, 0.0, 0.0]}

    def resolve(step, executor):
        evidence = executor("inspect_object_transform", {"file_name": "fixture.blend", "object_name": "Goal_Left_post"})
        return {"satisfied": False, "evidence": evidence}

    runtime = AutonomousFutureRuntime(_steps(), FutureRuntimeStateStore(tmp_path / "runtime.json"), _context())
    result = runtime.run_until_pause(execute, acknowledgements=_acknowledgements(), verification_resolver=resolve)

    assert result["blocked"] is True
    assert result["failure"]["step_id"] == "verification.pending"
    assert calls == ["move_object", "inspect_object_transform"]
