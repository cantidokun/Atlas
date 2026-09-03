import pytest

from action_plan import ActionSpec
from planning.action_authorization import ActionAuthorization
from planning.authorized_task_runtime import AuthorizedTaskRuntimeError, start_authorized_task_runtime
from planning.evidence_plan import EvidenceRequest
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition


def _task():
    evaluator = TargetStateEvaluator([StateInvariant("ready", lambda evidence: bool(evidence.get("ready")))])
    return AtlasTaskDefinition(
        name="preauthorized-runtime-test",
        evidence=(EvidenceRequest("inspect_scene", {"file_name": "fixture.blend"}, "scene"),),
        actions=(ActionSpec(
            "move_object",
            {"file_name": "fixture.blend", "object_name": "Goal_Left_post", "location": [1, 2, 3]},
            "move",
        ),),
        evaluator=evaluator,
        allowed_action_tools={"move_object"},
        allow_writes=True,
        verify_after_action=True,
    )


def _context():
    return RuntimeContext("Run a pre-authorized Atlas task.", {"environment": "test"})


def _auth(task):
    return ActionAuthorization.issue([*task.actions], "atlas-preissued")


def test_preissued_authorization_is_reused_without_minting_a_new_receipt(tmp_path):
    task = _task()
    authorization = _auth(task)

    runtime = start_authorized_task_runtime(
        task,
        FutureRuntimeStateStore(tmp_path / "runtime.json"),
        _context(),
        lambda tool, arguments: {"ready": False},
        authorization,
    )

    assert runtime.authorization is authorization
    assert runtime.authorization.authorization_id == "atlas-preissued"
    assert runtime.runtime.metadata["authorization_source"] == "atlas_preissued"
    assert runtime.runtime.metadata["action_authorization"]["plan_digest"] == authorization.plan_digest


def test_preissued_authorization_must_match_exact_action_plan(tmp_path):
    task = _task()
    mismatched = ActionAuthorization.issue(
        [ActionSpec("move_object", {"file_name": "fixture.blend", "object_name": "Other", "location": [1, 2, 3]}, "move")],
        "atlas-preissued",
    )

    with pytest.raises(AuthorizedTaskRuntimeError, match="does not match"):
        start_authorized_task_runtime(
            task,
            FutureRuntimeStateStore(tmp_path / "runtime.json"),
            _context(),
            lambda tool, arguments: {"ready": False},
            mismatched,
        )


def test_preissued_authorization_requires_unsatisfied_target(tmp_path):
    task = _task()
    authorization = _auth(task)

    with pytest.raises(AuthorizedTaskRuntimeError, match="satisfied task"):
        start_authorized_task_runtime(
            task,
            FutureRuntimeStateStore(tmp_path / "runtime.json"),
            _context(),
            lambda tool, arguments: {"ready": True},
            authorization,
        )


def test_invalid_authorization_type_is_rejected_before_evidence(tmp_path):
    calls = []

    with pytest.raises(TypeError, match="ActionAuthorization"):
        start_authorized_task_runtime(
            _task(),
            FutureRuntimeStateStore(tmp_path / "runtime.json"),
            _context(),
            lambda tool, arguments: calls.append((tool, arguments)) or {"ready": False},
            object(),
        )

    assert calls == []
