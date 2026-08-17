import tempfile

from planning.autonomous_runtime import AutonomousFutureRuntime
from planning.future_execution import FutureExecutionController
from planning.future_generator import FutureStep
from planning.runtime_state import FutureRuntimeStateStore


def _steps():
    return [
        FutureStep(0, "evidence.authoritative", "EVIDENCE", "evidence"),
        FutureStep(1, "action.0", "ACTION", "write", {"tool": "write", "arguments": {"value": 1}}),
        FutureStep(2, "verification.pending", "VERIFICATION", "verify"),
        FutureStep(3, "complete", "COMPLETE", "complete"),
    ]


def test_runtime_checkpoints_and_resumes_without_reexecuting_completed_action():
    with tempfile.TemporaryDirectory() as tmp:
        store = FutureRuntimeStateStore(f"{tmp}/future.json")
        runtime = AutonomousFutureRuntime(_steps(), store)
        calls = []

        runtime.run_until_pause(lambda tool, args: calls.append((tool, args)) or {"ok": True}, {"evidence.authoritative": {}}, {})
        assert calls == [("write", {"value": 1})]

        resumed = runtime.resume()
        result = resumed.run_until_pause(
            lambda tool, args: calls.append((tool, args)) or {"ok": True},
            verifications={"verification.pending": {"satisfied": True}},
        )
        assert result["complete"] is True
        assert calls == [("write", {"value": 1})]


def test_runtime_never_advances_past_failed_action():
    with tempfile.TemporaryDirectory() as tmp:
        store = FutureRuntimeStateStore(f"{tmp}/future.json")
        runtime = AutonomousFutureRuntime(_steps(), store)
        runtime.run_until_pause(lambda _tool, _args: {"error": "denied"}, {"evidence.authoritative": {}}, {})
        controller = FutureExecutionController.resume_from_snapshot(_steps(), store.load()["snapshot"])
        assert controller.blocked is True
        assert controller.current_step is None
