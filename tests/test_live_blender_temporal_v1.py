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
import tempfile
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
    "producer_session_id": "blender-pid-" + str(os.getpid()),
    "engine_version": bpy.app.version_string,
    "engine_build": bpy.app.build_hash,
}

if os.environ.get("ATLAS_TEMPORAL_CAPTURE_PAIR", "0") == "1":
    first_snapshot = snapshot
    obj.location.x = float(os.environ["ATLAS_TEMPORAL_X_SECOND"])
    second_payload = run_live_blender_extraction(bpy)
    second_scene = payload_to_scene_model(second_payload)
    second_snapshot = _scene_to_canonical(second_scene)
    result["first_snapshot"] = first_snapshot
    result["second_snapshot"] = second_snapshot

print("ATLAS_TEMPORAL_LIVE_START")
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
print("ATLAS_TEMPORAL_LIVE_END")
'''


def _run_blender_live_script(*, repo: str, env: Dict[str, str]) -> subprocess.CompletedProcess[str]:
    fd, script_path = tempfile.mkstemp(prefix="atlas_temporal_live_", suffix=".py", dir=repo, text=True)
    os.close(fd)
    try:
        with open(script_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(_live_script())
        return subprocess.run(
            [
                _blender_command(),
                "--background",
                "--python",
                script_path,
            ],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=repo,
            env=env,
        )
    finally:
        try:
            os.remove(script_path)
        except FileNotFoundError:
            pass


def _run_live_snapshot(*, x: float) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ)
    env.update(
        {
            "ATLAS_REPO_ROOT": repo,
            "PYTHONPATH": repo + os.pathsep + env.get("PYTHONPATH", ""),
            "ATLAS_TEMPORAL_X": str(x),
            "ATLAS_TEMPORAL_CAPTURE_PAIR": "0",
        }
    )
    proc = _run_blender_live_script(repo=repo, env=env)
    if proc.returncode != 0:
        raise AssertionError(
            "live Blender Temporal extraction failed "
            f"rc={proc.returncode}: stdout={proc.stdout[-3000:]} stderr={proc.stderr[-5000:]}"
        )

    start = proc.stdout.find("ATLAS_TEMPORAL_LIVE_START")
    end = proc.stdout.find("ATLAS_TEMPORAL_LIVE_END")
    assert start != -1 and end != -1, (
        "live Temporal output markers missing. "
        "stdout: " + proc.stdout[-3000:] + " | stderr: " + proc.stderr[-5000:]
    )
    payload = json.loads(
        proc.stdout[
            start + len("ATLAS_TEMPORAL_LIVE_START") : end
        ].strip()
    )
    return payload["snapshot"], payload


def _run_live_pair(*, continuity: str, ordering_epoch: int, first_x: float, second_x: float) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, str]]:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ)
    env.update(
        {
            "ATLAS_REPO_ROOT": repo,
            "PYTHONPATH": repo + os.pathsep + env.get("PYTHONPATH", ""),
            "ATLAS_TEMPORAL_X": str(first_x),
            "ATLAS_TEMPORAL_X_SECOND": str(second_x),
            "ATLAS_TEMPORAL_CAPTURE_PAIR": "1",
        }
    )
    proc = _run_blender_live_script(repo=repo, env=env)
    if proc.returncode != 0:
        raise AssertionError(
            "live Blender Temporal paired extraction failed "
            f"rc={proc.returncode}: stdout={proc.stdout[-3000:]} stderr={proc.stderr[-5000:]}"
        )
    start = proc.stdout.find("ATLAS_TEMPORAL_LIVE_START")
    end = proc.stdout.find("ATLAS_TEMPORAL_LIVE_END")
    assert start != -1 and end != -1, (
        "live Temporal paired output markers missing. "
        "stdout: " + proc.stdout[-3000:] + " | stderr: " + proc.stderr[-5000:]
    )
    result = json.loads(proc.stdout[start + len("ATLAS_TEMPORAL_LIVE_START") : end].strip())
    assert "first_snapshot" in result and "second_snapshot" in result
    return (
        result["first_snapshot"],
        result["second_snapshot"],
        {
            "producer_session_id": result["producer_session_id"],
            "engine_version": result["engine_version"],
            "engine_build": result["engine_build"],
        },
    )


def _observation(
    snapshot: Dict[str, Any],
    *,
    session: str,
    continuity: str,
    sequence: int,
    ordering_epoch: int,
    capture_time: int,
    engine_version: str,
    engine_build: str,
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
            engine_version=engine_version,
            engine_build=engine_build,
            producer_session_id=session,
            producer_instance_ordinal=1,
        ),
        capability=_producer_contract(),
        snapshot=snapshot,
        state_digest=temporal_state_digest(snapshot),
        capture_time=capture_time,
    )


def test_live_temporal_l1_two_observation_computed_delta_and_rerun():
    first_snapshot, second_snapshot, producer_meta = _run_live_pair(
        continuity="live-continuity-1",
        ordering_epoch=0,
        first_x=0.0,
        second_x=1.0,
    )

    assert sorted(first_snapshot["objects"][0]["object_id"] for _ in [0]) == ["temporal_probe"]
    assert sorted(second_snapshot["objects"][0]["object_id"] for _ in [0]) == ["temporal_probe"]
    assert len(first_snapshot["objects"][0]["mesh"]["vertices"]) == 3
    assert len(second_snapshot["objects"][0]["mesh"]["vertices"]) == 3

    a = _observation(
        first_snapshot,
        session=producer_meta["producer_session_id"],
        continuity="live-continuity-1",
        sequence=0,
        ordering_epoch=0,
        capture_time=1,
        engine_version=producer_meta["engine_version"],
        engine_build=producer_meta["engine_build"],
    )
    b = _observation(
        second_snapshot,
        session=producer_meta["producer_session_id"],
        continuity="live-continuity-1",
        sequence=1,
        ordering_epoch=0,
        capture_time=2,
        engine_version=producer_meta["engine_version"],
        engine_build=producer_meta["engine_build"],
    )

    stream = ObservationStream("live-temporal-v1")
    assert stream.step(a).record is None
    from_identity = stream.state.from_identity()
    assert from_identity is not None
    first = stream.step(b, a)
    assert first.record is not None
    assert first.record["outcome"] == "COMPUTED"
    assert any(
        change["field"] == "location"
        for entity in first.record["entity_deltas"]
        for change in entity["field_changes"]
    )

    rerun = finalize_record(
        evaluate(ComparisonInput(a=a, b=b, from_identity=from_identity)),
        "UNEMITTED_EPOCH_ANCHOR",
    )
    assert rerun["delta_digest"] == first.record["delta_digest"]
    print("ATLAS_TEMPORAL_L1_EVIDENCE=" + json.dumps({
        "engine_version": producer_meta["engine_version"],
        "engine_build": producer_meta["engine_build"],
        "producer_session_id": producer_meta["producer_session_id"],
        "from_observation_id": first.record["from_observation_id"],
        "to_observation_id": first.record["to_observation_id"],
        "delta_digest": first.record["delta_digest"],
        "outcome": first.record["outcome"],
    }, sort_keys=True))


def test_live_temporal_l2_real_process_restart_establishes_new_epoch():
    first_snapshot, first_meta = _run_live_snapshot(x=0.0)
    restarted_snapshot, restarted_meta = _run_live_snapshot(x=0.0)

    assert first_meta["engine_version"].startswith("4.4.")
    assert restarted_meta["engine_version"] == first_meta["engine_version"]

    first_session = first_meta["producer_session_id"]
    restarted_session = restarted_meta["producer_session_id"]
    assert first_session != restarted_session

    a = _observation(
        first_snapshot,
        session=first_session,
        continuity="live-continuity-1",
        sequence=7,
        ordering_epoch=0,
        capture_time=10,
        engine_version=first_meta["engine_version"],
        engine_build=first_meta["engine_build"],
    )
    b = _observation(
        restarted_snapshot,
        session=restarted_session,
        continuity="live-continuity-2",
        sequence=0,
        ordering_epoch=1,
        capture_time=1,
        engine_version=restarted_meta["engine_version"],
        engine_build=restarted_meta["engine_build"],
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
    print("ATLAS_TEMPORAL_L2_EVIDENCE=" + json.dumps({
        "engine_version": first_meta["engine_version"],
        "first_session": first_session,
        "restarted_session": restarted_session,
        "reason_codes": result.record["reason_codes"],
        "delta_digest": result.record["delta_digest"],
    }, sort_keys=True))


def test_live_temporal_l3_replay_epoch_change_is_boundary_not_transition():
    first_snapshot, first_meta = _run_live_snapshot(x=0.0)
    replay_snapshot, replay_meta = _run_live_snapshot(x=99.0)

    assert first_meta["engine_version"] == replay_meta["engine_version"]

    first_session = first_meta["producer_session_id"]
    replay_session = replay_meta["producer_session_id"]
    assert first_session != replay_session

    a = _observation(
        first_snapshot,
        session=first_session,
        continuity="live-continuity-1",
        sequence=12,
        ordering_epoch=0,
        capture_time=10,
        engine_version=first_meta["engine_version"],
        engine_build=first_meta["engine_build"],
    )
    b = _observation(
        replay_snapshot,
        session=replay_session,
        continuity="live-continuity-replay",
        sequence=0,
        ordering_epoch=7,
        capture_time=1,
        engine_version=replay_meta["engine_version"],
        engine_build=replay_meta["engine_build"],
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
    print("ATLAS_TEMPORAL_L3_EVIDENCE=" + json.dumps({
        "engine_version": first_meta["engine_version"],
        "first_session": first_session,
        "replay_session": replay_session,
        "reason_codes": result.record["reason_codes"],
        "delta_digest": result.record["delta_digest"],
    }, sort_keys=True))


def test_live_temporal_l5_frozen_pair_recomputes_identical_digest():
    snapshot_a, meta_a = _run_live_snapshot(x=0.0)
    snapshot_b, meta_b = _run_live_snapshot(x=1.0)
    assert meta_a["engine_version"] == meta_b["engine_version"]
    session_a = meta_a["producer_session_id"]

    # L-5 is a frozen-fixture determinism check. The snapshots are produced live,
    # then evaluated from the same immutable pair values twice. The process/session
    # used to produce each snapshot is not part of the semantic state comparison.
    a = _observation(
        snapshot_a,
        session=session_a,
        continuity="live-continuity-frozen",
        sequence=0,
        ordering_epoch=0,
        capture_time=100,
        engine_version=meta_a["engine_version"],
        engine_build=meta_a["engine_build"],
    )
    b = _observation(
        snapshot_b,
        session=session_a,
        continuity="live-continuity-frozen",
        sequence=1,
        ordering_epoch=0,
        capture_time=101,
        engine_version=meta_b["engine_version"],
        engine_build=meta_b["engine_build"],
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
    print("ATLAS_TEMPORAL_L5_EVIDENCE=" + json.dumps({
        "engine_version": meta_a["engine_version"],
        "engine_build": meta_a["engine_build"],
        "delta_digest": first["delta_digest"],
        "deterministic": True,
    }, sort_keys=True))
