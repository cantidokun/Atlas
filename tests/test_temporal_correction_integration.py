from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel
from planning.blender.temporal_correction_integration import mark_post_extraction_ambiguity
from planning.blender.temporal_correction_integration import TemporalCorrectionSession
from planning.temporal import AdmissionOutcome
from planning.temporal.model import TEMPORAL_FIELD_UNIVERSE
from planning.temporal.stream import ObservationStream


class _Report:
    def __init__(self, digest: str):
        self._digest = digest

    def digest(self) -> str:
        return self._digest


def _scene(*, x: float = 0.0, materials=()) -> SceneModel:
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
                    materials=materials,
                ),
            ),
        ),
    )


def _install_fake_bpy(monkeypatch, frame_current=12) -> None:
    fake = SimpleNamespace(
        context=SimpleNamespace(scene=SimpleNamespace(frame_current=frame_current)),
        app=SimpleNamespace(version_string="4.4.3", build_hash="test-build"),
    )
    monkeypatch.setitem(sys.modules, "bpy", fake)


def _session(monkeypatch, *, frame_current=12, representation_state=()):
    _install_fake_bpy(monkeypatch, frame_current)
    session = TemporalCorrectionSession()

    def extractor(_engine_state):
        return _scene(x=0.0), _Report("report-a")

    extractor.temporal_representation_state = representation_state
    wrapped = session.wrap(extractor)
    wrapped(None)
    return session


def test_a_is_admitted_before_mutation_and_b_after(monkeypatch):
    session = _session(monkeypatch)
    assert session.observation_a is not None
    assert session.admission_a["outcome"] == AdmissionOutcome.INITIAL_ACCEPTED.value

    session.capture(scene=_scene(x=1.0), report=_Report("report-b"), ordinal=2)

    assert session.admission_b["outcome"] == AdmissionOutcome.ACCEPTED.value
    assert session.observation_a.producer.producer_session_id == session.observation_b.producer.producer_session_id
    assert session.observation_a.continuity_id == session.observation_b.continuity_id
    assert session.observation_a.ordering_epoch == session.observation_b.ordering_epoch
    assert session.observation_a.sequence == 0
    assert session.observation_b.sequence == 1


def test_b_uses_frozen_stream_finalization(monkeypatch):
    session = _session(monkeypatch)
    session.capture(scene=_scene(x=1.0), report=_Report("report-b"), ordinal=2)
    record = session.delta_record
    assert record["delta_digest"]
    assert record["from_observation_origin"] == "UNEMITTED_EPOCH_ANCHOR"
    assert set(("delta_digest", "from_observation_origin")).issubset(record)


def test_unchanged_state_is_accepted_not_duplicate(monkeypatch):
    session = _session(monkeypatch)
    session.capture(scene=_scene(x=0.0), report=_Report("report-b"), ordinal=2)
    assert session.admission_b["outcome"] == AdmissionOutcome.ACCEPTED.value
    assert session.observation_a.state_digest == session.observation_b.state_digest
    assert session.delta_record["state_digest_changed"] is False
    assert session.delta_record["entity_deltas"] == [
        {"object_id": "probe", "kind": "NO_CHANGE", "field_changes": []}
    ]


def test_b_snapshot_is_independent_of_receipt_content(monkeypatch):
    session = _session(monkeypatch)
    session.capture(scene=_scene(x=2.0), report=_Report("report-b"), ordinal=2)
    before = session.result_payload()["temporal_transaction"]["post_snapshot"]
    fake_receipt = {"result": "COMPLETED", "target": {"location": [999.0, 999.0, 999.0]}}
    after = session.result_payload()["temporal_transaction"]["post_snapshot"]
    assert after == before
    assert after["objects"][0]["location"] == [2.0, 0.0, 0.0]
    assert fake_receipt["target"]["location"] != after["objects"][0]["location"]


def test_capability_representation_state_is_derived_from_extraction_boundary(monkeypatch):
    session = _session(monkeypatch, representation_state=("materials:omitted",))
    assert session.observation_a.capability.representation_state == ("materials:omitted",)


def test_representation_state_is_not_hardcoded_empty(monkeypatch):
    session = _session(monkeypatch, representation_state=("materials:omitted",))
    session.capture(scene=_scene(x=1.0), report=_Report("report-b"), ordinal=2)
    assert session.observation_b.capability.representation_state == ("materials:omitted",)
    assert session.delta_record["coverage"]["materials"] == "UNAVAILABLE"


def test_full_capability_is_transport_serialized(monkeypatch):
    session = _session(monkeypatch, representation_state=("materials:omitted",))
    payload = session.result_payload()["temporal_transaction"]["observation_a"]
    assert payload["capability"]["contract_id"] == "extraction_fidelity_v1"
    assert set(payload["capability"]["observable_fields"]) | set(payload["capability"]["unobservable_fields"]) == set(TEMPORAL_FIELD_UNIVERSE)
    assert payload["capability"]["representation_state"] == ["materials:omitted"]


def test_observation_identity_digest_can_be_recomputed_from_transport(monkeypatch):
    session = _session(monkeypatch, representation_state=("materials:omitted",))
    payload = session.result_payload()["temporal_transaction"]["observation_a"]
    obs = session.observation_a
    assert payload["admission_identity_digest"] == obs.admission_identity_digest
    assert payload["envelope_digest"] == obs.envelope_digest


def test_post_rejection_does_not_commit_observation_b(monkeypatch):
    session = _session(monkeypatch)
    # A valid same-stream B is accepted; force the rejection seam with a different scene scope.
    with pytest.raises(RuntimeError, match="post-correction Temporal admission failed"):
        session.capture(scene=SceneModel(
            scene_id="different-scene",
            unit_system="METERS",
            objects=(),
        ), report=_Report("report-b"), ordinal=2)
    assert session.observation_b is None


def test_frame_index_requires_exact_integer(monkeypatch):
    _install_fake_bpy(monkeypatch, frame_current=12.5)
    session = TemporalCorrectionSession()
    with pytest.raises(RuntimeError, match="exact int"):
        session.capture(scene=_scene(), report=_Report("report-a"), ordinal=1)


def test_source_time_is_frozen_to_frame_index(monkeypatch):
    session = _session(monkeypatch, frame_current=37)
    session.capture(scene=_scene(x=1.0), report=_Report("report-b"), ordinal=2)
    assert session.observation_a.source_time.domain == "FRAME_INDEX"
    assert session.observation_a.source_time.rate_num == 1
    assert session.observation_a.source_time.rate_den == 1
    assert session.observation_a.source_time.value == 37
    assert session.observation_b.source_time.value == 37


def test_fresh_sessions_mint_distinct_producer_sessions(monkeypatch):
    first = _session(monkeypatch)
    second = _session(monkeypatch)
    assert first.producer_session_id != second.producer_session_id
    assert first.observation_a.producer.producer_session_id != second.observation_a.producer.producer_session_id


def test_engine_provenance_is_frozen_inside_session(monkeypatch):
    session = _session(monkeypatch)
    assert session.observation_a.producer.engine_version == "4.4.3"
    assert session.observation_a.producer.engine_build == "test-build"
    assert session.observation_a.producer.producer_instance_ordinal == 0


def test_sequence_and_epoch_are_monotonic_within_transaction(monkeypatch):
    session = _session(monkeypatch)
    session.capture(scene=_scene(x=1.0), report=_Report("report-b"), ordinal=2)
    assert session.observation_a.sequence < session.observation_b.sequence
    assert session.observation_a.ordering_epoch == session.observation_b.ordering_epoch == 0


def test_state_delta_contains_from_identity_binding(monkeypatch):
    session = _session(monkeypatch)
    session.capture(scene=_scene(x=1.0), report=_Report("report-b"), ordinal=2)
    assert session.delta_record["from_observation_id"] == session.observation_a.observation_id
    assert session.delta_record["to_observation_id"] == session.observation_b.observation_id
    assert session.delta_record["from_state_digest"] == session.observation_a.state_digest
    assert session.delta_record["to_state_digest"] == session.observation_b.state_digest


def test_stream_finalization_matches_direct_frozen_contract(monkeypatch):
    session = _session(monkeypatch)
    expected = session.delta_record
    stream = ObservationStream(session.stream_id)
    step_a = stream.step(session.observation_a)
    step_b = stream.step(session.observation_b, predecessor=session.observation_a)
    assert step_a.admission.outcome == AdmissionOutcome.INITIAL_ACCEPTED
    assert step_b.record == expected


def test_no_raw_evaluator_draft_is_emitted(monkeypatch):
    session = _session(monkeypatch)
    session.capture(scene=_scene(x=1.0), report=_Report("report-b"), ordinal=2)
    assert "delta_digest" in session.delta_record
    assert "from_observation_origin" in session.delta_record


def test_post_candidate_is_not_exposed_as_accepted_b_on_failure(monkeypatch):
    session = _session(monkeypatch)
    with pytest.raises(RuntimeError):
        session.capture(
            scene=SceneModel(scene_id="different-scene", unit_system="METERS", objects=()),
            report=_Report("report-b"),
            ordinal=2,
        )
    assert session.observation_b is None
    assert session.delta_record is None


def test_caught_post_extraction_failure_marks_transport_ambiguous():
    evidence = {"mutator_invocations": 1, "ambiguous_result": False}
    mark_post_extraction_ambiguity(
        evidence,
        {"result": "MUTATION_FAILED", "failure_code": "POST_EXTRACTION_FAILED"},
    )
    assert evidence["ambiguous_result"] is True


def test_pre_mutation_failure_does_not_mark_post_extraction_ambiguity():
    evidence = {"mutator_invocations": 0, "ambiguous_result": False}
    _mark_post_extraction_ambiguity(
        evidence,
        {"result": "MUTATION_FAILED", "failure_code": "POST_EXTRACTION_FAILED"},
    )
    assert evidence["ambiguous_result"] is False
