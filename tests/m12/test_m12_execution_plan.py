"""M12.3 deterministic tests — Unreal semantic execution-plan boundary.

Covers: immutable plan construction, canonical serialization, deterministic IDs
and ordering, dependency/precondition/target-state preservation, provenance,
idempotence semantics, failure on ambiguity/contradiction, render-plan
representation without execution, and authority isolation.
"""

import json

import pytest

from planning.m12 import (
    DEFAULT_UNREAL_CATALOG,
    UnrealExecutionPlan,
    UnrealExecutionPlanError,
    UnrealExecutionPlanStep,
    UnsupportedCompileMappingError,
    compile_unreal_semantic_task,
    generate_execution_plan,
)


def _resolve_sequence():
    return DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.sequence-configure",
        {
            "twin_id": "twin-1",
            "sequence_name": "main",
            "frame_start": 1,
            "frame_end": 24,
        },
        digital_twin_id="twin-1",
        provenance={"proposal_source": "qwen-proposal-v1"},
    )


def _plan(**kwargs):
    return generate_execution_plan(_resolve_sequence(), **kwargs)


# ---------------------------------------------------------------------------
# Immutable construction & canonical serialization
# ---------------------------------------------------------------------------


def test_plan_is_frozen_and_immutable():
    plan = _plan()
    assert isinstance(plan, UnrealExecutionPlan)
    with pytest.raises(Exception):
        plan.plan_id = "mutated"
    assert plan.plan_id.startswith("plan:")


def test_plan_canonical_serialization_is_stable():
    p1 = _plan()
    p2 = _plan()
    assert p1.canonical_json() == p2.canonical_json()
    parsed = json.loads(p1.canonical_json())
    assert parsed["source_task_id"] == "unreal.sequence-configure"
    assert parsed["catalog_version"] == 1
    assert parsed["digital_twin_id"] == "twin-1"
    assert len(parsed["steps"]) == 3


def test_step_is_frozen():
    plan = _plan()
    with pytest.raises(Exception):
        plan.steps[0].semantic_operation = "mutated"


# ---------------------------------------------------------------------------
# Deterministic ids & ordering
# ---------------------------------------------------------------------------


def test_deterministic_step_ids_and_order():
    plan = _plan()
    plan2 = generate_execution_plan(_resolve_sequence())
    assert plan.ordered_step_ids() == plan2.ordered_step_ids()
    # Deterministic step id format.
    assert plan.ordered_step_ids()[0].endswith(":scene_setup:000")


def test_ordering_matches_fragment_dependency():
    plan = _plan()
    ops = [s.semantic_operation for s in plan.steps]
    assert ops == ["scene_setup", "camera_setup", "sequence_setup"]


# ---------------------------------------------------------------------------
# Dependency / precondition / target-state preservation
# ---------------------------------------------------------------------------


def test_dependencies_point_to_producing_steps():
    plan = _plan()
    by_op = {s.semantic_operation: s for s in plan.steps}
    # camera depends on scene_setup producing step.
    assert by_op["camera_setup"].dependencies == (
        "unreal.sequence-configure:scene_setup:000",
    )
    assert by_op["sequence_setup"].dependencies == (
        "unreal.sequence-configure:camera_setup:001",
        "unreal.sequence-configure:scene_setup:000",
    )


def test_preconditions_preserved():
    plan = _plan()
    by_op = {s.semantic_operation: s for s in plan.steps}
    assert by_op["camera_setup"].preconditions == ("scene_ready",)
    assert set(by_op["sequence_setup"].preconditions) == {
        "scene_ready",
        "cameras_ready",
    }


def test_target_state_contributions_preserved():
    plan = _plan()
    by_op = {s.semantic_operation: s for s in plan.steps}
    assert by_op["scene_setup"].target_state_contributions == ("scene_initialized",)
    assert by_op["camera_setup"].target_state_contributions == (
        "cameras_configured",
    )
    assert by_op["sequence_setup"].target_state_contributions == (
        "sequence_configured",
    )


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


def test_provenance_preserved():
    plan = _plan()
    assert plan.provenance["proposal_source"] == "qwen-proposal-v1"
    assert plan.provenance["source_task_version"] == 1
    assert plan.digital_twin_id == "twin-1"
    # No authority/artifact material.
    text = json.dumps(plan.to_json_compatible()).lower()
    for token in ("receipt", "authorization_id", "manifest", "hmac", "nonce", "artifact_id"):
        assert token not in text, f"authority token leaked: {token}"


# ---------------------------------------------------------------------------
# Idempotence semantics
# ---------------------------------------------------------------------------


def test_idempotence_carried_from_fragments():
    plan = _plan()
    by_op = {s.semantic_operation: s for s in plan.steps}
    # scene/camera/sequence are idempotent fragments.
    assert by_op["scene_setup"].idempotence == "idempotent"
    assert by_op["camera_setup"].idempotence == "idempotent"
    assert by_op["sequence_setup"].idempotence == "idempotent"


def test_render_fragment_is_non_idempotent_in_plan():
    task = DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.render-execute",
        {"twin_id": "twin-1", "sequence_name": "main"},
        digital_twin_id="twin-1",
    )
    plan = generate_execution_plan(task)
    by_op = {s.semantic_operation: s for s in plan.steps}
    assert by_op["render_setup"].idempotence == "non-idempotent"
    assert by_op["render_setup"].execution_capability_requirement == "inspect-only"


# ---------------------------------------------------------------------------
# Render-plan representation WITHOUT execution
# ---------------------------------------------------------------------------


def test_render_execute_is_authoritative_render_plan():
    task = DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.render-execute",
        {"twin_id": "twin-1", "sequence_name": "main"},
        digital_twin_id="twin-1",
    )
    plan = generate_execution_plan(task)
    # Authoritative render-bearing classification from the task contract.
    assert task.render_task is True
    assert plan.render_plan is True
    assert plan.has_render_step()
    assert not plan.can_execute  # plan has no execution capability
    # Mapping to runtime is still blocked (M12.1 rule).
    with pytest.raises(UnsupportedCompileMappingError):
        compile_unreal_semantic_task(task)


def test_artifact_validate_is_authoritative_render_plan():
    task = DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.artifact-validate",
        {"twin_id": "twin-1", "artifact_ref": "artifact-a"},
        digital_twin_id="twin-1",
    )
    plan = generate_execution_plan(task)
    # Authoritative render-bearing classification from the task contract,
    # independent of substring matching on the canonical task id.
    assert task.render_task is True
    assert plan.render_plan is True
    assert plan.has_render_step()
    assert not plan.can_execute  # plan has no execution capability
    # Mapping to runtime is still blocked (M12.1 rule) for render-bearing tasks.
    with pytest.raises(UnsupportedCompileMappingError):
        compile_unreal_semantic_task(task)


# ---------------------------------------------------------------------------
# Failure modes (fail closed)
# ---------------------------------------------------------------------------


def test_fails_on_task_with_no_fragment_dependencies():
    from planning.m12.semantic_task import UnrealProductionTaskDefinition
    from planning.m12.target_state import target_state_spec
    from action_plan import ActionSpec
    from planning.evidence_plan import EvidenceRequest

    task = UnrealProductionTaskDefinition(
        canonical_task_id="orphan",
        task_class="camera-configure",
        digital_twin_id="twin-1",
        task_version=1,
        intent="i",
        target_state=target_state_spec(
            description="d", invariant_names=["cameras_configured"]
        ),
        evidence=(EvidenceRequest(tool="unreal_inspect", arguments={}, name="e"),),
        actions=(ActionSpec(tool="unreal_inspect", arguments={}, name="a"),),
        allowed_action_tools=frozenset({"unreal_inspect"}),
        dependencies=(),
    )
    with pytest.raises(UnrealExecutionPlanError):
        generate_execution_plan(task)


def test_plan_rejects_non_task_input():
    with pytest.raises(TypeError):
        generate_execution_plan("not-a-task")


# ---------------------------------------------------------------------------
# Authorization isolation
# ---------------------------------------------------------------------------


def test_plan_object_has_no_authority_methods():
    plan = _plan()
    for attr in ("execute", "authorize", "submit", "reconcile", "schedule", "persist", "mint_receipt"):
        assert not hasattr(plan, attr), f"plan must not expose {attr}"


def test_plan_creation_has_no_side_effects_and_no_verified_flag():
    plan = _plan()
    assert not plan.__dict__.get("verified")
    snapshot = plan.to_json_compatible()
    assert "verified" not in snapshot
    assert "verification_result" not in snapshot