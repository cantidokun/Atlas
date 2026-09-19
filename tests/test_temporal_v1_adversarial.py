"""Adversarial deterministic coverage for Atlas Temporal v1 Revision 9."""
import copy

from dataclasses import replace

import pytest

from planning.temporal import (
    AdmissionCheckpoint,
    AdmissionOutcome,
    BoundaryInput,
    BoundaryRefusalInput,
    COMPARISON_CONTRACT_VERSION,
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


def test_evaluation_input_union_carries_and_enforces_v1_contract_version():
    stream = ObservationStream("stream-1")
    a = observation(0)
    stream.step(a)
    from_identity = stream.state.from_identity()
    assert from_identity is not None

    b_same = observation(1, location=(1.0, 0.0, 0.0))
    b_boundary = observation(0, continuity_id="continuity-2", ordering_epoch=1)

    inputs = (
        ComparisonInput(a, b_same, from_identity),
        RefusalInput(b_same, from_identity, DeltaReasonCode.PAIR_INPUT_UNAVAILABLE),
        BoundaryInput(a, b_boundary, from_identity),
        BoundaryRefusalInput(
            b_boundary,
            from_identity,
            DeltaReasonCode.PAIR_INPUT_UNAVAILABLE,
        ),
    )

    for evaluation_input in inputs:
        assert evaluation_input.comparison_contract_version == COMPARISON_CONTRACT_VERSION
        record = finalize_record(evaluate(evaluation_input), "UNEMITTED_EPOCH_ANCHOR")
        assert isinstance(record["delta_digest"], str)

    with pytest.raises(ValueError, match="unsupported comparison contract version"):
        evaluate(replace(inputs[0], comparison_contract_version=99))


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



def test_python_hash_seed_does_not_change_temporal_delta_digest():
    import os
    import subprocess
    import sys

    code = r'''
from planning.temporal import (
    CapabilityContract,
    ObservationStream,
    ProducerProvenance,
    SourceTime,
    TemporalObservation,
    temporal_state_digest,
)

fields = (
    "collection", "faces", "location", "materials", "mesh_id",
    "mesh_presence", "parent_object_id", "rotation", "scale",
    "scene_id", "unit_system", "vertices", "visible",
)
unobservable = ("coordinate_frame", "local_frame_id", "normals", "uvs")

def snap(x):
    return {
        "scene_id": "scene-a",
        "unit_system": "METERS",
        "objects": [{
            "object_id": "obj-1",
            "name": "obj-1",
            "collection": "Collection",
            "parent_object_id": None,
            "location": [x, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
            "rotation": [1.0, 0.0, 0.0, 0.0],
            "visible": True,
            "mesh": {
                "mesh_id": "mesh-1",
                "vertices": [[0.0,0.0,0.0],[1.0,0.0,0.0],[0.0,1.0,0.0]],
                "faces": [[0,1,2]],
                "materials": ["mat"],
            },
        }],
        "coordinate_frame": None,
        "world_bounds": None,
    }

def obs(x, seq):
    body = snap(x)
    return TemporalObservation(
        stream_id="hash-seed-stream",
        continuity_id="continuity-1",
        sequence=seq,
        source_time=SourceTime("FRAME_INDEX", seq, 1, 1, 0),
        producer=ProducerProvenance(
            producer_source="BLENDER",
            producer_contract="extraction_fidelity_v1",
            engine_version="4.4.3",
            engine_build="test",
            producer_session_id="session-1",
            producer_instance_ordinal=1,
        ),
        capability=CapabilityContract(
            contract_id="test-v1",
            observable_fields=tuple(sorted(fields)),
            unobservable_fields=tuple(sorted(unobservable)),
            representation_state=(),
        ),
        snapshot=body,
        state_digest=temporal_state_digest(body),
    )

stream = ObservationStream("hash-seed-stream")
a = obs(0.0, 0)
b = obs(1.0, 1)
stream.step(a)
print(stream.step(b, a).record["delta_digest"])
'''
    values = []
    for seed in ("1", "777", "random"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        values.append(proc.stdout.strip().splitlines()[-1])
    assert len(set(values)) == 1


def test_admission_counter_mutation_matrix():
    stream = ObservationStream("stream-1")
    a = observation(5)
    stream.step(a)

    duplicate = replace(a, capture_time=999)
    duplicate_result = stream.step(duplicate)
    assert duplicate_result.admission.outcome is AdmissionOutcome.DUPLICATE_ACKNOWLEDGED
    assert stream.state.accepted_count == 1
    assert stream.state.duplicate_acknowledged_count == 1
    assert stream.state.rejected_stale_count == 0
    assert stream.state.invalid_count == 0
    assert stream.state.epoch_count == 1

    stale = observation(4)
    stale_result = stream.step(stale)
    assert stale_result.admission.outcome is AdmissionOutcome.REJECTED_STALE
    assert stream.state.accepted_count == 1
    assert stream.state.duplicate_acknowledged_count == 1
    assert stream.state.rejected_stale_count == 1
    assert stream.state.invalid_count == 0
    assert stream.state.epoch_count == 1

    invalid = observation(6, scene_id="scene-b")
    invalid_result = stream.step(invalid)
    assert invalid_result.admission.outcome is AdmissionOutcome.REJECTED_INVALID
    assert stream.state.accepted_count == 1
    assert stream.state.duplicate_acknowledged_count == 1
    assert stream.state.rejected_stale_count == 1
    assert stream.state.invalid_count == 1
    assert stream.state.epoch_count == 1

    accepted = observation(6)
    accepted_result = stream.step(accepted)
    assert accepted_result.admission.outcome is AdmissionOutcome.ACCEPTED
    assert stream.state.accepted_count == 2
    assert stream.state.duplicate_acknowledged_count == 1
    assert stream.state.rejected_stale_count == 1
    assert stream.state.invalid_count == 1
    assert stream.state.epoch_count == 1

    boundary = observation(
        0,
        continuity_id="continuity-2",
        ordering_epoch=1,
        session="session-2",
    )
    boundary_result = stream.step(boundary)
    assert boundary_result.admission.outcome is AdmissionOutcome.NEW_EPOCH
    assert stream.state.accepted_count == 3
    assert stream.state.duplicate_acknowledged_count == 1
    assert stream.state.rejected_stale_count == 1
    assert stream.state.invalid_count == 1
    assert stream.state.epoch_count == 2


def test_duplicate_id_digest_is_order_independent_and_content_sensitive():
    base = snapshot()
    second = copy.deepcopy(base["objects"][0])
    second["location"] = [5.0, 0.0, 0.0]
    base["objects"].append(second)

    reversed_body = copy.deepcopy(base)
    reversed_body["objects"].reverse()

    assert temporal_state_digest(base) == temporal_state_digest(reversed_body)

    changed = copy.deepcopy(base)
    changed["objects"][1]["location"] = [6.0, 0.0, 0.0]
    assert temporal_state_digest(base) != temporal_state_digest(changed)


def test_entity_delta_and_field_change_order_is_canonical():
    a_body = snapshot()
    b_body = copy.deepcopy(a_body)
    obj = b_body["objects"][0]
    obj["visible"] = False
    obj["location"] = [1.0, 2.0, 3.0]
    obj["scale"] = [2.0, 2.0, 2.0]
    obj["collection"] = "Changed"
    obj["parent_object_id"] = "parent-1"

    a = observation(0)
    a = replace(a, snapshot=a_body, state_digest=temporal_state_digest(a_body))
    b = replace(
        observation(1),
        snapshot=b_body,
        state_digest=temporal_state_digest(b_body),
    )

    stream = ObservationStream("stream-1")
    stream.step(a)
    result = stream.step(b, a)
    changes = result.record["entity_deltas"][0]["field_changes"]

    assert [item["field"] for item in changes] == [
        "collection",
        "parent_object_id",
        "location",
        "scale",
        "visible",
    ]


def test_new_epoch_missing_a_preserves_boundary_causes_and_refusal_reason():
    stream = ObservationStream("stream-1")
    a = observation(0, session="session-1", ordering_epoch=0, continuity_id="continuity-1")
    b = observation(
        0,
        session="session-2",
        ordering_epoch=1,
        continuity_id="continuity-2",
        contract_id="other-contract",
    )

    stream.step(a)
    result = stream.step(b)

    assert result.admission.outcome is AdmissionOutcome.NEW_EPOCH
    assert result.record["outcome"] == "OBSERVATION_INVALID"
    assert result.record["pair_input"] == "UNAVAILABLE"
    assert result.record["entity_deltas"] == []
    assert result.record["observations_skipped"] == 0
    assert result.record["source_time_hold"] is False
    assert "PAIR_INPUT_UNAVAILABLE" in result.record["reason_codes"]
    assert result.record["reason_codes"] == sorted([
        "PAIR_INPUT_UNAVAILABLE",
        "RESTART_PRODUCER_SESSION",
        "ORDERING_EPOCH_CHANGE",
        "TEMPORAL_DISCONTINUITY_CONTINUITY_ID_CHANGE",
    ])
    assert stream.state.last_accepted_observation_id == b.observation_id


def test_same_epoch_missing_a_emits_closed_refusal_schema():
    stream = ObservationStream("stream-1")
    a = observation(0)
    b = observation(1, location=(1.0, 0.0, 0.0))
    stream.step(a)

    result = stream.step(b)

    assert result.admission.outcome is AdmissionOutcome.ACCEPTED
    record = result.record
    assert record is not None
    assert record["outcome"] == DeltaOutcome.OBSERVATION_INVALID.value
    assert record["pair_input"] == "UNAVAILABLE"
    assert record["continuity"] == "SAME_EPOCH"
    assert record["from_observation_id"] == a.observation_id
    assert record["from_state_digest"] == a.state_digest
    assert record["to_observation_id"] == b.observation_id
    assert record["to_state_digest"] == b.state_digest
    assert record["entity_deltas"] == []
    assert record["observations_skipped"] == 0
    assert record["source_time_hold"] is False
    assert "PAIR_INPUT_UNAVAILABLE" in record["reason_codes"]
    assert not any("field_changes" in entity for entity in record["entity_deltas"])


def test_refusal_projection_metadata_never_fabricates_content():
    a = observation(0)
    b = observation(1, location=(1.0, 0.0, 0.0))
    stream = ObservationStream("stream-1")
    stream.step(a)
    baseline = stream.state.from_identity()
    assert baseline is not None

    baseline_record = finalize_record(
        evaluate(
            RefusalInput(
                b=b,
                from_identity=baseline,
                reason=DeltaReasonCode.PAIR_INPUT_UNAVAILABLE,
            )
        ),
        "UNEMITTED_EPOCH_ANCHOR",
    )

    projections = (
        replace(baseline, last_accepted_observation_id="obs:wrong"),
        replace(baseline, last_accepted_state_digest="0" * 64),
        replace(
            baseline,
            last_accepted_observation_id="obs:wrong",
            last_accepted_state_digest="0" * 64,
        ),
    )

    for projection in projections:
        record = finalize_record(
            evaluate(
                RefusalInput(
                    b=b,
                    from_identity=projection,
                    reason=DeltaReasonCode.PAIR_INPUT_UNAVAILABLE,
                )
            ),
            "UNEMITTED_EPOCH_ANCHOR",
        )
        assert record["outcome"] == DeltaOutcome.OBSERVATION_INVALID.value
        assert record["pair_input"] == "UNAVAILABLE"
        assert record["entity_deltas"] == []
        assert record["from_observation_id"] == projection.last_accepted_observation_id
        assert record["from_state_digest"] == projection.last_accepted_state_digest
        assert record["to_observation_id"] == b.observation_id
        assert record["to_state_digest"] == b.state_digest
        assert record["state_digest_changed"] == (
            projection.last_accepted_state_digest != b.state_digest
        )
        assert record["coverage"]["location"] == "INVALID_OBSERVATION"
        assert "PAIR_INPUT_UNAVAILABLE" in record["reason_codes"]
        assert record["reason_codes"] == ["PAIR_INPUT_UNAVAILABLE"]

    assert baseline_record["entity_deltas"] == []


def test_refusal_and_boundary_input_determinism_is_byte_stable():
    a = observation(0)
    b = observation(1, location=(1.0, 0.0, 0.0))
    boundary_b = observation(0, continuity_id="continuity-2", ordering_epoch=1)
    stream = ObservationStream("stream-1")
    stream.step(a)
    from_identity = stream.state.from_identity()
    assert from_identity is not None

    refusal_input = RefusalInput(
        b=b,
        from_identity=from_identity,
        reason=DeltaReasonCode.PAIR_INPUT_UNAVAILABLE,
    )
    boundary_input = BoundaryInput(
        a=a,
        b=boundary_b,
        from_identity=from_identity,
    )

    refusal_one = finalize_record(
        evaluate(refusal_input),
        "UNEMITTED_EPOCH_ANCHOR",
    )
    refusal_two = finalize_record(
        evaluate(replace(refusal_input)),
        "UNEMITTED_EPOCH_ANCHOR",
    )
    boundary_one = finalize_record(
        evaluate(boundary_input),
        "UNEMITTED_EPOCH_ANCHOR",
    )
    boundary_two = finalize_record(
        evaluate(replace(boundary_input)),
        "UNEMITTED_EPOCH_ANCHOR",
    )

    assert refusal_one == refusal_two
    assert boundary_one == boundary_two


def test_evaluation_input_four_variant_matrix_has_one_record_form_each():
    a = observation(0)
    same_b = observation(1, location=(1.0, 0.0, 0.0))
    boundary_b = observation(0, continuity_id="continuity-2", ordering_epoch=1)
    stream = ObservationStream("stream-1")
    stream.step(a)
    from_identity = stream.state.from_identity()
    assert from_identity is not None

    cases = (
        (
            ComparisonInput(a, same_b, from_identity),
            "AVAILABLE",
            "COMPUTED",
            "SAME_EPOCH",
        ),
        (
            RefusalInput(
                same_b,
                from_identity,
                DeltaReasonCode.PAIR_INPUT_UNAVAILABLE,
            ),
            "UNAVAILABLE",
            "OBSERVATION_INVALID",
            "SAME_EPOCH",
        ),
        (
            BoundaryInput(a, boundary_b, from_identity),
            "AVAILABLE",
            "TEMPORAL_DISCONTINUITY",
            "NEW_EPOCH",
        ),
        (
            BoundaryRefusalInput(
                boundary_b,
                from_identity,
                DeltaReasonCode.PAIR_INPUT_UNAVAILABLE,
            ),
            "UNAVAILABLE",
            "OBSERVATION_INVALID",
            "NEW_EPOCH",
        ),
    )

    seen = set()
    for evaluation_input, pair_input, outcome, continuity in cases:
        record = finalize_record(
            evaluate(evaluation_input),
            "UNEMITTED_EPOCH_ANCHOR",
        )
        key = (
            type(evaluation_input).__name__,
            record["pair_input"],
            record["outcome"],
            record["continuity"],
        )
        seen.add(key)
        assert record["pair_input"] == pair_input
        assert record["outcome"] == outcome
        assert record["continuity"] == continuity
    assert len(seen) == 4


def test_refusal_variants_cannot_emit_computed_or_no_change_entities():
    a = observation(0)
    b = observation(1, location=(1.0, 0.0, 0.0))
    stream = ObservationStream("stream-1")
    stream.step(a)
    from_identity = stream.state.from_identity()
    assert from_identity is not None

    for evaluation_input in (
        RefusalInput(b, from_identity, DeltaReasonCode.PAIR_INPUT_UNAVAILABLE),
        BoundaryRefusalInput(
            observation(0, continuity_id="continuity-2", ordering_epoch=1),
            from_identity,
            DeltaReasonCode.PAIR_INPUT_UNAVAILABLE,
        ),
    ):
        record = finalize_record(
            evaluate(evaluation_input),
            "UNEMITTED_EPOCH_ANCHOR",
        )
        assert record["outcome"] == DeltaOutcome.OBSERVATION_INVALID.value
        assert record["entity_deltas"] == []
        assert not any(
            entity.get("kind") == "NO_CHANGE"
            for entity in record["entity_deltas"]
        )



def test_new_epoch_boundary_becomes_emitted_predecessor_for_next_edge():
    stream = ObservationStream("stream-1")
    a = observation(0)
    b = observation(0, continuity_id="continuity-2", ordering_epoch=1, session="session-2")
    c = observation(1, continuity_id="continuity-2", ordering_epoch=1, session="session-2", location=(2.0, 0.0, 0.0))

    stream.step(a)
    boundary = stream.step(b, a)
    assert boundary.admission.outcome is AdmissionOutcome.NEW_EPOCH
    assert boundary.record["from_observation_origin"] == "UNEMITTED_EPOCH_ANCHOR"

    next_edge = stream.step(c, b)
    assert next_edge.admission.outcome is AdmissionOutcome.ACCEPTED
    assert next_edge.record["from_observation_id"] == b.observation_id
    assert next_edge.record["from_observation_origin"] == "EMITTED_PREDECESSOR"

def test_reinitialize_anchor_remains_unemitted_after_non_record_admissions():
    stream = ObservationStream("stream-1")
    a = observation(0)
    stream.step(a)
    stream.reinitialize(
        new_continuity_id="continuity-2",
        new_ordering_epoch=1,
    )

    b = observation(0, continuity_id="continuity-2", ordering_epoch=1)
    duplicate = replace(b, capture_time=777)
    c = observation(
        1,
        continuity_id="continuity-2",
        ordering_epoch=1,
        location=(1.0, 0.0, 0.0),
    )

    first = stream.step(b)
    assert first.admission.outcome is AdmissionOutcome.INITIAL_ACCEPTED
    assert first.record is None

    duplicate_result = stream.step(duplicate)
    assert duplicate_result.admission.outcome is AdmissionOutcome.DUPLICATE_ACKNOWLEDGED
    assert duplicate_result.record is None

    result = stream.step(c, b)
    assert result.admission.outcome is AdmissionOutcome.ACCEPTED
    assert result.record["from_observation_id"] == b.observation_id
    assert result.record["from_observation_origin"] == "UNEMITTED_EPOCH_ANCHOR"
# --------------------------------------------------------------------------- mesh-presence coverage
# Rev9 10.1 compares the mesh fields "when both sides have a mesh". When one side has none, that
# observation did not carry mesh_id/vertices/faces/materials, which 10.2 defines as UNAVAILABLE. Before
# the correction those four fields were reported OBSERVED_UNCHANGED although the evaluator had
# deliberately skipped comparing them - a 10.2 "never report an unobserved field as observed" violation.
# No new coverage state is introduced: UNAVAILABLE already exists and already means "this observation
# did not carry the field".

_MESH_FIELDS = ("mesh_id", "vertices", "faces", "materials")


def _pair_record(a_body, b_body):
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
    return stream.step(b, a).record


def _two_object_snapshot():
    body = snapshot()
    second = copy.deepcopy(body["objects"][0])
    second["object_id"] = "obj-2"
    second["name"] = "obj-2"
    second["mesh"]["mesh_id"] = "obj-2"
    second["location"] = [3.0, 0.0, 0.0]
    body["objects"].append(second)
    return body


def test_mesh_presence_loss_reports_the_mesh_fields_unavailable():
    a_body = snapshot()
    b_body = copy.deepcopy(a_body)
    b_body["objects"][0]["mesh"] = None

    record = _pair_record(a_body, b_body)

    assert record["outcome"] == "COMPUTED"
    assert record["state_digest_changed"] is True
    assert record["coverage"]["mesh_presence"] == "OBSERVED_CHANGED"
    for field in _MESH_FIELDS:
        assert record["coverage"][field] == "UNAVAILABLE", (
            f"{field} was not compared and must not be reported as observed"
        )
    assert [
        change["field"]
        for entity in record["entity_deltas"]
        for change in entity["field_changes"]
    ] == ["mesh_presence"]


def test_mesh_appearance_reports_the_mesh_fields_unavailable():
    b_body = snapshot()
    a_body = copy.deepcopy(b_body)
    a_body["objects"][0]["mesh"] = None

    record = _pair_record(a_body, b_body)

    assert record["outcome"] == "COMPUTED"
    assert record["coverage"]["mesh_presence"] == "OBSERVED_CHANGED"
    for field in _MESH_FIELDS:
        assert record["coverage"][field] == "UNAVAILABLE"
    assert [
        change["field"]
        for entity in record["entity_deltas"]
        for change in entity["field_changes"]
    ] == ["mesh_presence"]


def test_both_meshes_present_still_reports_observed_states():
    """Falsification control: the correction must not spread UNAVAILABLE over comparable pairs."""
    a_body = snapshot()
    b_body = copy.deepcopy(a_body)
    b_body["objects"][0]["mesh"]["vertices"] = [
        [0.0, 0.0, 0.0],
        [2.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ]

    record = _pair_record(a_body, b_body)

    assert record["coverage"]["vertices"] == "OBSERVED_CHANGED"
    for field in ("mesh_id", "faces", "materials"):
        assert record["coverage"][field] == "OBSERVED_UNCHANGED"
    assert record["coverage"]["mesh_presence"] == "OBSERVED_UNCHANGED"


def test_one_mesh_less_entity_makes_the_field_unavailable_without_losing_a_real_change():
    """Coverage is per record, so one uncomparable entity is reported conservatively - and no change
    belonging to a comparable entity is lost."""
    a_body = _two_object_snapshot()
    b_body = copy.deepcopy(a_body)
    b_body["objects"][0]["location"] = [1.0, 0.0, 0.0]   # obj-1: fully comparable, real change
    b_body["objects"][1]["mesh"] = None                  # obj-2: no mesh on the B side

    record = _pair_record(a_body, b_body)

    assert record["coverage"]["vertices"] == "UNAVAILABLE"
    assert record["coverage"]["mesh_id"] == "UNAVAILABLE"
    assert record["coverage"]["location"] == "OBSERVED_CHANGED"
    changes = {
        (entity["object_id"], change["field"])
        for entity in record["entity_deltas"]
        for change in entity["field_changes"]
    }
    assert ("obj-1", "location") in changes
    assert ("obj-2", "mesh_presence") in changes


# --------------------------------------------------------------------------- contract closure
# Coverage is intentionally record-scoped in the emitted schema: it summarizes which fields were
# comparable across the pair. Entity deltas remain entity-scoped and retain the concrete changes.
# This distinction prevents a single uncomparable entity from fabricating a field change while also
# preserving real changes on other entities.


def test_temporal_v1_canonical_golden_vector_is_cross_language_pinnable():
    value = {"a": [1, True], "b": None}
    expected_bytes_hex = (
        "060000000000000002"
        "01000000000000000161050000000000000002"
        "0300000000000000010201"
        "0100000000000000016200"
    )
    expected_digest = "1edddc1f3d2ca55bca2da5333a453ebd628d0047bc603a35b18217f90127cb4e"
    from planning.temporal.canonical import temporal_canonical_bytes

    assert temporal_canonical_bytes(value).hex() == expected_bytes_hex
    assert sha256_digest(value) == expected_digest


def test_temporal_v1_emitted_record_golden_digest_is_pinnable():
    draft = {
        "delta_schema_version": 1,
        "outcome": "COMPUTED",
        "pair_input": "AVAILABLE",
        "stream_id": "stream-1",
        "from_observation_id": "obs:0000000000000001",
        "to_observation_id": "obs:0000000000000002",
        "from_state_digest": "0" * 64,
        "to_state_digest": "1" * 64,
        "state_digest_changed": True,
        "continuity": "SAME_EPOCH",
        "observations_skipped": 0,
        "source_time_hold": False,
        "identity_ambiguous_ids": [],
        "entity_deltas": [],
        "coverage": {
            "location": "OBSERVED_CHANGED",
            "materials": "UNAVAILABLE",
        },
        "reason_codes": [],
    }
    record = finalize_record(draft, "EMITTED_PREDECESSOR")
    assert record["delta_digest"] == "a0d8b0835a46c02d5ece046ef785d67c408a3ceeffbf203b15a0f1d93df3602d"


def test_unknown_representation_state_fails_closed():
    with pytest.raises(Exception, match="unknown values"):
        capability(representation_state=("materials:future-unknown",))


def test_mesh_coverage_scope_is_explicitly_record_wide_but_deltas_remain_entity_scoped():
    before = observation(0)
    after = observation(1)
    body = copy.deepcopy(after.snapshot)
    body["objects"][0]["mesh"] = None
    after = TemporalObservation(
        stream_id=after.stream_id,
        continuity_id=after.continuity_id,
        sequence=after.sequence,
        source_time=after.source_time,
        producer=after.producer,
        capability=after.capability,
        snapshot=body,
        state_digest=temporal_state_digest(body),
    )

    stream = ObservationStream("stream-1")
    stream.step(before)
    result = stream.step(after, before)

    assert result.record["coverage"]["mesh_presence"] == "OBSERVED_CHANGED"
    assert result.record["coverage"]["mesh_id"] == "UNAVAILABLE"
    assert result.record["coverage"]["vertices"] == "UNAVAILABLE"
    assert result.record["coverage"]["faces"] == "UNAVAILABLE"
    assert result.record["coverage"]["materials"] == "UNAVAILABLE"
    assert [
        (entity["object_id"], change["field"])
        for entity in result.record["entity_deltas"]
        for change in entity["field_changes"]
    ] == [("obj-1", "mesh_presence")]
