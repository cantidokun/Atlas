"""Tests for the UnrealAuthorizedExecutionGate.

Covers the complete flow from UnrealTaskIntent through UnrealTaskPlanner,
deterministic ActionSpec conversion, ActionPlan authorization, authorization
mismatch rejection, post-authorization plan mutation rejection, successful
authorized execution through UnrealPlanExecutor, and transport/evidence
failure behaviour.
"""

import pytest
from typing import List, Optional, Tuple

from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionPlan, ActionSpec
from planning.unreal_agent import (
    UnrealCapability,
    UnrealOperation,
    UnrealOperationKind,
    UnrealTaskIntent,
)
from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_authorized_execution_gate import (
    UnrealAuthorizationGateError,
    UnrealAuthorizedExecutionGate,
    operation_to_action_spec,
    task_plan_to_action_specs,
)
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_executor import (
    UnrealPlanExecutionError,
    UnrealPlanExecutionResult,
    UnrealPlanExecutor,
)
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner
from planning.unreal_transport_contract import (
    UnrealTransportRequest,
    UnrealTransportResponse,
)


# ---------------------------------------------------------------------------
# In-memory transport (same pattern as test_unreal_production_roundtrip)
# ---------------------------------------------------------------------------

class InMemoryTransport:
    def __init__(
        self,
        *,
        fail_at_index: Optional[int] = None,
        error_message: str = "boom",
    ):
        self._call_count = 0
        self._fail_at_index = fail_at_index
        self._error_message = error_message
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

def _make_intent(
    intent_id: str = "intent-gate-1",
    targets: Tuple[str, ...] = ("/Game/Mesh_A",),
) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="gate test intent",
        target_entity_ids=targets,
    )


def _build_gate(
    transport: Optional[InMemoryTransport] = None,
) -> Tuple[UnrealAuthorizedExecutionGate, InMemoryTransport]:
    if transport is None:
        transport = InMemoryTransport()
    adapter = UnrealAdapterProduction(transport, source_tag="gate-test")
    executor = UnrealPlanExecutor(adapter)
    gate = UnrealAuthorizedExecutionGate(executor)
    return gate, transport


# ---------------------------------------------------------------------------
# Deterministic ActionSpec conversion
# ---------------------------------------------------------------------------

class TestDeterministicConversion:
    def test_operation_to_action_spec_fields(self):
        op = UnrealOperation(
            capability=UnrealCapability.INSPECT_ACTOR,
            kind=UnrealOperationKind.READ,
            name="inspect_target_actors",
            arguments={"entity_ids": ("/Game/A",)},
            entity_ids=("/Game/A",),
        )
        spec = operation_to_action_spec(op)
        assert spec.tool == UnrealCapability.INSPECT_ACTOR.value
        assert spec.name == "inspect_target_actors"
        assert spec.arguments == {"entity_ids": ("/Game/A",)}
        assert spec.requires_success is True

    def test_task_plan_to_action_specs_length(self):
        planner = UnrealTaskPlanner()
        plan = planner.plan_material_variant(_make_intent())
        specs = task_plan_to_action_specs(plan)
        assert len(specs) == len(plan.operations)

    def test_conversion_is_deterministic(self):
        planner = UnrealTaskPlanner()
        plan = planner.plan_inspection(_make_intent())
        specs_a = task_plan_to_action_specs(plan)
        specs_b = task_plan_to_action_specs(plan)
        for a, b in zip(specs_a, specs_b):
            assert a.tool == b.tool
            assert a.name == b.name
            assert a.arguments == b.arguments
            assert a.requires_success == b.requires_success

    def test_digest_stable_across_conversions(self):
        planner = UnrealTaskPlanner()
        plan = planner.plan_material_variant(_make_intent())
        specs_a = task_plan_to_action_specs(plan)
        specs_b = task_plan_to_action_specs(plan)
        auth_a = ActionAuthorization.issue(specs_a, "auth-det-1")
        auth_b = ActionAuthorization.issue(specs_b, "auth-det-1")
        assert auth_a.plan_digest == auth_b.plan_digest


# ---------------------------------------------------------------------------
# Full flow: intent → planner → gate → executor → evidence
# ---------------------------------------------------------------------------

class TestFullFlowInspection:
    def test_inspection_round_trip(self):
        gate, transport = _build_gate()
        planner = UnrealTaskPlanner()
        plan = planner.plan_inspection(_make_intent())

        gate.load_plan(plan)
        gate.authorize("auth-gate-001")

        result = gate.execute()

        assert isinstance(result, UnrealPlanExecutionResult)
        assert result.success is True
        assert result.intent_id == plan.intent_id
        assert len(result.evidence_ledger) == len(plan.operations)

    def test_evidence_operation_names_match(self):
        gate, transport = _build_gate()
        planner = UnrealTaskPlanner()
        plan = planner.plan_inspection(_make_intent())

        gate.load_plan(plan)
        gate.authorize("auth-gate-002")
        result = gate.execute()

        for op, ev in zip(plan.operations, result.evidence_ledger):
            assert ev.operation_name == op.name

    def test_evidence_verified_always_false(self):
        gate, transport = _build_gate()
        planner = UnrealTaskPlanner()
        plan = planner.plan_inspection(_make_intent())

        gate.load_plan(plan)
        gate.authorize("auth-gate-003")
        result = gate.execute()

        for ev in result.evidence_ledger:
            assert ev.verified is False


class TestFullFlowMaterialVariant:
    def test_material_variant_round_trip(self):
        gate, transport = _build_gate()
        planner = UnrealTaskPlanner()
        plan = planner.plan_material_variant(_make_intent())

        gate.load_plan(plan)
        gate.authorize("auth-gate-010")
        result = gate.execute()

        assert result.success is True
        assert len(result.evidence_ledger) == 4

    def test_authorization_id_propagated_to_transport(self):
        gate, transport = _build_gate()
        planner = UnrealTaskPlanner()
        plan = planner.plan_material_variant(_make_intent())

        gate.load_plan(plan)
        gate.authorize("auth-gate-011")
        gate.execute()

        for req in transport.requests:
            assert req.authorization_id == "auth-gate-011"

    def test_entity_ids_propagated(self):
        targets = ("/Game/Mesh_A", "/Game/Mesh_B")
        gate, transport = _build_gate()
        planner = UnrealTaskPlanner()
        plan = planner.plan_material_variant(_make_intent(targets=targets))

        gate.load_plan(plan)
        gate.authorize("auth-gate-012")
        result = gate.execute()

        for ev in result.evidence_ledger:
            assert tuple(ev.entity_ids) == targets


# ---------------------------------------------------------------------------
# Missing authorization rejection
# ---------------------------------------------------------------------------

class TestMissingAuthorization:
    def test_execute_without_authorize_raises(self):
        gate, _ = _build_gate()
        planner = UnrealTaskPlanner()
        plan = planner.plan_inspection(_make_intent())

        gate.load_plan(plan)

        with pytest.raises(UnrealAuthorizationGateError, match="not authorized"):
            gate.execute()

    def test_execute_without_load_plan_raises(self):
        gate, _ = _build_gate()

        with pytest.raises(UnrealAuthorizationGateError, match="No task plan"):
            gate.execute()

    def test_authorize_without_load_plan_raises(self):
        gate, _ = _build_gate()

        with pytest.raises(UnrealAuthorizationGateError, match="No task plan"):
            gate.authorize("auth-gate-020")


# ---------------------------------------------------------------------------
# Empty authorization ID rejection
# ---------------------------------------------------------------------------

class TestEmptyAuthorizationId:
    def test_empty_string_rejected(self):
        gate, _ = _build_gate()
        planner = UnrealTaskPlanner()
        plan = planner.plan_inspection(_make_intent())
        gate.load_plan(plan)

        with pytest.raises(UnrealAuthorizationGateError, match="authorization_id"):
            gate.authorize("")

    def test_whitespace_only_rejected(self):
        gate, _ = _build_gate()
        planner = UnrealTaskPlanner()
        plan = planner.plan_inspection(_make_intent())
        gate.load_plan(plan)

        with pytest.raises(UnrealAuthorizationGateError, match="authorization_id"):
            gate.authorize("   ")


# ---------------------------------------------------------------------------
# Authorization mismatch rejection
# ---------------------------------------------------------------------------

class TestAuthorizationMismatch:
    def test_mismatched_authorization_rejected_on_execute(self):
        """Authorize one plan, swap the task plan, then execute — must fail."""
        gate, _ = _build_gate()
        planner = UnrealTaskPlanner()

        plan_a = planner.plan_inspection(_make_intent(intent_id="a"))
        plan_b = planner.plan_material_variant(_make_intent(intent_id="b"))

        gate.load_plan(plan_a)
        gate.authorize("auth-gate-030")

        # Forcibly replace the task plan after authorization
        gate._task_plan = plan_b

        with pytest.raises(UnrealAuthorizationGateError, match="mutated"):
            gate.execute()

    def test_external_receipt_mismatch(self):
        """An authorization receipt from a different plan must not pass."""
        gate, _ = _build_gate()
        planner = UnrealTaskPlanner()

        plan_a = planner.plan_inspection(_make_intent())
        plan_b = planner.plan_material_variant(_make_intent())

        # Build a receipt for plan_b
        specs_b = task_plan_to_action_specs(plan_b)
        foreign_auth = ActionAuthorization.issue(specs_b, "auth-gate-031")

        # Load plan_a and install the foreign receipt
        gate.load_plan(plan_a)
        # Manually install the wrong authorization
        gate._action_plan.authorization = foreign_auth

        with pytest.raises(UnrealAuthorizationGateError, match="mutated"):
            gate.execute()


# ---------------------------------------------------------------------------
# Post-authorization plan mutation rejection
# ---------------------------------------------------------------------------

class TestPostAuthorizationMutation:
    def test_appending_operation_detected(self):
        gate, _ = _build_gate()
        planner = UnrealTaskPlanner()
        plan = planner.plan_inspection(_make_intent())

        gate.load_plan(plan)
        gate.authorize("auth-gate-040")

        # Mutate the task plan by replacing it with a longer one
        longer_plan = planner.plan_material_variant(_make_intent())
        gate._task_plan = longer_plan

        with pytest.raises(UnrealAuthorizationGateError, match="mutated"):
            gate.execute()

    def test_removing_operation_detected(self):
        gate, _ = _build_gate()
        planner = UnrealTaskPlanner()
        plan = planner.plan_material_variant(_make_intent())

        gate.load_plan(plan)
        gate.authorize("auth-gate-041")

        # Mutate: replace with a shorter plan
        shorter_plan = planner.plan_inspection(_make_intent())
        gate._task_plan = shorter_plan

        with pytest.raises(UnrealAuthorizationGateError, match="mutated"):
            gate.execute()

    def test_swapping_entity_ids_detected(self):
        gate, _ = _build_gate()
        planner = UnrealTaskPlanner()
        plan = planner.plan_inspection(
            _make_intent(targets=("/Game/Original",))
        )

        gate.load_plan(plan)
        gate.authorize("auth-gate-042")

        # Replace with a plan targeting different entities
        different_plan = planner.plan_inspection(
            _make_intent(targets=("/Game/Tampered",))
        )
        gate._task_plan = different_plan

        with pytest.raises(UnrealAuthorizationGateError, match="mutated"):
            gate.execute()


# ---------------------------------------------------------------------------
# Transport / evidence failure — fail-closed
# ---------------------------------------------------------------------------

class TestTransportFailure:
    def test_first_operation_failure_propagates(self):
        transport = InMemoryTransport(fail_at_index=0)
        gate, _ = _build_gate(transport)
        planner = UnrealTaskPlanner()
        plan = planner.plan_inspection(_make_intent())

        gate.load_plan(plan)
        gate.authorize("auth-gate-050")

        with pytest.raises(UnrealPlanExecutionError, match="failed"):
            gate.execute()

    def test_mid_plan_failure_aborts(self):
        transport = InMemoryTransport(fail_at_index=2)
        gate, _ = _build_gate(transport)
        planner = UnrealTaskPlanner()
        plan = planner.plan_material_variant(_make_intent())

        gate.load_plan(plan)
        gate.authorize("auth-gate-051")

        with pytest.raises(UnrealPlanExecutionError):
            gate.execute()

        # Only 3 requests sent (indices 0, 1, 2 — failure at 2)
        assert len(transport.requests) == 3

    def test_failure_does_not_produce_partial_result(self):
        transport = InMemoryTransport(fail_at_index=1)
        gate, _ = _build_gate(transport)
        planner = UnrealTaskPlanner()
        plan = planner.plan_material_variant(_make_intent())

        gate.load_plan(plan)
        gate.authorize("auth-gate-052")

        with pytest.raises(UnrealPlanExecutionError):
            gate.execute()


# ---------------------------------------------------------------------------
# Introspection properties
# ---------------------------------------------------------------------------

class TestIntrospection:
    def test_is_authorized_false_before_authorize(self):
        gate, _ = _build_gate()
        planner = UnrealTaskPlanner()
        plan = planner.plan_inspection(_make_intent())
        gate.load_plan(plan)
        assert gate.is_authorized is False

    def test_is_authorized_true_after_authorize(self):
        gate, _ = _build_gate()
        planner = UnrealTaskPlanner()
        plan = planner.plan_inspection(_make_intent())
        gate.load_plan(plan)
        gate.authorize("auth-gate-060")
        assert gate.is_authorized is True

    def test_is_authorized_false_without_plan(self):
        gate, _ = _build_gate()
        assert gate.is_authorized is False

    def test_action_plan_exposed(self):
        gate, _ = _build_gate()
        planner = UnrealTaskPlanner()
        plan = planner.plan_inspection(_make_intent())
        action_plan = gate.load_plan(plan)
        assert gate.action_plan is action_plan

    def test_task_plan_exposed(self):
        gate, _ = _build_gate()
        planner = UnrealTaskPlanner()
        plan = planner.plan_inspection(_make_intent())
        gate.load_plan(plan)
        assert gate.task_plan is plan

    def test_load_plan_resets_authorization(self):
        gate, _ = _build_gate()
        planner = UnrealTaskPlanner()
        plan = planner.plan_inspection(_make_intent())

        gate.load_plan(plan)
        gate.authorize("auth-gate-061")
        assert gate.is_authorized is True

        # Loading a new plan must reset authorization
        plan2 = planner.plan_inspection(_make_intent(intent_id="new"))
        gate.load_plan(plan2)
        assert gate.is_authorized is False


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------

class TestConstructorValidation:
    def test_non_executor_rejected(self):
        with pytest.raises(TypeError, match="UnrealPlanExecutor"):
            UnrealAuthorizedExecutionGate("not-an-executor")

    def test_load_plan_rejects_non_task_plan(self):
        gate, _ = _build_gate()
        with pytest.raises(TypeError, match="UnrealTaskPlan"):
            gate.load_plan("not-a-plan")
