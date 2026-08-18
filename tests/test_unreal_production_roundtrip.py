"""Full round-trip tests: intent → planner → authorization → executor → evidence.

Uses an in-memory transport so no real Unreal process is needed.
"""

import pytest
from typing import Any, Dict, Mapping, Tuple

from planning.unreal_agent import (
    UnrealCapability,
    UnrealOperation,
    UnrealOperationKind,
    UnrealTaskIntent,
)
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_adapter_production import UnrealAdapterProduction, UnrealAdapterError
from planning.unreal_plan_executor import (
    UnrealPlanExecutor,
    UnrealPlanExecutionError,
    UnrealPlanExecutionResult,
)
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_transport_contract import (
    UnrealTransportRequest,
    UnrealTransportResponse,
)


# ---------------------------------------------------------------------------
# In-memory transport
# ---------------------------------------------------------------------------

class InMemoryTransport:
    """Deterministic in-memory transport for testing.

    By default every request succeeds with an echo of its own metadata as
    ``observed_state``.  Callers can inject failures for specific request
    indices.
    """

    def __init__(self, *, fail_at_index: int | None = None, error_message: str = "boom"):
        self._call_count = 0
        self._fail_at_index = fail_at_index
        self._error_message = error_message
        self.requests: list[UnrealTransportRequest] = []

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
            error=None,
            observed_state={
                "echo_capability": request.capability,
                "echo_kind": request.kind,
            },
            source="in-memory-test",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_intent(intent_id: str = "intent-1", targets: Tuple[str, ...] = ("/Game/Mesh_A",)) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="test intent",
        target_entity_ids=targets,
    )


def _build_executor(transport: InMemoryTransport) -> UnrealPlanExecutor:
    adapter = UnrealAdapterProduction(transport, source_tag="test")
    return UnrealPlanExecutor(adapter)


# ---------------------------------------------------------------------------
# Inspection plan round-trip
# ---------------------------------------------------------------------------

class TestInspectionRoundTrip:
    def test_inspection_plan_produces_evidence_for_each_operation(self):
        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        intent = _make_intent()
        task_plan = planner.plan_inspection(intent)

        result = executor.execute(task_plan, authorization_id="auth-001")

        assert isinstance(result, UnrealPlanExecutionResult)
        assert result.success is True
        assert result.intent_id == intent.intent_id
        assert len(result.evidence_ledger) == len(task_plan.operations)

    def test_inspection_evidence_operation_names_match(self):
        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_inspection(_make_intent())
        result = executor.execute(task_plan, authorization_id="auth-002")

        for operation, evidence in zip(task_plan.operations, result.evidence_ledger):
            assert evidence.operation_name == operation.name

    def test_inspection_transport_receives_correct_request_count(self):
        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_inspection(_make_intent())
        executor.execute(task_plan, authorization_id="auth-003")

        assert len(transport.requests) == len(task_plan.operations)


# ---------------------------------------------------------------------------
# Material-variant plan round-trip
# ---------------------------------------------------------------------------

class TestMaterialVariantRoundTrip:
    def test_material_variant_plan_produces_four_evidence_entries(self):
        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        intent = _make_intent()
        task_plan = planner.plan_material_variant(intent)

        # Expect: inspect_actor READ, material READ, material WRITE, material VERIFY
        assert len(task_plan.operations) == 4

        result = executor.execute(task_plan, authorization_id="auth-010")

        assert result.success is True
        assert len(result.evidence_ledger) == 4

    def test_material_variant_dispatches_correct_endpoints(self):
        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_material_variant(_make_intent())
        executor.execute(task_plan, authorization_id="auth-011")

        expected_kinds = [op.kind.value for op in task_plan.operations]
        actual_kinds = [req.kind for req in transport.requests]
        assert actual_kinds == expected_kinds

    def test_material_variant_entity_ids_propagated(self):
        targets = ("/Game/Mesh_A", "/Game/Mesh_B")
        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_material_variant(_make_intent(targets=targets))
        result = executor.execute(task_plan, authorization_id="auth-012")

        for evidence in result.evidence_ledger:
            assert tuple(evidence.entity_ids) == targets


# ---------------------------------------------------------------------------
# Transport failure — fail-closed
# ---------------------------------------------------------------------------

class TestTransportFailureClosed:
    def test_first_operation_failure_aborts_plan(self):
        transport = InMemoryTransport(fail_at_index=0)
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_inspection(_make_intent())

        with pytest.raises(UnrealPlanExecutionError, match="failed"):
            executor.execute(task_plan, authorization_id="auth-020")

    def test_mid_plan_failure_aborts_remaining(self):
        transport = InMemoryTransport(fail_at_index=2)
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_material_variant(_make_intent())
        assert len(task_plan.operations) == 4

        with pytest.raises(UnrealPlanExecutionError):
            executor.execute(task_plan, authorization_id="auth-021")

        # Only the first 3 requests were sent (index 0, 1, 2 — failure at 2).
        assert len(transport.requests) == 3

    def test_failure_does_not_produce_partial_result(self):
        transport = InMemoryTransport(fail_at_index=1)
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_material_variant(_make_intent())

        with pytest.raises(UnrealPlanExecutionError):
            executor.execute(task_plan, authorization_id="auth-022")


# ---------------------------------------------------------------------------
# Evidence correlation
# ---------------------------------------------------------------------------

class TestEvidenceCorrelation:
    def test_evidence_entity_ids_match_operation(self):
        targets = ("/Game/Actor_X",)
        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_inspection(_make_intent(targets=targets))
        result = executor.execute(task_plan, authorization_id="auth-030")

        for op, ev in zip(task_plan.operations, result.evidence_ledger):
            assert tuple(ev.entity_ids) == tuple(op.entity_ids)

    def test_evidence_operation_name_matches(self):
        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_material_variant(_make_intent())
        result = executor.execute(task_plan, authorization_id="auth-031")

        for op, ev in zip(task_plan.operations, result.evidence_ledger):
            assert ev.operation_name == op.name


# ---------------------------------------------------------------------------
# verified=False invariant
# ---------------------------------------------------------------------------

class TestVerifiedFalseInvariant:
    def test_all_evidence_verified_is_false_inspection(self):
        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_inspection(_make_intent())
        result = executor.execute(task_plan, authorization_id="auth-040")

        for evidence in result.evidence_ledger:
            assert evidence.verified is False

    def test_all_evidence_verified_is_false_material_variant(self):
        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_material_variant(_make_intent())
        result = executor.execute(task_plan, authorization_id="auth-041")

        for evidence in result.evidence_ledger:
            assert evidence.verified is False


# ---------------------------------------------------------------------------
# Edge cases / validation
# ---------------------------------------------------------------------------

class TestExecutorValidation:
    def test_empty_authorization_id_rejected(self):
        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_inspection(_make_intent())

        with pytest.raises(UnrealPlanExecutionError, match="authorization_id"):
            executor.execute(task_plan, authorization_id="   ")

    def test_non_plan_argument_rejected(self):
        transport = InMemoryTransport()
        executor = _build_executor(transport)

        with pytest.raises(TypeError, match="UnrealTaskPlan"):
            executor.execute("not-a-plan", authorization_id="auth-050")

    def test_authorization_id_transmitted_to_transport(self):
        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_inspection(_make_intent())
        executor.execute(task_plan, authorization_id="auth-060")

        for req in transport.requests:
            assert req.authorization_id == "auth-060"
