import pytest

from planning.autonomous_runtime import AutonomousFutureRuntime
from planning.production_autonomous_runtime_bridge import ProductionAutonomousRuntimeBridge
from planning.production_operation_lifecycle import ProductionOperationState


class _RuntimeResult:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def run_until_pause(self, execute, acknowledgements=None, verifications=None):
        return dict(self.snapshot)


def _runtime(snapshot):
    runtime = object.__new__(AutonomousFutureRuntime)
    runtime.run_until_pause = _RuntimeResult(snapshot).run_until_pause
    return runtime


def test_executor_success_and_runtime_completion_do_not_bypass_authoritative_verification():
    runtime = _runtime({"complete": True, "blocked": False, "history": []})
    bridge = ProductionAutonomousRuntimeBridge(runtime, lambda _snapshot: False)
    result = bridge.run(lambda _tool, _arguments: {"ok": True})
    assert result.state is ProductionOperationState.BLOCKED
    assert not result.completed
    assert "authoritative verification rejected" in result.reason


def test_authoritative_verification_promotes_completed_runtime():
    runtime = _runtime({"complete": True, "blocked": False, "history": []})
    bridge = ProductionAutonomousRuntimeBridge(runtime, lambda snapshot: snapshot["complete"])
    result = bridge.run(lambda _tool, _arguments: {"ok": True})
    assert result.state is ProductionOperationState.COMPLETED
    assert result.completed


def test_blocked_runtime_cannot_be_promoted():
    runtime = _runtime({"complete": False, "blocked": True, "history": []})
    called = False

    def verify(_snapshot):
        nonlocal called
        called = True
        return True

    result = ProductionAutonomousRuntimeBridge(runtime, verify).run(
        lambda _tool, _arguments: {"ok": True}
    )
    assert result.state is ProductionOperationState.BLOCKED
    assert not called


def test_verifier_exception_blocks_completion():
    runtime = _runtime({"complete": True, "blocked": False, "history": []})

    def verify(_snapshot):
        raise RuntimeError("authoritative state unavailable")

    result = ProductionAutonomousRuntimeBridge(runtime, verify).run(
        lambda _tool, _arguments: {"ok": True}
    )
    assert result.state is ProductionOperationState.BLOCKED
    assert "authoritative verification failed" in result.reason


def test_invalid_constructor_inputs_fail_closed():
    with pytest.raises(TypeError, match="AutonomousFutureRuntime"):
        ProductionAutonomousRuntimeBridge(object(), lambda _: True)
    runtime = _runtime({"complete": True, "blocked": False})
    with pytest.raises(TypeError, match="callable"):
        ProductionAutonomousRuntimeBridge(runtime, None)
