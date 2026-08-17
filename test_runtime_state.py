import json

import pytest

from planning.future_execution import FutureExecutionController
from planning.future_generator import DeterministicFutureGenerator, FutureStep
from planning.runtime_state import FutureRuntimeStateStore


class _Evaluator:
    pass


def _steps():
    return [
        FutureStep(0, "evidence.authoritative", "EVIDENCE", "evidence"),
        FutureStep(1, "target.evaluated", "TARGET", "target"),
        FutureStep(2, "action.0", "ACTION", "write", {"tool": "write", "arguments": {"value": 1}}),
        FutureStep(3, "verification.pending", "VERIFICATION", "verify"),
        FutureStep(4, "complete", "COMPLETE", "complete"),
    ]


def _at_action():
    controller = FutureExecutionController(_steps())
    controller.acknowledge({"source": "test"})
    controller.acknowledge({"satisfied": False})
    return controller


def test_runtime_state_round_trip(tmp_path):
    controller = _at_action()
    store = FutureRuntimeStateStore(tmp_path / "future.json")

    envelope = store.save(controller)
    assert envelope["version"] == 1
    assert store.load()["plan_digest"] == controller.plan_digest

    resumed = store.resume(_steps())
    assert resumed.current_index == controller.current_index
    assert resumed.plan_digest == controller.plan_digest
    assert resumed.next_action == controller.next_action


def test_runtime_state_rejects_different_plan(tmp_path):
    controller = _at_action()
    store = FutureRuntimeStateStore(tmp_path / "future.json")
    store.save(controller)

    altered = _steps()
    altered[2] = FutureStep(2, "action.0", "ACTION", "write", {"tool": "write", "arguments": {"value": 99}})
    with pytest.raises(RuntimeError, match="does not match"):
        store.resume(altered)


def test_runtime_state_rejects_tampered_envelope(tmp_path):
    controller = _at_action()
    store = FutureRuntimeStateStore(tmp_path / "future.json")
    store.save(controller)

    payload = store.load()
    payload["plan_digest"] = "tampered"
    store.path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="inconsistent"):
        store.load()


def test_runtime_state_uses_atomic_replacement(tmp_path):
    controller = _at_action()
    store = FutureRuntimeStateStore(tmp_path / "nested" / "future.json")
    store.save(controller)
    assert store.path.exists()
    assert not list(store.path.parent.glob(".future.json.*"))
