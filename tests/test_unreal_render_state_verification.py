"""Deterministic coverage for render-state semantic verification (frozen design contract).

Proves the contract frozen in the verify_render_state design gate:
T-R1 positive verified path, T-R2 anti-self-comparison, T-R3 expectation provenance,
T-R4 identity/state failures, T-R5 malformed expectation before dispatch,
T-R6 registry/vacuous-pass guard, T-R7 schema and planner contract guards,
T-R8 single-authority flag guard.

No engine is involved: the adapter is a recording stub, every expected value is
plan-derived, and every observation is a fresh stub read. Nothing here is live.
"""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind, UnrealTaskIntent
from planning.unreal_capability_registry import UnrealCapabilityRegistry
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_executor import UnrealPlanExecutionError, UnrealPlanExecutor
from planning.unreal_render_contract import normalize_render_config, verify_render_config
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner
from planning.unreal_tool_schema import validate_unreal_tool_call

ENTITY_ID = "ATLAS_RENDER_TEST"
OTHER_ENTITY_ID = "ATLAS_RENDER_OTHER"
CONFIG = {
    "width": 1280,
    "height": 720,
    "start_frame": 1,
    "end_frame": 24,
    "output_directory": "Saved/AtlasRenderOutput",
    "output_format": "png",
}
CONFIG_KEYS = ("width", "height", "start_frame", "end_frame", "output_directory", "output_format")
RENDER_CONFIG_ASSET_PATH = "/Game/AtlasTest/RenderConfig"  # engine-reported, never authorized here


def _observed(config=None, entity_id=ENTITY_ID, include_render=True):
    """Observed render state as fresh engine evidence presents it."""
    if not include_render:
        return {entity_id: {"entity_id": entity_id}}
    render = {key: (config or CONFIG)[key] for key in CONFIG_KEYS}
    render["asset_path"] = RENDER_CONFIG_ASSET_PATH  # unrelated identity, ignored by verification
    return {entity_id: {"entity_id": entity_id, "render": render}}


class RecordingRenderAdapter(UnrealAdapterProduction):
    """Records every adapter call, returns one fresh observation per call."""

    def __init__(self, state=None, verify_override=None, verify_entities=None):
        super().__init__(transport=object(), source_tag="render-semantic-test")
        self.calls = []
        self.state = dict(CONFIG if state is None else state)
        self.verify_override = dict(verify_override or {})
        self.verify_entities = verify_entities

    def _observe(self, operation, observed_state):
        self.calls.append(("dispatch", operation.name))
        return UnrealEvidence(
            operation_name=operation.name,
            entity_ids=tuple(operation.entity_ids),
            observed_state=observed_state,
            source="render-semantic-test",
            verified=False,
        )

    def inspect(self, operation, authorization_id):
        return self._observe(operation, _observed(self.state))

    def apply_authorized(self, operation, authorization_id):
        for key in CONFIG_KEYS:
            if key in operation.arguments:
                self.state[key] = operation.arguments[key]
        return self._observe(operation, _observed(self.state))

    def verify(self, operation, authorization_id):
        state = dict(self.state)
        state.update(self.verify_override)
        observed = _observed(state) if self.verify_entities is None else self.verify_entities
        return self._observe(operation, observed)

    @property
    def dispatched(self):
        return [name for _, name in self.calls]


def _plan(intent_id, config=None):
    return UnrealTaskPlanner().plan_render_configuration(
        UnrealTaskIntent(intent_id, "render-state semantic verification", (ENTITY_ID,)),
        dict(config or CONFIG),
    )


def _operation(name, kind, arguments, entity_ids=(ENTITY_ID,)):
    return UnrealOperation(
        capability=UnrealCapability.RENDER,
        kind=kind,
        name=name,
        arguments={"entity_ids": tuple(entity_ids), **arguments},
        entity_ids=tuple(entity_ids),
    )


def _plan_with_verify_arguments(intent_id, verify_arguments, write_arguments=None):
    """Hand-built plan carrying an authorized WRITE and a divergent/malformed VERIFY argument set."""
    base = _plan(intent_id)
    write = dict(CONFIG if write_arguments is None else write_arguments)
    return UnrealTaskPlan(
        intent_id,
        (
            base.operations[0],
            _operation("configure_render", UnrealOperationKind.WRITE, write),
            _operation("verify_render_state", UnrealOperationKind.VERIFY, dict(verify_arguments)),
        ),
    )


def _execute(adapter, intent_id="render-semantic", plan=None):
    return UnrealPlanExecutor(adapter).execute(plan or _plan(intent_id), f"{intent_id}-auth")


# --------------------------------------------------------------------------- T-R1
def test_tr1_matching_render_state_is_semantically_verified():
    adapter = RecordingRenderAdapter()
    result = _execute(adapter, "tr1")

    assert result.success is True
    assert [e.operation_name for e in result.evidence_ledger] == [
        "inspect_render_state",
        "configure_render",
        "verify_render_state",
    ]
    assert [e.verified for e in result.evidence_ledger] == [False, False, True]
    assert adapter.dispatched == ["inspect_render_state", "configure_render", "verify_render_state"]


def test_tr1_verification_uses_its_own_fresh_read():
    adapter = RecordingRenderAdapter()
    result = _execute(adapter, "tr1-fresh")
    ledger = result.evidence_ledger

    assert ledger[2] is not ledger[0]
    assert ledger[2] is not ledger[1]
    assert adapter.dispatched.count("verify_render_state") == 1
    assert all(e.verified is False for e in ledger[:2])
    assert ledger[2].observed_state[ENTITY_ID]["render"]["width"] == CONFIG["width"]


# --------------------------------------------------------------------------- T-R2
def test_tr2_engine_state_contradicting_the_plan_fails_closed():
    adapter = RecordingRenderAdapter(verify_override={"width": CONFIG["width"] * 2})
    with pytest.raises(UnrealPlanExecutionError) as caught:
        _execute(adapter, "tr2")

    failure = caught.value.failure
    assert failure.operation_index == 2
    assert failure.operation_name == "verify_render_state"
    assert len(failure.completed_evidence) == 2
    assert all(e.verified is False for e in failure.completed_evidence)
    assert f"width={CONFIG['width']}" in failure.error
    assert f"width={CONFIG['width'] * 2}" in failure.error
    assert "does not match expected configuration" in failure.error
    assert "verify_render_state" in adapter.dispatched


@pytest.mark.parametrize(
    "field,drifted",
    [
        ("width", 640),
        ("height", 480),
        ("start_frame", 5),
        ("end_frame", 12),
        ("output_directory", "Saved/OtherRenderOutput"),
        ("output_format", "exr"),
    ],
)
def test_tr2_observed_state_is_never_the_expectation(field, drifted):
    adapter = RecordingRenderAdapter(verify_override={field: drifted})
    with pytest.raises(UnrealPlanExecutionError, match="does not match expected configuration"):
        _execute(adapter, f"tr2-{field}")


# --------------------------------------------------------------------------- T-R3
def test_tr3_expectation_comes_from_the_authorized_verify_arguments():
    # The authorized WRITE configures 1920; the authorized VERIFICATION independently expects 1280.
    plan = _plan_with_verify_arguments(
        "tr3-provenance",
        verify_arguments=dict(CONFIG, width=1280),
        write_arguments=dict(CONFIG, width=1920),
    )
    adapter = RecordingRenderAdapter(state=dict(CONFIG, width=1920))

    with pytest.raises(UnrealPlanExecutionError, match="does not match expected configuration") as caught:
        _execute(adapter, "tr3-provenance", plan=plan)

    error = caught.value.failure.error
    assert "width=1280" in error  # authorized VERIFY argument, not the write's value
    assert "width=1920" in error  # fresh engine state, which followed the authorized write


def test_tr3_unrelated_engine_identity_is_not_bound():
    # The engine reports a render-config asset path; Atlas has no authorized argument for it.
    adapter = RecordingRenderAdapter()
    result = _execute(adapter, "tr3-identity")
    assert result.evidence_ledger[2].verified is True
    assert result.evidence_ledger[2].observed_state[ENTITY_ID]["render"]["asset_path"] == RENDER_CONFIG_ASSET_PATH


# --------------------------------------------------------------------------- T-R4
def test_tr4_wrong_entity_identity_fails_closed():
    adapter = RecordingRenderAdapter(verify_entities={OTHER_ENTITY_ID: _observed(CONFIG)[ENTITY_ID]})
    with pytest.raises(UnrealPlanExecutionError, match="missing state for entity"):
        _execute(adapter, "tr4-entity")


def test_tr4_missing_render_mapping_fails_closed():
    adapter = RecordingRenderAdapter(verify_entities=_observed(include_render=False))
    with pytest.raises(UnrealPlanExecutionError, match="missing render state for entity"):
        _execute(adapter, "tr4-render")


def test_tr4_non_mapping_entity_state_fails_closed():
    adapter = RecordingRenderAdapter(verify_entities={ENTITY_ID: "not-a-state"})
    with pytest.raises(UnrealPlanExecutionError, match="missing state for entity"):
        _execute(adapter, "tr4-shape")


# --------------------------------------------------------------------------- T-R5
def test_tr5_missing_authorized_field_is_rejected_before_dispatch():
    adapter = RecordingRenderAdapter()
    plan = _plan_with_verify_arguments(
        "tr5-missing-field",
        {key: CONFIG[key] for key in CONFIG_KEYS if key != "width"},
    )
    with pytest.raises(UnrealPlanExecutionError, match="failed preflight"):
        _execute(adapter, "tr5-missing-field", plan=plan)
    assert adapter.calls == []


@pytest.mark.parametrize(
    "field,bad",
    [("width", "1280"), ("width", True), ("height", None), ("end_frame", 12.5)],
)
def test_tr5_non_integer_authorized_field_is_rejected_before_dispatch(field, bad):
    adapter = RecordingRenderAdapter()
    plan = _plan_with_verify_arguments(f"tr5-{field}", dict(CONFIG, **{field: bad}))
    with pytest.raises(UnrealPlanExecutionError, match="failed preflight"):
        _execute(adapter, f"tr5-{field}", plan=plan)
    assert adapter.calls == []


# --------------------------------------------------------------------------- T-R6
def test_tr6_registration_cannot_create_a_vacuous_pass():
    verify_operation = _plan("tr6").operations[2]

    assert UnrealPlanExecutor._is_semantically_verified(verify_operation, None) is True

    adapter = RecordingRenderAdapter(verify_override={"output_format": "jpg"})
    with pytest.raises(UnrealPlanExecutionError, match="does not match expected configuration"):
        _execute(adapter, "tr6")

    assert "verify_render_state" in adapter.dispatched


# --------------------------------------------------------------------------- T-R7
def test_tr7_render_verify_argument_key_set_is_unchanged():
    registry = UnrealCapabilityRegistry()
    allowed = _operation("verify_render_state", UnrealOperationKind.VERIFY, dict(CONFIG))
    assert registry.validate_operation(allowed) is allowed

    for extra_key in (
        "asset_path",
        "job_id",
        "sequence_asset_path",
        "expected_render_config",
        "expected_asset_path",
        "metadata_key",
    ):
        rejected = _operation(
            "verify_render_state",
            UnrealOperationKind.VERIFY,
            dict(CONFIG, **{extra_key: "/Game/AtlasTest/X"}),
        )
        with pytest.raises(ValueError, match="do not match the capability schema"):
            registry.validate_operation(rejected)


def test_tr7_planner_sequence_and_payload_are_unchanged():
    plan = _plan("tr7-plan")

    assert [operation.name for operation in plan.operations] == [
        "inspect_render_state",
        "configure_render",
        "verify_render_state",
    ]
    assert plan.operations[1].arguments == plan.operations[2].arguments
    assert set(plan.operations[2].arguments) == {"entity_ids", *CONFIG_KEYS}

    snapshot = validate_unreal_tool_call(
        "verify_render_state",
        {"entity_ids": (ENTITY_ID,), "authorization_id": "tr7-auth", **CONFIG},
    )
    assert snapshot["entity_ids"] == (ENTITY_ID,)
    assert {key: snapshot[key] for key in CONFIG_KEYS} == CONFIG


def test_tr7_six_field_normalization_is_unchanged():
    config = normalize_render_config(dict(CONFIG))
    assert (config.width, config.height, config.start_frame, config.end_frame) == (1280, 720, 1, 24)
    assert config.output_directory == CONFIG["output_directory"]
    assert config.output_format == CONFIG["output_format"]

    for field in CONFIG_KEYS:
        incomplete = {key: value for key, value in CONFIG.items() if key != field}
        with pytest.raises(ValueError, match="does not match the required schema"):
            normalize_render_config(incomplete)

    with pytest.raises(TypeError, match="must be an integer"):
        normalize_render_config(dict(CONFIG, width=True))
    with pytest.raises(ValueError, match="positive"):
        normalize_render_config(dict(CONFIG, width=0))
    with pytest.raises(ValueError, match="end_frame"):
        normalize_render_config(dict(CONFIG, start_frame=24, end_frame=1))


# --------------------------------------------------------------------------- T-R8
def test_tr8_verifier_does_not_flag_evidence_and_the_executor_is_the_sole_producer():
    fresh = UnrealEvidence(
        operation_name="verify_render_state",
        entity_ids=(ENTITY_ID,),
        observed_state=_observed(CONFIG),
        source="render-semantic-test",
    )
    compared = verify_render_config(fresh, dict(CONFIG))
    assert compared is fresh
    assert compared.verified is False

    contradicting = UnrealEvidence(
        operation_name="verify_render_state",
        entity_ids=(ENTITY_ID,),
        observed_state=_observed(dict(CONFIG, width=640)),
        source="render-semantic-test",
    )
    with pytest.raises(ValueError, match="does not match expected configuration"):
        verify_render_config(contradicting, dict(CONFIG))

    adapter = RecordingRenderAdapter()
    result = _execute(adapter, "tr8")
    assert result.evidence_ledger[2].verified is True
    assert result.evidence_ledger[2].operation_name == "verify_render_state"
