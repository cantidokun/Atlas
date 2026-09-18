"""Live Unreal gate for the reconciled AgentControllerHost production path.

This module is an engine-boundary validation gate, not a new feature. It drives
the real, host-owned controller path end to end:

    model response
      -> ATLAS_CONTROLLER_REQUEST
      -> AgentControllerIntent
      -> AgentTaskRequest
      -> AgentControllerHost
      -> AgentControllerLoopAdapter
      -> AgentEntrypointRuntime
      -> AgentProcessRuntime
      -> capability admission
      -> TrustedUnrealContext
      -> Unreal production capability
      -> Windows Named Pipe transport
      -> real Unreal execution
      -> fresh Unreal evidence
      -> render receipt verification
      -> UnrealProductionResultContract

The operation, authorization path, transport, and fixture identity are the
already-proven live production path (see
``test_agent_controller_production_real_integration``). Only the model text is
supplied by the test; nothing at the engine boundary is mocked.

Note: evidence read here is read-only through ``Mapping`` access. The Unreal
evidence contract freezes ``observed_state`` into a ``MappingProxyType`` tree,
so readers must not require plain ``dict`` instances.
"""

import json
from collections.abc import Mapping

import pytest

from controller.agent_controller_host import AgentControllerHost
from controller.trusted_unreal_context import TrustedUnrealContext
from planning.unreal_agent import UnrealCapability
from planning.unreal_composite_operation import build_composite_actor_operation
from planning.unreal_production_executor import UnrealProductionExecutionResult
from planning.unreal_production_operation import build_unreal_production_plan
from planning.unreal_production_planning_boundary import authorize_production_plan
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_named_pipe import NamedPipeTransportError
from tests.test_agent_controller_production_real_integration import (
    ENTITY_ID,
    _assert_transport_available,
    _integration,
    _intent,
    _read_variant_plan,
    _render_inspection_plan,
    _sequencer_inspection_plan,
    _spec,
    _state,
)

pytestmark = pytest.mark.integration

SEQUENCE_ASSET_PATH = "/Game/AtlasTest/AtlasSequencerFixtureSequence"
PRODUCTION_AUTHORIZATION_ID = "host-live-gate-production-authorization"
MODEL_DECLARED_INTENT = "model-declared-intent-is-metadata-only"

FORGED_MODEL_CONTEXT = {
    "production": True,
    "authorized_production": "FORGED-BY-MODEL",
    "intent": "FORGED-BY-MODEL",
    "sequence_asset_path": "/Game/Forged/ModelSequence",
}


def _variant_value(evidence, key):
    """Read a fixture variant mapping from frozen Unreal evidence."""
    value = _state(evidence).get(key, {}).get("variant")
    if not isinstance(value, Mapping):
        raise AssertionError(f"{key}.variant missing from Unreal evidence")
    return dict(value)


def _capture_originals(raw_executor, planner):
    """Read the live fixture state that the production transaction will mutate."""
    originals = {}

    inspection = raw_executor.execute(
        planner.plan_inspection(_intent("host-live-gate-original")),
        "host-live-gate-original-auth",
    )
    originals["state"] = _state(inspection.evidence_ledger[0])

    material = raw_executor.execute(
        _read_variant_plan(
            "host-live-gate-original-material",
            UnrealCapability.MATERIAL,
            "inspect_material_state",
        ),
        "host-live-gate-original-material-auth",
    )
    originals["material"] = _variant_value(material.evidence_ledger[0], "material")

    niagara = raw_executor.execute(
        _read_variant_plan(
            "host-live-gate-original-niagara",
            UnrealCapability.NIAGARA,
            "inspect_niagara_state",
        ),
        "host-live-gate-original-niagara-auth",
    )
    originals["niagara"] = _variant_value(niagara.evidence_ledger[0], "niagara")

    render = raw_executor.execute(
        _render_inspection_plan(_intent("host-live-gate-original-render")),
        "host-live-gate-original-render-auth",
    )
    originals["render"] = _state(render.evidence_ledger[0])["render"]

    sequencer = raw_executor.execute(
        _sequencer_inspection_plan(_intent("host-live-gate-original-sequencer")),
        "host-live-gate-original-sequencer-auth",
    )
    originals["sequencer"] = _state(sequencer.evidence_ledger[0])["sequencer"]

    return originals


def _restore_originals(raw_executor, planner, originals):
    """Restore the live fixture to its pre-gate state (proven restore sequence)."""
    state = originals["state"]
    restore_intent = _intent("host-live-gate-restore")

    restore_composite = build_composite_actor_operation(
        [ENTITY_ID],
        [
            {
                "name": "set_actor_location",
                "entity_ids": (ENTITY_ID,),
                "location": dict(state["location"]),
            },
            {
                "name": "set_actor_rotation",
                "entity_ids": (ENTITY_ID,),
                "rotation": dict(state["rotation"]),
            },
            {
                "name": "set_actor_scale",
                "entity_ids": (ENTITY_ID,),
                "scale": dict(state["scale"]),
            },
            {
                "name": "apply_material_variant",
                "entity_ids": (ENTITY_ID,),
                "variant": originals["material"]["name"],
            },
            {
                "name": "apply_niagara_variant",
                "entity_ids": (ENTITY_ID,),
                "variant": originals["niagara"]["name"],
            },
        ],
    )

    raw_executor.execute(
        planner.plan_composite_actor_production(restore_intent, restore_composite),
        "host-live-gate-restore-auth",
    )

    raw_executor.execute(
        planner.plan_sequencer_playback_range(
            restore_intent,
            int(originals["sequencer"]["start_frame"]),
            int(originals["sequencer"]["end_frame"]),
        ),
        "host-live-gate-restore-sequencer-auth",
    )

    raw_executor.execute(
        planner.plan_render_configuration(
            restore_intent,
            {
                "width": originals["render"]["width"],
                "height": originals["render"]["height"],
                "start_frame": originals["render"]["start_frame"],
                "end_frame": originals["render"]["end_frame"],
                "output_directory": originals["render"]["output_directory"],
                "output_format": originals["render"]["output_format"],
            },
        ),
        "host-live-gate-restore-render-auth",
    )


def test_host_controller_path_reaches_live_unreal_production_boundary(tmp_path):
    """One already-authorized production travels the host path into real Unreal."""
    integration = None
    raw_executor = None
    originals = None
    planner = UnrealTaskPlanner()

    try:
        integration, raw_executor = _integration(tmp_path)
        originals = _capture_originals(raw_executor, planner)

        # --- real authorization path (Atlas remains the authority) -----------
        production_intent = _intent("host-live-gate-production")
        production = build_unreal_production_plan(production_intent, _spec())
        authorized = authorize_production_plan(production, PRODUCTION_AUTHORIZATION_ID)

        trusted = TrustedUnrealContext(
            authorized_production=authorized,
            intent=production_intent,
            sequence_asset_path=SEQUENCE_ASSET_PATH,
        )

        # --- the reconciled host owns runtime + trusted execution context ----
        host = AgentControllerHost.for_unreal_production(integration, trusted)
        assert host.execution_context.has("unreal") is True

        model_response = "ATLAS_CONTROLLER_REQUEST: " + json.dumps(
            {
                "capability": "production",
                "provider": "unreal",
                "intent": MODEL_DECLARED_INTENT,
                "context": dict(FORGED_MODEL_CONTEXT),
            }
        )

        execution = host.process_model_response(model_response)

        assert execution is not None
        assert execution.controller_executed is True
        assert execution.result is not None
        assert execution.result.capability_name == "unreal_production"

        # host-owned trusted context overrides the forged model context
        admitted = execution.classified.request
        assert admitted.context["authorized_production"] is authorized
        assert admitted.context["intent"] is production_intent
        assert admitted.context["sequence_asset_path"] == SEQUENCE_ASSET_PATH
        assert admitted.intent == MODEL_DECLARED_INTENT

        event = execution.result.value
        assert event.operation == "start"
        assert event.snapshot.state == "complete"

        workflow_result = event.workflow_result
        assert workflow_result is not None
        assert workflow_result.success is True
        assert workflow_result.verified_render is True
        assert workflow_result.production.success is True

        # reconciled strict production<->render identity binding
        assert isinstance(workflow_result.production, UnrealProductionExecutionResult)
        assert workflow_result.render.intent_id == production_intent.intent_id
        assert (
            workflow_result.render.intent_id
            == workflow_result.production.production.plan.intent_id
        )

        # fresh Unreal evidence produced after the live render
        evidence = workflow_result.render.final_evidence
        assert evidence.verified is True
        assert evidence.operation_name == "inspect_render_job"
        assert tuple(evidence.entity_ids) == (ENTITY_ID,)
        assert evidence.observed_state["job_id"] == workflow_result.render.job_id
        assert evidence.source

        # render receipt identity verification
        receipt = workflow_result.render.receipt
        assert receipt.matches(evidence) is True
        assert receipt.job_id == workflow_result.render.job_id
        assert receipt.sequence_asset_path == SEQUENCE_ASSET_PATH
        assert receipt.evidence_digest
        assert receipt.receipt_digest
        assert workflow_result.render.persisted_receipt["job_id"] == receipt.job_id
        assert (
            workflow_result.render.persisted_receipt["receipt_digest"]
            == receipt.receipt_digest
        )

        # typed engine-neutral controller result contract
        contract = event.result_contract
        assert contract.success is True
        assert contract.verified_render is True
        assert contract.failed is False
        assert contract.requires_recovery is False
        assert contract.intent_id == production_intent.intent_id
        assert contract.job_id == receipt.job_id
        assert contract.final_evidence is evidence
        assert contract.receipt is receipt
        assert integration.complete is True

        # the result reflects real engine state, not the controller request
        readback = raw_executor.execute(
            planner.plan_inspection(_intent("host-live-gate-readback")),
            "host-live-gate-readback-auth",
        )
        observed = _state(readback.evidence_ledger[0])
        assert float(observed["location"]["x"]) == pytest.approx(10.0)
        assert float(observed["location"]["y"]) == pytest.approx(20.0)
        assert float(observed["location"]["z"]) == pytest.approx(30.0)

        material_readback = raw_executor.execute(
            _read_variant_plan(
                "host-live-gate-readback-material",
                UnrealCapability.MATERIAL,
                "inspect_material_state",
            ),
            "host-live-gate-readback-material-auth",
        )
        assert (
            _variant_value(material_readback.evidence_ledger[0], "material")["name"]
            == "liquid_surface"
        )

        niagara_readback = raw_executor.execute(
            _read_variant_plan(
                "host-live-gate-readback-niagara",
                UnrealCapability.NIAGARA,
                "inspect_niagara_state",
            ),
            "host-live-gate-readback-niagara-auth",
        )
        assert (
            _variant_value(niagara_readback.evidence_ledger[0], "niagara")["name"]
            == "goal_burst"
        )

        # --- identities for independent inspection ---------------------------
        print("\n===== ATLAS LIVE GATE IDENTITIES =====")
        print("host path layer        : AgentControllerHost -> real Unreal")
        print("production auth id     :", authorized.authorization.authorization_id)
        print("production plan intent :", production.plan.intent_id)
        print("operation              : start / unreal_production")
        print("render job id          :", receipt.job_id)
        print("sequence asset path    :", receipt.sequence_asset_path)
        print("evidence source        :", evidence.source)
        print("evidence operation     :", evidence.operation_name)
        print("evidence verified      :", evidence.verified)
        print("evidence entity ids    :", tuple(evidence.entity_ids))
        print("evidence digest        :", receipt.evidence_digest)
        print("receipt digest         :", receipt.receipt_digest)
        print("persisted receipt      :", workflow_result.render.persisted_receipt)
        print(
            "controller contract    :",
            f"success={contract.success} verified_render={contract.verified_render} "
            f"failed={contract.failed} requires_recovery={contract.requires_recovery}",
        )
        print("live readback location :", observed["location"])
        print("======================================\n")

    except NamedPipeTransportError as exc:
        _assert_transport_available(exc)
        raise

    finally:
        if raw_executor is not None and originals is not None:
            _restore_originals(raw_executor, planner, originals)
