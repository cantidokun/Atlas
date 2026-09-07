"""M12.1 deterministic tests — semantic task contract + normalization/compile.

Covers: immutable construction, malformed/unsupported rejection, canonicalization
determinism, stable serialization, target-state validation, dependency
preservation, provenance preservation, compile determinism, compile failure on
unsupported mappings, authorization isolation, and canonical twin/artifact
identity separation.
"""

import json

import pytest

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.m12 import (
    UnauthorizedSemanticFieldError,
    UnrealProductionTaskDefinition,
    UnrealSemanticTaskError,
    UnsupportedCompileMappingError,
    compile_unreal_semantic_task,
    normalize_unreal_semantic_request,
    target_state_spec,
)
from planning.task_definition import AtlasTaskDefinition


def make_raw(**overrides):
    raw = {
        "canonical_task_id": "cam-01-setup",
        "task_class": "camera-configure",
        "digital_twin_id": "twin-stadium-01",
        "task_name": "Configure camera slot 1",
        "task_version": 2,
        "intent": "Configure primary camera framing for the match.",
        "target_state": {
            "description": "Camera slot 1 framed at the configured pan/tilt.",
            "invariant_names": ["camera_slot_1_framed"],
            "expects_render": False,
        },
        "allowed_mutations": ["camera-configure"],
        "dependencies": ["scene-prepare"],
        "evidence": [
            {
                "tool": "unreal_inspect",
                "arguments": {"capability": "camera"},
                "name": "inspect_camera",
            }
        ],
        "actions": [
            {
                "tool": "unreal_inspect",
                "arguments": {"op": "get_capabilities"},
                "name": "inspect_capabilities",
                "requires_success": True,
                "depends_on": [],
            },
            {
                "tool": "unreal_inspect",
                "arguments": {"op": "inspect", "target": "camera"},
                "name": "inspect_camera",
                "requires_success": False,
                "depends_on": ["inspect_capabilities"],
            },
        ],
        "allowed_action_tools": ["unreal_inspect"],
        "provenance": {
            "proposal_source": "qwen-proposal-v1",
            "proposal_id": "prop-abc-123",
        },
        "metadata": {"stage": "m12.1"},
    }
    raw.update(overrides)
    return raw


# ---------------------------------------------------------------------------
# Immutable construction
# ---------------------------------------------------------------------------


def test_normalize_produces_frozen_task():
    task = normalize_unreal_semantic_request(make_raw())
    assert isinstance(task, UnrealProductionTaskDefinition)
    # Frozen dataclass cannot be mutated.
    with pytest.raises(Exception):
        task.intent = "mutated"
    assert task.intent == "Configure primary camera framing for the match."


def test_direct_construction_validates_and_is_frozen():
    task = UnrealProductionTaskDefinition(
        canonical_task_id="cam-02",
        task_class="lighting-configure",
        digital_twin_id="twin-stadium-01",
        task_version=1,
        intent="Set lighting rig states.",
        target_state=target_state_spec(
            description="Lighting invoked.", invariant_names=["lighting_set"]
        ),
        evidence=(
            EvidenceRequest(tool="unreal_inspect", arguments={}, name="inspect"),
        ),
        actions=(
            ActionSpec(tool="unreal_inspect", arguments={}, name="inspect"),
        ),
        allowed_action_tools=frozenset({"unreal_inspect"}),
    )
    with pytest.raises(Exception):
        task.intent = "mutated"
    assert task.task_class == "lighting-configure"
    # A frozen dataclass with a mangled instance cannot be added to (immutable).
    assert task.digital_twin_id == "twin-stadium-01"


def test_direct_construction_rejects_bare_value_error_classes():
    # Reserved task class rejected at construction too.
    with pytest.raises(UnrealSemanticTaskError):
        UnrealProductionTaskDefinition(
            canonical_task_id="x",
            task_class="effect-pass-prepare",
            digital_twin_id="twin",
            task_version=1,
            intent="i",
            target_state=target_state_spec(description="d", invariant_names=["s"]),
            evidence=(),
            actions=(),
            allowed_action_tools=frozenset(),
        )


# ---------------------------------------------------------------------------
# Malformed / unsupported rejection
# ---------------------------------------------------------------------------


def test_rejects_empty_canonical_task_id():
    with pytest.raises(UnrealSemanticTaskError):
        normalize_unreal_semantic_request(make_raw(canonical_task_id="  "))


def test_rejects_whitespace_in_digital_twin_id():
    with pytest.raises(UnrealSemanticTaskError):
        normalize_unreal_semantic_request(make_raw(digital_twin_id="twin stadium 1"))


def test_rejects_unsupported_task_class():
    with pytest.raises(UnrealSemanticTaskError):
        normalize_unreal_semantic_request(make_raw(task_class="not-a-task"))


def test_rejects_reserved_future_task_class():
    with pytest.raises(UnrealSemanticTaskError):
        normalize_unreal_semantic_request(make_raw(task_class="effect-pass-prepare"))


def test_rejects_empty_intent():
    with pytest.raises(UnrealSemanticTaskError):
        normalize_unreal_semantic_request(make_raw(intent="  "))


def test_rejects_bad_task_version():
    with pytest.raises(UnrealSemanticTaskError):
        normalize_unreal_semantic_request(make_raw(task_version=0))
    with pytest.raises(UnrealSemanticTaskError):
        normalize_unreal_semantic_request(make_raw(task_version="one"))


def test_rejects_empty_evidence():
    with pytest.raises(UnrealSemanticTaskError):
        normalize_unreal_semantic_request(make_raw(evidence=[]))


def test_rejects_empty_actions():
    with pytest.raises(UnrealSemanticTaskError):
        normalize_unreal_semantic_request(make_raw(actions=[]))


def test_rejects_action_with_unauthorized_tool():
    raw = make_raw()
    raw["actions"] = [{"tool": "shell_exec", "arguments": {}, "name": "bad"}]
    with pytest.raises(UnrealSemanticTaskError):
        normalize_unreal_semantic_request(raw)


def test_rejects_render_task_without_render_target_state():
    raw = make_raw(
        task_class="render-execute",
        target_state={"description": "rendered", "invariant_names": ["done"]},
    )
    with pytest.raises(UnrealSemanticTaskError):
        normalize_unreal_semantic_request(raw)


def test_rejects_non_render_task_with_render_target_state():
    raw = make_raw(
        target_state={
            "description": "x",
            "invariant_names": ["done"],
            "expects_render": True,
        }
    )
    with pytest.raises(UnrealSemanticTaskError):
        normalize_unreal_semantic_request(raw)


def test_rejects_unknown_top_level_field():
    with pytest.raises(UnrealSemanticTaskError):
        normalize_unreal_semantic_request(make_raw(bogus_field=1))


# ---------------------------------------------------------------------------
# Canonicalization determinism & stable serialization
# ---------------------------------------------------------------------------


def test_normalization_is_deterministic():
    a = normalize_unreal_semantic_request(make_raw())
    b = normalize_unreal_semantic_request(make_raw())
    assert a == b
    assert a.canonical_json() == b.canonical_json()


def test_serialization_is_stable_and_reproducible():
    a = normalize_unreal_semantic_request(make_raw())
    j1 = a.canonical_json()
    j2 = a.canonical_json()
    assert j1 == j2
    parsed = json.loads(j1)
    assert parsed["canonical_task_id"] == "cam-01-setup"
    assert parsed["task_class"] == "camera-configure"
    assert parsed["digital_twin_id"] == "twin-stadium-01"
    assert parsed["task_version"] == 2
    assert "authorization" not in json.dumps(parsed).lower()


def test_serialization_has_no_authority_keys():
    task = normalize_unreal_semantic_request(make_raw())
    text = json.dumps(task.to_json_compatible()).lower()
    for token in (
        "authorization",
        "receipt",
        "artifact_id",
        "manifest_id",
        "hmac",
        "nonce",
        "api_key",
    ):
        assert token not in text, f"forbidden token leaked: {token}"


# ---------------------------------------------------------------------------
# Target-state validation
# ---------------------------------------------------------------------------


def test_target_state_preserved_and_inspectable():
    task = normalize_unreal_semantic_request(make_raw())
    assert task.target_state.invariant_names == frozenset({"camera_slot_1_framed"})
    assert task.target_state.to_invariant_names() == ("camera_slot_1_framed",)
    assert task.target_state.expects_render is False


def test_target_state_missing_description_rejected():
    raw = make_raw()
    raw["target_state"] = {"invariant_names": ["x"]}
    with pytest.raises(UnrealSemanticTaskError):
        normalize_unreal_semantic_request(raw)


# ---------------------------------------------------------------------------
# Dependency preservation
# ---------------------------------------------------------------------------


def test_dependencies_preserved():
    task = normalize_unreal_semantic_request(make_raw())
    assert task.dependencies == ("scene-prepare",)
    compiled = compile_unreal_semantic_task(task)
    assert compiled.metadata["unreal_semantic_dependencies"] == ["scene-prepare"]


def test_action_dependency_graph_preserved_in_compile():
    task = normalize_unreal_semantic_request(make_raw())
    compiled = compile_unreal_semantic_task(task)
    actions = {a.name: a.dependency_names() for a in compiled.actions}
    assert actions["inspect_camera"] == ("inspect_capabilities",)
    assert actions["inspect_capabilities"] == ()


# ---------------------------------------------------------------------------
# Provenance preservation
# ---------------------------------------------------------------------------


def test_provenance_preserved_and_canonical_ids_added():
    task = normalize_unreal_semantic_request(make_raw())
    compiled = compile_unreal_semantic_task(task)
    prov = compiled.metadata["unreal_provenance"]
    assert prov["proposal_source"] == "qwen-proposal-v1"
    # Serialization provenance carries canonical identity but never collapses
    # artifact identity into twin identity.
    ser = task.to_json_compatible()
    assert ser["digital_twin_id"] == "twin-stadium-01"
    assert "proposal_source" in ser["provenance"]


# ---------------------------------------------------------------------------
# Compile determinism / boundary
# ---------------------------------------------------------------------------


def test_compile_produces_atlas_task_definition():
    task = normalize_unreal_semantic_request(make_raw())
    compiled = compile_unreal_semantic_task(task)
    assert isinstance(compiled, AtlasTaskDefinition)
    assert compiled.name == "Configure camera slot 1"  # task_name takes precedence
    assert compiled.metadata["unreal_semantic_task_id"] == "cam-01-setup"
    assert compiled.metadata["unreal_digital_twin_id"] == "twin-stadium-01"


def test_compile_is_deterministic():
    t1 = compile_unreal_semantic_task(normalize_unreal_semantic_request(make_raw()))
    t2 = compile_unreal_semantic_task(normalize_unreal_semantic_request(make_raw()))
    assert t1.snapshot() == t2.snapshot()


def test_compile_fails_for_render_task():
    raw = make_raw(
        task_class="render-execute",
        digital_twin_id="twin-stadium-01",
        target_state={
            "description": "render",
            "invariant_names": ["done"],
            "expects_render": True,
        },
    )
    task = normalize_unreal_semantic_request(raw)
    with pytest.raises(UnsupportedCompileMappingError):
        compile_unreal_semantic_task(task)


# ---------------------------------------------------------------------------
# Authorization isolation
# ---------------------------------------------------------------------------


def test_normalization_never_trusts_authorization_material():
    raw = make_raw()
    raw["authorization_id"] = "gotcha"
    with pytest.raises(UnauthorizedSemanticFieldError):
        normalize_unreal_semantic_request(raw)


def test_authorization_smuggled_in_provenance_rejected():
    raw = make_raw()
    raw["provenance"] = {"authorization_id": "gotcha"}
    with pytest.raises(UnauthorizedSemanticFieldError):
        normalize_unreal_semantic_request(raw)


def test_compiled_task_never_mints_receipt_or_recovery():
    task = normalize_unreal_semantic_request(make_raw())
    compiled = compile_unreal_semantic_task(task)
    text = json.dumps(compiled.snapshot()).lower()
    for token in ("receipt", "authorization_id", "artifact_manifest", "recovery"):
        assert token not in text, f"authority token leaked into compile: {token}"


def test_semantic_layer_has_no_scheduler_or_persistence():
    task = normalize_unreal_semantic_request(make_raw())
    compiled = compile_unreal_semantic_task(task)
    assert not hasattr(task, "submit_render")
    assert not hasattr(task, "reconcile_render_jobs")
    assert not hasattr(compiled, "authorize")
    assert not hasattr(compiled, "schedule")
    assert not hasattr(compiled, "persist")


# ---------------------------------------------------------------------------
# Canonical twin / artifact identity separation
# ---------------------------------------------------------------------------


def test_artifact_material_rejected_from_provenance():
    raw = make_raw()
    raw["provenance"] = {"artifact_manifest": "must-not-coalesce"}
    with pytest.raises(UnauthorizedSemanticFieldError):
        normalize_unreal_semantic_request(raw)


def test_twin_identity_not_collapsed_with_artifact_identity():
    task = normalize_unreal_semantic_request(make_raw())
    ser = task.to_json_compatible()
    assert ser["digital_twin_id"] == "twin-stadium-01"
    # No artifact identity is synthesized or stored on the semantic task.
    assert "artifact_id" not in ser
    assert "manifest_id" not in ser