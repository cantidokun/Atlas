"""Deterministic tests for the Temporal Observation + State Delta v1 core."""

import copy

import pytest

from planning.temporal import (
    AdmissionOutcome,
    CapabilityContract,
    DeltaReasonCode,
    AdmissionCheckpoint,
    ObservationStream,
    ProducerProvenance,
    RecoveryCheckpointError,
    validate_reinitialization_declaration,
    SourceTime,
    TemporalObservation,
    temporal_state_digest,
)
from planning.temporal.canonical import CanonicalValueError, sha256_digest


COMPARISON_FIELDS = (
    "collection",
    "faces",
    "location",
    "materials",
    "mesh_id",
    "mesh_presence",
    "parent_object_id",
    "rotation",
    "scale",
    "unit_system",
    "vertices",
    "visible",
    "scene_id",
)
UNOBSERVABLE_FIELDS = ("coordinate_frame", "local_frame_id", "normals", "uvs")


def capability(contract_id="test-v1"):
    return CapabilityContract(
        contract_id=contract_id,
        observable_fields=tuple(sorted(COMPARISON_FIELDS)),
        unobservable_fields=tuple(sorted(UNOBSERVABLE_FIELDS)),
        representation_state=(),
    )


def producer(session="session-1"):
    return ProducerProvenance(
        producer_source="BLENDER",
        producer_contract="extraction_fidelity_v1",
        engine_version="4.4.3",
        engine_build="802179c51ccc",
        producer_session_id=session,
        producer_instance_ordinal=1,
    )


def snapshot(location=(0.0, 0.0, 0.0), rotation=(1.0, 0.0, 0.0, 0.0), scene_id="scene-a"):
    return {
        "scene_id": scene_id,
        "unit_system": "METERS",
        "objects": [
            {
                "object_id": "obj-1",
                "name": "obj-1",
                "collection": "Collection",
                "parent_object_id": None,
                "location": list(location),
                "scale": [1.0, 1.0, 1.0],
                "rotation": list(rotation),
                "visible": True,
                "mesh": {
                    "mesh_id": "mesh-1",
                    "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                    "faces": [[0, 1, 2]],
                    "materials": ["mat"],
                },
            }
        ],
        "coordinate_frame": None,
        "world_bounds": None,
    }


def observation(
    sequence,
    *,
    ordering_epoch=0,
    continuity_id="continuity-1",
    session="session-1",
    location=(0.0, 0.0, 0.0),
    rotation=(1.0, 0.0, 0.0, 0.0),
    scene_id="scene-a",
    contract_id="test-v1",
):
    body = snapshot(location=location, rotation=rotation, scene_id=scene_id)
    return TemporalObservation(
        stream_id="stream-1",
        continuity_id=continuity_id,
        sequence=sequence,
        source_time=SourceTime(
            domain="FRAME_INDEX",
            value=sequence,
            rate_num=1,
            rate_den=1,
            ordering_epoch=ordering_epoch,
        ),
        producer=producer(session),
        capability=capability(contract_id),
        snapshot=body,
        state_digest=temporal_state_digest(body),
    )


def test_canonical_bytes_reject_nonfinite_and_surrogate():
    with pytest.raises(CanonicalValueError):
        sha256_digest(float("nan"))
    with pytest.raises(CanonicalValueError):
        sha256_digest("\ud800")


def test_canonical_bytes_preserve_signed_zero():
    assert sha256_digest(-0.0) != sha256_digest(0.0)


def test_observation_id_includes_epoch():
    a = observation(0, ordering_epoch=0)
    b = observation(0, ordering_epoch=1, continuity_id="continuity-2")
    assert a.observation_id != b.observation_id


def test_first_second_third_lineage():
    stream = ObservationStream("stream-1")
    a = observation(0)
    b = observation(1, location=(1.0, 0.0, 0.0))
    c = observation(2, location=(2.0, 0.0, 0.0))

    first = stream.step(a)
    second = stream.step(b, a)
    third = stream.step(c, b)

    assert first.admission.outcome is AdmissionOutcome.INITIAL_ACCEPTED
    assert first.record is None

    assert second.admission.outcome is AdmissionOutcome.ACCEPTED
    assert second.record["from_observation_origin"] == "UNEMITTED_EPOCH_ANCHOR"
    assert second.record["outcome"] == "COMPUTED"

    assert third.record["from_observation_origin"] == "EMITTED_PREDECESSOR"
    assert third.record["from_observation_id"] == b.observation_id


def test_refusal_then_continue_uses_refused_b_as_predecessor():
    stream = ObservationStream("stream-1")
    a = observation(0)
    b = observation(1, contract_id="other-contract")
    c = observation(2, location=(2.0, 0.0, 0.0), contract_id="other-contract")

    stream.step(a)
    refusal = stream.step(b, a)
    computed = stream.step(c, b)

    assert refusal.admission.outcome is AdmissionOutcome.ACCEPTED
    assert refusal.record["outcome"] == "OBSERVATION_INVALID"
    assert DeltaReasonCode.CAPABILITY_MISMATCH.value in refusal.record["reason_codes"]
    assert computed.record["outcome"] == "COMPUTED"
    assert computed.record["from_observation_id"] == b.observation_id


def test_rejected_arrival_does_not_rewrite_predecessor_origin():
    stream = ObservationStream("stream-1")
    a = observation(0)
    duplicate = observation(0)
    b = observation(1, location=(1.0, 0.0, 0.0))

    stream.step(a)
    duplicate_result = stream.step(duplicate)
    result = stream.step(b, a)

    assert duplicate_result.admission.outcome is AdmissionOutcome.DUPLICATE_ACKNOWLEDGED
    assert result.record["from_observation_origin"] == "UNEMITTED_EPOCH_ANCHOR"


def test_scene_scope_change_is_admission_rejection():
    stream = ObservationStream("stream-1")
    a = observation(0)
    b = observation(1, scene_id="scene-b")

    stream.step(a)
    result = stream.step(b, a)

    assert result.admission.outcome is AdmissionOutcome.REJECTED_INVALID
    assert "SCENE_SCOPE_CHANGED" in [code.value for code in result.admission.reason_codes]
    assert result.record is None
    assert stream.state.last_accepted_observation_id == a.observation_id


def test_equal_source_time_is_legal():
    stream = ObservationStream("stream-1")
    a = observation(0)
    b_body = snapshot(location=(1.0, 0.0, 0.0))
    b = TemporalObservation(
        stream_id="stream-1",
        continuity_id="continuity-1",
        sequence=1,
        source_time=SourceTime("FRAME_INDEX", 0, 1, 1, 0),
        producer=producer(),
        capability=capability(),
        snapshot=b_body,
        state_digest=temporal_state_digest(b_body),
    )

    stream.step(a)
    result = stream.step(b, a)
    assert result.admission.outcome is AdmissionOutcome.ACCEPTED
    assert result.record["outcome"] == "COMPUTED"
    assert result.record["source_time_hold"] is True


def test_quaternion_sign_equivalence_keeps_raw_digest_change():
    stream = ObservationStream("stream-1")
    a = observation(0, rotation=(1.0, 0.0, 0.0, 0.0))
    b = observation(1, rotation=(-1.0, -0.0, -0.0, -0.0))

    stream.step(a)
    result = stream.step(b, a)

    assert result.record["state_digest_changed"] is True
    assert result.record["source_time_hold"] is False
    assert "ROTATION_SIGN_EQUIVALENT_ONLY" in result.record["reason_codes"]
    changed = [
        item for entity in result.record["entity_deltas"]
        for item in entity["field_changes"]
        if item["field"] == "rotation"
    ]
    assert changed == []


def test_new_epoch_boundary_never_compares_fields():
    stream = ObservationStream("stream-1")
    a = observation(0)
    b = observation(
        0,
        ordering_epoch=1,
        continuity_id="continuity-2",
        location=(50.0, 0.0, 0.0),
    )

    stream.step(a)
    result = stream.step(b, a)

    assert result.admission.outcome is AdmissionOutcome.NEW_EPOCH
    assert result.record["outcome"] == "TEMPORAL_DISCONTINUITY"
    assert result.record["continuity"] == "NEW_EPOCH"
    assert result.record["entity_deltas"] == []
    assert result.record["observations_skipped"] == 0
    assert result.record["source_time_hold"] is False
    assert result.record["from_observation_origin"] == "UNEMITTED_EPOCH_ANCHOR"


def test_new_epoch_missing_predecessor_is_refusal_but_still_admitted():
    stream = ObservationStream("stream-1")
    a = observation(0)
    b = observation(0, ordering_epoch=1, continuity_id="continuity-2")

    stream.step(a)
    result = stream.step(b)

    assert result.admission.outcome is AdmissionOutcome.NEW_EPOCH
    assert result.record["outcome"] == "OBSERVATION_INVALID"
    assert result.record["pair_input"] == "UNAVAILABLE"
    assert "PAIR_INPUT_UNAVAILABLE" in result.record["reason_codes"]
    assert stream.state.last_accepted_observation_id == b.observation_id



def test_recovery_checkpoint_round_trip_is_content_free_and_integrity_checked():
    stream = ObservationStream("stream-1")
    a = observation(0)
    stream.step(a)

    checkpoint = AdmissionCheckpoint.from_state(stream.state, generation=7)
    payload = checkpoint.to_dict()
    restored = AdmissionCheckpoint.restore(payload).restore_state()

    assert restored.stream_id == stream.state.stream_id
    assert restored.last_accepted_observation_id == stream.state.last_accepted_observation_id
    assert restored.last_accepted_state_digest == stream.state.last_accepted_state_digest
    assert "snapshot" not in payload
    assert payload["checkpoint_commit_state"] == "COMMITTED"


def test_recovery_checkpoint_fails_closed_for_tamper_and_non_committed_state():
    stream = ObservationStream("stream-1")
    stream.step(observation(0))
    payload = AdmissionCheckpoint.from_state(stream.state, generation=1).to_dict()

    tampered = dict(payload)
    tampered["accepted_count"] += 1
    with pytest.raises(RecoveryCheckpointError, match="digest mismatch"):
        AdmissionCheckpoint.restore(tampered)

    uncommitted = dict(payload)
    uncommitted["checkpoint_commit_state"] = "PREPARED"
    with pytest.raises(RecoveryCheckpointError, match="not COMMITTED"):
        AdmissionCheckpoint.restore(uncommitted)


def test_recovery_checkpoint_rejects_unknown_or_missing_fields():
    stream = ObservationStream("stream-1")
    stream.step(observation(0))
    payload = AdmissionCheckpoint.from_state(stream.state, generation=1).to_dict()

    unknown = dict(payload)
    unknown["unexpected"] = 1
    with pytest.raises(RecoveryCheckpointError, match="unknown checkpoint fields"):
        AdmissionCheckpoint.restore(unknown)

    missing = dict(payload)
    del missing["last_accepted_sequence"]
    with pytest.raises(RecoveryCheckpointError, match="incomplete checkpoint"):
        AdmissionCheckpoint.restore(missing)


def test_recovery_reinitialization_requires_new_continuity_and_higher_epoch():
    stream = ObservationStream("stream-1")
    stream.step(observation(0))

    with pytest.raises(RecoveryCheckpointError, match="strictly greater ordering_epoch"):
        validate_reinitialization_declaration(
            stream.state,
            new_continuity_id=stream.state.continuity_id,
            new_ordering_epoch=stream.state.ordering_epoch,
        )

    with pytest.raises(RecoveryCheckpointError, match="new continuity_id"):
        validate_reinitialization_declaration(
            stream.state,
            new_continuity_id=stream.state.continuity_id,
            new_ordering_epoch=stream.state.ordering_epoch + 1,
        )

    validate_reinitialization_declaration(
        stream.state,
        new_continuity_id="continuity-2",
        new_ordering_epoch=stream.state.ordering_epoch + 1,
    )



def test_temporal_state_digest_changes_for_name_and_material_state():
    base = snapshot()
    renamed = copy.deepcopy(base)
    renamed["objects"][0]["name"] = "obj-1-renamed"
    changed_material = copy.deepcopy(base)
    changed_material["objects"][0]["mesh"]["materials"] = ["mat-2"]

    assert temporal_state_digest(base) != temporal_state_digest(renamed)
    assert temporal_state_digest(base) != temporal_state_digest(changed_material)


def test_snapshot_representation_preserves_omitted_materials_key():
    body = snapshot()
    del body["objects"][0]["mesh"]["materials"]
    obs = TemporalObservation(
        stream_id="stream-1",
        continuity_id="continuity-1",
        sequence=0,
        source_time=SourceTime("FRAME_INDEX", 0, 1, 1, 0),
        producer=producer(),
        capability=capability(),
        snapshot=body,
        state_digest=temporal_state_digest(body),
    )

    assert "materials" not in obs.snapshot["objects"][0]["mesh"]



def test_stream_restore_from_checkpoint_preserves_predecessor_identity():
    stream = ObservationStream("stream-1")
    a = observation(0)
    stream.step(a)

    checkpoint = AdmissionCheckpoint.from_state(stream.state, generation=4)
    restored = ObservationStream.from_checkpoint(checkpoint)

    b = observation(1, location=(1.0, 0.0, 0.0))
    result = restored.step(b, a)

    assert result.admission.outcome is AdmissionOutcome.ACCEPTED
    assert result.record["from_observation_id"] == a.observation_id


def test_stream_explicit_reinitialize_discards_baseline_without_synthetic_record():
    stream = ObservationStream("stream-1")
    a = observation(0)
    stream.step(a)

    stream.reinitialize(
        new_continuity_id="continuity-2",
        new_ordering_epoch=1,
    )

    b = observation(0, continuity_id="continuity-2", ordering_epoch=1)
    result = stream.step(b)

    assert result.admission.outcome is AdmissionOutcome.INITIAL_ACCEPTED
    assert result.record is None
    assert stream.state.accepted_count == 2
    assert stream.state.epoch_count == 2



def test_duplicate_object_digest_is_order_independent():
    first = snapshot()
    second = copy.deepcopy(first)
    second["objects"].insert(0, second["objects"].pop())
    assert temporal_state_digest(first) == temporal_state_digest(second)


def test_reinitialize_requires_the_declared_epoch_on_the_first_valid_observation():
    stream = ObservationStream("stream-1")
    stream.step(observation(0))

    stream.reinitialize(
        new_continuity_id="continuity-2",
        new_ordering_epoch=1,
    )

    wrong = observation(0, continuity_id="continuity-3", ordering_epoch=2)
    rejected = stream.step(wrong)
    assert rejected.admission.outcome is AdmissionOutcome.REJECTED_INVALID
    assert "CONTINUITY_DECLARATION_MISMATCH" in [
        code.value for code in rejected.admission.reason_codes
    ]
    assert rejected.record is None
    assert stream.state.last_accepted_observation_id is None

    right = observation(0, continuity_id="continuity-2", ordering_epoch=1)
    accepted = stream.step(right)
    assert accepted.admission.outcome is AdmissionOutcome.INITIAL_ACCEPTED
    assert accepted.record is None
    assert stream.state.last_accepted_observation_id == right.observation_id
