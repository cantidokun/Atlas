from planning.task_sequence import TaskSequenceDefinition, TaskSequenceSession
from planning.task_definition import AtlasTaskDefinition
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.evidence_plan import EvidenceRequest
from action_plan import ActionSpec


def test_recover_current_skips_repeat_write_after_interruption():
    def reducer(evidence):
        return evidence[-1]

    task = AtlasTaskDefinition(
        name="move",
        evidence=(EvidenceRequest("inspect", {}, "inspect"),),
        actions=(ActionSpec("move", {}, "move"),),
        evaluator=TargetStateEvaluator([
            StateInvariant("moved", lambda evidence: evidence.get("moved") is True),
        ]),
        allowed_action_tools={"move"},
        allow_writes=True,
        verify_after_action=True,
    )
    definition = TaskSequenceDefinition((task,))
    state = {"moved": False, "writes": 0, "crash": True}

    def execute(tool, arguments):
        if tool == "inspect":
            return {"moved": state["moved"]}
        state["moved"] = True
        state["writes"] += 1
        if state["crash"]:
            state["crash"] = False
            raise RuntimeError("simulated process interruption after mutation")
        return {"status": "moved"}

    checkpoint = TaskSequenceSession(definition, execute, (reducer,)).checkpoint()
    interrupted = TaskSequenceSession.resume_from_checkpoint(definition, execute, (reducer,), checkpoint)
    try:
        interrupted.run_current(authorization_id="recovery-test")
    except RuntimeError as exc:
        assert "interruption" in str(exc)

    resumed = TaskSequenceSession.resume_from_checkpoint(definition, execute, (reducer,), checkpoint)
    resumed.recover_current(authorization_id="must-not-be-needed")

    assert state["writes"] == 1
    assert resumed.complete is True
