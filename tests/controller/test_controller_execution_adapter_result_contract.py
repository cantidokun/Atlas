from controller.controller_execution_adapter import ControllerExecutionAdapter


TASK = "Authorized to modify Goal_Left_post and move it to midpoint [0.0, 0.0, 0.0]"


def test_controller_adapter_marks_canonical_false_result_unsuccessful():
    ledger = []
    adapter = ControllerExecutionAdapter("scene.blend", TASK, ledger)
    assert adapter.active

    # The controller's first required action is evidence. The adapter must
    # never classify an explicit canonical failure as successful evidence.
    history = []
    adapter.execute_required_step(
        lambda *_: {"ok": False, "state": "failed", "details": {"reason": "fixture"}},
        history,
    )

    assert history[-1]["successful"] is False
    assert ledger == []


def test_controller_adapter_preserves_legacy_success_results():
    ledger = []
    adapter = ControllerExecutionAdapter("scene.blend", TASK, ledger)
    history = []

    adapter.execute_required_step(
        lambda *_: {
            "status": "ok",
            "object_a": {"name": "Goal_Left_post", "location": [-1.0, 0.0, 0.0]},
            "object_b": {"name": "Goal_Right_Post", "location": [1.0, 0.0, 0.0]},
            "midpoint": [0.0, 0.0, 0.0],
        },
        history,
    )

    assert history[-1]["successful"] is True
    assert len(ledger) == 1
