import json

import pytest

from planning.autonomous_runtime import AutonomousFutureRuntime
from planning.future_generator import FutureStep
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore


def steps():
    return [
        FutureStep(0, "evidence.authoritative", "EVIDENCE", "acknowledge evidence"),
        FutureStep(1, "verification.pending", "VERIFICATION", "verify result"),
        FutureStep(2, "complete", "COMPLETE", "complete after verification"),
    ]


def context(instructions="stable Atlas instructions"):
    return RuntimeContext(instructions, {"environment": "test"})


def test_initial_checkpoint_persists_integrity_receipt(tmp_path):
    store = FutureRuntimeStateStore(tmp_path / "runtime.json")
    runtime = AutonomousFutureRuntime(steps(), store, context())

    envelope = store.load()
    receipt = envelope["runtime_integrity"]
    assert receipt["stable_fingerprint"] == context().stable_fingerprint()
    assert receipt["plan_digest"] == runtime.controller.plan_digest
    assert receipt["state_digest"]


def test_resume_requires_matching_stable_context(tmp_path):
    store = FutureRuntimeStateStore(tmp_path / "runtime.json")
    AutonomousFutureRuntime(steps(), store, context())

    with pytest.raises(RuntimeError, match="integrity"):
        AutonomousFutureRuntime(steps(), store, context("changed stable instructions")).resume()


def test_resume_rejects_tampered_integrity_receipt(tmp_path):
    path = tmp_path / "runtime.json"
    store = FutureRuntimeStateStore(path)
    AutonomousFutureRuntime(steps(), store, context())

    envelope = store.load()
    envelope["runtime_integrity"]["state_digest"] = "tampered"
    path.write_text(json.dumps(envelope), encoding="utf-8")

    with pytest.raises(RuntimeError, match="integrity"):
        AutonomousFutureRuntime(steps(), store, context()).resume()


def test_resume_rejects_missing_integrity_receipt(tmp_path):
    path = tmp_path / "runtime.json"
    store = FutureRuntimeStateStore(path)
    AutonomousFutureRuntime(steps(), store, context())

    envelope = store.load()
    del envelope["runtime_integrity"]
    path.write_text(json.dumps(envelope), encoding="utf-8")

    with pytest.raises(RuntimeError, match="integrity"):
        AutonomousFutureRuntime(steps(), store, context()).resume()


def test_resume_with_matching_integrity_continues_exact_checkpoint(tmp_path):
    store = FutureRuntimeStateStore(tmp_path / "runtime.json")
    runtime = AutonomousFutureRuntime(steps(), store, context())
    runtime.run_until_pause(lambda tool, arguments: {"ok": True}, acknowledgements={"evidence.authoritative": {"source": "test"}})

    resumed = AutonomousFutureRuntime(steps(), store, context()).resume()
    assert resumed.snapshot()["current_index"] == 1
    assert resumed.snapshot()["history"][0]["step_id"] == "evidence.authoritative"
