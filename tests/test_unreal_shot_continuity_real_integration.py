"""Live UE 5.6.1 gate for shot-level production continuity.

This module is an engine-boundary validation gate, not a new feature. It drives
the already-proven heterogeneous production transaction and the real MRQ
submission path end to end and proves the frozen continuity invariants of
``docs/UNREAL_SHOT_CONTINUITY_DESIGN_REVIEW.md`` against fresh engine evidence:

    authorized sequence asset path   -> final render-job evidence
    authorized frame range           -> effective submitted frame range
    authorized output directory      -> final render-job output directory
    authorized output format         -> final render-job output format
    exact job identity               -> final evidence and receipt
    PNG frame coverage               -> unique observed artifacts
    receipt                          -> issued, persisted, continuity-bound

Nothing at the engine boundary is mocked. The fixture is restored to its
original values in ``finally`` and the tracked fixture assets are restored
byte-for-byte outside the test.
"""

import pytest

from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability
from planning.unreal_composite_operation import build_composite_actor_operation
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_production_executor import UnrealProductionExecutor
from planning.unreal_production_operation import (
    UnrealProductionSpec,
    build_unreal_production_plan,
)
from planning.unreal_production_planning_boundary import authorize_production_plan
from planning.unreal_production_workflow import UnrealProductionWorkflow
from planning.unreal_render_contract import UnrealRenderConfig
from planning.unreal_render_job_verifier import resolve_render_job_state
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_workflow import UnrealRenderWorkflow
from planning.unreal_shot_continuity import verify_shot_continuity_completeness
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_named_pipe import (
    NamedPipeTransportError,
    WindowsNamedPipeTransport,
)
from planning.unreal_adapter_production import UnrealAdapterError
from tests.test_agent_controller_production_real_integration import (
    ENTITY_ID,
    SEQUENCE_ASSET_PATH,
    _intent,
    _read_variant_plan,
    _render_inspection_plan,
    _sequencer_inspection_plan,
    _state,
    _variant,
)

pytestmark = pytest.mark.integration

START_FRAME = 1
END_FRAME = 2
OUTPUT_DIRECTORY = "Saved/AtlasShotContinuityOutput"
OUTPUT_FORMAT = "png"


def _build(transport):
    adapter = UnrealAdapterProduction(transport, "shot-continuity-live-gate")
    raw_executor = UnrealPlanExecutor(adapter)

    return adapter, raw_executor, UnrealProductionExecutor(raw_executor)


def test_real_unreal_shot_continuity_survives_from_authorization_to_receipt(tmp_path):
    """Prove authorized shot continuity against fresh engine evidence."""

    adapter = None
    originals = {}
    planner = UnrealTaskPlanner()

    try:
        adapter, raw_executor, production_executor = _build(
            WindowsNamedPipeTransport()
        )

        receipt_store = UnrealRenderReceiptStore(
            tmp_path / "shot-continuity-render-receipt.json"
        )
        workflow = UnrealProductionWorkflow(
            production_executor,
            UnrealRenderWorkflow(
                raw_executor,
                receipt_store,
                poll_interval_seconds=0.25,
                timeout_seconds=120.0,
            ),
        )

        # --- capture the live fixture state this gate will mutate ------------
        original_state = _state(
            raw_executor.execute(
                planner.plan_inspection(_intent("shot-continuity-original")),
                "shot-continuity-original-auth",
            ).evidence_ledger[0]
        )
        originals["state"] = original_state

        original_sequencer = _state(
            raw_executor.execute(
                _sequencer_inspection_plan(
                    _intent("shot-continuity-original-sequencer")
                ),
                "shot-continuity-original-sequencer-auth",
            ).evidence_ledger[0]
        )["sequencer"]
        originals["sequencer"] = dict(original_sequencer)

        original_render = _state(
            raw_executor.execute(
                _render_inspection_plan(_intent("shot-continuity-original-render")),
                "shot-continuity-original-render-auth",
            ).evidence_ledger[0]
        )["render"]
        originals["render"] = dict(original_render)

        original_material = _variant(
            raw_executor.execute(
                _read_variant_plan(
                    "shot-continuity-original-material",
                    UnrealCapability.MATERIAL,
                    "inspect_material_state",
                ),
                "shot-continuity-original-material-auth",
            ).evidence_ledger[0],
            "material",
        )
        originals["material"] = original_material

        original_niagara = _variant(
            raw_executor.execute(
                _read_variant_plan(
                    "shot-continuity-original-niagara",
                    UnrealCapability.NIAGARA,
                    "inspect_niagara_state",
                ),
                "shot-continuity-original-niagara-auth",
            ).evidence_ledger[0],
            "niagara",
        )
        originals["niagara"] = original_niagara

        # --- authorized production intent -----------------------------------
        composite = build_composite_actor_operation(
            [ENTITY_ID],
            [
                {
                    "name": "set_actor_location",
                    "location": {
                        "x": original_state["location"]["x"] + 10.0,
                        "y": original_state["location"]["y"] + 5.0,
                        "z": original_state["location"]["z"] + 3.0,
                    },
                },
                {
                    "name": "set_actor_rotation",
                    "rotation": {
                        "pitch": original_state["rotation"]["pitch"],
                        "yaw": original_state["rotation"]["yaw"] + 15.0,
                        "roll": original_state["rotation"]["roll"],
                    },
                },
                {
                    "name": "set_actor_scale",
                    "scale": {
                        "x": original_state["scale"]["x"] * 1.02,
                        "y": original_state["scale"]["y"] * 1.02,
                        "z": original_state["scale"]["z"] * 1.02,
                    },
                },
                {"name": "apply_material_variant", "variant": "liquid_surface"},
                {"name": "apply_niagara_variant", "variant": "goal_burst"},
            ],
        )

        intent = _intent("shot-continuity-live")
        spec = UnrealProductionSpec(
            composite=composite,
            start_frame=START_FRAME,
            end_frame=END_FRAME,
            render_config=UnrealRenderConfig(
                width=640,
                height=360,
                start_frame=START_FRAME,
                end_frame=END_FRAME,
                output_directory=OUTPUT_DIRECTORY,
                output_format=OUTPUT_FORMAT,
            ),
            sequence_asset_path=SEQUENCE_ASSET_PATH,
        )
        production = build_unreal_production_plan(intent, spec)
        continuity = production.continuity

        authorized = authorize_production_plan(
            production,
            "shot-continuity-production-auth",
        )
        assert authorized.authorization.continuity_bound is True
        assert authorized.authorization.matches(
            production.plan,
            continuity_digest=continuity.continuity_digest,
        )

        result = workflow.run(
            production,
            authorized.authorization,
            intent,
            SEQUENCE_ASSET_PATH,
            lambda plan: UnrealPlanAuthorization.issue(
                plan,
                "shot-continuity-render-auth",
            ),
        )

        # --- continuity survives into the final fresh evidence --------------
        assert result.production.success is True
        assert result.success is True
        assert result.verified_render is True

        evidence = result.render.final_evidence
        assert evidence.verified is True
        assert evidence.operation_name == "inspect_render_job"

        job_state = resolve_render_job_state(evidence)

        assert job_state["job_id"] == result.render.job_id
        assert result.render.receipt.job_id == result.render.job_id
        assert job_state["sequence_asset_path"] == continuity.sequence_asset_path
        assert job_state["sequence_asset_path"] == SEQUENCE_ASSET_PATH
        assert int(job_state["start_frame"]) == START_FRAME
        assert int(job_state["end_frame"]) == END_FRAME
        # The engine boundary is the half-open translation of the authorized
        # inclusive range; it must correspond exactly.
        assert int(job_state["end_frame_exclusive"]) == continuity.end_frame_exclusive
        assert (
            job_state["output_format"].strip().lower()
            == continuity.normalized_output_format
        )

        output_files = [
            str(value) for value in job_state["output_files"] if str(value).strip()
        ]
        assert len(set(output_files)) == continuity.expected_frame_count, output_files

        # The authoritative continuity verifier accepts this exact evidence.
        assert (
            verify_shot_continuity_completeness(evidence, continuity) is evidence
        )

        # --- receipt continuity ---------------------------------------------
        assert result.render.receipt.matches(evidence) is True
        assert result.render.receipt.sequence_asset_path == SEQUENCE_ASSET_PATH
        assert receipt_store.exists() is True
        assert receipt_store.load() == result.render.receipt
        assert (
            result.render.persisted_receipt["receipt_digest"]
            == result.render.receipt.receipt_digest
        )
        assert (
            result.render.persisted_receipt["evidence_digest"]
            == result.render.receipt.evidence_digest
        )

        print("shot continuity live gate")
        print("  sequence asset path :", continuity.sequence_asset_path)
        print("  effective frames    :", job_state["start_frame"], job_state["end_frame"])
        print("  output directory    :", job_state["output_directory"])
        print("  output format       :", job_state["output_format"])
        print("  job id              :", result.render.job_id)
        print("  unique png files    :", len(set(output_files)))
        print("  receipt digest      :", result.render.receipt.receipt_digest)

    except (NamedPipeTransportError, UnrealAdapterError) as exc:
        message = str(exc).lower()
        if any(
            token in message
            for token in ("not available", "pipe not found", "disconnected")
        ):
            pytest.skip("Unreal Editor transport is unavailable")
        if "not found" in message:
            pytest.skip("Required Unreal production fixture is unavailable")
        raise

    finally:
        if adapter is not None and originals:
            restore_executor = UnrealPlanExecutor(adapter)
            restore_intent = _intent("shot-continuity-restore")

            restore_composite = build_composite_actor_operation(
                [ENTITY_ID],
                [
                    {
                        "name": "set_actor_location",
                        "location": dict(originals["state"]["location"]),
                    },
                    {
                        "name": "set_actor_rotation",
                        "rotation": dict(originals["state"]["rotation"]),
                    },
                    {
                        "name": "set_actor_scale",
                        "scale": dict(originals["state"]["scale"]),
                    },
                    {
                        "name": "apply_material_variant",
                        "variant": originals["material"]["name"],
                    },
                    {
                        "name": "apply_niagara_variant",
                        "variant": originals["niagara"]["name"],
                    },
                ],
            )

            restore_executor.execute(
                planner.plan_composite_actor_production(
                    restore_intent,
                    restore_composite,
                ),
                "shot-continuity-restore-auth",
            )

            restore_executor.execute(
                planner.plan_sequencer_playback_range(
                    restore_intent,
                    int(originals["sequencer"]["start_frame"]),
                    int(originals["sequencer"]["end_frame"]),
                ),
                "shot-continuity-restore-sequencer-auth",
            )

            restore_executor.execute(
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
                "shot-continuity-restore-render-auth",
            )
