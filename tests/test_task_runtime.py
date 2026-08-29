import pytest

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition
from planning.task_runtime import (
    TaskRuntimeSession,
    prepare_task_runtime,
    validate_task_runtime,
)


def task(allow_writes=True, verify=True):
    evaluator = TargetStateEvaluator([StateInvariant("ready", lambda evidence: bool(evidence.get("ready")))])
    return AtlasTaskDefinition(
        "runtime-test",
        (EvidenceRequest("inspect_scene", {"file_name": "x.blend"}, "scene"),),
        (ActionSpec("move_object", {"file_name": "x.blend"}, "move"),),
        evaluator,
        {"move_object"},
        allow_writes=allow_writes,
        verify_after_action=verify,
    )


def _invalid_runtime_definition(*, allow_writes, verify, action_tool="move_object"):
    definition = object.__new__(AtlasTaskDefinition)
    evaluator = TargetStateEvaluator([StateInvariant("ready", lambda evidence: True)])
    object.__setattr__(definition, "name", "runtime-invalid")
    object.__setattr__(definition, "evidence", (EvidenceRequest("inspect_scene", {}, "scene"),))
    object.__setattr__(definition, "actions", (ActionSpec(action_tool, {}, action_tool),))
    object.__setattr__(definition, "evaluator", evaluator)
    object.__setattr__(definition, "allowed_action_tools", {"move_object"})
    object.__setattr__(definition, "allow_writes", allow_writes)
    object.__setattr__(definition, "verify_after_action", verify)
    object.__setattr__(definition, "metadata", None)
    return definition


def test_prepare_runtime_preserves_task_contract():
    runtime = prepare_task_runtime(task())
    assert runtime.evidence_plan.next_request.tool == "inspect_scene"
    assert runtime.conditional_plan.next_action is None
    assert runtime.next_phase() == "EVIDENCE"


def test_runtime_rejects_write_without_verification():
    definition = _invalid_runtime_definition(allow_writes=True, verify=False)
    assert validate_task_runtime(definition) == ("write-capable task requires verification",)
    with pytest.raises(ValueError, match="requires verification"):
        prepare_task_runtime(definition)


def test_runtime_rejects_unauthorized_action_tool():
    definition = _invalid_runtime_definition(allow_writes=False, verify=True, action_tool="delete_object")
    assert validate_task_runtime(definition)[0].startswith("unauthorized action tools")
    with pytest.raises(ValueError, match="unauthorized action tools"):
        prepare_task_runtime(definition)


def test_session_generic_zero_write_lifecycle():
    calls = []

    def execute(tool, arguments):
        calls.append((tool, arguments))
        return {"ready": True}

    session = TaskRuntimeSession(task(), execute, lambda results: results[0])
    assert session.acquire_initial_evidence() == {"ready": True}
    assert session.evaluate_target().satisfied is True
    assert session.phase == "VERIFICATION"
    session.verify_post_action({"ready": True})
    assert session.complete is True
    session.finalize()
    assert calls == [("inspect_scene", {"file_name": "x.blend"})]


def test_session_generic_write_lifecycle_requires_authorization_and_fresh_verification():
    calls = []
    state = {"ready": False}

    def execute(tool, arguments):
        calls.append((tool, arguments))
        if tool == "move_object":
            state["ready"] = True
            return {"ok": True}
        return dict(state)

    session = TaskRuntimeSession(task(), execute, lambda results: results[0])
    assert session.acquire_initial_evidence() == {"ready": False}
    assert session.evaluate_target().satisfied is False
    assert session.phase == "AUTHORIZATION"

    session.authorize("runtime-test-authorization")
    assert session.phase == "ACTION"
    assert session.execute_authorized_action() == {"ok": True}
    assert session.phase == "VERIFICATION"
    assert session.verify_post_action(dict(state)).satisfied is True
    assert session.complete is True
    session.finalize()

    assert calls == [
        ("inspect_scene", {"file_name": "x.blend"}),
        ("move_object", {"file_name": "x.blend"}),
    ]


def test_session_acquires_fresh_post_action_evidence_from_declared_requests():
    state = {"ready": False}
    calls = []

    def execute(tool, arguments):
        calls.append(tool)
        if tool == "move_object":
            state["ready"] = True
            return {"ok": True}
        return dict(state)

    session = TaskRuntimeSession(task(), execute, lambda results: results[0])
    assert session.acquire_initial_evidence() == {"ready": False}
    assert session.evaluate_target().satisfied is False
    session.authorize("fresh-evidence")
    session.execute_authorized_action()
    fresh = session.acquire_post_action_evidence()
    assert fresh == {"ready": True}
    assert session.verify_post_action(fresh).satisfied is True
    assert calls == ["inspect_scene", "move_object", "inspect_scene"]


def test_session_blocks_evaluation_until_all_declared_evidence_is_recorded():
    definition = AtlasTaskDefinition(
        "multi-evidence",
        (
            EvidenceRequest("inspect_scene", {}, "scene"),
            EvidenceRequest("inspect_object", {}, "object"),
        ),
        (ActionSpec("move_object", {}, "move"),),
        TargetStateEvaluator([StateInvariant("ready", lambda evidence: evidence.get("ready") is True)]),
        {"move_object"},
        allow_writes=True,
        verify_after_action=True,
    )

    calls = []

    def execute(tool, arguments):
        calls.append(tool)
        return {"ready": True}

    session = TaskRuntimeSession(definition, execute, lambda results: {"ready": all(r["ready"] for r in results)})
    with pytest.raises(RuntimeError, match="Initial evidence must be acquired"):
        session.evaluate_target()

    session.acquire_initial_evidence()
    assert calls == ["inspect_scene", "inspect_object"]
    assert session.evaluate_target().satisfied is True


def test_session_run_conditional_lifecycle_skips_write_when_target_is_satisfied():
    calls = []

    def execute(tool, arguments):
        calls.append(tool)
        return {"ready": True}

    session = TaskRuntimeSession(task(), execute, lambda results: results[0])
    session.acquire_initial_evidence()
    state, execution, verified = session.run_conditional_lifecycle("skip-write")

    assert state.satisfied is True
    assert execution is None
    assert verified.satisfied is True
    assert session.complete is True
    assert calls == ["inspect_scene", "inspect_scene"]


def test_session_run_conditional_lifecycle_authorizes_executes_and_verifies():
    calls = []
    state = {"ready": False}

    def execute(tool, arguments):
        calls.append(tool)
        if tool == "move_object":
            state["ready"] = True
            return {"ok": True}
        return dict(state)

    session = TaskRuntimeSession(task(), execute, lambda results: results[0])
    session.acquire_initial_evidence()
    initial, execution, verified = session.run_conditional_lifecycle("run-write")

    assert initial.satisfied is False
    assert execution == {"ok": True}
    assert verified.satisfied is True
    assert session.complete is True
    assert calls == ["inspect_scene", "move_object", "inspect_scene"]
