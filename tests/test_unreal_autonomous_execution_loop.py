"""Tests for UnrealAutonomousExecutionLoop.

Covers:
- Successful one-pass completion
- Verification-required progression
- Recoverable failure and bounded recovery
- Maximum-iteration termination
- Authorization enforcement
- Transport failure propagation
- Malformed input rejection
- Deterministic history
- Preserved intent/entity context
- No execution after terminal state
"""

from dataclasses import replace

import pytest
from typing import List, Optional, Tuple

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import (
    UnrealCapability,
    UnrealOperation,
    UnrealOperationKind,
    UnrealTaskIntent,
)
from planning.unreal_authorized_execution_gate import UnrealAuthorizedExecutionGate
from planning.unreal_autonomous_execution_loop import (
    AuthorizationIdProvider,
    AutonomousLoopResult,
    LoopConfig,
    LoopStepRecord,
    LoopTermination,
    UnrealAutonomousExecutionLoop,
)
from planning.unreal_evidence_contract import UnrealEvidence

from planning.unreal_execution_evaluator import (
    EvaluationOutcome,
    UnrealExecutionEvaluator,
)
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_recovery_planner import RecoveryAction, UnrealRecoveryPlanner
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_contract import (
    UnrealTransportRequest,
    UnrealTransportResponse,
)


# ---------------------------------------------------------------------------
# In-memory transport (reuses pattern from existing test suites)
# ---------------------------------------------------------------------------

class InMemoryTransport:
    def __init__(
        self,
        *,
        fail_at_index: Optional[int] = None,
        error_message: str = "boom",
        verified: bool = False,
    ):
        self._call_count = 0
        self._fail_at_index = fail_at_index
        self._error_message = error_message
        self._verified = verified
        self.requests: List[UnrealTransportRequest] = []

    def send(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        index = self._call_count
        self._call_count += 1
        self.requests.append(request)

        if self._fail_at_index is not None and index == self._fail_at_index:
            return UnrealTransportResponse(
                request_id=request.request_id,
                operation_name=request.operation_name,
                entity_ids=request.entity_ids,
                success=False,
                error=self._error_message,
                observed_state={},
                source="in-memory-test",
            )

        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=True,
            error="",
            observed_state={
                "echo_capability": request.capability,
                "echo_kind": request.kind,
            },
            source="in-memory-test",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _intent(
    intent_id: str = "loop-intent-1",
    targets: Tuple[str, ...] = ("/Game/Mesh_A",),
) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="loop test",
        target_entity_ids=targets,
    )


def _build_loop(
    transport: Optional[InMemoryTransport] = None,
) -> Tuple[UnrealAutonomousExecutionLoop, InMemoryTransport]:
    if transport is None:
        transport = InMemoryTransport()
    adapter = UnrealAdapterProduction(transport, source_tag="loop-test")
    executor = UnrealPlanExecutor(adapter)
    gate = UnrealAuthorizedExecutionGate(executor)
    loop = UnrealAutonomousExecutionLoop(
        planner=UnrealTaskPlanner(),
        gate=gate,
        evaluator=UnrealExecutionEvaluator(),
        recovery_planner=UnrealRecoveryPlanner(),
    )
    return loop, transport


def _simple_auth_provider(iteration: int) -> str:
    return f"auth-loop-{iteration}"


# ---------------------------------------------------------------------------
# LoopConfig validation
# ---------------------------------------------------------------------------

class TestLoopConfigValidation:
    def test_valid_config(self):
        cfg = LoopConfig(max_iterations=5, max_recovery_attempts=3)
        assert cfg.max_iterations == 5
        assert cfg.max_recovery_attempts == 3

    def test_default_config(self):
        cfg = LoopConfig()
        assert cfg.max_iterations == 5
        assert cfg.max_recovery_attempts == 3

    def test_zero_max_iterations_rejected(self):
        with pytest.raises(ValueError, match="max_iterations"):
            LoopConfig(max_iterations=0)

    def test_negative_max_iterations_rejected(self):
        with pytest.raises(ValueError, match="max_iterations"):
            LoopConfig(max_iterations=-1)

    def test_zero_max_recovery_rejected(self):
        with pytest.raises(ValueError, match="max_recovery_attempts"):
            LoopConfig(max_recovery_attempts=0)

    def test_negative_max_recovery_rejected(self):
        with pytest.raises(ValueError, match="max_recovery_attempts"):
            LoopConfig(max_recovery_attempts=-1)

    def test_frozen(self):
        cfg = LoopConfig()
        with pytest.raises(AttributeError):
            cfg.max_iterations = 10


# ---------------------------------------------------------------------------
# Successful one-pass completion
# ---------------------------------------------------------------------------

class _VerifiedTransport:
    """Transport that returns a normal successful, unverified response."""

    def __init__(self):
        self.requests: List[UnrealTransportRequest] = []

    def send(self, request: UnrealTransportRequest) -> UnrealTransportResponse:
        self.requests.append(request)
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=True,
            error="",
            observed_state={"status": "ok"},
            source="verified-test",
        )


class _VerifiedTestAdapter(UnrealAdapterProduction):
    """Test-only adapter representing Atlas verification after transport."""

    @staticmethod
    def _to_evidence(response: UnrealTransportResponse) -> UnrealEvidence:
        evidence = UnrealAdapterProduction._to_evidence(response)
        return replace(evidence, verified=True)


class TestSuccessfulOnePass:
    """The loop must terminate immediately on SATISFIED after one pass
    when the adapter returns fully verified evidence."""

    def test_one_pass_satisfied(self):
        transport = _VerifiedTransport()
        adapter = _VerifiedTestAdapter(transport, source_tag="loop-test")
        executor = UnrealPlanExecutor(adapter)
        gate = UnrealAuthorizedExecutionGate(executor)
        loop = UnrealAutonomousExecutionLoop(
            planner=UnrealTaskPlanner(),
            gate=gate,
            evaluator=UnrealExecutionEvaluator(),
            recovery_planner=UnrealRecoveryPlanner(),
        )

        result = loop.run(_intent(), _simple_auth_provider)

        assert result.termination == LoopTermination.SATISFIED
        assert result.iterations_used == 1
        assert len(result.history) == 1
        assert result.final_evaluation is not None
        assert result.final_evaluation.outcome == EvaluationOutcome.SATISFIED

    def test_one_pass_intent_id_preserved(self):
        transport = _VerifiedTransport()
        adapter = _VerifiedTestAdapter(transport, source_tag="loop-test")
        executor = UnrealPlanExecutor(adapter)
        gate = UnrealAuthorizedExecutionGate(executor)
        loop = UnrealAutonomousExecutionLoop(
            planner=UnrealTaskPlanner(),
            gate=gate,
            evaluator=UnrealExecutionEvaluator(),
            recovery_planner=UnrealRecoveryPlanner(),
        )

        result = loop.run(_intent(intent_id="my-id"), _simple_auth_provider)

        assert result.intent_id == "my-id"

    def test_one_pass_history_record_fields(self):
        transport = _VerifiedTransport()
        adapter = _VerifiedTestAdapter(transport, source_tag="loop-test")
        executor = UnrealPlanExecutor(adapter)
        gate = UnrealAuthorizedExecutionGate(executor)
        loop = UnrealAutonomousExecutionLoop(
            planner=UnrealTaskPlanner(),
            gate=gate,
            evaluator=UnrealExecutionEvaluator(),
            recovery_planner=UnrealRecoveryPlanner(),
        )

        result = loop.run(_intent(), _simple_auth_provider)
        record = result.history[0]

        assert record.iteration == 1
        assert record.execution_success is True
        assert record.evaluation is not None
        assert record.error is None
        assert record.authorization_id == "auth-loop-1"


# ---------------------------------------------------------------------------
# Verification-required progression
# ---------------------------------------------------------------------------

class TestVerificationRequiredProgression:
    """When evidence is unverified, the loop must continue iterating
    (up to bounds) with recovery decisions."""

    def test_unverified_evidence_causes_multiple_iterations(self):
        # Default InMemoryTransport returns unverified evidence
        loop, transport = _build_loop()
        config = LoopConfig(max_iterations=3, max_recovery_attempts=3)

        result = loop.run(_intent(), _simple_auth_provider, config)

        # With 3 max_recovery_attempts and 3 max_iterations, the loop
        # should iterate until recovery exhaustion or iteration limit.
        assert result.iterations_used >= 2
        assert len(result.history) >= 2

    def test_verification_required_records_recovery_decision(self):
        loop, _ = _build_loop()
        config = LoopConfig(max_iterations=2, max_recovery_attempts=3)

        result = loop.run(_intent(), _simple_auth_provider, config)

        # First iteration should have a recovery decision
        first = result.history[0]
        assert first.recovery_decision is not None


# ---------------------------------------------------------------------------
# Recoverable failure and bounded recovery
# ---------------------------------------------------------------------------

class TestRecoverableFailureBoundedRecovery:
    """Transport failures that propagate through the gate must terminate
    the loop with FAILED."""

    def test_transport_failure_terminates_with_failed(self):
        transport = InMemoryTransport(fail_at_index=0)
        loop, _ = _build_loop(transport)

        result = loop.run(_intent(), _simple_auth_provider)

        assert result.termination == LoopTermination.FAILED
        assert result.iterations_used == 1

    def test_mid_plan_transport_failure(self):
        # Inspection plan has 2 ops; fail at index 1
        transport = InMemoryTransport(fail_at_index=1)
        loop, _ = _build_loop(transport)

        result = loop.run(_intent(), _simple_auth_provider)

        assert result.termination == LoopTermination.FAILED
        assert result.history[0].error is not None


# ---------------------------------------------------------------------------
# Maximum-iteration termination
# ---------------------------------------------------------------------------

class TestMaxIterationTermination:
    def test_iteration_limit_reached(self):
        loop, _ = _build_loop()
        config = LoopConfig(max_iterations=2, max_recovery_attempts=5)

        result = loop.run(_intent(), _simple_auth_provider, config)

        # Unverified evidence → VERIFICATION_REQUIRED → loop continues
        # until iteration limit (recovery budget > iteration limit)
        assert result.termination == LoopTermination.ITERATION_LIMIT
        assert result.iterations_used == 2
        assert len(result.history) == 2

    def test_single_iteration_limit(self):
        loop, _ = _build_loop()
        config = LoopConfig(max_iterations=1, max_recovery_attempts=5)

        result = loop.run(_intent(), _simple_auth_provider, config)

        # One iteration, unverified → not satisfied → iteration limit
        # But recovery_attempt=1 with max=5 → REQUEST_VERIFICATION (non-terminal)
        # → iteration limit reached
        assert result.iterations_used == 1


# ---------------------------------------------------------------------------
# Recovery exhaustion
# ---------------------------------------------------------------------------

class TestRecoveryExhaustion:
    def test_recovery_exhausted_terminates(self):
        loop, _ = _build_loop()
        # 1 recovery attempt allowed, many iterations
        config = LoopConfig(max_iterations=10, max_recovery_attempts=1)

        result = loop.run(_intent(), _simple_auth_provider, config)

        # First iteration: unverified → recovery attempt 1/1 → exhausted → REVIEW
        assert result.termination == LoopTermination.RECOVERY_EXHAUSTED
        assert result.iterations_used == 1
        assert result.final_recovery is not None
        assert result.final_recovery.action == RecoveryAction.REQUEST_REVIEW


# ---------------------------------------------------------------------------
# Authorization enforcement
# ---------------------------------------------------------------------------

class TestAuthorizationEnforcement:
    def test_empty_auth_id_terminates_with_failed(self):
        loop, _ = _build_loop()

        def bad_provider(iteration: int) -> str:
            return ""

        result = loop.run(_intent(), bad_provider)

        assert result.termination == LoopTermination.FAILED
        assert result.history[0].error is not None

    def test_whitespace_auth_id_terminates_with_failed(self):
        loop, _ = _build_loop()

        def ws_provider(iteration: int) -> str:
            return "   "

        result = loop.run(_intent(), ws_provider)

        assert result.termination == LoopTermination.FAILED

    def test_auth_provider_exception_terminates_with_failed(self):
        loop, _ = _build_loop()

        def exploding_provider(iteration: int) -> str:
            raise RuntimeError("provider exploded")

        result = loop.run(_intent(), exploding_provider)

        assert result.termination == LoopTermination.FAILED

    def test_each_iteration_gets_fresh_auth_id(self):
        loop, transport = _build_loop()
        config = LoopConfig(max_iterations=3, max_recovery_attempts=5)

        ids_seen: List[str] = []

        def tracking_provider(iteration: int) -> str:
            aid = f"auth-{iteration}"
            ids_seen.append(aid)
            return aid

        loop.run(_intent(), tracking_provider, config)

        # Each iteration should have called the provider
        assert len(ids_seen) >= 2
        # All IDs should be unique
        assert len(set(ids_seen)) == len(ids_seen)


# ---------------------------------------------------------------------------
# Transport failure propagation
# ---------------------------------------------------------------------------

class TestTransportFailurePropagation:
    def test_failure_error_recorded_in_history(self):
        transport = InMemoryTransport(fail_at_index=0, error_message="network down")
        loop, _ = _build_loop(transport)

        result = loop.run(_intent(), _simple_auth_provider)

        assert result.termination == LoopTermination.FAILED
        assert result.history[0].error is not None
        assert "failed" in result.history[0].error.lower() or "network" in result.history[0].error.lower()

    def test_no_further_requests_after_failure(self):
        transport = InMemoryTransport(fail_at_index=0)
        loop, _ = _build_loop(transport)
        config = LoopConfig(max_iterations=5)

        loop.run(_intent(), _simple_auth_provider, config)

        # Only 1 request sent (the failing one)
        assert len(transport.requests) == 1


# ---------------------------------------------------------------------------
# Malformed input rejection
# ---------------------------------------------------------------------------

class TestMalformedInputRejection:
    def test_non_intent_rejected(self):
        loop, _ = _build_loop()
        with pytest.raises(TypeError, match="UnrealTaskIntent"):
            loop.run("not-an-intent", _simple_auth_provider)

    def test_none_intent_rejected(self):
        loop, _ = _build_loop()
        with pytest.raises(TypeError, match="UnrealTaskIntent"):
            loop.run(None, _simple_auth_provider)

    def test_non_callable_provider_rejected(self):
        loop, _ = _build_loop()
        with pytest.raises(TypeError, match="callable"):
            loop.run(_intent(), "not-callable")

    def test_invalid_config_type_rejected(self):
        loop, _ = _build_loop()
        with pytest.raises(TypeError, match="LoopConfig"):
            loop.run(_intent(), _simple_auth_provider, "not-a-config")

    def test_non_planner_rejected(self):
        with pytest.raises(TypeError, match="UnrealTaskPlanner"):
            UnrealAutonomousExecutionLoop(
                planner="not-a-planner",
                gate=_build_loop()[0]._gate,
                evaluator=UnrealExecutionEvaluator(),
                recovery_planner=UnrealRecoveryPlanner(),
            )

    def test_non_gate_rejected(self):
        with pytest.raises(TypeError, match="UnrealAuthorizedExecutionGate"):
            UnrealAutonomousExecutionLoop(
                planner=UnrealTaskPlanner(),
                gate="not-a-gate",
                evaluator=UnrealExecutionEvaluator(),
                recovery_planner=UnrealRecoveryPlanner(),
            )

    def test_non_evaluator_rejected(self):
        with pytest.raises(TypeError, match="UnrealExecutionEvaluator"):
            UnrealAutonomousExecutionLoop(
                planner=UnrealTaskPlanner(),
                gate=_build_loop()[0]._gate,
                evaluator="not-an-evaluator",
                recovery_planner=UnrealRecoveryPlanner(),
            )

    def test_non_recovery_planner_rejected(self):
        with pytest.raises(TypeError, match="UnrealRecoveryPlanner"):
            UnrealAutonomousExecutionLoop(
                planner=UnrealTaskPlanner(),
                gate=_build_loop()[0]._gate,
                evaluator=UnrealExecutionEvaluator(),
                recovery_planner="not-a-recovery-planner",
            )


# ---------------------------------------------------------------------------
# Deterministic history
# ---------------------------------------------------------------------------

class TestDeterministicHistory:
    def test_identical_inputs_produce_identical_results(self):
        def run_once():
            transport = _VerifiedTransport()
            adapter = UnrealAdapterProduction(transport, source_tag="det-test")
            executor = UnrealPlanExecutor(adapter)
            gate = UnrealAuthorizedExecutionGate(executor)
            loop = UnrealAutonomousExecutionLoop(
                planner=UnrealTaskPlanner(),
                gate=gate,
                evaluator=UnrealExecutionEvaluator(),
                recovery_planner=UnrealRecoveryPlanner(),
            )
            return loop.run(_intent(), _simple_auth_provider)

        result_a = run_once()
        result_b = run_once()

        assert result_a.termination == result_b.termination
        assert result_a.iterations_used == result_b.iterations_used
        assert len(result_a.history) == len(result_b.history)
        for a, b in zip(result_a.history, result_b.history):
            assert a.iteration == b.iteration
            assert a.plan_intent_id == b.plan_intent_id
            assert a.authorization_id == b.authorization_id
            assert a.execution_success == b.execution_success

    def test_unverified_determinism(self):
        def run_once():
            transport = InMemoryTransport()
            adapter = UnrealAdapterProduction(transport, source_tag="det-test")
            executor = UnrealPlanExecutor(adapter)
            gate = UnrealAuthorizedExecutionGate(executor)
            loop = UnrealAutonomousExecutionLoop(
                planner=UnrealTaskPlanner(),
                gate=gate,
                evaluator=UnrealExecutionEvaluator(),
                recovery_planner=UnrealRecoveryPlanner(),
            )
            config = LoopConfig(max_iterations=3, max_recovery_attempts=2)
            return loop.run(_intent(), _simple_auth_provider, config)

        result_a = run_once()
        result_b = run_once()

        assert result_a.termination == result_b.termination
        assert result_a.iterations_used == result_b.iterations_used
        assert len(result_a.history) == len(result_b.history)


# ---------------------------------------------------------------------------
# Preserved intent/entity context
# ---------------------------------------------------------------------------

class TestPreservedContext:
    def test_intent_id_in_result(self):
        loop, _ = _build_loop()
        result = loop.run(
            _intent(intent_id="ctx-test-42"), _simple_auth_provider,
            LoopConfig(max_iterations=1, max_recovery_attempts=1),
        )
        assert result.intent_id == "ctx-test-42"

    def test_intent_id_in_history_records(self):
        loop, _ = _build_loop()
        result = loop.run(
            _intent(intent_id="ctx-hist"), _simple_auth_provider,
            LoopConfig(max_iterations=1, max_recovery_attempts=1),
        )
        for record in result.history:
            assert record.plan_intent_id == "ctx-hist"

    def test_entity_ids_in_recovery_decision(self):
        loop, _ = _build_loop()
        config = LoopConfig(max_iterations=1, max_recovery_attempts=1)
        targets = ("/Game/X", "/Game/Y")

        result = loop.run(
            _intent(targets=targets), _simple_auth_provider, config,
        )

        if result.final_recovery is not None:
            assert result.final_recovery.entity_ids == targets


# ---------------------------------------------------------------------------
# No execution after terminal state
# ---------------------------------------------------------------------------

class TestNoExecutionAfterTerminal:
    def test_no_requests_after_satisfied(self):
        transport = _VerifiedTransport()
        adapter = _VerifiedTestAdapter(transport, source_tag="term-test")
        executor = UnrealPlanExecutor(adapter)
        gate = UnrealAuthorizedExecutionGate(executor)
        loop = UnrealAutonomousExecutionLoop(
            planner=UnrealTaskPlanner(),
            gate=gate,
            evaluator=UnrealExecutionEvaluator(),
            recovery_planner=UnrealRecoveryPlanner(),
        )
        config = LoopConfig(max_iterations=5)

        result = loop.run(_intent(), _simple_auth_provider, config)

        assert result.termination == LoopTermination.SATISFIED
        assert result.iterations_used == 1
        # Only 2 transport requests (inspection plan = 2 ops)
        assert len(transport.requests) == 2

    def test_no_requests_after_failure(self):
        transport = InMemoryTransport(fail_at_index=0)
        loop, _ = _build_loop(transport)
        config = LoopConfig(max_iterations=5)

        result = loop.run(_intent(), _simple_auth_provider, config)

        assert result.termination == LoopTermination.FAILED
        assert len(transport.requests) == 1

    def test_no_requests_after_recovery_exhausted(self):
        transport = InMemoryTransport()
        adapter = UnrealAdapterProduction(transport, source_tag="exh-test")
        executor = UnrealPlanExecutor(adapter)
        gate = UnrealAuthorizedExecutionGate(executor)
        loop = UnrealAutonomousExecutionLoop(
            planner=UnrealTaskPlanner(),
            gate=gate,
            evaluator=UnrealExecutionEvaluator(),
            recovery_planner=UnrealRecoveryPlanner(),
        )
        config = LoopConfig(max_iterations=10, max_recovery_attempts=1)

        result = loop.run(_intent(), _simple_auth_provider, config)

        assert result.termination == LoopTermination.RECOVERY_EXHAUSTED
        # Only 1 iteration executed → 2 transport requests (inspection)
        assert len(transport.requests) == 2


# ---------------------------------------------------------------------------
# AutonomousLoopResult validation
# ---------------------------------------------------------------------------

class TestAutonomousLoopResultValidation:
    def test_empty_intent_id_rejected(self):
        with pytest.raises(ValueError, match="intent_id"):
            AutonomousLoopResult(
                intent_id="",
                termination=LoopTermination.SATISFIED,
                iterations_used=1,
                history=(),
                final_evaluation=None,
                final_recovery=None,
            )

    def test_negative_iterations_rejected(self):
        with pytest.raises(ValueError, match="iterations_used"):
            AutonomousLoopResult(
                intent_id="x",
                termination=LoopTermination.SATISFIED,
                iterations_used=-1,
                history=(),
                final_evaluation=None,
                final_recovery=None,
            )

    def test_frozen(self):
        result = AutonomousLoopResult(
            intent_id="x",
            termination=LoopTermination.SATISFIED,
            iterations_used=1,
            history=(),
            final_evaluation=None,
            final_recovery=None,
        )
        with pytest.raises(AttributeError):
            result.termination = LoopTermination.FAILED
