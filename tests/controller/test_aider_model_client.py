"""Offline tests for the bounded Aider model-process boundary."""

import subprocess

import pytest

from controller.aider_model_client import AiderModelClient


class FakeProcess:
    def __init__(self, *, timeout=False):
        self.timeout = timeout
        self.returncode = 0
        self.terminated = False
        self.killed = False

    def communicate(self, timeout=None):
        if self.timeout and not self.terminated and not self.killed:
            raise subprocess.TimeoutExpired(
                ["aider"],
                timeout,
                output="partial-out",
                stderr="partial-err",
            )
        if self.killed:
            return "killed-out", "killed-err"
        if self.terminated:
            return "terminated-out", "terminated-err"
        return "complete-out", "complete-err"

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.killed = True
        self.returncode = -9


def test_aider_turn_uses_explicit_working_directory_and_no_shell():
    calls = []
    process = FakeProcess()

    def factory(command, **kwargs):
        calls.append((command, kwargs))
        return process

    client = AiderModelClient(
        working_directory="C:/Atlas/unreal",
        extra_args=("--yes-always",),
        process_factory=factory,
    )

    result = client.run_turn("Inspect the controller boundary.", timeout_seconds=30)

    assert result.timed_out is False
    assert result.returncode == 0
    assert result.stdout == "complete-out"
    assert calls[0][0] == [
        "aider",
        "--yes-always",
        "--message",
        "Inspect the controller boundary.",
    ]
    assert calls[0][1]["cwd"] == "C:/Atlas/unreal"
    assert calls[0][1]["shell"] is False
    assert calls[0][1]["stdin"] is subprocess.DEVNULL


def test_aider_turn_terminates_and_reports_stall():
    process = FakeProcess(timeout=True)

    client = AiderModelClient(
        working_directory="C:/Atlas/unreal",
        process_factory=lambda command, **kwargs: process,
    )

    result = client.run_turn("Continue the task.", timeout_seconds=0.1)

    assert result.timed_out is True
    assert process.terminated is True
    assert process.killed is False
    assert result.stdout == "partial-outterminated-out"
    assert result.stderr == "partial-errterminated-err"


def test_aider_turn_rejects_non_finite_timeout_before_starting_process():
    calls = []

    def factory(command, **kwargs):
        calls.append((command, kwargs))
        return FakeProcess()

    client = AiderModelClient(
        working_directory="C:/Atlas/unreal",
        process_factory=factory,
    )

    with pytest.raises(ValueError, match="finite positive"):
        client.run_turn("Continue the task.", timeout_seconds=float("inf"))

    assert calls == []
