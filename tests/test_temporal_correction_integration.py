from __future__ import annotations

import sys
from types import SimpleNamespace

from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel
from planning.blender.temporal_correction_integration import TemporalCorrectionSession
from planning.temporal import AdmissionOutcome


class _Report:
    def __init__(self, digest: str):
        self._digest = digest

    def digest(self) -> str:
        return self._digest


def _scene(*, x: float = 0.0) -> SceneModel:
    return SceneModel(
        scene_id="scene-temporal-test",
        unit_system="METERS",
        objects=(
            ObjectModel(
                object_id="probe",
                name="probe",
                collection="AtlasTemporal",
                location=(x, 0.0, 0.0),
                mesh=MeshModel(
                    mesh_id="mesh-probe",
                    vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
                    faces=((0, 1, 2),),
                ),
            ),
        ),
    )


def _install_fake_bpy(monkeypatch, frame_current: int = 12) -> None:
    fake = SimpleNamespace(
        context=SimpleNamespace(scene=SimpleNamespace(frame_current=frame_current)),
        app=SimpleNamespace(version_string="4.4.3", build_hash="test-build"),
    )
    monkeypatch.setitem(sys.modules, "bpy", fake)


def test_temporal_session_admits_a_before_mutation_and_b_after(monkeypatch):
    _install_fake_bpy(monkeypatch)

    session = TemporalCorrectionSession()
    events = []

    def extractor(_engine_state):
        return _scene(x=0.0), _Report("report-a")

    wrapped = session.wrap(extractor)
    wrapped(None)

    assert session.observation_a is not None
    assert session.admission_a["outcome"] == AdmissionOutcome.INITIAL_ACCEPTED.value
    events.append("a_admitted")

    events.append("mutate")

    def extractor_after(_engine_state):
        return _scene(x=1.0), _Report("report-b")

    wrapped_after = session.wrap(extractor_after)
    # A new wrapper starts its ordinal at one, so use the same session's capture
    # seam directly for the second executor extraction.
    session.capture(scene=_scene(x=1.0), report=_Report("report-b"), ordinal=2)
    events.append("b_admitted")

    assert events == ["a_admitted", "mutate", "b_admitted"]
    assert session.admission_b["outcome"] == AdmissionOutcome.ACCEPTED.value
    assert session.observation_a.producer.producer_session_id == session.observation_b.producer.producer_session_id
    assert session.observation_a.continuity_id == session.observation_b.continuity_id
    assert session.observation_a.ordering_epoch == session.observation_b.ordering_epoch
    assert session.observation_a.sequence == 0
    assert session.observation_b.sequence == 1
    assert session.observation_a.source_time.domain == "FRAME_INDEX"
    assert session.observation_a.source_time.rate_num == 1
    assert session.observation_a.source_time.rate_den == 1
    assert session.observation_a.source_time.value == session.observation_b.source_time.value
    assert session.delta_record["state_digest_changed"] is True


def test_unchanged_canonical_state_is_accepted_not_duplicate(monkeypatch):
    _install_fake_bpy(monkeypatch)

    session = TemporalCorrectionSession()
    session.capture(scene=_scene(x=0.0), report=_Report("report-a"), ordinal=1)
    session.capture(scene=_scene(x=0.0), report=_Report("report-b"), ordinal=2)

    assert session.admission_a["outcome"] == AdmissionOutcome.INITIAL_ACCEPTED.value
    assert session.admission_b["outcome"] == AdmissionOutcome.ACCEPTED.value
    assert session.observation_a.sequence == 0
    assert session.observation_b.sequence == 1
    assert session.observation_a.state_digest == session.observation_b.state_digest
    assert session.delta_record["state_digest_changed"] is False
    assert session.delta_record["entity_deltas"] == []


def test_b_is_independent_of_receipt_content(monkeypatch):
    _install_fake_bpy(monkeypatch)

    session = TemporalCorrectionSession()
    session.capture(scene=_scene(x=0.0), report=_Report("report-a"), ordinal=1)
    session.capture(scene=_scene(x=2.0), report=_Report("report-b"), ordinal=2)

    payload_before = session.result_payload()["temporal_transaction"]["post_snapshot"]
    fake_receipt = {
        "result": "COMPLETED",
        "output_report_digest": "fabricated-receipt-digest",
        "target": {"location": [999.0, 999.0, 999.0]},
    }

    # Receipt data is intentionally not an input to the session capture path.
    payload_after = session.result_payload()["temporal_transaction"]["post_snapshot"]
    assert payload_after == payload_before
    assert payload_after["objects"][0]["location"] == [2.0, 0.0, 0.0]
    assert fake_receipt["target"]["location"] != payload_after["objects"][0]["location"]
