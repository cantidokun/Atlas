"""Full round-trip tests: intent → planner → authorization → executor → evidence.

Uses an in-memory transport so no real Unreal process is needed.
"""

import pytest
from typing import List, Optional, Tuple

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

    Successful responses model the semantic state that the production Unreal
    transport is expected to return. This keeps these tests focused on the
    adapter/executor contract instead of making semantic verification depend
    on an echo-only fixture.
    """

    def __init__(self, *, fail_at_index: Optional[int] = None, error_message: str = "boom"):
        self._call_count = 0
        self._fail_at_index = fail_at_index
        self._error_message = error_message
        self.requests: List[UnrealTransportRequest] = []

    @staticmethod
    def _observed_state(request: UnrealTransportRequest):
        state = {
            "echo_capability": request.capability,
            "echo_kind": request.kind,
        }
        for entity_id in request.entity_ids:
            entity_state = {}
            args = request.arguments
            if request.operation_name in {"set_actor_location", "verify_actor_location", "inspect_target_actors"}:
                location = args.get("location", args.get("expected_location"))
                if isinstance(location, dict):
                    entity_state["location"] = dict(location)
            if request.operation_name in {"set_actor_rotation", "verify_actor_rotation", "inspect_target_actors"}:
                rotation = args.get("rotation", args.get("expected_rotation"))
                if isinstance(rotation, dict):
                    entity_state["rotation"] = dict(rotation)
            if request.operation_name in {"set_actor_scale", "verify_actor_scale", "inspect_target_actors"}:
                scale = args.get("scale", args.get("expected_scale"))
                if isinstance(scale, dict):
                    entity_state["scale"] = dict(scale)
            if request.operation_name in {"apply_material_variant", "verify_material_variant", "inspect_material_state"}:
                variant = args.get("material_variant", args.get("expected_material_variant"))
                if isinstance(variant, dict):
                    entity_state["material"] = {"variant": dict(variant)}
            if request.operation_name in {"apply_niagara_variant", "verify_niagara_variant", "inspect_niagara_state"}:
                variant = args.get("niagara_variant", args.get("expected_niagara_variant"))
                if isinstance(variant, dict):
                    entity_state["niagara"] = {"variant": dict(variant)}
            if request.operation_name in {"set_sequencer_playback_range", "verify_sequencer_playback_range", "inspect_sequencer_state"}:
                start_frame = args.get("start_frame", args.get("expected_start_frame"))
                end_frame = args.get("end_frame", args.get("expected_end_frame"))
                if start_frame is not None and end_frame is not None:
                    entity_state["sequencer"] = {"playback_range": {"start_frame": start_frame, "end_frame": end_frame}}
            if entity_state:
                state[entity_id] = entity_state
        return state

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
            observed_state=self._observed_state(request),
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


def _material_variant():
    return {"name": "liquid_surface"}


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
        task_plan = planner.plan_material_variant(intent, _material_variant())

        assert len(task_plan.operations) == 4

        result = executor.execute(task_plan, authorization_id="auth-010")

        assert result.success is True
        assert len(result.evidence_ledger) == 4

    def test_material_variant_dispatches_correct_endpoints(self):
        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_material_variant(_make_intent(), _material_variant())
        executor.execute(task_plan, authorization_id="auth-011")

        expected_kinds = [op.kind.value for op in task_plan.operations]
        actual_kinds = [req.kind for req in transport.requests]
        assert actual_kinds == expected_kinds

    def test_material_variant_entity_ids_propagated(self):
        targets = ("/Game/Mesh_A", "/Game/Mesh_B")
        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_material_variant(_make_intent(targets=targets), _material_variant())
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

        task_plan = planner.plan_material_variant(_make_intent(), _material_variant())
        assert len(task_plan.operations) == 4

        with pytest.raises(UnrealPlanExecutionError):
            executor.execute(task_plan, authorization_id="auth-021")

        assert len(transport.requests) == 3

    def test_failure_does_not_produce_partial_result(self):
        transport = InMemoryTransport(fail_at_index=1)
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_material_variant(_make_intent(), _material_variant())

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

        task_plan = planner.plan_material_variant(_make_intent(), _material_variant())
        result = executor.execute(task_plan, authorization_id="auth-031")

        for op, ev in zip(task_plan.operations, result.evidence_ledger):
            assert ev.operation_name == op.name


# ---------------------------------------------------------------------------
# verified flag invariant
# ---------------------------------------------------------------------------

class TestVerifiedFlagInvariant:
    def test_transport_evidence_is_unverified_before_semantic_verification(self):
        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_inspection(_make_intent())
        result = executor.execute(task_plan, authorization_id="auth-040")

        for evidence in result.evidence_ledger:
            assert evidence.verified is False

    def test_material_verification_marks_only_verification_evidence_verified(self):
        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_material_variant(_make_intent(), _material_variant())
        result = executor.execute(task_plan, authorization_id="auth-041")

        assert [evidence.verified for evidence in result.evidence_ledger] == [False, False, False, True]


# ---------------------------------------------------------------------------
# ActionPlan authorization round-trip
# ---------------------------------------------------------------------------

class TestActionPlanAuthorizationRoundTrip:
    """Prove the full chain: intent → planner → ActionPlan → authorize → executor → evidence."""

    def _action_specs_from_plan(self, task_plan):
        from planning.action_plan import ActionSpec
        return [
            ActionSpec(
                tool=op.capability.value,
                arguments=dict(op.arguments),
                name=op.name,
                requires_success=True,
            )
            for op in task_plan.operations
        ]

    def test_inspection_with_action_plan_authorization(self):
        from planning.action_plan import ActionPlan

        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        intent = _make_intent()
        task_plan = planner.plan_inspection(intent)

        action_plan = ActionPlan(actions=self._action_specs_from_plan(task_plan))
        auth = action_plan.authorize_with_id("auth-100")

        assert action_plan.authorized is True
        assert action_plan.authorization_id == "auth-100"

        result = executor.execute(task_plan, authorization_id=auth.authorization_id)

        assert result.success is True
        assert len(result.evidence_ledger) == len(task_plan.operations)

    def test_material_variant_with_action_plan_authorization(self):
        from planning.action_plan import ActionPlan

        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        intent = _make_intent()
        task_plan = planner.plan_material_variant(intent, _material_variant())

        action_plan = ActionPlan(actions=self._action_specs_from_plan(task_plan))
        auth = action_plan.authorize_with_id("auth-101")

        assert action_plan.authorized is True

        result = executor.execute(task_plan, authorization_id=auth.authorization_id)

        assert result.success is True
        assert len(result.evidence_ledger) == 4
        assert result.evidence_ledger[-1].verified is True

    def test_authorization_digest_is_deterministic(self):
        from planning.action_plan import ActionPlan

        planner = UnrealTaskPlanner()
        task_plan = planner.plan_material_variant(_make_intent(), _material_variant())

        specs = self._action_specs_from_plan(task_plan)
        auth_a = ActionPlan(actions=list(specs)).authorize_with_id("auth-102")
        auth_b = ActionPlan(actions=list(specs)).authorize_with_id("auth-102")

        assert auth_a.plan_digest == auth_b.plan_digest

    def test_authorization_id_propagated_through_transport(self):
        from planning.action_plan import ActionPlan

        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        task_plan = planner.plan_inspection(_make_intent())
        action_plan = ActionPlan(actions=self._action_specs_from_plan(task_plan))
        auth = action_plan.authorize_with_id("auth-103")

        executor.execute(task_plan, authorization_id=auth.authorization_id)

        for req in transport.requests:
            assert req.authorization_id == "auth-103"


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

    def test_unsupported_operation_handling(self):
        transport = InMemoryTransport()
        unsupported_request = UnrealTransportRequest(
            request_id="req-unsupported",
            operation_name="unsupported_operation",
            capability="unsupported_capability",
            kind="read",
            entity_ids=("/Game/TestActor",),
            arguments={},
            authorization_id="auth-unsupported"
        )

        response = transport.send(unsupported_request)

        assert response.success is True
        assert response.request_id == "req-unsupported"
        assert response.operation_name == "unsupported_operation"
        assert response.entity_ids == ("/Game/TestActor",)
        assert response.source == "in-memory-test"
        assert "echo_capability" in response.observed_state
        assert response.observed_state["echo_capability"] == "unsupported_capability"

    def test_transport_request_validation_deterministic(self):
        from planning.unreal_transport_contract import UnrealTransportRequest

        invalid_cases = [
            ("", "inspect_target_actors", "inspect_actor", "read", {}, ("/Game/Actor",), "auth-001"),
            ("req-001", "inspect_target_actors", "inspect_actor", "read", {}, (), "auth-001"),
            ("req-001", "inspect_target_actors", "inspect_actor", "read", {}, ("/Game/Actor",), ""),
        ]

        for case in invalid_cases:
            with pytest.raises(ValueError):
                UnrealTransportRequest(*case)

    def test_evidence_metadata_consistency(self):
        """Test semantic evidence metadata through the transport mapping boundary."""
        transport = InMemoryTransport()
        executor = _build_executor(transport)
        planner = UnrealTaskPlanner()

        intent = _make_intent(intent_id="consistency-test", targets=("/Game/TestActor",))
        task_plan = planner.plan_inspection(intent)
        result = executor.execute(task_plan, authorization_id="auth-consistency")

        for i, (operation, evidence) in enumerate(zip(task_plan.operations, result.evidence_ledger)):
            assert evidence.operation_name == operation.name
            assert tuple(evidence.entity_ids) == tuple(operation.entity_ids)
            assert evidence.verified is False

            transport_req = transport.requests[i]
            assert transport_req.operation_name == operation.name
            assert tuple(transport_req.entity_ids) == tuple(evidence.entity_ids)
            assert transport_req.authorization_id == "auth-consistency"
