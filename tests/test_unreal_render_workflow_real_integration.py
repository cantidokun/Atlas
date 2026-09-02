"""Real Unreal integration coverage for the high-level render workflow."""

import pytest

from planning.unreal_adapter_production import create_production_adapter
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_workflow import (
    UnrealRenderWorkflow,
    UnrealRenderWorkflowError,
)
from planning.unreal_task_planner import UnrealTaskIntent


pytestmark = pytest.mark.integration

ENTITY_ID = "ATLAS_RENDER_TEST"
SEQUENCE_ASSET_PATH = "/Game/AtlasTest/AtlasSequencerFixtureSequence"

CONFIG = {
    "width": 640,
    "height": 360,
    "start_frame": 1,
    "end_frame": 2,
    "output_directory": "Saved/AtlasRenderOutput",
    "output_format": "png",
}


def _intent(intent_id: str) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="real Unreal high-level render workflow integration",
        target_entity_ids=(ENTITY_ID,),
    )


def test_real_unreal_render_workflow_runs_to_verified_persisted_receipt(tmp_path):
    try:
        adapter = create_production_adapter("render-workflow-real-integration")
        executor = UnrealPlanExecutor(adapter)
        store = UnrealRenderReceiptStore(
            tmp_path / "unreal-render-receipt.json"
        )
        workflow = UnrealRenderWorkflow(
            executor,
            store,
            poll_interval_seconds=0.25,
            timeout_seconds=120.0,
        )

        def authorize(plan):
            return UnrealPlanAuthorization.issue(
                plan,
                f"real-workflow-auth-{plan.intent_id}",
            )

        result = workflow.run(
            _intent("real-render-workflow"),
            CONFIG,
            SEQUENCE_ASSET_PATH,
            authorize,
        )

        assert result.intent_id == "real-render-workflow"
        assert result.job_id
        assert result.final_evidence.verified is True
        assert result.receipt.job_id == result.job_id
        assert result.receipt.sequence_asset_path == SEQUENCE_ASSET_PATH

        assert store.exists() is True
        persisted = store.load()

        assert persisted == result.receipt
        assert result.persisted_receipt["job_id"] == result.job_id
        assert result.persisted_receipt["sequence_asset_path"] == SEQUENCE_ASSET_PATH

        job_state = result.final_evidence.observed_state
        if ENTITY_ID in job_state:
            job_state = job_state[ENTITY_ID]["render_job"]

        assert job_state["finished"] is True
        assert job_state["success"] is True
        assert job_state["failed"] is False
        assert job_state["output_files"]

    except Exception as exc:
        message = str(exc).lower()
        if any(
            token in message
            for token in ("pipe not found", "not available", "disconnected")
        ):
            pytest.skip("Unreal Editor transport is unavailable")
        if "render config asset not found" in message:
            pytest.skip(
                "Run AtlasRenderFixture commandlet before real render integration"
            )
        if "sequence" in message and "not found" in message:
            pytest.skip(
                "AtlasSequencerFixtureSequence is unavailable in this Unreal project"
            )
        if isinstance(exc, UnrealRenderWorkflowError):
            raise
        raise
