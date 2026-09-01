import json

import pytest

from planning.action_plan import ActionSpec
from planning.action_authorization import ActionAuthorization
from planning.autonomous_runtime import AutonomousFutureRuntime
from planning.future_generator import DeterministicFutureGenerator
from planning.parent_marker_task import parent_target_evaluator
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore


def _runtime(tmp_path):
    action = ActionSpec("parent_object", {"file_name": "scene.blend"})
    evaluator = parent_target_evaluator()
    future = DeterministicFutureGenerator(evaluator).generate(False, [action])
    store = FutureRuntimeStateStore(str(tmp_path / "runtime.json"))
    context = RuntimeContext("parent marker", {"file": "scene.blend"})
    runtime = AutonomousFutureRuntime(future, store, context)
    return future, store, context, runtime


def test_persisted_envelope_mutation_fails_closed(tmp_path):
    future, store, context, runtime = _runtime(tmp_path)
    runtime.run_until_pause(lambda *_: {"ok": True})

    payload = json.loads((tmp_path / "runtime.json").read_text())
    payload["snapshot"]["current_step"]["step_id"] = "tampered-step"
    (tmp_path / "runtime.json").write_text(json.dumps(payload))

    with pytest.raises(RuntimeError):
        AutonomousFutureRuntime.resume_from_store(future, store, context)


def test_persisted_integrity_receipt_mutation_fails_closed(tmp_path):
    future, store, context, runtime = _runtime(tmp_path)
    runtime.run_until_pause(lambda *_: {"ok": True})

    payload = json.loads((tmp_path / "runtime.json").read_text())
    payload["runtime_integrity"]["plan_digest"] = "tampered"
    (tmp_path / "runtime.json").write_text(json.dumps(payload))

    with pytest.raises(RuntimeError):
        AutonomousFutureRuntime.resume_from_store(future, store, context)
