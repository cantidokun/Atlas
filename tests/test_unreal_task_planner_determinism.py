"""Determinism, validation, and authorization-compatibility tests for UnrealTaskPlanner.

Covers:
- Deterministic equivalent planning (same intent → same plan)
- Stable operation ordering, kinds, names, and entity IDs
- Invalid / ambiguous intent rejection
- Absence of execution side effects during planning
- Compatibility with ActionSpec conversion and ActionAuthorization binding
"""

import copy
import pytest
from typing import Tuple

from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionPlan, ActionSpec
from planning.unreal_agent import (
    UnrealCapability,
    UnrealOperation,
    UnrealOperationKind,
    UnrealTaskIntent,
)
from planning.unreal_authorized_execution_gate import (
    operation_to_action_spec,
    task_plan_to_action_specs,
)
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _intent(
    intent_id: str = "det-intent-1",
    targets: Tuple[str, ...] = ("/Game/Mesh_A",),
    description: str = "determinism test",
) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description=description,
        target_entity_ids=targets,
    )


# ---------------------------------------------------------------------------
# Deterministic equivalent planning
# ---------------------------------------------------------------------------

class TestDeterministicEquivalentPlanning:
    """Equivalent valid intents must produce equivalent plans."""

    def test_inspection_same_intent_same_plan(self):
        planner = UnrealTaskPlanner()
        plan_a = planner.plan_inspection(_intent())
        plan_b = planner.plan_inspection(_intent())

        assert plan_a.intent_id == plan_b.intent_id
        assert len(plan_a.operations) == len(plan_b.operations)
        for op_a, op_b in zip(plan_a.operations, plan_b.operations):
            assert op_a == op_b

    def test_material_variant_same_intent_same_plan(self):
        planner = UnrealTaskPlanner()
        plan_a = planner.plan_material_variant(_intent())
        plan_b = planner.plan_material_variant(_intent())

        assert plan_a.intent_id == plan_b.intent_id
        assert len(plan_a.operations) == len(plan_b.operations)
        for op_a, op_b in zip(plan_a.operations, plan_b.operations):
            assert op_a == op_b

    def test_separate_planner_instances_produce_same_plan(self):
        plan_a = UnrealTaskPlanner().plan_inspection(_intent())
        plan_b = UnrealTaskPlanner().plan_inspection(_intent())

        for op_a, op_b in zip(plan_a.operations, plan_b.operations):
            assert op_a == op_b

    def test_different_intent_ids_produce_different_plan_ids(self):
        planner = UnrealTaskPlanner()
        plan_a = planner.plan_inspection(_intent(intent_id="aaa"))
        plan_b = planner.plan_inspection(_intent(intent_id="bbb"))

        assert plan_a.intent_id != plan_b.intent_id

    def test_different_targets_produce_different_operations(self):
        planner = UnrealTaskPlanner()
        plan_a = planner.plan_inspection(_intent(targets=("/Game/A",)))
        plan_b = planner.plan_inspection(_intent(targets=("/Game/B",)))

        for op_a, op_b in zip(plan_a.operations, plan_b.operations):
            assert op_a.entity_ids != op_b.entity_ids


# ---------------------------------------------------------------------------
# Stable ordering
# ---------------------------------------------------------------------------

class TestStableOrdering:
    """Operation order must be fixed and meaningful."""

    def test_inspection_order_is_read_then_verify(self):
        plan = UnrealTaskPlanner().plan_inspection(_intent())
        assert len(plan.operations) == 2
        assert plan.operations[0].kind == UnrealOperationKind.READ
        assert plan.operations[1].kind == UnrealOperationKind.VERIFY

    def test_material_variant_order_is_read_read_write_verify(self):
        plan = UnrealTaskPlanner().plan_material_variant(_intent())
        assert len(plan.operations) == 4
        expected_kinds = [
            UnrealOperationKind.READ,
            UnrealOperationKind.READ,
            UnrealOperationKind.WRITE,
            UnrealOperationKind.VERIFY,
        ]
        actual_kinds = [op.kind for op in plan.operations]
        assert actual_kinds == expected_kinds

    def test_ordering_stable_across_many_invocations(self):
        planner = UnrealTaskPlanner()
        reference = planner.plan_material_variant(_intent())
        for _ in range(20):
            plan = planner.plan_material_variant(_intent())
            for op_ref, op_new in zip(reference.operations, plan.operations):
                assert op_ref.name == op_new.name
                assert op_ref.kind == op_new.kind


# ---------------------------------------------------------------------------
# Operation and entity correctness
# ---------------------------------------------------------------------------

class TestOperationEntityCorrectness:
    """Each operation must carry the correct capability, name, and entity IDs."""

    def test_inspection_operations_have_correct_capabilities(self):
        plan = UnrealTaskPlanner().plan_inspection(_intent())
        assert plan.operations[0].capability == UnrealCapability.INSPECT_ACTOR
        assert plan.operations[1].capability == UnrealCapability.INSPECT_ACTOR

    def test_material_variant_operations_have_correct_capabilities(self):
        plan = UnrealTaskPlanner().plan_material_variant(_intent())
        assert plan.operations[0].capability == UnrealCapability.INSPECT_ACTOR
        assert plan.operations[1].capability == UnrealCapability.MATERIAL
        assert plan.operations[2].capability == UnrealCapability.MATERIAL
        assert plan.operations[3].capability == UnrealCapability.MATERIAL

    def test_inspection_operation_names(self):
        plan = UnrealTaskPlanner().plan_inspection(_intent())
        assert plan.operations[0].name == "inspect_target_actors"
        assert plan.operations[1].name == "verify_target_actor_mapping"

    def test_material_variant_operation_names(self):
        plan = UnrealTaskPlanner().plan_material_variant(_intent())
        names = [op.name for op in plan.operations]
        assert names == [
            "inspect_target_actors",
            "inspect_material_state",
            "apply_material_variant",
            "verify_material_variant",
        ]

    def test_all_operations_carry_intent_entity_ids(self):
        targets = ("/Game/X", "/Game/Y")
        plan = UnrealTaskPlanner().plan_material_variant(_intent(targets=targets))
        for op in plan.operations:
            assert tuple(op.entity_ids) == targets

    def test_single_target_propagated(self):
        targets = ("/Game/Solo",)
        plan = UnrealTaskPlanner().plan_inspection(_intent(targets=targets))
        for op in plan.operations:
            assert tuple(op.entity_ids) == targets

    def test_plan_intent_id_matches_input(self):
        intent = _intent(intent_id="my-unique-id")
        plan = UnrealTaskPlanner().plan_inspection(intent)
        assert plan.intent_id == "my-unique-id"


# ---------------------------------------------------------------------------
# Invalid / ambiguous intent rejection
# ---------------------------------------------------------------------------

class TestInvalidIntentRejection:
    """Invalid or ambiguous intents must be rejected, not silently normalized."""

    def test_no_targets_rejected_inspection(self):
        intent = UnrealTaskIntent(
            intent_id="no-targets",
            description="missing targets",
            target_entity_ids=(),
        )
        with pytest.raises(ValueError, match="target entity"):
            UnrealTaskPlanner().plan_inspection(intent)

    def test_no_targets_rejected_material_variant(self):
        intent = UnrealTaskIntent(
            intent_id="no-targets",
            description="missing targets",
            target_entity_ids=(),
        )
        with pytest.raises(ValueError, match="target entity"):
            UnrealTaskPlanner().plan_material_variant(intent)

    def test_whitespace_only_target_rejected(self):
        intent = UnrealTaskIntent(
            intent_id="ws-target",
            description="whitespace target",
            target_entity_ids=("   ",),
        )
        with pytest.raises(ValueError, match="non-empty"):
            UnrealTaskPlanner().plan_inspection(intent)

    def test_empty_string_target_rejected(self):
        intent = UnrealTaskIntent(
            intent_id="empty-target",
            description="empty target",
            target_entity_ids=("",),
        )
        with pytest.raises(ValueError, match="non-empty"):
            UnrealTaskPlanner().plan_inspection(intent)

    def test_mixed_valid_and_empty_targets_rejected(self):
        intent = UnrealTaskIntent(
            intent_id="mixed",
            description="mixed targets",
            target_entity_ids=("/Game/Valid", ""),
        )
        with pytest.raises(ValueError, match="non-empty"):
            UnrealTaskPlanner().plan_material_variant(intent)

    def test_non_intent_type_rejected_inspection(self):
        with pytest.raises(TypeError, match="UnrealTaskIntent"):
            UnrealTaskPlanner().plan_inspection("not-an-intent")

    def test_non_intent_type_rejected_material_variant(self):
        with pytest.raises(TypeError, match="UnrealTaskIntent"):
            UnrealTaskPlanner().plan_material_variant(42)

    def test_none_rejected(self):
        with pytest.raises(TypeError, match="UnrealTaskIntent"):
            UnrealTaskPlanner().plan_inspection(None)


# ---------------------------------------------------------------------------
# UnrealTaskPlan post-init validation
# ---------------------------------------------------------------------------

class TestTaskPlanValidation:
    """UnrealTaskPlan must reject structurally invalid construction."""

    def test_empty_intent_id_rejected(self):
        op = UnrealOperation(
            capability=UnrealCapability.INSPECT_ACTOR,
            kind=UnrealOperationKind.READ,
            name="op",
            arguments={},
            entity_ids=("/Game/A",),
        )
        with pytest.raises(ValueError, match="intent_id"):
            UnrealTaskPlan(intent_id="", operations=(op,))

    def test_whitespace_intent_id_rejected(self):
        op = UnrealOperation(
            capability=UnrealCapability.INSPECT_ACTOR,
            kind=UnrealOperationKind.READ,
            name="op",
            arguments={},
            entity_ids=("/Game/A",),
        )
        with pytest.raises(ValueError, match="intent_id"):
            UnrealTaskPlan(intent_id="   ", operations=(op,))

    def test_empty_operations_rejected(self):
        with pytest.raises(ValueError, match="at least one"):
            UnrealTaskPlan(intent_id="valid-id", operations=())


# ---------------------------------------------------------------------------
# Absence of execution side effects during planning
# ---------------------------------------------------------------------------

class TestNoSideEffects:
    """Planning must not execute, mutate, or produce observable side effects."""

    def test_planning_does_not_modify_intent(self):
        intent = _intent(targets=("/Game/A", "/Game/B"))
        original_targets = intent.target_entity_ids
        original_id = intent.intent_id
        original_desc = intent.description

        planner = UnrealTaskPlanner()
        planner.plan_inspection(intent)
        planner.plan_material_variant(intent)

        assert intent.target_entity_ids == original_targets
        assert intent.intent_id == original_id
        assert intent.description == original_desc

    def test_plan_is_frozen(self):
        plan = UnrealTaskPlanner().plan_inspection(_intent())
        with pytest.raises(AttributeError):
            plan.intent_id = "tampered"
        with pytest.raises(AttributeError):
            plan.operations = ()

    def test_operations_are_frozen(self):
        plan = UnrealTaskPlanner().plan_inspection(_intent())
        for op in plan.operations:
            with pytest.raises(AttributeError):
                op.name = "tampered"

    def test_repeated_planning_produces_independent_plans(self):
        planner = UnrealTaskPlanner()
        plan_a = planner.plan_inspection(_intent())
        plan_b = planner.plan_inspection(_intent())
        # Equal but not the same object
        assert plan_a == plan_b
        assert plan_a is not plan_b
        assert plan_a.operations is not plan_b.operations


# ---------------------------------------------------------------------------
# Compatibility with ActionSpec conversion and authorization
# ---------------------------------------------------------------------------

class TestAuthorizationCompatibility:
    """Plans must convert cleanly to ActionSpecs and produce stable digests."""

    def test_inspection_converts_to_action_specs(self):
        plan = UnrealTaskPlanner().plan_inspection(_intent())
        specs = task_plan_to_action_specs(plan)
        assert len(specs) == len(plan.operations)
        for spec in specs:
            assert isinstance(spec, ActionSpec)

    def test_material_variant_converts_to_action_specs(self):
        plan = UnrealTaskPlanner().plan_material_variant(_intent())
        specs = task_plan_to_action_specs(plan)
        assert len(specs) == 4

    def test_action_spec_tool_matches_capability_value(self):
        plan = UnrealTaskPlanner().plan_material_variant(_intent())
        specs = task_plan_to_action_specs(plan)
        for op, spec in zip(plan.operations, specs):
            assert spec.tool == op.capability.value

    def test_action_spec_name_matches_operation_name(self):
        plan = UnrealTaskPlanner().plan_inspection(_intent())
        specs = task_plan_to_action_specs(plan)
        for op, spec in zip(plan.operations, specs):
            assert spec.name == op.name

    def test_action_spec_requires_success_always_true(self):
        plan = UnrealTaskPlanner().plan_material_variant(_intent())
        specs = task_plan_to_action_specs(plan)
        for spec in specs:
            assert spec.requires_success is True

    def test_authorization_digest_stable_for_inspection(self):
        planner = UnrealTaskPlanner()
        specs_a = task_plan_to_action_specs(planner.plan_inspection(_intent()))
        specs_b = task_plan_to_action_specs(planner.plan_inspection(_intent()))
        auth_a = ActionAuthorization.issue(specs_a, "auth-det-1")
        auth_b = ActionAuthorization.issue(specs_b, "auth-det-1")
        assert auth_a.plan_digest == auth_b.plan_digest

    def test_authorization_digest_stable_for_material_variant(self):
        planner = UnrealTaskPlanner()
        specs_a = task_plan_to_action_specs(planner.plan_material_variant(_intent()))
        specs_b = task_plan_to_action_specs(planner.plan_material_variant(_intent()))
        auth_a = ActionAuthorization.issue(specs_a, "auth-det-2")
        auth_b = ActionAuthorization.issue(specs_b, "auth-det-2")
        assert auth_a.plan_digest == auth_b.plan_digest

    def test_authorization_receipt_matches_converted_specs(self):
        plan = UnrealTaskPlanner().plan_material_variant(_intent())
        specs = task_plan_to_action_specs(plan)
        auth = ActionAuthorization.issue(specs, "auth-match-1")
        assert auth.matches(specs) is True

    def test_different_plans_produce_different_digests(self):
        planner = UnrealTaskPlanner()
        specs_insp = task_plan_to_action_specs(planner.plan_inspection(_intent()))
        specs_mat = task_plan_to_action_specs(planner.plan_material_variant(_intent()))
        auth_insp = ActionAuthorization.issue(specs_insp, "auth-diff")
        auth_mat = ActionAuthorization.issue(specs_mat, "auth-diff")
        assert auth_insp.plan_digest != auth_mat.plan_digest

    def test_different_targets_produce_different_digests(self):
        planner = UnrealTaskPlanner()
        specs_a = task_plan_to_action_specs(
            planner.plan_inspection(_intent(targets=("/Game/A",)))
        )
        specs_b = task_plan_to_action_specs(
            planner.plan_inspection(_intent(targets=("/Game/B",)))
        )
        auth_a = ActionAuthorization.issue(specs_a, "auth-tgt")
        auth_b = ActionAuthorization.issue(specs_b, "auth-tgt")
        assert auth_a.plan_digest != auth_b.plan_digest

    def test_action_plan_can_be_authorized_from_task_plan(self):
        plan = UnrealTaskPlanner().plan_inspection(_intent())
        specs = task_plan_to_action_specs(plan)
        action_plan = ActionPlan(actions=specs)
        auth = action_plan.authorize_with_id("auth-compat-1")
        assert action_plan.authorized is True
        assert auth.matches(specs) is True

    def test_cross_plan_authorization_does_not_match(self):
        planner = UnrealTaskPlanner()
        specs_insp = task_plan_to_action_specs(planner.plan_inspection(_intent()))
        specs_mat = task_plan_to_action_specs(planner.plan_material_variant(_intent()))
        auth_insp = ActionAuthorization.issue(specs_insp, "auth-cross")
        assert auth_insp.matches(specs_mat) is False
