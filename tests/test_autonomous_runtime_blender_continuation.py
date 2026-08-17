import json

import pytest

from action_plan import ActionSpec
from planning.autonomous_runtime import AutonomousFutureRuntime
from planning.future_generator import DeterministicFutureGenerator
from planning.parent_marker_task import parent_target_evaluator
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore


def _steps(satisfied=False):
    action = ActionSpec("parent_object", {"file_name": "fixture.blend", "child_name": "Atlas_Marker", "parent_name": "Goal_Left_post"}, "parent")
    return DeterministicFutureGenerator(parent_target_evaluator()).generate(satisfied, [action])


def _context():
    return RuntimeContext("Ensure Atlas_Marker is parented to Goal_Left_post in the supplied Blender fixture.", {"environment": "local-blender", "file": "fixture.blend"})


def _acknowledgements(satisfied=False):
    values = {
        "evidence.authoritative": {"source": "fresh_blender_evidence"},
        "target.evaluated": {"satisfied": satisfied},
    }
    if satisfied:
        values["writes.skipped"] = {"reason": "target_already_satisfied"}
    return values


def test_incorrect_future_pauses_at_verification_and_resumes_to_completion(tmp_path):
    store = FutureRuntimeStateStore(tmp_path / "runtime.json")
    runtime = AutonomousFutureRuntime(_steps(False), store, _context())
    paused = runtime.run_until_pause(
        lambda tool, arguments: {"ok": True},
        acknowledgements=_acknowledgements(False),
    )
    assert paused["current_step"]["phase"] == "VERIFICATION"

    resumed = AutonomousFutureRuntime.resume_from_store(_steps(False), store, _context())
    result = resumed.run_until_pause(
        lambda tool, arguments: {"ok": True},
        verifications={"verification.pending": {"satisfied": True}},
    )
    assert result["complete"] is True


def test_tampered_runtime_context_is_rejected_after_checkpoint(tmp_path):
    store = FutureRuntimeStateStore(tmp_path / "runtime.json")
    AutonomousFutureRuntime(_steps(False), store, _context()).run_until_pause(
        lambda tool, arguments: {"ok": True},
        acknowledgements=_acknowledgements(False),
    )
    tampered = RuntimeContext("TAMPERED", {"environment": "local-blender", "file": "fixture.blend"})
    with pytest.raises(RuntimeError, match="integrity"):
        AutonomousFutureRuntime.resume_from_store(_steps(False), store, tampered)


def test_tampered_persisted_snapshot_is_rejected(tmp_path):
    path = tmp_path / "runtime.json"
    store = FutureRuntimeStateStore(path)
    AutonomousFutureRuntime(_steps(False), store, _context()).run_until_pause(
        lambda tool, arguments: {"ok": True},
        acknowledgements=_acknowledgements(False),
    )
    envelope = store.load()
    envelope["snapshot"]["current_index"] = 0
    path.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(RuntimeError):
        AutonomousFutureRuntime.resume_from_store(_steps(False), store, _context())


def test_already_correct_future_contains_no_write(tmp_path):
    steps = _steps(True)
    assert all(step.phase != "ACTION" for step in steps)
    store = FutureRuntimeStateStore(tmp_path / "runtime.json")
    runtime = AutonomousFutureRuntime(steps, store, _context())
    paused = runtime.run_until_pause(
        lambda tool, arguments: {"ok": False},
        acknowledgements=_acknowledgements(True),
    )
    assert paused["current_step"]["phase"] == "VERIFICATION"
