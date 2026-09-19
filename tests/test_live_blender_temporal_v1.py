"""Operator-gated live Blender evidence for Temporal Observation + State Delta v1.

These tests are deliberately excluded from ordinary CI. They start real Blender background
processes, extract the resulting in-memory scene through Atlas' existing read-only extraction
adapter, convert that real state into the frozen TemporalObservation canonical snapshot shape,
and then exercise the pure temporal core.

Enable explicitly:
    ATLAS_RUN_LIVE_BLENDER=1 python -m pytest tests/test_live_blender_temporal_v1.py -s

No .blend file is opened, modified, or saved by this gate.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, Tuple

import pytest

from planning.temporal import (
    CapabilityContract,
    DeltaReasonCode,
    ObservationStream,
    ProducerProvenance,
    SourceTime,
    TemporalObservation,
    evaluate,
    finalize_record,
    temporal_state_digest,
)
from planning.temporal.evaluator import ComparisonInput
from planning.temporal.model import _scene_to_canonical


LIVE = os.environ.get("ATLAS_RUN_LIVE_BLENDER", "") == "1"
pytestmark = [pytest.mark.skipif(not LIVE, reason="live Temporal Blender gate off")]

_COMPARISON_FIELDS = (
    "collection",
    "faces",
    "location",
    "materials",
    "mesh_id",
    "mesh_presence",
    "parent_object_id",
    "rotation",
    "scale",
    "scene_id",
    "unit_system",
    "vertices",
    "visible",
)
_UNOBSERVABLE_FIELDS = (
    "coordinate_frame",
    "local_frame_id",
    "normals",
    "uvs",
)


def _blender_command() -> str:
    import tools.blender as tb

    return tb.BLENDER


def _producer_contract() -> CapabilityContract:
    return CapabilityContract(
        contract_id="extraction_fidelity_v1",
        observable_fields=tuple(sorted(_COMPARISON_FIELDS)),
        unobservable_fields=tuple(sorted(_UNOBSERVABLE_FIELDS)),
        representation_state=(),
    )


def _live_script() -> str:
    return r'''
import bpy, json, os, sys

sys.path.insert(0, os.environ["ATLAS_REPO_ROOT"])

from planning.blender.bpy_extraction import run_live_blender_extraction
from planning.blender.extraction_payload import payload_to_scene_model
from planning.temporal.model import _scene_to_canonical

# Build a disposable deterministic scene. Nothing is saved.
for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

collection = bpy.data.collections.new("AtlasTemporal")
bpy.context.scene.collection.children.link(collection)

mesh = bpy.data.meshes.new("TemporalMesh")
mesh.from_pydata(
    [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
    [],
    [(0, 1, 2)],
)
mesh.update()

obj = bpy.data.objects.new("temporal_probe", mesh)
collection.objects.link(obj)
obj.location.x = float(os.environ["ATLAS_TEMPORAL_X"])

payload = run_live_blender_extraction(bpy)
scene = payload_to_scene_model(payload)
snapshot = _scene_to_canonical(scene)

result = {
    "snapshot": snapshot,
    "scene_id": scene.scene_id,
    "object_ids": sorted(item["object_id"] for item in snapshot["objects"]),
    "vertex_count": len(snapshot["objects"][0]["mesh"]["vertices"]),
}

print("ATLAS_TEMPORAL_LIVE_START")
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
print("ATLAS_TEMPORAL_LIVE_END")
'''


def _run_live_snapshot(
    *,
    session: str,
    continuity: str,
    ordering_epoch: int,
    x: float,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ)
    env.update(
        {
            "ATLAS_REPO_ROOT": repo,
            "ATLAS_TEMPORAL_SESSION": session,
            "ATLAS_TEMPORAL_CONTINUITY": continuity,
            "ATLAS_TEMPORAL_EPOCH": str(ordering_epoch),
            "ATLAS_TEMPORAL_X": str(x),
        }
    )
    proc = subprocess.run(
        [
            _blender_command(),
            "--background",
            "--python-expr",
            _live_script(),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=repo,
        env=env,
    )
    if proc.returncode != 0:
        raise AssertionError(
            "live Blender Temporal extraction failed "
            f"rc={proc.returncode}: {proc.stderr[-3000:]}"
        )

    start = proc.stdout.find("ATLAS_TEMPORAL_LIVE_START")
    end = proc.stdout.find("ATLAS_TEMPORAL_LIVE_END")
    assert start != -1 and end != -1, (
        "live Temporal output markers missing: " + proc.stdout[-3000:]
    )
    payload = json.loads(
        proc.stdout[
            start + len("ATLAS_TEMPORAL_LIVE_START") : end
        ].strip()
    )
    return payload["snapshot"], payload


def _observation(
    snapshot: Dict[str, Any],
    *,
    session: str,
    continuity: str,
    sequence: int,
    ordering_epoch: int,
    capture_time: int,
) -> TemporalObservation:
    return TemporalObservation(
        stream_id="live-temporal-v1",
        continuity_id=continuity,
        sequence=sequence,
        source_time=SourceTime(
            "FRAME_INDEX",
            sequence,
            1,
            1,
            ordering_epoch,
        ),
        producer=ProducerProvenance(
            producer_source="BLENDER",
            producer_contract="extraction_fidelity_v1",
            engine_version="live",
            engine_build="operator-gated",
            producer_session_id=session,
            producer_instance_ordinal=1,
        ),
        capability=_producer_contract(),
        snapshot=snapshot,
        state_digest=temporal_state_digest(snapshot),
        capture_time=capture_time,
    )


def test_live_temporal_l1_two_observation_computed_delta_and_rerun():
    first_snapshot, first_meta = _run_live_snapshot(
        session="live-session-1",
        continuity="live-continuity-1",
        ordering_epoch=0,
        x=0.0,
    )
    second_snapshot, second_meta = _run_live_snapshot(
        session="live-session-1",
        continuity="live-continuity-1",
        ordering_epoch=0,
        x=1.0,
    )

    assert first_meta["object_ids"] == ["temporal_probe"]
    assert second_meta["object_ids"] == ["temporal_probe"]
    assert first_meta["vertex_count"] == second_meta["vertex_count"] == 3

    a = _observation(
        first_snapshot,
        session="live-session-1",
        continuity="live-continuity-1",
        sequence=0,
        ordering_epoch=0,
        capture_time=1,
    )
    b = _observation(
        second_snapshot,
        session="live-session-1",
        continuity="live-continuity-1",
        sequence=1,
        ordering_epoch=0,
        capture_time=2,
    )

    stream = ObservationStream("live-temporal-v1")
    assert stream.step(a).record is None
    first = stream.step(b, a)
    assert first.record is not None
    assert first.record["outcome"] == "COMPUTED"
    assert any(
        change["field"] == "location"
        for entity in first.record["entity_deltas"]
        for change in entity["field_changes"]
    )

    from_identity = stream.state.from_identity()
    assert from_identity is not None

    rerun = finalize_record(
        evaluate(ComparisonInput(a=a, b=b, from_identity=from_identity)),
        "EMITTED_PREDECESSOR",
    )
    assert rerun["delta_digest"] == first.record["delta_digest"]


def test_live_temporal_l2_real_process_restart_establishes_new_epoch():
    first_snapshot, _ = _run_live_snapshot(
        session="live-session-1",
        continuity="live-continuity-1",
        ordering_epoch=0,
        x=0.0,
    )
    restarted_snapshot, _ = _run_live_snapshot(
        session="live-session-2",
        continuity="live-continuity-2",
        ordering_epoch=1,
        x=0.0,
    )

    a = _observation(
        first_snapshot,
        session="live-session-1",
        continuity="live-continuity-1",
        sequence=7,
        ordering_epoch=0,
        capture_time=10,
    )
    b = _observation(
        restarted_snapshot,
        session="live-session-2",
        continuity="live-continuity-2",
        sequence=0,
        ordering_epoch=1,
        capture_time=1,
    )

    stream = ObservationStream("live-temporal-v1")
    stream.step(a)
    result = stream.step(b, a)

    assert result.admission.outcome.value == "NEW_EPOCH"
    assert result.record is not None
    assert result.record["continuity"] == "NEW_EPOCH"
    assert result.record["outcome"] == "TEMPORAL_DISCONTINUITY"
    assert result.record["entity_deltas"] == []
    assert result.record["observations_skipped"] == 0
    assert result.record["source_time_hold"] is False
    assert "RESTART_PRODUCER_SESSION" in result.record["reason_codes"]
    assert "ORDERING_EPOCH_CHANGE" in result.record["reason_codes"]
    assert "TEMPORAL_DISCONTINUITY_CONTINUITY_ID_CHANGE" in result.record["reason_codes"]


def test_live_temporal_l3_replay_epoch_change_is_boundary_not_transition():
    first_snapshot, _ = _run_live_snapshot(
        session="live-session-1",
        continuity="live-continuity-1",
        ordering_epoch=0,
        x=0.0,
    )
    replay_snapshot, _ = _run_live_snapshot(
        session="live-session-3",
        continuity="live-continuity-replay",
        ordering_epoch=7,
        x=99.0,
    )

    a = _observation(
        first_snapshot,
        session="live-session-1",
        continuity="live-continuity-1",
        sequence=12,
        ordering_epoch=0,
        capture_time=10,
    )
    b = _observation(
        replay_snapshot,
        session="live-session-3",
        continuity="live-continuity-replay",
        sequence=0,
        ordering_epoch=7,
        capture_time=1,
    )

    stream = ObservationStream("live-temporal-v1")
    stream.step(a)
    result = stream.step(b, a)

    assert result.record is not None
    assert result.record["outcome"] == "TEMPORAL_DISCONTINUITY"
    assert result.record["continuity"] == "NEW_EPOCH"
    assert result.record["entity_deltas"] == []
    assert result.record["observations_skipped"] == 0
    assert result.record["source_time_hold"] is False
    assert "ORDERING_EPOCH_CHANGE" in result.record["reason_codes"]


def test_live_temporal_l5_frozen_pair_recomputes_identical_digest():
    snapshot_a, _ = _run_live_snapshot(
        session="live-session-frozen",
        continuity="live-continuity-frozen",
        ordering_epoch=0,
        x=0.0,
    )
    snapshot_b, _ = _run_live_snapshot(
        session="live-session-frozen",
        continuity="live-continuity-frozen",
        ordering_epoch=0,
        x=1.0,
    )

    a = _observation(
        snapshot_a,
        session="live-session-frozen",
        continuity="live-continuity-frozen",
        sequence=0,
        ordering_epoch=0,
        capture_time=100,
    )
    b = _observation(
        snapshot_b,
        session="live-session-frozen",
        continuity="live-continuity-frozen",
        sequence=1,
        ordering_epoch=0,
        capture_time=101,
    )

    stream = ObservationStream("live-temporal-v1")
    stream.step(a)
    from_identity = stream.state.from_identity()
    assert from_identity is not None

    first = finalize_record(
        evaluate(ComparisonInput(a=a, b=b, from_identity=from_identity)),
        "UNEMITTED_EPOCH_ANCHOR",
    )
    second = finalize_record(
        evaluate(ComparisonInput(a=a, b=b, from_identity=from_identity)),
        "UNEMITTED_EPOCH_ANCHOR",
    )

    assert first["delta_digest"] == second["delta_digest"]
    assert first == second
