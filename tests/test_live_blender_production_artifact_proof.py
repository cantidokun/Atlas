from __future__ import annotations

import pytest

from live_blender_production_artifact_proof import observed_location


class _Result:
    def __init__(self, details):
        self.details = details


def test_observed_location_extracts_requested_object_from_fresh_scene_evidence():
    result = _Result(
        {
            "objects": [
                {"name": "Other", "location": [1.0, 2.0, 3.0]},
                {"name": "Atlas_Marker", "location": [0.5, 5.233, 0.0]},
            ]
        }
    )

    assert observed_location(result, "Atlas_Marker") == [0.5, 5.233, 0.0]


def test_observed_location_fails_closed_when_object_is_missing():
    result = _Result({"objects": [{"name": "Other", "location": [1.0, 2.0, 3.0]}]})

    with pytest.raises(RuntimeError, match="was not independently observed"):
        observed_location(result, "Atlas_Marker")


def test_observed_location_fails_closed_when_scene_evidence_is_malformed():
    result = _Result({"objects": [{"name": "Atlas_Marker", "location": [0.5, 5.233]}]})

    with pytest.raises(RuntimeError, match="was not independently observed"):
        observed_location(result, "Atlas_Marker")
