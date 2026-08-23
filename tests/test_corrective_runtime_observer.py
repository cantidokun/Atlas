from planning.corrective_runtime_observer import CorrectiveRuntimeObserver


def test_observer_calls_interruption_hook_between_observations():
    state = {"value": 0}
    events = []

    def observe():
        return dict(state)

    def on_step(step, evidence):
        events.append((step, evidence["value"]))
        if step == 0:
            state["value"] = 99

    observer = CorrectiveRuntimeObserver(observe, on_step)

    assert observer()["value"] == 0
    assert observer()["value"] == 99
    assert events == [(0, 0), (1, 99)]
