import json

import pytest

from action_plan import ActionSpec
from planning.autonomous_runtime import AutonomousFutureRuntime
from planning.future_generator import DeterministicFutureGenerator
from planning.object_rename_task import object_rename_target_evaluator
from planning.parent_marker_task import parent_target_evaluator
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore


def _steps(satisfied=False):
    action = ActionSpec("parent_object", {"file_name": "fixture.blend", "child_name": "Atlas_Marker", "parent_name": "Goal_Left_post"}, "parent")
    return DeterministicFutureGenerator(parent_target_evaluator()).generate(satisfied, [action])


def _rename_steps(satisfied=False):
    action = ActionSpec(
        "rename_object",
        {"file_name": "rename.blend", "object_name": "Goal_Left_post", "new_name": "Goal_Left_Post"},
        "rename",
    )
    return DeterministicFutureGenerator(object_rename_target_evaluator()).generate(satisfied, [action])


def _context():
    return RuntimeContext("Ensure Atlas_Marker is parented to Goal_Left_post in the supplied Blender fixture.", {"environment": "local-blender", "file": "fixture.blend"})


def _rename_context():
    return RuntimeContext("Ensure Goal_Left_post is renamed to Goal_Left_Post in the supplied Blender fixture.", {"environment": "local-blender", "file": "rename.blend"})


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


def test_rename_task_pauses_and_resumes_to_completion(tmp_path):
    store = FutureRuntimeStateStore(tmp_path / "rename-runtime.json")
    runtime = AutonomousFutureRuntime(_rename_steps(False), store, _rename_context())
    paused = runtime.run_until_pause(
        lambda tool, arguments: {"ok": True},
        acknowledgements=_acknowledgements(False),
    )
    assert paused["current_step"]["phase"] == "VERIFICATION"

    resumed = AutonomousFutureRuntime.resume_from_store(_rename_steps(False), store, _rename_context())
    result = resumed.run_until_pause(
        lambda tool, arguments: {"ok": True},
        verifications={"verification.pending": {"satisfied": True}},
    )
    assert result["complete"] is True


def test_rename_task_already_correct_future_contains_no_write(tmp_path):
    steps = _rename_steps(True)
    assert all(step.phase != "ACTION" for step in steps)
    store = FutureRuntimeStateStore(tmp_path / "rename-correct.json")
    runtime = AutonomousFutureRuntime(steps, store, _rename_context())
    paused = runtime.run_until_pause(
        lambda tool, arguments: {"ok": False},
        acknowledgements=_acknowledgements(True),
    )
    assert paused["current_step"]["phase"] == "VERIFICATION"


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
