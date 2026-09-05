"""Focused tests for UnrealExecutionBoundary and UnrealAutonomousExecutor.

Validates:
1. Tool validation and conversion to UnrealOperation across READ, WRITE, and VERIFY.
2. Authority preservation: authorization_id passed through without forging or mutating.
3. Fail-closed error handling: invalid schema, missing arguments, transport failure.
4. ToolExecutor interface compatibility with AutonomousFutureRuntime.
5. Invariant enforcement: evidence remains verified=False.
"""

import tempfile
import pytest

from planning.action_plan import ActionSpec
from planning.action_authorization import ActionAuthorization
from planning.autonomous_runtime import AutonomousFutureRuntime
from planning.future_execution import FutureExecutionController
from planning.future_generator import FutureStep
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore
from planning.unreal_adapter_production import (
    UnrealAdapterError,
    UnrealAdapterProduction,
)
from planning.unreal_agent import (
    UnrealCapability,
    UnrealOperation,
    UnrealOperationKind,
)
from planning.unreal_autonomous_executor import UnrealAutonomousExecutor
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_execution_boundary import UnrealExecutionBoundary
from planning.unreal_transport_contract import (
    UnrealTransportRequest,
    UnrealTransportResponse,
)


class MockTransport:
    def __init__(self, *, success=True, observed_state=None, error="", source="mock-ue"):
        self.success = success
        self.observed_state = observed_state if observed_state is not None else {"location": {"x": 10.0, "y": 20.0, "z": 30.0}}
        self.error = error
        self.source = source
        self.sent_requests = []

    def send(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        self.sent_requests.append(request)
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=self.success,
            observed_state=self.observed_state,
            error=self.error,
            source=self.source,
        )


class DisconnectingTransport:
    def send(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        raise UnrealAdapterError("transport connection broken")


# ── 1. UnrealExecutionBoundary Unit Tests ─────────────────────────────────

def test_execution_boundary_maps_and_executes_write_operation():
    transport = MockTransport()
    adapter = UnrealAdapterProduction(transport)
    boundary = UnrealExecutionBoundary(adapter)

    args = {
        "entity_ids": ["ACTOR_1"],
        "authorization_id": "auth-xyz-123",
        "location": {"x": 10.0, "y": 20.0, "z": 30.0},
    }

    evidence = boundary.execute("set_actor_location", args)

    assert isinstance(evidence, UnrealEvidence)
    assert evidence.operation_name == "set_actor_location"
    assert evidence.entity_ids == ("ACTOR_1",)
    assert evidence.verified is False
    assert len(transport.sent_requests) == 1
    req = transport.sent_requests[0]
    assert req.operation_name == "set_actor_location"
    assert req.capability == UnrealCapability.MODIFY_ACTOR.value
    assert req.kind == UnrealOperationKind.WRITE.value
    assert req.authorization_id == "auth-xyz-123"
    assert req.arguments["location"] == {"x": 10.0, "y": 20.0, "z": 30.0}
    assert "authorization_id" not in req.arguments


def test_execution_boundary_maps_and_executes_read_operation():
    transport = MockTransport(observed_state={"ACTOR_1": {"location": {"x": 0.0, "y": 0.0, "z": 0.0}}})
    adapter = UnrealAdapterProduction(transport)
    boundary = UnrealExecutionBoundary(adapter)

    args = {
        "entity_ids": ["ACTOR_1"],
        "authorization_id": "auth-read-456",
    }

    evidence = boundary.execute("inspect_target_actors", args)

    assert isinstance(evidence, UnrealEvidence)
    assert evidence.operation_name == "inspect_target_actors"
    assert evidence.verified is False
    assert len(transport.sent_requests) == 1
    assert transport.sent_requests[0].kind == UnrealOperationKind.READ.value


def test_execution_boundary_rejects_missing_authorization_id():
    transport = MockTransport()
    adapter = UnrealAdapterProduction(transport)
    boundary = UnrealExecutionBoundary(adapter)

    args = {
        "entity_ids": ["ACTOR_1"],
        "location": {"x": 1.0, "y": 2.0, "z": 3.0},
    }

    with pytest.raises(ValueError, match="missing required argument: authorization_id"):
        boundary.execute("set_actor_location", args)

    assert len(transport.sent_requests) == 0


def test_execution_boundary_rejects_empty_authorization_id():
    transport = MockTransport()
    adapter = UnrealAdapterProduction(transport)
    boundary = UnrealExecutionBoundary(adapter)

    args = {
        "entity_ids": ["ACTOR_1"],
        "authorization_id": "   ",
        "location": {"x": 1.0, "y": 2.0, "z": 3.0},
    }

    with pytest.raises(ValueError, match="authorization_id must be a non-empty string"):
        boundary.execute("set_actor_location", args)

    assert len(transport.sent_requests) == 0


def test_execution_boundary_rejects_unknown_tool():
    transport = MockTransport()
    adapter = UnrealAdapterProduction(transport)
    boundary = UnrealExecutionBoundary(adapter)

    with pytest.raises(ValueError, match="unsupported Unreal tool: delete_actor"):
        boundary.execute("delete_actor", {"authorization_id": "auth-1"})


# ── 2. UnrealAutonomousExecutor Unit Tests ───────────────────────────────

def test_autonomous_executor_returns_ok_contract():
    transport = MockTransport()
    adapter = UnrealAdapterProduction(transport)
    executor = UnrealAutonomousExecutor(adapter)

    args = {
        "entity_ids": ["GOAL_POST"],
        "authorization_id": "auth-789",
        "rotation": {"pitch": 0.0, "yaw": 90.0, "roll": 0.0},
    }

    result = executor("set_actor_rotation", args)

    assert result["ok"] is True
    assert result["state"] == "executed"
    assert result["details"]["operation_name"] == "set_actor_rotation"
    assert result["details"]["verified"] is False
    assert executor.last_evidence is not None
    assert executor.last_evidence.operation_name == "set_actor_rotation"


def test_autonomous_executor_fails_closed_on_transport_failure():
    transport = DisconnectingTransport()
    adapter = UnrealAdapterProduction(transport)
    executor = UnrealAutonomousExecutor(adapter)

    args = {
        "entity_ids": ["ACTOR_1"],
        "authorization_id": "auth-1",
        "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
    }

    result = executor("set_actor_scale", args)

    assert result["ok"] is False
    assert "transport connection broken" in result["error"]
    assert result["exception_type"] == "UnrealAdapterError"
    assert executor.last_evidence is None


def test_autonomous_executor_uses_default_authorization_id_if_configured():
    transport = MockTransport()
    adapter = UnrealAdapterProduction(transport)
    executor = UnrealAutonomousExecutor(adapter, default_authorization_id="host-authorized-id")

    # Call without authorization_id in arguments
    args = {
        "entity_ids": ["ACTOR_1"],
        "scale": {"x": 2.0, "y": 2.0, "z": 2.0},
    }

    result = executor("set_actor_scale", args)

    assert result["ok"] is True
    assert transport.sent_requests[0].authorization_id == "host-authorized-id"


# ── 3. AutonomousTaskRuntime Integration with UnrealAutonomousExecutor ──

def _steps():
    return [
        FutureStep(0, "evidence.authoritative", "EVIDENCE", "evidence"),
        FutureStep(
            1,
            "action.0",
            "ACTION",
            "write",
            {
                "tool": "set_actor_location",
                "arguments": {
                    "entity_ids": ["ACTOR_1"],
                    "authorization_id": "auth-step-001",
                    "location": {"x": 100.0, "y": 200.0, "z": 50.0},
                },
            },
        ),
        FutureStep(2, "verification.pending", "VERIFICATION", "verify"),
        FutureStep(3, "complete", "COMPLETE", "complete"),
    ]


def test_generic_autonomous_runtime_executes_unreal_action():
    transport = MockTransport()
    adapter = UnrealAdapterProduction(transport)
    executor = UnrealAutonomousExecutor(adapter)

    with tempfile.TemporaryDirectory() as tmp:
        store = FutureRuntimeStateStore(f"{tmp}/future.json")
        context = RuntimeContext("Unreal autonomous execution test", {"env": "test"})
        runtime = AutonomousFutureRuntime(_steps(), store, context)

        # Advance through EVIDENCE to ACTION
        runtime.run_until_pause(executor, {"evidence.authoritative": {}}, {})

        # Verify the action was dispatched to Unreal transport
        assert len(transport.sent_requests) == 1
        req = transport.sent_requests[0]
        assert req.operation_name == "set_actor_location"
        assert req.authorization_id == "auth-step-001"
        assert req.arguments["location"] == {"x": 100.0, "y": 200.0, "z": 50.0}

        # Checkpoint snapshot verification
        snapshot = runtime.snapshot()
        assert snapshot["current_step"]["phase"] == "VERIFICATION"
        assert executor.last_evidence is not None
        assert executor.last_evidence.verified is False

        # Supply verification and advance to COMPLETE
        completed = runtime.run_until_pause(
            executor,
            verifications={"verification.pending": {"satisfied": True}},
        )
        assert completed["complete"] is True


def test_generic_autonomous_runtime_blocks_on_unreal_transport_failure():
    transport = DisconnectingTransport()
    adapter = UnrealAdapterProduction(transport)
    executor = UnrealAutonomousExecutor(adapter)

    with tempfile.TemporaryDirectory() as tmp:
        store = FutureRuntimeStateStore(f"{tmp}/future.json")
        context = RuntimeContext("Unreal autonomous failure test", {"env": "test"})
        runtime = AutonomousFutureRuntime(_steps(), store, context)

        # Execute action which fails at transport
        paused = runtime.run_until_pause(executor, {"evidence.authoritative": {}}, {})

        assert runtime.controller.blocked is True
        assert runtime.controller.failed is not None
        assert "error" in runtime.controller.failed["result"]
        assert "transport connection broken" in runtime.controller.failed["result"]["error"]


def test_action_authorization_binding_invariant():
    action = ActionSpec(
        tool="set_actor_location",
        arguments={
            "entity_ids": ("ACTOR_1",),
            "authorization_id": "auth-imm-1",
            "location": {"x": 1.0, "y": 2.0, "z": 3.0},
        },
        name="action.0",
    )
    auth = ActionAuthorization.issue([action], "auth-imm-1")

    # Matches exact action
    assert auth.matches([action]) is True

    # Fails if tool changes
    tampered_tool = ActionSpec(
        tool="set_actor_rotation",
        arguments=action.arguments,
        name=action.name,
    )
    assert auth.matches([tampered_tool]) is False

    # Fails if arguments change
    tampered_args = ActionSpec(
        tool=action.tool,
        arguments={
            "entity_ids": ("ACTOR_1",),
            "authorization_id": "auth-imm-1",
            "location": {"x": 999.0, "y": 2.0, "z": 3.0},
        },
        name=action.name,
    )
    assert auth.matches([tampered_args]) is False

    # Fails if entity_ids change
    tampered_entities = ActionSpec(
        tool=action.tool,
        arguments={
            "entity_ids": ("DIFFERENT_ACTOR",),
            "authorization_id": "auth-imm-1",
            "location": {"x": 1.0, "y": 2.0, "z": 3.0},
        },
        name=action.name,
    )
    assert auth.matches([tampered_entities]) is False
