"""M12.4 deterministic tests — Unreal semantic → runtime adapter boundary.

Covers: adapter contract (immutable input/output, invalid plan + identity
rejection); per-step operation mapping (+ required input / target-state /
provenance / capability / dependency preservation); safety (unsupported
operations / unknown idempotence / unsupported capability fail closed; no
authorization / receipt / recovery / scheduler / evidence verification generated);
render (render-bearing plan recognized correctly; existing render restriction intact;
no MRQ submission; no authorization fabrication; no synthetic verification);
determinism (identical plan → identical mapping; stable canonical serialization);
authority isolation (no authority-shaped methods; no production-record mutation).
"""

import json

import pytest

from planning.m12 import (
    DEFAULT_UNREAL_CATALOG,
    UnrealExecutionPlan,
    UnrealExecutionPlanStep,
    UnrealRuntimeAdapterError,
    UnrealRuntimeMapping,
    UnrealRuntimeStepMapping,
    UnsupportedCompileMappingError,
    compile_unreal_semantic_task,
    generate_execution_plan,
    map_unreal_execution_plan,
)
from planning.m12.execution_plan import _deterministic_step_id
from planning.m12.runtime_adapter import (
    EXISTING_RUNTIME_INSPECT_TOOL,
    REQUIRES_EXISTING_RENDER_SUBMISSION_PATH,
    compute_source_task_digest,
    is_forbidden_authority_key,
)
from planning.m12.semantic_task import UnrealProductionTaskDefinition
from planning.m12.target_state import target_state_spec
from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.task_definition import AtlasTaskDefinition


def _resolve(**params):
    return DEFAULT_UNREAL_CATALOG.resolve(**params)


def _sequence_task():
    return _resolve(
        name="unreal.sequence-configure",
        parameters={
            "twin_id": "twin-1",
            "sequence_name": "main",
            "frame_start": 1,
            "frame_end": 24,
        },
        digital_twin_id="twin-1",
        provenance={"proposal_source": "qwen-proposal-v1"},
    )


def _foreign_task():
    """A valid semantic task whose identity differs from the sequence task."""
    return _resolve(
        name="unreal.camera-configure",
        parameters={"twin_id": "twin-1", "camera_slots": [1, 2]},
        digital_twin_id="twin-1",
    )


def _task(provenance=None):
    return _sequence_task() if provenance is None else _resolve(
        name="unreal.sequence-configure",
        parameters={
            "twin_id": "twin-1",
            "sequence_name": "main",
            "frame_start": 1,
            "frame_end": 24,
        },
        digital_twin_id="twin-1",
        provenance=provenance,
    )


def _plan(task=None):
    task = task or _sequence_task()
    return generate_execution_plan(task)


def _map(plan=None, task=None):
    task = task or _sequence_task()
    plan = plan or generate_execution_plan(task)
    return map_unreal_execution_plan(plan, source_task=task)


# ---------------------------------------------------------------------------
# Adapter contract
# ---------------------------------------------------------------------------


def test_mapping_is_frozen_and_immutable():
    mapping = _map()
    assert isinstance(mapping, UnrealRuntimeMapping)
    with pytest.raises(Exception):
        mapping.plan_id = "mutated"
    assert mapping.can_execute is False


def test_mapping_canonical_serialization_is_stable():
    m1 = _map()
    m2 = _map()
    assert m1.canonical_json() == m2.canonical_json()
    parsed = json.loads(m1.canonical_json())
    assert parsed["source_task_id"] == "unreal.sequence-configure"
    assert parsed["catalog_version"] == 1
    assert parsed["digital_twin_id"] == "twin-1"
    assert parsed["requires_existing_render_submission_path"] is False


def test_map_rejects_non_plan_input():
    with pytest.raises(TypeError):
        map_unreal_execution_plan("not-a-plan", source_task=_sequence_task())


def test_map_rejects_non_task_source():
    plan = _plan()
    with pytest.raises(TypeError):
        map_unreal_execution_plan(plan, source_task="not-a-task")


def test_map_rejects_identity_mismatch():
    plan = _plan()
    foreign = _foreign_task()
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan, source_task=foreign)


def test_map_rejects_step_operation_mismatch():
    plan = _plan()
    base = _sequence_task()
    reordered = UnrealProductionTaskDefinition(
        canonical_task_id=base.canonical_task_id,
        task_class=base.task_class,
        digital_twin_id=base.digital_twin_id,
        task_version=base.task_version,
        intent=base.intent,
        target_state=base.target_state,
        evidence=base.evidence,
        actions=base.actions,
        allowed_action_tools=base.allowed_action_tools,
        allowed_mutations=base.allowed_mutations,
        dependencies=tuple(reversed(base.dependencies)),
        provenance=dict(base.provenance or {}),
        metadata=dict(base.metadata or {}),
    )
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan, source_task=reordered)


# ---------------------------------------------------------------------------
# Operation mapping
# ---------------------------------------------------------------------------


def test_non_render_map_reuses_existing_atlas_runtime():
    mapping = _map()
    assert mapping.runtime_task_snapshot is not None
    assert mapping.runtime_task_digest is not None
    assert isinstance(mapping.materialize_runtime_task(), AtlasTaskDefinition)
    assert mapping.requires_existing_render_submission_path is False
    assert mapping.render_plan is False


def test_per_step_mappings_target_existing_runtime_inspect():
    mapping = _map()
    ops = [s.semantic_operation for s in mapping.steps]
    assert ops == ["scene_setup", "camera_setup", "sequence_setup"]
    for step in mapping.steps:
        assert step.supported
        assert step.target_runtime_operation == EXISTING_RUNTIME_INSPECT_TOOL


def test_per_step_required_inputs_preserved():
    mapping = _map()
    for step in mapping.steps:
        assert isinstance(step.required_inputs, tuple)


def test_dependencies_preserved_in_mapping():
    mapping = _map()
    by_op = {s.semantic_operation: s for s in mapping.steps}
    assert by_op["camera_setup"].dependencies == (
        "unreal.sequence-configure:scene_setup:000",
    )
    assert set(by_op["sequence_setup"].dependencies) == {
        "unreal.sequence-configure:scene_setup:000",
        "unreal.sequence-configure:camera_setup:001",
    }


def test_target_state_preserved_in_mapping():
    mapping = _map()
    by_op = {s.semantic_operation: s for s in mapping.steps}
    assert by_op["scene_setup"].target_state_contributions == ("scene_initialized",)


def test_idempotence_preserved_in_mapping():
    mapping = _map()
    by_op = {s.semantic_operation: s for s in mapping.steps}
    assert by_op["scene_setup"].idempotence == "idempotent"


def test_capability_preserved_in_mapping():
    mapping = _map()
    for step in mapping.steps:
        assert step.capability_requirement == "inspect-only"


def test_provenance_preserved_through_mapping():
    mapping = _map(task=_task(provenance={"proposal_source": "qwen-proposal-v1"}))
    assert mapping.provenance["proposal_source"] == "qwen-proposal-v1"


def test_identity_fields_not_collapsed():
    mapping = _map()
    assert mapping.plan_id != mapping.source_task_id
    assert mapping.digital_twin_id == "twin-1"
    assert mapping.source_task_version == 1
    assert mapping.catalog_version == 1
    # runtime mapping carries distinct identity; mapping keeps plan/task/twin distinct.
    assert isinstance(mapping.materialize_runtime_task(), AtlasTaskDefinition)


# ---------------------------------------------------------------------------
# Safety (fail closed)
# ---------------------------------------------------------------------------


def _scene_task():
    """A single-fragment (scene-prepare) task whose plan has exactly one step."""
    return _resolve(
        name="unreal.scene-prepare",
        parameters={"twin_id": "twin-1"},
        digital_twin_id="twin-1",
    )


def _plan_with_single_step(task, idempotence, capability="inspect-only"):
    """Build an execution plan with exactly one step carrying the given
    idempotence/capability, matching the source task's single-fragment
    dependencies so the adapter reaches (and exercises) the guard."""
    fragment_ids = tuple(task.dependencies)
    assert len(fragment_ids) == 1, "guard tests need a single-fragment task"
    from planning.m12.execution_plan import _build_plan_id

    step = UnrealExecutionPlanStep(
        step_id=_deterministic_step_id(task.canonical_task_id, fragment_ids[0], 0),
        semantic_operation=fragment_ids[0],
        required_inputs=(),
        preconditions=(),
        target_state_contributions=(),
        dependencies=(),
        idempotence=idempotence,
        verification_requirements=("scene_initialized",),
        execution_capability_requirement=capability,
        provenance={},
    )
    return UnrealExecutionPlan(
        plan_id=_build_plan_id(task.canonical_task_id, task.task_version, fragment_ids),
        source_task_id=task.canonical_task_id,
        source_task_version=task.task_version,
        catalog_version=1,
        digital_twin_id=task.digital_twin_id,
        steps=(step,),
        provenance={},
        render_plan=task.render_task,
    )


def test_unknown_idempotence_fails_closed():
    # A supported step that declares "unknown" idempotence cannot be mapped: the
    # adapter must never silently upgrade it to idempotent. Synthesize such a
    # plan from a single-fragment task so the guard is the reason for rejection.
    task = _scene_task()
    plan = _plan_with_single_step(task, "unknown")
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan, source_task=task)


def test_unsupported_capability_fails_closed():
    # A step requesting a capability other than the existing runtime's
    # "inspect-only" must fail closed (no new capability authority).
    task = _scene_task()
    plan = _plan_with_single_step(task, "idempotent", capability="write")
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan, source_task=task)


def test_no_authorization_material_in_mapping():
    mapping = _map()
    text = json.dumps(mapping.to_json_compatible()).lower()
    for token in (
        "receipt",
        "authorization_id",
        "manifest",
        "hmac",
        "nonce",
        "artifact_id",
        "recovery_authority",
        "attempt_nonce",
    ):
        assert token not in text, f"authority token leaked: {token}"


def test_mapping_object_has_no_authority_methods():
    mapping = _map()
    for attr in (
        "execute",
        "authorize",
        "submit",
        "reconcile",
        "schedule",
        "persist",
        "mint_receipt",
        "recover",
        "verify",
    ):
        assert not hasattr(mapping, attr), f"runtime mapping must not expose {attr}"


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def _render_task(cls, params):
    return DEFAULT_UNREAL_CATALOG.resolve(cls, params, digital_twin_id="twin-1")


def test_render_execute_plan_recognized_fail_closed():
    task = _render_task("unreal.render-execute", {"twin_id": "twin-1", "sequence_name": "main"})
    plan = generate_execution_plan(task)
    assert plan.render_plan
    mapping = map_unreal_execution_plan(plan, source_task=task)
    assert mapping.render_plan
    assert mapping.requires_existing_render_submission_path
    assert mapping.runtime_task_snapshot is None
    assert mapping.materialize_runtime_task() is None
    assert mapping.can_execute is False
    for step in mapping.steps:
        assert not step.supported
        assert step.unsupported_reason == REQUIRES_EXISTING_RENDER_SUBMISSION_PATH


def test_artifact_validate_plan_recognized_fail_closed():
    task = _render_task("unreal.artifact-validate", {"twin_id": "twin-1", "artifact_ref": "a1"})
    plan = generate_execution_plan(task)
    assert plan.render_plan
    mapping = map_unreal_execution_plan(plan, source_task=task)
    assert mapping.render_plan
    assert mapping.requires_existing_render_submission_path
    assert mapping.runtime_task_snapshot is None
    assert mapping.can_execute is False


def test_render_mapping_compile_still_blocked():
    task = _render_task("unreal.render-execute", {"twin_id": "twin-1", "sequence_name": "main"})
    plan = generate_execution_plan(task)
    mapping = map_unreal_execution_plan(plan, source_task=task)
    assert mapping.runtime_task_snapshot is None
    # The existing M12.1 rule is untouched: a render-bearing compile still raises
    # UnsupportedCompileMappingError. M12.4 does not work around it.
    with pytest.raises(UnsupportedCompileMappingError):
        compile_unreal_semantic_task(task)


def test_render_mapping_does_not_submit_or_fabricate():
    task = _render_task("unreal.render-execute", {"twin_id": "twin-1", "sequence_name": "main"})
    plan = generate_execution_plan(task)
    mapping = map_unreal_execution_plan(plan, source_task=task)
    text = json.dumps(mapping.to_json_compatible(), default=str).lower()
    for token in ("submitted", "job_id", "receipt", "authorization_id", "render_job", "attempt_nonce"):
        assert token not in text, f"render-submission material leaked: {token}"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_identical_input_identical_mapping():
    m1 = _map()
    m2 = _map()
    assert m1.canonical_json() == m2.canonical_json()
    assert m1.to_json_compatible() == m2.to_json_compatible()


# ---------------------------------------------------------------------------
# Adversarial regression tests (red-team remediation)
# ---------------------------------------------------------------------------


def _render_src():
    """A render-bearing (unreal.render-execute) source task."""
    return DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.render-execute",
        {"twin_id": "twin-1", "sequence_name": "main"},
        digital_twin_id="twin-1",
    )


def _clone_sequence_plan(step_overrides=None, plan_provenance=None, render=None):
    """Reconstruct an UnrealExecutionPlan for the sequence task with optional
    adversarial step/plan tampering (bypasses M12.3's generator)."""
    base = generate_execution_plan(_sequence_task())
    steps = []
    for i, s in enumerate(base.steps):
        ov = (step_overrides or {}).get(i, {})
        steps.append(
            UnrealExecutionPlanStep(
                step_id=ov.get("step_id", s.step_id),
                semantic_operation=ov.get("semantic_operation", s.semantic_operation),
                required_inputs=ov.get("required_inputs", s.required_inputs),
                preconditions=ov.get("preconditions", s.preconditions),
                target_state_contributions=ov.get("target_state_contributions", s.target_state_contributions),
                dependencies=ov.get("dependencies", s.dependencies),
                idempotence=ov.get("idempotence", s.idempotence),
                verification_requirements=ov.get("verification_requirements", s.verification_requirements),
                execution_capability_requirement=ov.get("execution_capability_requirement", s.execution_capability_requirement),
                provenance=ov.get("provenance", dict(s.provenance)),
            )
        )
    kw = dict(
        plan_id=base.plan_id,
        source_task_id=base.source_task_id,
        source_task_version=base.source_task_version,
        catalog_version=base.catalog_version,
        digital_twin_id=base.digital_twin_id,
        steps=tuple(steps),
        provenance=plan_provenance if plan_provenance is not None else dict(base.provenance),
    )
    if render is not None:
        kw["render_plan"] = render
    return UnrealExecutionPlan(**kw)


# ---- Fix 1: authority/secret smuggling -------------------------------------------


@pytest.mark.parametrize("token", [
    "authorization_id", "authorization", "receipt", "receipt_id",
    "attempt_nonce", "nonce", "hmac", "hmac_key", "api_key", "credential",
    "recovery_authority", "artifact_id", "manifest_id", "scheduler",
    "retry_controller", "protected_flag", "is_authorized",
])
def test_fix1_forbidden_authority_in_plan_provenance_rejected(token):
    plan = _clone_sequence_plan(plan_provenance={"proposal_source": "qwen", token: "forged"})
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan, source_task=_sequence_task())


def test_fix1_forbidden_authority_in_step_provenance_rejected():
    plan = _clone_sequence_plan({0: {"provenance": {"authorization_id": "x"}}})
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan, source_task=_sequence_task())


def test_fix1_legitimate_provenance_preserved():
    plan = _clone_sequence_plan(plan_provenance={"proposal_source": "qwen-proposal-v1", "note": "kept"})
    mapping = map_unreal_execution_plan(plan, source_task=_sequence_task())
    assert mapping.provenance["proposal_source"] == "qwen-proposal-v1"
    assert mapping.provenance["note"] == "kept"
    assert "authorization_id" not in mapping.canonical_json()


def test_fix1_is_forbidden_helper():
    assert is_forbidden_authority_key("authorization_id")
    assert is_forbidden_authority_key("hmac")
    assert is_forbidden_authority_key("attempt_nonce")
    assert not is_forbidden_authority_key("proposal_source")
    assert not is_forbidden_authority_key("note")


# ---- Fix 2: write-authority reconciliation ----------------------------------------


def test_fix2_inspect_only_plan_does_not_claim_write_authority():
    mapping = _map()
    assert all(s.capability_requirement == "inspect-only" for s in mapping.steps)
    # The immutable runtime snapshot must not permit writes for an inspect-only plan,
    # and nor must a freshly materialized copy.
    assert mapping.runtime_task_snapshot["allow_writes"] is False
    assert mapping.materialize_runtime_task().allow_writes is False


# ---- Fix 3: dependency/target-state/input fidelity --------------------------------


def test_fix3_dropped_dependency_rejected():
    plan = _clone_sequence_plan({2: {"dependencies": ()}})
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan, source_task=_sequence_task())


def test_fix3_target_state_tamper_rejected():
    plan = _clone_sequence_plan({1: {"target_state_contributions": ()}})
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan, source_task=_sequence_task())


def test_fix3_idempotence_tamper_rejected():
    # scene_setup is idempotent; claiming non-idempotent diverges from canonical.
    plan = _clone_sequence_plan({0: {"idempotence": "non-idempotent"}})
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan, source_task=_sequence_task())


def test_fix3_operation_reorder_rejected():
    plan = _clone_sequence_plan({0: {"semantic_operation": "camera_setup"}})
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan, source_task=_sequence_task())


# ---- Fix 4: fragment identity/version preserved -----------------------------------


def test_fix4_fragment_identity_version_preserved_in_steps():
    mapping = _map()
    by_op = {s.semantic_operation: s for s in mapping.steps}
    assert by_op["scene_setup"].fragment_id == "scene_setup"
    assert by_op["scene_setup"].fragment_version == 1
    assert by_op["camera_setup"].fragment_id == "camera_setup"
    assert by_op["camera_setup"].fragment_version == 1
    parsed = json.loads(mapping.canonical_json())
    assert parsed["steps"][1]["fragment_id"] == "camera_setup"
    assert parsed["steps"][1]["fragment_version"] == 1


# ---- Fix 5: render classification reconciliation ----------------------------------


def test_fix5_render_underflag_rejected():
    rt = _render_src()
    base = generate_execution_plan(rt)
    steps = [
        UnrealExecutionPlanStep(
            step_id=s.step_id, semantic_operation=s.semantic_operation,
            required_inputs=s.required_inputs, preconditions=s.preconditions,
            target_state_contributions=s.target_state_contributions,
            dependencies=s.dependencies, idempotence=s.idempotence,
            verification_requirements=s.verification_requirements,
            execution_capability_requirement=s.execution_capability_requirement,
            provenance=dict(s.provenance),
        )
        for s in base.steps
    ]
    under = UnrealExecutionPlan(
        plan_id=base.plan_id, source_task_id=base.source_task_id,
        source_task_version=base.source_task_version, catalog_version=base.catalog_version,
        digital_twin_id=base.digital_twin_id, steps=tuple(steps),
        provenance=dict(base.provenance), render_plan=False,
    )
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(under, source_task=rt)


def test_fix5_render_overflag_rejected():
    # non-render source over-flagged render_plan=True must fail closed
    plan = _clone_sequence_plan(render=True)
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan, source_task=_sequence_task())


def test_fix5_render_true_path_unchanged():
    rt = _render_src()
    mapping = map_unreal_execution_plan(generate_execution_plan(rt), source_task=rt)
    assert mapping.render_plan
    assert mapping.requires_existing_render_submission_path
    assert mapping.runtime_task_snapshot is None
    assert mapping.can_execute is False
    assert mapping.semantic_fidelity == "unavailable"


# ---- Fix 6: deep immutability -----------------------------------------------------


def test_fix6_provenance_deep_frozen():
    mapping = _map()
    with pytest.raises(TypeError):
        mapping.provenance["x"] = "y"  # MappingProxyType is read-only
    with pytest.raises(TypeError):
        mapping.steps[0].provenance["x"] = "y"
    before = mapping.canonical_json()
    assert mapping.canonical_json() == before


# ---- Fix 7: semantic-fidelity decision explicit -----------------------------------


def test_fix7_semantic_fidelity_declared():
    mapping = _map()
    assert mapping.semantic_fidelity == "aggregate"
    assert "semantic_fidelity" in mapping.to_json_compatible()
    rm = map_unreal_execution_plan(
        generate_execution_plan(_render_src()), source_task=_render_src()
    )
    assert rm.semantic_fidelity == "unavailable"

# ---------------------------------------------------------------------------
# Round-2 blocker regression tests (independent red-team gate)
# ---------------------------------------------------------------------------


# ---- R2-1: nested / casing / alias authority smuggling ---------------------


@pytest.mark.parametrize("token", [
    "authorization_id", "authorization", "receipt", "attempt_nonce", "nonce",
    "hmac", "hmac_key", "api_key", "credential", "recovery_authority",
    "artifact_id", "manifest_id", "scheduler", "retry_controller",
    "protected_flag", "is_authorized", "authorized",
])
@pytest.mark.parametrize("shape", ["nested_dict", "nested_list", "cased", "alias"])
def test_r2_forbidden_authority_nested_casing_alias_rejected(token, shape):
    if shape == "nested_dict":
        prov = {"proposal_source": "qwen", "notes": {"meta": {token: "forged"}}}
    elif shape == "nested_list":
        prov = {"proposal_source": "qwen", "notes": [{"meta": [{token: "forged"}]}]}
    elif shape == "cased":
        prov = {"proposal_source": "qwen", token.upper(): "forged"}
    else:  # alias
        alias = {"api_key": "apiKey", "recognized_render_plan": "recognizedRenderPlan",
                 "attempt_nonce": "attemptNonce", "authorization": "Authorisation",
                 "session": "sessionToken", "jwt": "jwt"}.get(token, token)
        prov = {"proposal_source": "qwen", alias: "forged"}
    plan = _clone_sequence_plan(plan_provenance=prov)
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan, source_task=_sequence_task())


def test_r2_nested_step_provenance_rejected():
    plan = _clone_sequence_plan({0: {"provenance": {"meta": {"receipt": {"id": "r"}}}}})
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan, source_task=_sequence_task())


def test_r2_is_forbidden_alias_vocabulary():
    for k in ("api_key", "apiKey", "apikey", "API_KEY", "IS_AUTHORIZED",
              "IsAuthorized", "session_token", "sessionToken", "client_secret",
              "private_key", "jwt", "bearer", "password", "hmac"):
        assert is_forbidden_authority_key(k), k
    for k in ("proposal_source", "note", "stage", "sequence_name"):
        assert not is_forbidden_authority_key(k), k


# ---- R2-2: embedded runtime-task mutation isolation --------------------------


def test_r2_runtime_task_no_mutable_handle_exposed():
    # The mapping must NOT expose a mutable AtlasTaskDefinition that can diverge
    # from the canonical snapshot/digest.
    mapping = _map()
    assert not hasattr(mapping, "runtime_task")
    assert mapping.runtime_task_snapshot is not None
    assert mapping.runtime_task_digest is not None
    # Materialize a copy and mutate it aggressively.
    mat = mapping.materialize_runtime_task()
    mat.allowed_action_tools.add("unreal_render")
    mat.metadata["unreal_semantic_task_class"] = "render-execute"
    # allow_writes is a frozen field on AtlasTaskDefinition (itself immutable by
    # tuple/set semantics); assigning raises — a fresh-frozen + isolated object.
    with pytest.raises(Exception):  # FrozenInstanceError (or FrozenSet)
        mat.allow_writes = True
    # The snapshot/digest/canonical view are completely unaffected.
    assert "unreal_render" not in mapping.runtime_task_snapshot["allowed_action_tools"]
    assert mapping.runtime_task_snapshot["allow_writes"] is False
    assert mapping.runtime_task_snapshot["metadata"]["unreal_semantic_task_class"] == "sequence-configure"
    # A fresh materialization is isolated again.
    assert "unreal_render" not in mapping.materialize_runtime_task().allowed_action_tools
    # The snapshot itself is deeply immutable.
    with pytest.raises((TypeError, AttributeError)):
        mapping.runtime_task_snapshot["allow_writes"] = True


def test_r2_canonical_binds_runtime_permissions():
    mapping = _map()
    before = mapping.canonical_json()
    rt = mapping.materialize_runtime_task()
    rt.allowed_action_tools.add("unreal_render")
    assert mapping.canonical_json() == before
    parsed = json.loads(before)
    assert parsed["runtime_task_snapshot"]["allowed_action_tools"] == ["unreal_inspect"]
    assert parsed["runtime_task_digest"]


# ---- R2-3: fidelity reconciliation on every step incl. render path -----------


def test_r2_render_path_step_fidelity_reconciled():
    rt = _render_src()
    base = generate_execution_plan(rt)
    # render_setup step is index 3; forge its target-state contributions.
    st = list(base.steps)
    st[3] = UnrealExecutionPlanStep(
        step_id=st[3].step_id, semantic_operation=st[3].semantic_operation,
        required_inputs=st[3].required_inputs, preconditions=st[3].preconditions,
        target_state_contributions=("forged_invariant",),
        dependencies=st[3].dependencies, idempotence=st[3].idempotence,
        verification_requirements=st[3].verification_requirements,
        execution_capability_requirement=st[3].execution_capability_requirement,
        provenance=dict(st[3].provenance),
    )
    forged = UnrealExecutionPlan(
        plan_id=base.plan_id, source_task_id=base.source_task_id,
        source_task_version=base.source_task_version, catalog_version=base.catalog_version,
        digital_twin_id=base.digital_twin_id, steps=tuple(st),
        provenance=dict(base.provenance), render_plan=True,
    )
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(forged, source_task=rt)


def test_r2_render_path_precondition_tamper_rejected():
    rt = _render_src()
    base = generate_execution_plan(rt)
    st = list(base.steps)
    st[3] = UnrealExecutionPlanStep(
        step_id=st[3].step_id, semantic_operation=st[3].semantic_operation,
        required_inputs=st[3].required_inputs, preconditions=(),
        target_state_contributions=st[3].target_state_contributions,
        dependencies=st[3].dependencies, idempotence=st[3].idempotence,
        verification_requirements=st[3].verification_requirements,
        execution_capability_requirement=st[3].execution_capability_requirement,
        provenance=dict(st[3].provenance),
    )
    forged = UnrealExecutionPlan(
        plan_id=base.plan_id, source_task_id=base.source_task_id,
        source_task_version=base.source_task_version, catalog_version=base.catalog_version,
        digital_twin_id=base.digital_twin_id, steps=tuple(st),
        provenance=dict(base.provenance), render_plan=True,
    )
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(forged, source_task=rt)


def test_r2_preconditions_and_verification_preserved():
    mapping = _map()
    by_op = {s.semantic_operation: s for s in mapping.steps}
    assert by_op["camera_setup"].preconditions == ("scene_ready",)
    assert by_op["camera_setup"].verification_requirements == ("cameras_configured",)
    assert by_op["sequence_setup"].preconditions == ("cameras_ready", "scene_ready")
    assert by_op["sequence_setup"].verification_requirements == ("sequence_configured",)


def test_r2_canonic_step_layout_has_preconditions_and_verification():
    mapping = _map()
    step0 = json.loads(mapping.canonical_json())["steps"][0]
    assert "preconditions" in step0
    assert "verification_requirements" in step0


# ---- R2-4: source binding / deterministic digest -----------------------------


def _seq_task_named(seq_name):
    return _resolve(
        name="unreal.sequence-configure",
        parameters={
            "twin_id": "twin-1", "sequence_name": seq_name,
            "frame_start": 1, "frame_end": 24,
        },
        digital_twin_id="twin-1",
        provenance={"proposal_source": "qwen-proposal-v1"},
    )


def test_r2_source_digest_binds_resolved_content():
    ta = _seq_task_named("main")
    tb = _seq_task_named("OTHER")
    da = compute_source_task_digest(ta)
    db = compute_source_task_digest(tb)
    assert da != db  # same class/version/twin, different resolved content

    mapping = map_unreal_execution_plan(generate_execution_plan(ta), source_task=ta)
    assert mapping.source_task_digest == da
    assert "source_task_digest" in json.loads(mapping.canonical_json())


def test_r2_expected_source_digest_rejects_substitution():
    ta = _seq_task_named("main")
    tb = _seq_task_named("OTHER")
    digA = compute_source_task_digest(ta)
    plan = generate_execution_plan(ta)
    # Substituting B for A with the expected digest of A fails closed.
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan, source_task=tb, expected_source_task_digest=digA)
    # Correct source + digest accepted.
    m = map_unreal_execution_plan(plan, source_task=ta, expected_source_task_digest=digA)
    assert m.source_task_digest == digA


def test_r2_adapter_owned_provenance_not_shadowable():
    # A caller seeding adapter-owned PLAN-level keys is rejected.
    plan = _clone_sequence_plan(plan_provenance={"recognized_render_plan": True})
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan, source_task=_sequence_task())
    plan2 = _clone_sequence_plan(plan_provenance={"semantic_fidelity": "unavailable"})
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan2, source_task=_sequence_task())
    plan3 = _clone_sequence_plan(plan_provenance={"source_task_digest": "deadbeef"})
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan3, source_task=_sequence_task())
    # A caller seeding STEP-level fragment identity is OVERWRITTEN to canonical
    # (adapter truth wins; no shadow survives).
    forged_step = _clone_sequence_plan({0: {"provenance": {
        "fragment_id": "render_setup", "fragment_version": 999,
        "target_state_contribution": ["forged"],
    }}})
    mapping = map_unreal_execution_plan(forged_step, source_task=_sequence_task())
    assert mapping.steps[0].fragment_id == "scene_setup"
    assert mapping.steps[0].fragment_version == 1
    assert mapping.steps[0].provenance["fragment_id"] == "scene_setup"
    assert mapping.steps[0].provenance["fragment_version"] == 1
    # Adapter-owned provenance is authoritative on the real mapping.
    mapping2 = _map()
    assert mapping2.provenance["recognized_render_plan"] is False
    assert mapping2.provenance["semantic_fidelity"] == "aggregate"
    assert mapping2.provenance["mapped_runtime_task_type"] == "AtlasTaskDefinition"


# ---- R2-5: deterministic binding / nested canonical-json-safety ----------------

def test_r2_deterministic_source_binding():
    ta = _seq_task_named("main")
    m1 = map_unreal_execution_plan(generate_execution_plan(ta), source_task=ta)
    m2 = map_unreal_execution_plan(generate_execution_plan(ta), source_task=ta)
    assert m1.source_task_digest == m2.source_task_digest
    assert m1.canonical_json() == m2.canonical_json()


def test_r2_nested_provenance_canonical_json_serializes():
    # Nested legit provenance under an ALLOWED key must not break canonical
    # serialization (the earlier MappingProxyType bug) and must be deterministic.
    # (B3: unknown keys are now rejected by the closed allowlist.)
    plan = _clone_sequence_plan(plan_provenance={
        "proposal_source": "qwen",
        "note": {"stage": "proposal", "k": [1, 2, {"legit": "ok"}]},
    })
    mapping = map_unreal_execution_plan(plan, source_task=_sequence_task())
    canonical = mapping.canonical_json()  # must not raise TypeError
    parsed = json.loads(canonical)
    assert parsed["provenance"]["note"]["stage"] == "proposal"
    assert parsed["provenance"]["note"]["k"][2]["legit"] == "ok"


def test_r2_nested_provenance_immutable_after_construction():
    plan = _clone_sequence_plan(plan_provenance={"proposal_source": "qwen", "note": {"stage": "p"}})
    mapping = map_unreal_execution_plan(plan, source_task=_sequence_task())
    with pytest.raises((TypeError, AttributeError)):
        mapping.provenance["note"]["stage"] = "tampered"
    before = mapping.canonical_json()
    # Mutating the ORIGINAL plan provenance after mapping must not change canonical.
    import copy
    # The mapping froze a copy at construction; the caller's dict is separate.
    assert mapping.canonical_json() == before


def test_r2_canonical_provenance_adapter_keys_authoritative():
    mapping = _map()
    parsed = json.loads(mapping.canonical_json())
    assert parsed["provenance"]["recognized_render_plan"] is False
    assert parsed["provenance"]["semantic_fidelity"] == "aggregate"
    assert parsed["source_task_digest"]

# ---------------------------------------------------------------------------
# Round-3 regression tests (independent red-team gate #2 — 9 blockers)
# ---------------------------------------------------------------------------


def _build_task(canonical_task_id, task_class, invariant_names, actions, allowed_tools,
                dependencies, expects_render=False, provenance=None, metadata=None,
                idempotence_fields=None):
    """Construct a validated M12.1 semantic task with chosen actions/tools."""
    return UnrealProductionTaskDefinition(
        canonical_task_id=canonical_task_id,
        task_class=task_class,
        digital_twin_id="twin-1",
        task_version=1,
        intent="i",
        target_state=target_state_spec(
            description="d",
            invariant_names=invariant_names,
            expects_render=expects_render,
        ),
        evidence=(EvidenceRequest(tool="unreal_inspect", arguments={}, name="e"),),
        actions=actions,
        allowed_action_tools=frozenset(allowed_tools),
        allowed_mutations=frozenset(),
        dependencies=tuple(dependencies),
        provenance=provenance,
        metadata=metadata,
    )


# ---- B1: runtime action authority -----------------------------------------------------


def test_b1_render_tool_in_inspect_task_rejected():
    task = _build_task(
        canonical_task_id="cam-01", task_class="camera-configure",
        invariant_names=["scene_initialized", "cameras_configured"],
        actions=(ActionSpec(tool="unreal_render", arguments={}, name="a"),),
        allowed_tools=["unreal_render"],
        dependencies=("scene_setup", "camera_setup"),
    )
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(generate_execution_plan(task), source_task=task)


def test_b1_extra_render_tool_rejected():
    # Even keeping inspect, adding unreal_render to allowed tools must fail.
    task = _build_task(
        canonical_task_id="cam-02", task_class="camera-configure",
        invariant_names=["scene_initialized", "cameras_configured"],
        actions=(ActionSpec(tool="unreal_inspect", arguments={}, name="a"),),
        allowed_tools=["unreal_inspect", "unreal_render"],
        dependencies=("scene_setup", "camera_setup"),
    )
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(generate_execution_plan(task), source_task=task)


def test_b1_unknown_tool_in_actions_rejected():
    task = _build_task(
        canonical_task_id="cam-03", task_class="camera-configure",
        invariant_names=["scene_initialized", "cameras_configured"],
        actions=(ActionSpec(tool="shell", arguments={}, name="a"),),
        allowed_tools=["shell"],
        dependencies=("scene_setup", "camera_setup"),
    )
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(generate_execution_plan(task), source_task=task)


# ---- B2: render classification from all axes ----------------------------------------


def test_b2_render_setup_via_non_render_class_rejected():
    task = _build_task(
        canonical_task_id="seq-01", task_class="sequence-configure",
        invariant_names=["scene_initialized", "cameras_configured",
                         "sequence_configured", "render_configured"],
        actions=(ActionSpec(tool="unreal_inspect", arguments={}, name="a"),),
        allowed_tools=["unreal_inspect"],
        dependencies=("scene_setup", "camera_setup", "sequence_setup", "render_setup"),
    )
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(generate_execution_plan(task), source_task=task)


def test_b2_render_class_still_fails_toward_boundary():
    # A legitimate render-execute task routes to the render boundary.
    rt = _render_src()
    m = map_unreal_execution_plan(generate_execution_plan(rt), source_task=rt)
    assert m.render_plan
    assert m.requires_existing_render_submission_path
    assert m.runtime_task_snapshot is None


def test_b2_artifact_validate_still_routes_to_boundary():
    task = DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.artifact-validate", {"twin_id": "twin-1", "artifact_ref": "a"},
        digital_twin_id="twin-1",
    )
    m = map_unreal_execution_plan(generate_execution_plan(task), source_task=task)
    assert m.render_plan
    assert m.requires_existing_render_submission_path
    assert m.runtime_task_snapshot is None


# ---- B3: provenance closed allowlist + source metadata smuggling --------------------


def test_b3_unknown_provenance_key_rejected():
    plan = _clone_sequence_plan(plan_provenance={"proposal_source": "q", "signature": "x"})
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan, source_task=_sequence_task())


def test_b3_source_metadata_smuggling_rejected():
    task = DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.camera-configure",
        {"twin_id": "twin-1", "camera_slots": {"authorization_id": "forged"}},
        digital_twin_id="twin-1",
    )
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(generate_execution_plan(task), source_task=task)


def test_b3_legitimate_provenance_preserved():
    plan = _clone_sequence_plan(plan_provenance={"proposal_source": "qwen-proposal-v1", "note": "ok"})
    m = map_unreal_execution_plan(plan, source_task=_sequence_task())
    assert m.provenance["proposal_source"] == "qwen-proposal-v1"
    assert m.provenance["note"] == "ok"


# ---- B4: snapshot is the sole authoritative runtime representation ----------------

def test_b4_no_hidden_backing_task():
    m = _map()
    assert not hasattr(m, "_materialized_runtime_task")
    rt = m.materialize_runtime_task()
    rt.allowed_action_tools.add("unreal_render")
    rt.metadata["x"] = "t"
    assert m.runtime_task_snapshot["allowed_action_tools"] == ("unreal_inspect",)
    assert "x" not in m.runtime_task_snapshot["metadata"]
    assert "unreal_render" not in m.canonical_json()
    assert sorted(m.materialize_runtime_task().allowed_action_tools) == ["unreal_inspect"]


def test_b4_materialize_rebuild_matches_digest():
    m = _map()
    rt = m.materialize_runtime_task()
    # Rebuilding a second time and comparing the digest-consistent snapshot.
    from planning.m12.runtime_adapter import _atlas_to_snapshot, _freeze_json, _thaw_json, _digest_of_jsonable
    snap2 = _freeze_json(_atlas_to_snapshot(rt))
    assert _digest_of_jsonable(_thaw_json(snap2)) == m.runtime_task_digest


# ---- B5: unresolved requirements fail closed -----------------------------------------


def test_b5_orphan_step_fails_closed():
    task = _build_task(
        canonical_task_id="cam-orphan", task_class="camera-configure",
        invariant_names=["cameras_configured"],
        actions=(ActionSpec(tool="unreal_inspect", arguments={}, name="a"),),
        allowed_tools=["unreal_inspect"],
        dependencies=("camera_setup",),
    )
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(generate_execution_plan(task), source_task=task)


# ---- B6: catalog version single source of truth -------------------------------------


def test_b6_catalog_version_conflict_rejected():
    plan = _plan()
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(plan, source_task=_sequence_task(), catalog_version=999)


def test_b6_catalog_version_agrees_accepted():
    plan = _plan()
    m = map_unreal_execution_plan(plan, source_task=_sequence_task(), catalog_version=1)
    assert m.catalog_version == 1


# ---- B7: declared / validated semantics machine-visible -----------------------------


def test_b7_declared_false_for_clean_mapping():
    m = _map()
    assert all(s.declared is False for s in m.steps)
    assert m.provenance["declared"] is False
    assert m.provenance["reconciled"] is True


def test_b7_step_with_caller_provenance_is_declared():
    plan = _clone_sequence_plan({0: {"provenance": {"proposal_source": "other"}}})
    m = map_unreal_execution_plan(plan, source_task=_sequence_task())
    assert m.steps[0].declared is True


# ---- B8: strict JSON / canonical representation --------------------------------------


def test_b8_nan_via_source_parameter_rejected():
    task = DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.camera-configure", {"twin_id": "twin-1", "camera_slots": [float("nan")]},
        digital_twin_id="twin-1",
    )
    with pytest.raises(UnrealRuntimeAdapterError):
        map_unreal_execution_plan(generate_execution_plan(task), source_task=task)


def test_b8_canonical_json_is_strict_and_stable():
    m1 = _map()
    m2 = _map()
    assert m1.canonical_json() == m2.canonical_json()
    # allow_nan=False means we never emit NaN/Infinity.
    assert "NaN" not in m1.canonical_json()
    assert "Infinity" not in m1.canonical_json()


# ---- B9: self-validating construction -----------------------------------------------


def test_b9_direct_invalid_render_contradiction_rejected():
    from types import MappingProxyType
    s = UnrealRuntimeStepMapping(
        step_id="s0", semantic_operation="scene_setup", supported=True,
        target_runtime_operation="unreal_inspect", target_state_contributions=("scene_initialized",),
        idempotence="idempotent", fragment_id="scene_setup", fragment_version=1,
        verification_requirements=("scene_initialized",), provenance={"proposal_source": "q"},
    )
    with pytest.raises(UnrealRuntimeAdapterError):
        UnrealRuntimeMapping(
            plan_id="p", source_task_id="t", source_task_version=1, catalog_version=1,
            digital_twin_id="twin-1", steps=(s,),
            render_plan=True, requires_existing_render_submission_path=False,
            runtime_task_snapshot=None, runtime_task_digest=None,
            semantic_fidelity="aggregate", source_task_digest="a" * 64,
            provenance={"proposal_source": "q"},
        )


def test_b9_direct_invalid_snapshot_tools_rejected():
    from types import MappingProxyType
    from planning.m12.runtime_adapter import _freeze_json
    s = UnrealRuntimeStepMapping(
        step_id="s0", semantic_operation="scene_setup", supported=True,
        target_runtime_operation="unreal_inspect", target_state_contributions=("scene_initialized",),
        idempotence="idempotent", fragment_id="scene_setup", fragment_version=1,
        verification_requirements=("scene_initialized",), provenance={"proposal_source": "q"},
    )
    snap = _freeze_json({
        "name": "x", "evidence": [],
        "actions": [{"tool": "unreal_inspect", "arguments": {}, "name": "a",
                     "requires_success": True, "depends_on": []}],
        "allowed_action_tools": ["unreal_render"],
        "allow_writes": False, "verify_after_action": True, "metadata": {},
    })
    with pytest.raises(UnrealRuntimeAdapterError):
        UnrealRuntimeMapping(
            plan_id="p", source_task_id="t", source_task_version=1, catalog_version=1,
            digital_twin_id="twin-1", steps=(s,),
            render_plan=False, requires_existing_render_submission_path=False,
            runtime_task_snapshot=snap, runtime_task_digest="deadbeef",
            semantic_fidelity="aggregate", source_task_digest="a" * 64,
            provenance={"proposal_source": "q"},
        )

