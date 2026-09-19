"""Adversarial deterministic coverage for Atlas Temporal v1 Revision 9."""
import copy

from dataclasses import replace

import pytest

from planning.temporal import (
    AdmissionCheckpoint,
    AdmissionOutcome,
    BoundaryInput,
    BoundaryRefusalInput,
    CapabilityContract,
    ComparisonInput,
    DeltaReasonCode,
    DeltaOutcome,
    FromIdentity,
    ObservationStream,
    ProducerProvenance,
    RecoveryCheckpointError,
    RefusalInput,
    SourceTime,
    TemporalObservation,
    evaluate,
    finalize_record,
    temporal_state_digest,
)
from planning.temporal.canonical import CanonicalValueError, sha256_digest
from planning.temporal.model import parse_canonical_snapshot_json


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


def capability(contract_id="test-v1", representation_state=()):
    return CapabilityContract(
        contract_id=contract_id,
        observable_fields=tuple(sorted(COMPARISON_FIELDS)),
        unobservable_fields=tuple(sorted(UNOBSERVABLE_FIELDS)),
        representation_state=tuple(sorted(representation_state)),
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


def snapshot(
    *,
    location=(0.0, 0.0, 0.0),
    rotation=(1.0, 0.0, 0.0, 0.0),
    scene_id="scene-a",
    unit_system="METERS",
):
    return {
        "scene_id": scene_id,
        "unit_system": unit_system,
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
    unit_system="METERS",
    source_domain="FRAME_INDEX",
    source_value=None,
    rate_num=1,
    rate_den=1,
    contract_id="test-v1",
    representation_state=(),
):
    body = snapshot(
        location=location,
        rotation=rotation,
        scene_id=scene_id,
        unit_system=unit_system,
    )
    return TemporalObservation(
        stream_id="stream-1",
        continuity_id=continuity_id,
        sequence=sequence,
        source_time=SourceTime(
            domain=source_domain,
            value=sequence if source_value is None else source_value,
            rate_num=rate_num,
            rate_den=rate_den,
            ordering_epoch=ordering_epoch,
        ),
        producer=producer(session),
        capability=capability(contract_id, representation_state),
        snapshot=body,
        state_digest=temporal_state_digest(body),
    )


def test_canonical_dict_order_is_digest_invariant():
    left = {"b": [1, True, 2.0], "a": {"z": "x", "y": "q"}}
    right = {"a": {"y": "q", "z": "x"}, "b": [1, True, 2.0]}
    assert sha256_digest(left) == sha256_digest(right)


def test_canonical_integer_domain_and_bool_are_distinct():
    assert sha256_digest(0) != sha256_digest(False)
    assert sha256_digest(-(1 << 63))
    assert sha256_digest((1 << 63) - 1)
    with pytest.raises(CanonicalValueError):
        sha256_digest(-(1 << 63) - 1)
    with pytest.raises(CanonicalValueError):
        sha256_digest(1 << 63)


def test_duplicate_json_object_keys_fail_before_mapping():
    payload = '{"scene_id":"scene-a","scene_id":"scene-b"}'
    with pytest.raises(Exception, match="duplicate key"):
        parse_canonical_snapshot_json(payload)


def test_stale_ordering_epoch_is_rejected_without_mutating_baseline():
    stream = ObservationStream("stream-1")
    a = observation(3, ordering_epoch=2)
    stream.step(a)
    stale = observation(99, ordering_epoch=1, continuity_id="old")
    result = stream.step(stale, a)

    assert result.admission.outcome is AdmissionOutcome.REJECTED_STALE
    assert "ORDERING_EPOCH_REGRESSION" in [code.value for code in result.admission.reason_codes]
    assert stream.state.last_accepted_observation_id == a.observation_id


def test_epoch_only_bump_fails_closed():
    stream = ObservationStream("stream-1")
    a = observation(0)
    b = observation(0, ordering_epoch=1, continuity_id="continuity-1")
    stream.step(a)
    result = stream.step(b, a)

    assert result.admission.outcome is AdmissionOutcome.REJECTED_INVALID
    assert "CONTINUITY_DECLARATION_MISMATCH" in [code.value for code in result.admission.reason_codes]


def test_continuity_only_change_fails_closed():
    stream = ObservationStream("stream-1")
    a = observation(0)
    b = observation(1, continuity_id="continuity-2", ordering_epoch=0)
    stream.step(a)
    result = stream.step(b, a)

    assert result.admission.outcome is AdmissionOutcome.REJECTED_INVALID
    assert "CONTINUITY_DECLARATION_MISMATCH" in [code.value for code in result.admission.reason_codes]


def test_session_only_change_fails_closed():
    stream = ObservationStream("stream-1")
    a = observation(0, session="session-1")
    b = observation(1, session="session-2")
    stream.step(a)
    result = stream.step(b, a)

    assert result.admission.outcome is AdmissionOutcome.REJECTED_INVALID
    assert "CONTINUITY_DECLARATION_MISMATCH" in [code.value for code in result.admission.reason_codes]


def test_sequence_regression_is_stale():
    stream = ObservationStream("stream-1")
    a = observation(5)
    stream.step(a)
    stale = observation(4)
    result = stream.step(stale, a)

    assert result.admission.outcome is AdmissionOutcome.REJECTED_STALE
    assert result.record is None


def test_same_sequence_identical_identity_is_idempotent():
    stream = ObservationStream("stream-1")
    a = observation(0)
    stream.step(a)
    duplicate = stream.step(replace(a, capture_time=999), a)

    assert duplicate.admission.outcome is AdmissionOutcome.DUPLICATE_ACKNOWLEDGED
    assert duplicate.record is None
    assert stream.state.last_accepted_observation_id == a.observation_id


def test_same_sequence_contradictory_identity_is_rejected():
    stream = ObservationStream("stream-1")
    a = observation(0)
    stream.step(a)
    contradictory = observation(0, location=(2.0, 0.0, 0.0))
    result = stream.step(contradictory, a)

    assert result.admission.outcome is AdmissionOutcome.REJECTED_INVALID
    assert "CONTRADICTORY_SEQUENCE" in [code.value for code in result.admission.reason_codes]


def test_source_time_domain_mismatch_is_admission_failure():
    stream = ObservationStream("stream-1")
    a = observation(0, source_domain="FRAME_INDEX")
    stream.step(a)
    b = observation(1, source_domain="MEDIA_TICKS")
    result = stream.step(b, a)

    assert result.admission.outcome is AdmissionOutcome.REJECTED_INVALID
    assert "SOURCE_TIME_DOMAIN_MISMATCH" in [code.value for code in result.admission.reason_codes]


def test_source_time_rate_mismatch_is_admission_failure():
    stream = ObservationStream("stream-1")
    a = observation(0, rate_num=1, rate_den=1)
    stream.step(a)
    b = observation(1, rate_num=2, rate_den=1)
    result = stream.step(b, a)

    assert result.admission.outcome is AdmissionOutcome.REJECTED_INVALID
    assert "SOURCE_TIME_RATE_MISMATCH" in [code.value for code in result.admission.reason_codes]


def test_source_time_regression_is_admission_failure():
    stream = ObservationStream("stream-1")
    a = observation(0)
    stream.step(a)
    b = observation(1, source_value=-1)
    result = stream.step(b, a)

    assert result.admission.outcome is AdmissionOutcome.REJECTED_INVALID
    assert "SOURCE_TIME_NON_MONOTONIC" in [code.value for code in result.admission.reason_codes]


def test_source_time_equal_value_is_accepted_when_state_changes():
    stream = ObservationStream("stream-1")
    a = observation(0)
    b = observation(1, source_value=0, location=(1.0, 0.0, 0.0))
    stream.step(a)
    result = stream.step(b, a)

    assert result.admission.outcome is AdmissionOutcome.ACCEPTED
    assert result.record["source_time_hold"] is True


def test_same_epoch_unit_change_is_pair_refusal_not_membership_failure():
    stream = ObservationStream("stream-1")
    a = observation(0, unit_system="METERS")
    b = observation(1, unit_system="CENTIMETERS")
    c = observation(2, unit_system="CENTIMETERS", location=(2.0, 0.0, 0.0))

    stream.step(a)
    refusal = stream.step(b, a)
    computed = stream.step(c, b)

    assert refusal.admission.outcome is AdmissionOutcome.ACCEPTED
    assert refusal.record["outcome"] == "OBSERVATION_INVALID"
    assert "UNIT_SYSTEM_CHANGED" in refusal.record["reason_codes"]
    assert computed.record["outcome"] == "COMPUTED"
    assert computed.record["from_observation_id"] == b.observation_id


def test_identity_mismatch_is_pure_evaluation_refusal():
    a = observation(0)
    b = observation(1, location=(1.0, 0.0, 0.0))
    stream = ObservationStream("stream-1")
    stream.step(a)
    from_identity = stream.state.from_identity()
    assert isinstance(from_identity, FromIdentity)

    wrong_projection = replace(from_identity, last_accepted_observation_id="obs:wrong")
    result = evaluate(ComparisonInput(a=a, b=b, from_identity=wrong_projection))

    assert result["outcome"] == DeltaOutcome.OBSERVATION_INVALID.value
    assert DeltaReasonCode.PAIR_INPUT_IDENTITY_MISMATCH.value in result["reason_codes"]
    assert result["pair_input"] == "AVAILABLE"
    assert result["entity_deltas"] == []


def test_boundary_identity_mismatch_preserves_boundary_outcome_only_as_refusal():
    a = observation(0)
    b = observation(0, ordering_epoch=1, continuity_id="continuity-2")
    wrong_a = replace(a, sequence=10)
    stream = ObservationStream("stream-1")
    stream.step(a)
    from_identity = stream.state.from_identity()
    result = evaluate(BoundaryInput(a=wrong_a, b=b, from_identity=from_identity))

    assert result["outcome"] == DeltaOutcome.OBSERVATION_INVALID.value
    assert DeltaReasonCode.PAIR_INPUT_IDENTITY_MISMATCH.value in result["reason_codes"]
    assert result["continuity"] == "NEW_EPOCH"


def test_boundary_multi_cause_reason_set_is_complete_and_sorted():
    stream = ObservationStream("stream-1")
    a = observation(0, continuity_id="continuity-1", session="session-1", ordering_epoch=0)
    b = observation(
        0,
        continuity_id="continuity-2",
        session="session-2",
        ordering_epoch=1,
    )
    stream.step(a)
    result = stream.step(b, a)

    assert result.admission.outcome is AdmissionOutcome.NEW_EPOCH
    expected = sorted([
        DeltaReasonCode.TEMPORAL_DISCONTINUITY_CONTINUITY_ID_CHANGE.value,
        DeltaReasonCode.RESTART_PRODUCER_SESSION.value,
        DeltaReasonCode.ORDERING_EPOCH_CHANGE.value,
    ])
    assert result.record["reason_codes"] == expected


def test_boundary_does_not_compare_capability_or_sequence_gap():
    stream = ObservationStream("stream-1")
    a = observation(10)
    b = observation(
        0,
        continuity_id="continuity-2",
        ordering_epoch=1,
        contract_id="other-contract",
    )
    stream.step(a)
    result = stream.step(b, a)

    assert result.admission.outcome is AdmissionOutcome.NEW_EPOCH
    assert result.record["outcome"] == "TEMPORAL_DISCONTINUITY"
    assert result.record["observations_skipped"] == 0
    assert result.record["entity_deltas"] == []
    assert result.record["reason_codes"] == sorted([
        DeltaReasonCode.TEMPORAL_DISCONTINUITY_CONTINUITY_ID_CHANGE.value,
        DeltaReasonCode.ORDERING_EPOCH_CHANGE.value,
    ])


def test_equal_input_evaluation_is_digest_deterministic():
    a = observation(0)
    b = observation(1, location=(1.0, 0.0, 0.0))
    stream = ObservationStream("stream-1")
    stream.step(a)
    from_identity = stream.state.from_identity()
    assert isinstance(from_identity, FromIdentity)

    first = finalize_record(
        evaluate(ComparisonInput(a=a, b=b, from_identity=from_identity)),
        "UNEMITTED_EPOCH_ANCHOR",
    )
    second = finalize_record(
        evaluate(ComparisonInput(a=a, b=b, from_identity=from_identity)),
        "UNEMITTED_EPOCH_ANCHOR",
    )
    assert first == second



def test_duplicate_object_id_emits_ambiguity_cardinality_without_pairing():
    a = observation(0)
    b_body = snapshot()
    b_body["objects"].append(copy.deepcopy(b_body["objects"][0]))

    b = TemporalObservation(
        stream_id="stream-1",
        continuity_id="continuity-1",
        sequence=1,
        source_time=SourceTime("FRAME_INDEX", 1, 1, 1, 0),
        producer=producer(),
        capability=capability(),
        snapshot=b_body,
        state_digest=temporal_state_digest(b_body),
    )
    stream = ObservationStream("stream-1")
    stream.step(a)
    result = stream.step(b, a)

    ambiguous = [
        item for item in result.record["entity_deltas"]
        if item["kind"] == "IDENTITY_AMBIGUOUS"
    ]
    assert len(ambiguous) == 1
    assert ambiguous[0]["ambiguity"] == {"count_before": 1, "count_after": 2}
    assert ambiguous[0]["field_changes"] == []
    assert ambiguous[0]["object_id"] == "obj-1"



def test_material_omission_is_unavailable_not_observed_unchanged():
    stream = ObservationStream("stream-1")
    a_body = snapshot()
    b_body = snapshot()
    del a_body["objects"][0]["mesh"]["materials"]
    del b_body["objects"][0]["mesh"]["materials"]

    a = TemporalObservation(
        stream_id="stream-1",
        continuity_id="continuity-1",
        sequence=0,
        source_time=SourceTime("FRAME_INDEX", 0, 1, 1, 0),
        producer=producer(),
        capability=capability(representation_state=("materials:omitted",)),
        snapshot=a_body,
        state_digest=temporal_state_digest(a_body),
    )
    b = TemporalObservation(
        stream_id="stream-1",
        continuity_id="continuity-1",
        sequence=1,
        source_time=SourceTime("FRAME_INDEX", 0, 1, 1, 0),
        producer=producer(),
        capability=capability(representation_state=("materials:omitted",)),
        snapshot=b_body,
        state_digest=temporal_state_digest(b_body),
    )

    stream.step(a)
    result = stream.step(b, a)

    assert result.record["coverage"]["materials"] == "UNAVAILABLE"
    assert not any(
        change["field"] == "materials"
        for entity in result.record["entity_deltas"]
        for change in entity["field_changes"]
    )


def test_temporal_metadata_does_not_change_temporal_state_digest():
    body = snapshot()
    a = observation(0, source_value=0)
    b = observation(99, source_value=99, session="session-2")

    assert a.state_digest == temporal_state_digest(body)
    assert b.state_digest == temporal_state_digest(body)
    assert a.state_digest == b.state_digest
    assert a.admission_identity_digest != b.admission_identity_digest



@pytest.mark.parametrize(
    "field,mutator",
    [
        ("collection", lambda body: body["objects"][0].update(collection="Other")),
        ("parent_object_id", lambda body: body["objects"][0].update(parent_object_id="parent-1")),
        ("location", lambda body: body["objects"][0].update(location=[1.0, 0.0, 0.0])),
        ("scale", lambda body: body["objects"][0].update(scale=[2.0, 1.0, 1.0])),
        ("rotation", lambda body: body["objects"][0].update(rotation=[0.0, 1.0, 0.0, 0.0])),
        ("visible", lambda body: body["objects"][0].update(visible=False)),
        ("mesh_presence", lambda body: body["objects"][0].update(mesh=None)),
        ("mesh_id", lambda body: body["objects"][0]["mesh"].update(mesh_id="mesh-2")),
        ("vertices", lambda body: body["objects"][0]["mesh"].update(
            vertices=[[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        )),
        ("faces", lambda body: body["objects"][0]["mesh"].update(faces=[[0, 2, 1]])),
        ("materials", lambda body: body["objects"][0]["mesh"].update(materials=["mat-2"])),
    ],
)
def test_each_temporal_comparison_field_is_reported(field, mutator):
    a_body = snapshot()
    b_body = copy.deepcopy(a_body)
    mutator(b_body)

    a = TemporalObservation(
        stream_id="stream-1",
        continuity_id="continuity-1",
        sequence=0,
        source_time=SourceTime("FRAME_INDEX", 0, 1, 1, 0),
        producer=producer(),
        capability=capability(),
        snapshot=a_body,
        state_digest=temporal_state_digest(a_body),
    )
    b = TemporalObservation(
        stream_id="stream-1",
        continuity_id="continuity-1",
        sequence=1,
        source_time=SourceTime("FRAME_INDEX", 1, 1, 1, 0),
        producer=producer(),
        capability=capability(),
        snapshot=b_body,
        state_digest=temporal_state_digest(b_body),
    )

    stream = ObservationStream("stream-1")
    stream.step(a)
    result = stream.step(b, a)

    changes = [
        change
        for entity in result.record["entity_deltas"]
        for change in entity["field_changes"]
        if change["field"] == field
    ]
    assert len(changes) == 1


def test_name_change_is_raw_digest_change_without_semantic_field_change():
    a_body = snapshot()
    b_body = copy.deepcopy(a_body)
    b_body["objects"][0]["name"] = "different-name"

    a = TemporalObservation(
        stream_id="stream-1",
        continuity_id="continuity-1",
        sequence=0,
        source_time=SourceTime("FRAME_INDEX", 0, 1, 1, 0),
        producer=producer(),
        capability=capability(),
        snapshot=a_body,
        state_digest=temporal_state_digest(a_body),
    )
    b = TemporalObservation(
        stream_id="stream-1",
        continuity_id="continuity-1",
        sequence=1,
        source_time=SourceTime("FRAME_INDEX", 1, 1, 1, 0),
        producer=producer(),
        capability=capability(),
        snapshot=b_body,
        state_digest=temporal_state_digest(b_body),
    )

    stream = ObservationStream("stream-1")
    stream.step(a)
    result = stream.step(b, a)

    assert result.record["state_digest_changed"] is True
    assert all(
        change["field"] != "name"
        for entity in result.record["entity_deltas"]
        for change in entity["field_changes"]
    )
    assert all(entity["kind"] == "NO_CHANGE" for entity in result.record["entity_deltas"])


def test_unobservable_fields_are_unsupported_in_coverage():
    stream = ObservationStream("stream-1")
    a = observation(0)
    b = observation(1, location=(1.0, 0.0, 0.0))

    stream.step(a)
    result = stream.step(b, a)

    for field in UNOBSERVABLE_FIELDS:
        assert result.record["coverage"][field] == "UNSUPPORTED_BY_PRODUCER"


def test_sequence_gap_is_independent_from_source_time_gap():
    stream = ObservationStream("stream-1")
    a = observation(0, source_value=0)
    b = observation(3, source_value=0, location=(1.0, 0.0, 0.0))
    stream.step(a)
    result = stream.step(b, a)

    assert result.record["observations_skipped"] == 2
    assert result.record["source_time_hold"] is True

    stream2 = ObservationStream("stream-1")
    x = observation(0, source_value=0)
    y = observation(1, source_value=10, location=(1.0, 0.0, 0.0))
    stream2.step(x)
    result2 = stream2.step(y, x)

    assert result2.record["observations_skipped"] == 0
    assert result2.record["source_time_hold"] is False


def test_envelope_digest_changes_with_capture_time_but_state_digest_does_not():
    a = observation(0)
    b = replace(a, capture_time=1234)

    assert a.state_digest == b.state_digest
    assert a.admission_identity_digest == b.admission_identity_digest
    assert a.envelope_digest != b.envelope_digest
