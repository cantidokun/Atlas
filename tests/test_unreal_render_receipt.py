from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_render_receipt import UnrealRenderReceipt


def _evidence(**overrides):
    state = {
        "job_id": "job-123",
        "status": "finished",
        "finished": True,
        "success": True,
        "failed": False,
        "sequence_asset_path": "/Game/AtlasTest/AtlasSequencerFixtureSequence",
        "output_directory": "Saved/AtlasRenderOutput",
        "output_format": "png",
        "output_files": ["C:/renders/AtlasRender_0001.png"],
    }
    state.update(overrides)
    return UnrealEvidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=state, verified=True, source="render-receipt-test")


def test_render_receipt_issues_from_verified_inspection():
    receipt = UnrealRenderReceipt.issue(_evidence())
    assert receipt.job_id == "job-123"
    assert receipt.sequence_asset_path.startswith("/Game/")
    assert receipt.evidence_digest
    assert receipt.receipt_digest


def test_unreal_evidence_snapshot_round_trips_exactly():
    evidence = _evidence()
    restored = UnrealEvidence.from_snapshot(evidence.snapshot())
    assert restored == evidence
    assert restored.observed_state == evidence.observed_state
    assert restored.snapshot() == evidence.snapshot()


def test_unreal_evidence_snapshot_rejects_unknown_fields():
    snapshot = _evidence().snapshot()
    snapshot["unexpected"] = True
    try:
        UnrealEvidence.from_snapshot(snapshot)
    except ValueError as exc:
        assert "fields are invalid" in str(exc)
    else:
        raise AssertionError("unknown Unreal evidence snapshot fields must be rejected")


def test_render_receipt_snapshot_round_trips_exactly():
    receipt = UnrealRenderReceipt.issue(_evidence())
    restored = UnrealRenderReceipt.from_snapshot(receipt.snapshot())
    assert restored == receipt
    assert restored.receipt_digest == receipt.receipt_digest
    assert restored.snapshot() == receipt.snapshot()


def test_render_receipt_snapshot_rejects_unknown_fields():
    snapshot = UnrealRenderReceipt.issue(_evidence()).snapshot()
    snapshot["unexpected"] = True
    try:
        UnrealRenderReceipt.from_snapshot(snapshot)
    except ValueError as exc:
        assert "fields are invalid" in str(exc)
    else:
        raise AssertionError("unknown Unreal receipt snapshot fields must be rejected")


def test_unreal_evidence_snapshot_is_detached_from_mutation():
    evidence = _evidence()
    snapshot = evidence.snapshot()
    snapshot["entity_ids"].append("MUTATED")
    snapshot["observed_state"]["output_files"].append("MUTATED.png")
    assert evidence.entity_ids == ("FIELD_SURFACE",)
    assert evidence.observed_state["output_files"] == ("C:/renders/AtlasRender_0001.png",)


def test_unreal_evidence_is_deeply_immutable():
    state = {"job_id": "job-123", "nested": {"output_files": ["render-0001.png"]}}
    evidence = UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=["FIELD_SURFACE"],
        observed_state=state,
        verified=True,
        source="render-receipt-test",
    )
    state["nested"]["output_files"].append("render-0002.png")
    assert evidence.entity_ids == ("FIELD_SURFACE",)
    assert evidence.observed_state["nested"]["output_files"] == ("render-0001.png",)

    try:
        evidence.observed_state["job_id"] = "tampered"
    except TypeError:
        pass
    else:
        raise AssertionError("Unreal evidence observed_state must be immutable")

    try:
        evidence.observed_state["nested"]["output_files"] += ("tampered.png",)
    except TypeError:
        pass
    else:
        raise AssertionError("nested Unreal evidence state must be immutable")


def test_render_receipt_rejects_unverified_evidence():
    evidence = UnrealEvidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state={"job_id": "job-123", "sequence_asset_path": "/Game/AtlasTest/Sequence"}, verified=False, source="render-receipt-test")
    try:
        UnrealRenderReceipt.issue(evidence)
    except ValueError as exc:
        assert "verified" in str(exc)
    else:
        raise AssertionError("unverified evidence must not issue a receipt")


def test_render_receipt_rejects_wrong_operation():
    evidence = UnrealEvidence(operation_name="submit_render", entity_ids=("FIELD_SURFACE",), observed_state={"job_id": "job-123", "sequence_asset_path": "/Game/AtlasTest/Sequence"}, verified=True, source="render-receipt-test")
    try:
        UnrealRenderReceipt.issue(evidence)
    except ValueError as exc:
        assert "inspect_render_job" in str(exc)
    else:
        raise AssertionError("submit evidence must not issue a render receipt")


def test_render_receipt_rejects_incomplete_render():
    for overrides in (
        {"status": "running"},
        {"status": "failed", "success": False, "failed": True},
        {"success": False},
        {"failed": True},
    ):
        try:
            UnrealRenderReceipt.issue(_evidence(**overrides))
        except ValueError as exc:
            assert "completed" in str(exc) or "successful" in str(exc) or "non-failed" in str(exc)
        else:
            raise AssertionError("incomplete or failed render evidence must not issue a receipt")


def test_render_receipt_detects_artifact_drift():
    original = _evidence()
    receipt = UnrealRenderReceipt.issue(original)
    changed = _evidence(output_files=["C:/renders/AtlasRender_0001.png", "C:/renders/AtlasRender_0002.png"])
    assert receipt.matches(original)
    assert not receipt.matches(changed)


def test_render_receipt_detects_job_id_drift():
    receipt = UnrealRenderReceipt.issue(_evidence())
    assert not receipt.matches(_evidence(job_id="job-999"))


def test_render_receipt_detects_sequence_drift():
    receipt = UnrealRenderReceipt.issue(_evidence())
    assert not receipt.matches(_evidence(sequence_asset_path="/Game/AtlasTest/OtherSequence"))
