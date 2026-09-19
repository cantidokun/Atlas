"""Stage-1 ingress classification coverage for Temporal v1 Rev9."""

import json

import pytest

from planning.temporal import ArrivalValidationError, parse_temporal_observation, parse_temporal_observation_json
from planning.temporal.admission import AdmissionReasonCode
from planning.temporal.canonical import CanonicalValueError


def _snapshot():
    return {
        "scene_id": "scene-a",
        "unit_system": "METERS",
        "objects": [
            {
                "object_id": "obj-1",
                "name": "obj-1",
                "collection": "Collection",
                "parent_object_id": None,
                "location": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
                "rotation": [1.0, 0.0, 0.0, 0.0],
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


def _envelope():
    return {
        "observation_schema_version": "1",
        "stream_id": "stream-1",
        "continuity_id": "continuity-1",
        "sequence": 0,
        "source_time": {
            "domain": "FRAME_INDEX",
            "value": 0,
            "rate": {"num": 1, "den": 1},
            "ordering_epoch": 0,
        },
        "producer": {
            "producer_source": "BLENDER",
            "producer_contract": "extraction_fidelity_v1",
            "engine_version": "4.4.3",
            "engine_build": "802179c51ccc",
            "producer_session_id": "session-1",
            "producer_instance_ordinal": 1,
        },
        "capability": {
            "contract_id": "test-v1",
            "observable_fields": ["collection","coordinate_frame","faces","local_frame_id","location","materials","mesh_id","mesh_presence","normals","parent_object_id","rotation","scale","scene_id","unit_system","uvs","vertices","visible"],
            "unobservable_fields": [],
            "representation_state": [],
        },
        "snapshot": _snapshot(),
        "state_digest": "not-the-right-digest",
    }


def _assert_invalid(value, expected_message_fragment):
    with pytest.raises(ArrivalValidationError) as exc_info:
        parse_temporal_observation(value)
    assert exc_info.value.reason_code is AdmissionReasonCode.INVALID_CANONICAL_VALUE_DOMAIN
    assert expected_message_fragment in str(exc_info.value)


def test_invalid_canonical_value_domain_is_normative_reason_code():
    assert AdmissionReasonCode.INVALID_CANONICAL_VALUE_DOMAIN.value == "INVALID_CANONICAL_VALUE_DOMAIN"


def test_nonfinite_snapshot_value_is_rejected_at_stage_one():
    value = _envelope()
    value["snapshot"]["objects"][0]["location"][0] = float("nan")
    _assert_invalid(value, "must be finite")


def test_int64_overflow_snapshot_value_is_rejected_at_stage_one():
    value = _envelope()
    value["snapshot"]["objects"][0]["mesh"]["faces"][0][0] = 1 << 63
    _assert_invalid(value, "signed-64")


def test_surrogate_snapshot_string_is_rejected_at_stage_one():
    value = _envelope()
    value["snapshot"]["objects"][0]["object_id"] = "\ud800"
    _assert_invalid(value, "Unicode surrogate")


def test_duplicate_json_key_is_rejected_as_structured_arrival_error():
    value = _envelope()
    text = json.dumps(value, separators=(",", ":"))
    marker = '"stream_id":"stream-1"'
    text = text.replace(marker, marker + ',"stream_id":"stream-duplicate"', 1)

    with pytest.raises(ArrivalValidationError) as exc_info:
        parse_temporal_observation_json(text)

    assert exc_info.value.reason_code is AdmissionReasonCode.INVALID_CANONICAL_VALUE_DOMAIN
    assert str(exc_info.value) == "duplicate key 'stream_id'"


def test_canonical_parser_error_is_preserved_verbatim():
    value = _envelope()
    value["snapshot"]["objects"][0]["mesh"]["faces"][0][0] = 1 << 63

    from planning.temporal.canonical import temporal_canonical_bytes

    try:
        temporal_canonical_bytes(value["snapshot"])
    except CanonicalValueError as expected:
        parser_message = str(expected)
    else:
        pytest.fail("expected canonical parser failure")

    with pytest.raises(ArrivalValidationError) as exc_info:
        parse_temporal_observation(value)

    assert exc_info.value.reason_code is AdmissionReasonCode.INVALID_CANONICAL_VALUE_DOMAIN
    assert str(exc_info.value) == "$['mesh']['faces'][0][0] is outside signed-64 range"
    assert parser_message == "$['objects'][0]['mesh']['faces'][0][0] is outside signed-64 range"
