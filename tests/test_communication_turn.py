"""Offline coverage for bounded model-turn communication supervision."""

import pytest

from controller.communication_gateway import CommunicationProtocolError
from controller.communication_runtime import ControllerCommunicationRuntime
from controller.communication_turn import ModelTurnSupervisor, TurnState


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def test_turn_deadline_is_fixed_even_when_heartbeats_arrive():
    clock = FakeClock()
    supervisor = ModelTurnSupervisor(clock=clock)

    started = supervisor.begin("turn-1", 30)
    clock.advance(10)
    heartbeat = supervisor.heartbeat("turn-1")
    clock.advance(19)
    current = supervisor.poll()

    assert started.state is TurnState.RUNNING
    assert heartbeat.state is TurnState.RUNNING
    assert current.state is TurnState.RUNNING
    assert current.deadline == 130.0
    assert current.last_heartbeat == 110.0


def test_turn_expires_without_blocking_or_sleeping():
    clock = FakeClock()
    supervisor = ModelTurnSupervisor(clock=clock)
    supervisor.begin("turn-1", 5)

    clock.advance(5)
    expired = supervisor.poll()

    assert expired.state is TurnState.TIMED_OUT
    assert expired.expired is True
    assert expired.error == "model turn deadline exceeded"


def test_completion_before_deadline_is_terminal():
    clock = FakeClock()
    supervisor = ModelTurnSupervisor(clock=clock)
    supervisor.begin("turn-1", 5)
    clock.advance(4)

    completed = supervisor.complete("turn-1")

    assert completed.state is TurnState.COMPLETED
    assert supervisor.poll().state is TurnState.COMPLETED


def test_completion_after_deadline_cannot_resurrect_timed_out_turn():
    clock = FakeClock()
    supervisor = ModelTurnSupervisor(clock=clock)
    supervisor.begin("turn-1", 5)
    clock.advance(5)

    completed = supervisor.complete("turn-1")

    assert completed.state is TurnState.TIMED_OUT
    with pytest.raises(CommunicationProtocolError, match="already timed_out"):
        supervisor.complete("turn-1")


def test_turn_rejects_wrong_identity_and_invalid_deadline():
    supervisor = ModelTurnSupervisor(clock=FakeClock())

    with pytest.raises(CommunicationProtocolError, match="turn_id"):
        supervisor.begin("", 5)
    with pytest.raises(CommunicationProtocolError, match="greater than zero"):
        supervisor.begin("turn-1", 0)

    supervisor.begin("turn-1", 5)
    with pytest.raises(CommunicationProtocolError, match="does not match"):
        supervisor.heartbeat("turn-2")


def test_terminal_turn_rejects_late_heartbeat():
    supervisor = ModelTurnSupervisor(clock=FakeClock())
    supervisor.begin("turn-1", 5)
    supervisor.cancel("turn-1")

    with pytest.raises(CommunicationProtocolError, match="already cancelled"):
        supervisor.heartbeat("turn-1")


def test_runtime_exposes_model_turn_lifecycle_through_existing_gateway_contract():
    clock = FakeClock()
    runtime = ControllerCommunicationRuntime(lambda tool, arguments: {"status": "ok"}, clock=clock)

    started = runtime.handle_command(
        "session-1",
        "start-task",
        {
            "command": "start_task",
            "arguments": {"file_name": "fixture.blend", "task_text": "inspect"},
        },
    )
    assert started["model_turn"]["state"] == "idle"

    begun = runtime.handle_command(
        "session-1",
        "turn-begin",
        {
            "command": "model_begin",
            "arguments": {"turn_id": "turn-1", "timeout_seconds": 20},
        },
    )
    assert begun["model_turn"]["state"] == "running"
    assert begun["model_turn"]["deadline"] == 120.0

    clock.advance(21)
    status = runtime.handle_command(
        "session-1",
        "turn-status",
        {"command": "model_status", "arguments": {}},
    )
    assert status["model_turn"]["state"] == "timed_out"
    assert status["model_turn"]["expired"] is True


def test_runtime_model_failure_is_explicit_and_not_an_implicit_retry():
    clock = FakeClock()
    runtime = ControllerCommunicationRuntime(lambda tool, arguments: {"status": "ok"}, clock=clock)
    runtime.handle_command(
        "session-1",
        "start-task",
        {
            "command": "start_task",
            "arguments": {"file_name": "fixture.blend", "task_text": "inspect"},
        },
    )
    runtime.handle_command(
        "session-1",
        "turn-begin",
        {
            "command": "model_begin",
            "arguments": {"turn_id": "turn-1", "timeout_seconds": 20},
        },
    )

    failed = runtime.handle_command(
        "session-1",
        "turn-fail",
        {
            "command": "model_fail",
            "arguments": {"turn_id": "turn-1", "error": "provider unavailable"},
        },
    )

    assert failed["model_turn"]["state"] == "failed"
    assert failed["model_turn"]["error"] == "provider unavailable"
