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
# Atlas' current extraction boundary enumerates direct scene-root membership.
# Keep the semantic collection link while also linking this disposable fixture
# object to the scene master collection, matching the established live gate pattern.
bpy.context.scene.collection.objects.link(obj)
obj.location.x = float(os.environ["ATLAS_TEMPORAL_X"])

payload = run_live_blender_extraction(bpy)
scene = payload_to_scene_model(payload)
snapshot = _scene_to_canonical(scene)

build_hash = bpy.app.build_hash
if isinstance(build_hash, (bytes, bytearray)):
    build_hash = bytes(build_hash).decode("ascii")
else:
    build_hash = str(build_hash)

result = {
    "snapshot": snapshot,
    "scene_id": scene.scene_id,
    "object_ids": sorted(item["object_id"] for item in snapshot["objects"]),
    "vertex_count": len(snapshot["objects"][0]["mesh"]["vertices"]),
    "process_id": os.getpid(),
    "producer_session_id": "blender-proc-" + str(os.getpid()) + "-" + os.urandom(8).hex(),
    "engine_version": str(bpy.app.version_string),
    "engine_build": build_hash,
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
            "process_id": result["process_id"],
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



def test_live_temporal_l4_material_omission_is_unavailable_not_unchanged():
    snapshot_a, meta = _run_live_snapshot(x=0.0)
    snapshot_b = json.loads(json.dumps(snapshot_a, sort_keys=True))

    # Use a real Blender-produced snapshot as the fixture, then model the frozen
    # producer omission contract explicitly: an omitted materials key is not an
    # observed empty/materials-equal value and must surface as UNAVAILABLE.
    for snapshot in (snapshot_a, snapshot_b):
        mesh = snapshot["objects"][0]["mesh"]
        mesh.pop("materials", None)

    capability = CapabilityContract(
        contract_id="extraction_fidelity_v1",
        observable_fields=tuple(sorted(_COMPARISON_FIELDS)),
        unobservable_fields=tuple(sorted(_UNOBSERVABLE_FIELDS)),
        representation_state=("materials:omitted",),
    )

    def make_observation(snapshot: Dict[str, Any], sequence: int) -> TemporalObservation:
        return TemporalObservation(
            stream_id="live-temporal-v1",
            continuity_id="live-continuity-materials",
            sequence=sequence,
            source_time=SourceTime("FRAME_INDEX", sequence, 1, 1, 0),
            producer=ProducerProvenance(
                producer_source="BLENDER",
                producer_contract="extraction_fidelity_v1",
                engine_version=meta["engine_version"],
                engine_build=meta["engine_build"],
                producer_session_id=meta["producer_session_id"],
                producer_instance_ordinal=1,
            ),
            capability=capability,
            snapshot=snapshot,
            state_digest=temporal_state_digest(snapshot),
        )

    a = make_observation(snapshot_a, 0)
    b = make_observation(snapshot_b, 1)
    stream = ObservationStream("live-temporal-v1")
    stream.step(a)
    result = stream.step(b, a)

    assert result.record is not None
    assert result.record["outcome"] == "COMPUTED"
    assert result.record["coverage"]["materials"] == "UNAVAILABLE"
    assert not any(
        change["field"] == "materials"
        for entity in result.record["entity_deltas"]
        for change in entity["field_changes"]
    )
    print("ATLAS_TEMPORAL_L4_EVIDENCE=" + json.dumps({
        "engine_version": meta["engine_version"],
        "engine_build": meta["engine_build"],
        "producer_session_id": meta["producer_session_id"],
        "materials_coverage": result.record["coverage"]["materials"],
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

# ---------------------------------------------------------------------------
# Temporal v1 live campaign additions.
#
# Phase 2/3 strengthening: the restart and replay boundaries are re-proved with a
# REAL, measurable state difference present across the two real Blender processes,
# so "no false transition" cannot be satisfied merely because the two endpoints
# happen to be identical.
#
# Phase 5 (L-4): a REAL representation case, measured against the live producer.
# ---------------------------------------------------------------------------


def _companion_from_identity(observation: TemporalObservation):
    """Real admission baseline projection for one observation (comparison-path control)."""

    baseline = ObservationStream("live-temporal-v1")
    baseline.step(observation)
    return baseline.state.from_identity()


def _same_epoch_pair(snapshot_a, snapshot_b, *, sequence_a: int, sequence_b: int, meta: Dict[str, Any]):
    """Harness-only positive control: both real snapshots on ONE declared session.

    The comparison path requires a single declared producer session and a single
    continuity for a same-epoch pair, so this control pair is a declared envelope
    around two real payloads. It is used only to show that the comparison path DOES
    report the real difference that the boundary path suppresses.
    """

    session = "companion-single-declared-session"
    a = _observation(
        snapshot_a,
        session=session,
        continuity="live-continuity-companion",
        sequence=sequence_a,
        ordering_epoch=0,
        capture_time=500,
        engine_version=meta["engine_version"],
        engine_build=meta["engine_build"],
    )
    b = _observation(
        snapshot_b,
        session=session,
        continuity="live-continuity-companion",
        sequence=sequence_b,
        ordering_epoch=0,
        capture_time=501,
        engine_version=meta["engine_version"],
        engine_build=meta["engine_build"],
    )
    return a, b


def _location_changed(record) -> bool:
    return any(
        change["field"] == "location"
        for entity in record["entity_deltas"]
        for change in entity["field_changes"]
    )


def test_live_temporal_l2b_restart_boundary_suppresses_a_real_state_change():
    """A real restart with a REAL state difference is still a boundary, not a transition."""

    first_snapshot, first_meta = _run_live_snapshot(x=0.0)
    restarted_snapshot, restarted_meta = _run_live_snapshot(x=5.0)

    assert first_meta["engine_version"].startswith("4.4.")
    assert restarted_meta["engine_version"] == first_meta["engine_version"]
    assert first_meta["producer_session_id"] != restarted_meta["producer_session_id"]

    # Section 4.4: producer_session_id identifies one producer PROCESS INCARNATION;
    # "PID alone is not identity", so each incarnation also carries a fresh nonce.
    nonces = []
    for meta in (first_meta, restarted_meta):
        pid_prefix = "blender-proc-" + str(meta["process_id"]) + "-"
        assert meta["producer_session_id"].startswith(pid_prefix)
        nonce = meta["producer_session_id"][len(pid_prefix):]
        assert len(nonce) >= 16
        nonces.append(nonce)
    assert first_meta["process_id"] != restarted_meta["process_id"]
    assert nonces[0] != nonces[1]

    first_object = first_snapshot["objects"][0]
    restarted_object = restarted_snapshot["objects"][0]
    assert first_object["object_id"] == restarted_object["object_id"]
    assert first_object["location"] != restarted_object["location"]

    a = _observation(
        first_snapshot,
        session=first_meta["producer_session_id"],
        continuity="live-continuity-1",
        sequence=7,
        ordering_epoch=0,
        capture_time=10,
        engine_version=first_meta["engine_version"],
        engine_build=first_meta["engine_build"],
    )
    b = _observation(
        restarted_snapshot,
        session=restarted_meta["producer_session_id"],
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
    assert result.record["outcome"] == "TEMPORAL_DISCONTINUITY"
    assert result.record["continuity"] == "NEW_EPOCH"
    assert result.record["entity_deltas"] == []
    assert result.record["observations_skipped"] == 0
    assert result.record["source_time_hold"] is False
    assert result.record["state_digest_changed"] is True
    assert "RESTART_PRODUCER_SESSION" in result.record["reason_codes"]
    assert "ORDERING_EPOCH_CHANGE" in result.record["reason_codes"]
    assert "TEMPORAL_DISCONTINUITY_CONTINUITY_ID_CHANGE" in result.record["reason_codes"]

    companion_a, companion_b = _same_epoch_pair(
        first_snapshot, restarted_snapshot, sequence_a=0, sequence_b=1, meta=first_meta
    )
    companion = finalize_record(
        evaluate(
            ComparisonInput(
                a=companion_a,
                b=companion_b,
                from_identity=_companion_from_identity(companion_a),
            )
        ),
        "UNEMITTED_EPOCH_ANCHOR",
    )
    assert companion["outcome"] == "COMPUTED"
    assert _location_changed(companion)

    print("ATLAS_TEMPORAL_L2B_EVIDENCE=" + json.dumps({
        "engine_version": first_meta["engine_version"],
        "engine_build": first_meta["engine_build"],
        "first_session": first_meta["producer_session_id"],
        "restarted_session": restarted_meta["producer_session_id"],
        "first_location": first_object["location"],
        "restarted_location": restarted_object["location"],
        "boundary_outcome": result.record["outcome"],
        "boundary_entity_deltas": result.record["entity_deltas"],
        "boundary_state_digest_changed": result.record["state_digest_changed"],
        "boundary_delta_digest": result.record["delta_digest"],
        "companion_outcome": companion["outcome"],
        "companion_location_changed": True,
    }, sort_keys=True))


def test_live_temporal_l3b_replay_cannot_enter_or_contradict_an_established_epoch():
    """A replay from a real second process must never become a temporal transition."""

    first_snapshot, first_meta = _run_live_snapshot(x=0.0)
    replay_snapshot, replay_meta = _run_live_snapshot(x=99.0)

    assert first_meta["engine_version"].startswith("4.4.")
    assert replay_meta["engine_version"] == first_meta["engine_version"]
    assert first_meta["producer_session_id"] != replay_meta["producer_session_id"]
    assert first_snapshot["objects"][0]["location"] != replay_snapshot["objects"][0]["location"]

    baseline = _observation(
        first_snapshot,
        session=first_meta["producer_session_id"],
        continuity="live-continuity-9",
        sequence=40,
        ordering_epoch=3,
        capture_time=900,
        engine_version=first_meta["engine_version"],
        engine_build=first_meta["engine_build"],
    )

    stream = ObservationStream("live-temporal-v1")
    stream.step(baseline)
    assert stream.state.last_accepted_observation_id == baseline.observation_id

    def replay_observation(*, continuity, sequence, epoch):
        return _observation(
            replay_snapshot,
            session=replay_meta["producer_session_id"],
            continuity=continuity,
            sequence=sequence,
            ordering_epoch=epoch,
            capture_time=1,
            engine_version=replay_meta["engine_version"],
            engine_build=replay_meta["engine_build"],
        )

    # (1) a replay of an OLDER epoch is stale: no record, baseline intact.
    stale = stream.step(replay_observation(continuity="live-continuity-old", sequence=0, epoch=0))
    assert stale.admission.outcome.value == "REJECTED_STALE"
    assert "ORDERING_EPOCH_REGRESSION" in [code.value for code in stale.admission.reason_codes]
    assert stale.record is None
    assert stream.state.last_accepted_observation_id == baseline.observation_id
    assert stream.state.rejected_stale_count == 1

    # (2) the CURRENT epoch with a different continuity is a malformed declaration.
    mismatched = stream.step(
        replay_observation(continuity="live-continuity-other", sequence=41, epoch=3)
    )
    assert mismatched.admission.outcome.value == "REJECTED_INVALID"
    assert "CONTINUITY_DECLARATION_MISMATCH" in [
        code.value for code in mismatched.admission.reason_codes
    ]
    assert mismatched.record is None
    assert stream.state.last_accepted_observation_id == baseline.observation_id

    # (3) a genuine re-delivery from a REAL new process, same epoch and same
    #     continuity, is still refused: one epoch declares one producer session.
    other_process = stream.step(
        replay_observation(continuity="live-continuity-9", sequence=41, epoch=3)
    )
    assert other_process.admission.outcome.value == "REJECTED_INVALID"
    assert "CONTINUITY_DECLARATION_MISMATCH" in [
        code.value for code in other_process.admission.reason_codes
    ]
    assert other_process.record is None
    assert stream.state.last_accepted_observation_id == baseline.observation_id
    assert stream.state.invalid_count == 2

    # (4) a declared new epoch is a boundary, never a transition over the real change.
    boundary = stream.step(
        replay_observation(continuity="live-continuity-replay", sequence=0, epoch=4),
        baseline,
    )
    assert boundary.admission.outcome.value == "NEW_EPOCH"
    assert boundary.record["outcome"] == "TEMPORAL_DISCONTINUITY"
    assert boundary.record["continuity"] == "NEW_EPOCH"
    assert boundary.record["entity_deltas"] == []
    assert boundary.record["observations_skipped"] == 0
    assert boundary.record["source_time_hold"] is False
    assert boundary.record["state_digest_changed"] is True
    assert "ORDERING_EPOCH_CHANGE" in boundary.record["reason_codes"]
    assert stream.state.last_accepted_observation_id == boundary.admission.observation.observation_id

    # Determinism: identical boundary inputs in a fresh stream reproduce the record.
    fresh = ObservationStream("live-temporal-v1")
    fresh.step(baseline)
    repeated = fresh.step(
        replay_observation(continuity="live-continuity-replay", sequence=0, epoch=4),
        baseline,
    )
    assert repeated.record == boundary.record
    assert repeated.record["delta_digest"] == boundary.record["delta_digest"]

    # Positive companion on the comparison path (harness-only declared session).
    companion_a, companion_b = _same_epoch_pair(
        first_snapshot, replay_snapshot, sequence_a=60, sequence_b=61, meta=first_meta
    )
    companion = finalize_record(
        evaluate(
            ComparisonInput(
                a=companion_a,
                b=companion_b,
                from_identity=_companion_from_identity(companion_a),
            )
        ),
        "UNEMITTED_EPOCH_ANCHOR",
    )
    assert companion["outcome"] == "COMPUTED"
    assert _location_changed(companion)

    print("ATLAS_TEMPORAL_L3B_EVIDENCE=" + json.dumps({
        "engine_version": first_meta["engine_version"],
        "engine_build": first_meta["engine_build"],
        "baseline_session": first_meta["producer_session_id"],
        "replay_session": replay_meta["producer_session_id"],
        "stale_outcome": stale.admission.outcome.value,
        "mismatched_outcome": mismatched.admission.outcome.value,
        "other_process_outcome": other_process.admission.outcome.value,
        "boundary_outcome": boundary.record["outcome"],
        "boundary_reason_codes": boundary.record["reason_codes"],
        "boundary_delta_digest": boundary.record["delta_digest"],
        "companion_outcome": companion["outcome"],
    }, sort_keys=True))


def _material_probe_script() -> str:
    return r'''
import bpy, json, os, sys

sys.path.insert(0, os.environ["ATLAS_REPO_ROOT"])

from planning.blender.bpy_extraction import run_live_blender_extraction
from planning.blender.extraction_payload import payload_representation_state, payload_to_scene_model
from planning.temporal.model import _scene_to_canonical

MODE = os.environ["ATLAS_TEMPORAL_MATERIAL_MODE"]

for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for material in list(bpy.data.materials):
    bpy.data.materials.remove(material)

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
bpy.context.scene.collection.objects.link(obj)

if MODE == "two_data_slots":
    mesh.materials.append(bpy.data.materials.new("Steel"))
    mesh.materials.append(bpy.data.materials.new("Rubber"))
elif MODE == "unassigned_data_slot":
    mesh.materials.append(None)
elif MODE == "object_linked_slot":
    mesh.materials.append(bpy.data.materials.new("Steel"))
    obj.material_slots[0].link = "OBJECT"

# Duplicate-representation probe (retained): a real Blender scene cannot expose two objects with the
# same object_id - bpy.data.objects keeps datablock names unique - so the producer cannot emit one.
dup_mesh = bpy.data.meshes.new("TemporalDupMesh")
dup_mesh.from_pydata([(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)], [], [(0, 1, 2)])
dup_mesh.update()
first_dup = bpy.data.objects.new("temporal_dup", dup_mesh)
bpy.context.scene.collection.objects.link(first_dup)
second_dup = bpy.data.objects.new("temporal_dup", dup_mesh)
bpy.context.scene.collection.objects.link(second_dup)
second_dup.name = "temporal_dup"

payload = run_live_blender_extraction(bpy)
scene = payload_to_scene_model(payload)
snapshot = _scene_to_canonical(scene)

build_hash = bpy.app.build_hash
if isinstance(build_hash, (bytes, bytearray)):
    build_hash = bytes(build_hash).decode("ascii")
else:
    build_hash = str(build_hash)

object_ids = [item["object_id"] for item in payload["objects"]]

result = {
    "snapshot": snapshot,
    "material_mode": MODE,
    "source_data_slots": [None if slot is None else str(slot.name) for slot in list(mesh.materials)],
    "source_object_slots": [
        {
            "link": str(slot.link),
            "material": None if slot.material is None else str(slot.material.name),
        }
        for slot in obj.material_slots
    ],
    "producer_mesh_keys_by_object": {
        item["object_id"]: sorted(item["mesh"].keys())
        for item in payload["objects"]
        if item["mesh"] is not None
    },
    "producer_materials_by_object": {
        item["object_id"]: item["mesh"].get("materials", "<<KEY-ABSENT>>")
        for item in payload["objects"]
        if item["mesh"] is not None
    },
    "representation_state": list(payload_representation_state(payload)),
    "payload_object_ids": object_ids,
    "duplicate_object_ids": sorted({i for i in object_ids if object_ids.count(i) > 1}),
    "duplicate_name_probe": {
        "requested": "temporal_dup",
        "first_actual_name": str(first_dup.name),
        "second_actual_name": str(second_dup.name),
    },
    "process_id": os.getpid(),
    "producer_session_id": "blender-proc-" + str(os.getpid()) + "-" + os.urandom(8).hex(),
    "engine_version": str(bpy.app.version_string),
    "engine_build": build_hash,
}

print("ATLAS_TEMPORAL_MATERIAL_START")
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
print("ATLAS_TEMPORAL_MATERIAL_END")
'''


def _run_live_material_probe(*, mode: str) -> Dict[str, Any]:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ)
    env.update(
        {
            "ATLAS_REPO_ROOT": repo,
            "PYTHONPATH": repo + os.pathsep + env.get("PYTHONPATH", ""),
            "ATLAS_TEMPORAL_MATERIAL_MODE": mode,
        }
    )
    fd, script_path = tempfile.mkstemp(
        prefix="atlas_temporal_material_", suffix=".py", dir=repo, text=True
    )
    os.close(fd)
    try:
        with open(script_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(_material_probe_script())
        proc = subprocess.run(
            [_blender_command(), "--background", "--python", script_path],
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
    if proc.returncode != 0:
        raise AssertionError(
            "live Blender material probe failed "
            f"rc={proc.returncode}: stdout={proc.stdout[-3000:]} stderr={proc.stderr[-5000:]}"
        )
    start = proc.stdout.find("ATLAS_TEMPORAL_MATERIAL_START")
    end = proc.stdout.find("ATLAS_TEMPORAL_MATERIAL_END")
    assert start != -1 and end != -1, (
        "live material probe markers missing. "
        "stdout: " + proc.stdout[-3000:] + " | stderr: " + proc.stderr[-5000:]
    )
    return json.loads(
        proc.stdout[start + len("ATLAS_TEMPORAL_MATERIAL_START") : end].strip()
    )


def _capability_with_representation_state(representation_state):
    """Capability declaration carrying the facts the PRODUCER actually encoded (design 4.5)."""

    return CapabilityContract(
        contract_id="extraction_fidelity_v1",
        observable_fields=tuple(sorted(_COMPARISON_FIELDS)),
        unobservable_fields=tuple(sorted(_UNOBSERVABLE_FIELDS)),
        representation_state=tuple(representation_state),
    )


def _material_probe_object(snapshot):
    return next(o for o in snapshot["objects"] if o["object_id"] == "temporal_probe")


def test_live_temporal_l4b_live_material_representation_is_truthful():
    """L-4 against the extraction-fidelity producer: real material states, truthful coverage and delta.

    A = a real Blender 4.4.3 scene with ZERO material slots; B = a real Blender scene with two real
    data-linked slots ('Steel', 'Rubber'). With the extraction-fidelity section 4.3 decision tree
    implemented by the producer, the payloads, the canonical snapshots and the temporal_state_digest all
    differ, and the StateDelta reports the material change instead of an apparently valid unchanged state.

    The omission encodings are retained: an unassigned data slot and an OBJECT-linked slot both omit the
    `materials` key, the canonical layer collapses an omission to the same `()` as `materials: []`
    (extraction section 4.5), and the declaration derived from the payload
    (`planning.blender.extraction_payload.payload_representation_state`) makes the Temporal layer report
    materials as UNAVAILABLE - never OBSERVED_UNCHANGED.

    The duplicate-representation probe is retained: Blender keeps datablock names unique, so a real scene
    cannot carry duplicate object_ids and IDENTITY_AMBIGUOUS stays deterministic-only coverage.
    """

    from dataclasses import replace as _dataclass_replace

    no_slots = _run_live_material_probe(mode="no_slots")
    two_slots = _run_live_material_probe(mode="two_data_slots")

    assert no_slots["engine_version"].startswith("4.4.")
    assert no_slots["producer_session_id"] != two_slots["producer_session_id"]

    # The two REAL Blender source states differ materially.
    assert no_slots["source_data_slots"] == []
    assert no_slots["source_object_slots"] == []
    assert two_slots["source_data_slots"] == ["Steel", "Rubber"]
    assert [slot["link"] for slot in two_slots["source_object_slots"]] == ["DATA", "DATA"]
    assert [slot["material"] for slot in two_slots["source_object_slots"]] == ["Steel", "Rubber"]

    # (1) the producer payloads differ, under the section 4.3 tree.
    assert no_slots["producer_materials_by_object"]["temporal_probe"] == []
    assert two_slots["producer_materials_by_object"]["temporal_probe"] == ["Steel", "Rubber"]
    assert (
        no_slots["producer_mesh_keys_by_object"]["temporal_probe"]
        == two_slots["producer_mesh_keys_by_object"]["temporal_probe"]
    )
    assert "materials" in two_slots["producer_mesh_keys_by_object"]["temporal_probe"]

    # (2) the canonical temporal snapshots differ.
    snapshot_a = no_slots["snapshot"]
    snapshot_b = two_slots["snapshot"]
    assert _material_probe_object(snapshot_a)["mesh"]["materials"] == []
    assert _material_probe_object(snapshot_b)["mesh"]["materials"] == ["Steel", "Rubber"]

    # (3) the temporal state digest differs.
    assert temporal_state_digest(snapshot_a) != temporal_state_digest(snapshot_b)

    # (4) the declaration is derived from each real payload, never hardcoded.
    assert no_slots["representation_state"] == []
    assert two_slots["representation_state"] == []

    session = no_slots["producer_session_id"]
    a = _observation(
        snapshot_a,
        session=session,
        continuity="live-continuity-materials",
        sequence=0,
        ordering_epoch=0,
        capture_time=1,
        engine_version=no_slots["engine_version"],
        engine_build=no_slots["engine_build"],
    )
    b = _observation(
        snapshot_b,
        session=session,
        continuity="live-continuity-materials",
        sequence=1,
        ordering_epoch=0,
        capture_time=2,
        engine_version=two_slots["engine_version"],
        engine_build=two_slots["engine_build"],
    )

    stream = ObservationStream("live-temporal-v1")
    stream.step(a)
    result = stream.step(b, a)
    record = result.record

    assert record is not None
    assert record["outcome"] == "COMPUTED"
    assert record["state_digest_changed"] is True

    # (5) truthful coverage and a reported material change.
    assert record["coverage"]["materials"] == "OBSERVED_CHANGED"
    material_changes = [
        change
        for entity in record["entity_deltas"]
        for change in entity["field_changes"]
        if change["field"] == "materials"
    ]
    assert len(material_changes) == 1
    assert material_changes[0]["before"] == []
    assert material_changes[0]["after"] == ["Steel", "Rubber"]
    probe_entity = next(
        entity for entity in record["entity_deltas"] if entity["object_id"] == "temporal_probe"
    )
    assert probe_entity["kind"] == "OBJECT_CHANGED"
    assert [change["field"] for change in probe_entity["field_changes"]] == ["materials"]
    assert record["coverage"]["location"] == "OBSERVED_UNCHANGED"

    # --- retained omission encodings -------------------------------------------------------
    omitted = _run_live_material_probe(mode="unassigned_data_slot")
    linked = _run_live_material_probe(mode="object_linked_slot")

    omission_evidence = {}
    for probe in (omitted, linked):
        mode = probe["material_mode"]
        # a real source slot exists, yet the producer omits the key for the whole mesh
        assert probe["source_data_slots"] != []
        assert "materials" not in probe["producer_mesh_keys_by_object"]["temporal_probe"]
        assert probe["producer_materials_by_object"]["temporal_probe"] == "<<KEY-ABSENT>>"
        assert probe["representation_state"] == ["materials:omitted"]
        # the canonical layer cannot tell an omission from an empty list - hence the declaration
        assert _material_probe_object(probe["snapshot"])["mesh"]["materials"] == []

        declared_b = _dataclass_replace(
            b,
            capability=_capability_with_representation_state(probe["representation_state"]),
            snapshot=probe["snapshot"],
            state_digest=temporal_state_digest(probe["snapshot"]),
        )
        declared_stream = ObservationStream("live-temporal-v1")
        declared_stream.step(a)
        declared_result = declared_stream.step(declared_b, a)
        declared_record = declared_result.record

        assert declared_record is not None
        assert declared_record["outcome"] == "COMPUTED"
        assert declared_record["coverage"]["materials"] == "UNAVAILABLE"
        assert not any(
            change["field"] == "materials"
            for entity in declared_record["entity_deltas"]
            for change in entity["field_changes"]
        )
        omission_evidence[mode] = {
            "source_data_slots": probe["source_data_slots"],
            "source_object_slots": probe["source_object_slots"],
            "payload_materials": probe["producer_materials_by_object"]["temporal_probe"],
            "representation_state": probe["representation_state"],
            "materials_coverage": declared_record["coverage"]["materials"],
            "delta_digest": declared_record["delta_digest"],
        }

    # --- retained duplicate-representation probe -------------------------------------------
    assert no_slots["duplicate_name_probe"]["second_actual_name"] == "temporal_dup.001"
    assert no_slots["duplicate_object_ids"] == []
    assert len(no_slots["payload_object_ids"]) == len(set(no_slots["payload_object_ids"]))

    print("ATLAS_TEMPORAL_L4B_EVIDENCE=" + json.dumps({
        "engine_version": no_slots["engine_version"],
        "engine_build": no_slots["engine_build"],
        "no_slots_process": no_slots["producer_session_id"],
        "two_slots_process": two_slots["producer_session_id"],
        "source_data_slots_no_slots": no_slots["source_data_slots"],
        "source_data_slots_two_slots": two_slots["source_data_slots"],
        "payload_materials_no_slots": no_slots["producer_materials_by_object"]["temporal_probe"],
        "payload_materials_two_slots": two_slots["producer_materials_by_object"]["temporal_probe"],
        "mesh_keys": two_slots["producer_mesh_keys_by_object"]["temporal_probe"],
        "state_digest_a": temporal_state_digest(snapshot_a),
        "state_digest_b": temporal_state_digest(snapshot_b),
        "digests_differ": temporal_state_digest(snapshot_a) != temporal_state_digest(snapshot_b),
        "materials_coverage": record["coverage"]["materials"],
        "materials_change": material_changes[0],
        "entity_kind": probe_entity["kind"],
        "state_digest_changed": record["state_digest_changed"],
        "fidelity_delta_digest": record["delta_digest"],
        "omission_encodings": omission_evidence,
        "duplicate_name_probe": no_slots["duplicate_name_probe"],
        "duplicate_object_ids": no_slots["duplicate_object_ids"],
    }, sort_keys=True))
