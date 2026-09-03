import json

import pytest

from action_plan import ActionSpec
from planning.autonomous_task_runtime import AutonomousTaskRuntime
from planning.evidence_plan import EvidenceRequest
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
        name="production-provenance-test",
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
        metadata={
            "workflow": "broadcast-goal-preparation",
            "workflow_version": 1,
            "production_phase": "layout",
        },
    )


def _context():
    return RuntimeContext(
        "Prepare the supplied soccer production fixture.",
        {"environment": "local-blender", "file": "fixture.blend"},
    )


def _replacement():
    return [
        ActionSpec(
            "move_object",
            {"file_name": "fixture.blend", "object_name": "Goal_Left_post", "location": [2, 3, 4]},
            "replacement",
        )
    ]


def test_semantic_metadata_is_persisted_and_survives_replan(tmp_path):
    store = FutureRuntimeStateStore(tmp_path / "runtime.json")
    task = _task()
    evidence_calls = 0
    move_attempts = 0

    def execute(tool, arguments):
        nonlocal evidence_calls, move_attempts
        if tool == "inspect_scene":
            evidence_calls += 1
            return {"ready": evidence_calls >= 3}
        move_attempts += 1
        if move_attempts == 1:
            raise RuntimeError("controlled write failure")
        return {"ok": True, "state": "moved"}

    runtime = AutonomousTaskRuntime.start(task, store, _context(), execute, "initial")
    assert store.load()["metadata"]["task_metadata"] == task.metadata

    runtime.run_until_pause()
    runtime.recover_with_fresh_evidence()
    receipt = runtime.authorize_replan(_replacement(), "replacement")
    assert isinstance(receipt, ReplanAuthorization)
    runtime.install_authorized_replan(receipt, _replacement())

    persisted = store.load()["metadata"]
    assert persisted["task_metadata"] == task.metadata
    assert runtime.runtime.metadata["task_metadata"] == task.metadata


def test_resume_rejects_tampered_semantic_metadata(tmp_path):
    store = FutureRuntimeStateStore(tmp_path / "runtime.json")
    task = _task()

    runtime = AutonomousTaskRuntime.start(
        task,
        store,
        _context(),
        lambda tool, arguments: {"ready": False},
        "initial",
    )
    assert runtime.runtime.metadata["task_metadata"] == task.metadata

    envelope = store.load()
    envelope["metadata"]["task_metadata"]["workflow_version"] = 999
    store.path.write_text(json.dumps(envelope), encoding="utf-8")

    with pytest.raises(RuntimeError, match="semantic metadata"):
        AutonomousTaskRuntime.resume_from_store(task, store, _context(), lambda tool, arguments: {})


def test_replan_preserves_deep_copied_semantic_metadata(tmp_path):
    store = FutureRuntimeStateStore(tmp_path / "runtime.json")
    task = _task()
    evidence_calls = 0
    move_attempts = 0

    def execute(tool, arguments):
        nonlocal evidence_calls, move_attempts
        if tool == "inspect_scene":
            evidence_calls += 1
            return {"ready": evidence_calls >= 3}
        move_attempts += 1
        if move_attempts == 1:
            raise RuntimeError("controlled write failure")
        return {"ok": True}

    runtime = AutonomousTaskRuntime.start(task, store, _context(), execute, "initial")
    runtime.run_until_pause()
    runtime.recover_with_fresh_evidence()
    replacement = _replacement()
    receipt = runtime.authorize_replan(replacement, "replacement")
    runtime.install_authorized_replan(receipt, replacement)

    task.metadata["workflow"] = "tampered-after-start"
    assert runtime.runtime.metadata["task_metadata"]["workflow"] == "broadcast-goal-preparation"
