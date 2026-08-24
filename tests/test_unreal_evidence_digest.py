import pytest

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_evidence_digest import (
    UnrealEvidenceDigestError,
    digest_evidence,
    digest_evidence_ledger,
)


def _evidence(value=10, *, operation_name="inspect_target_actors", entity_ids=("FIELD_SURFACE",)):
    return UnrealEvidence(
        operation_name=operation_name,
        entity_ids=entity_ids,
        observed_state={"FIELD_SURFACE": {"location": {"x": value, "y": 0, "z": 0}}},
        source="unreal-editor-atlas-transport",
        verified=False,
    )


def test_same_evidence_produces_same_digest():
    assert digest_evidence(_evidence()) == digest_evidence(_evidence())


def test_mapping_order_does_not_change_digest():
    first = UnrealEvidence(
        "inspect_target_actors",
        ("FIELD_SURFACE",),
        {"FIELD_SURFACE": {"z": 3, "x": 1, "y": 2}},
        "unreal-editor-atlas-transport",
    )
    second = UnrealEvidence(
        "inspect_target_actors",
        ("FIELD_SURFACE",),
        {"FIELD_SURFACE": {"y": 2, "x": 1, "z": 3}},
        "unreal-editor-atlas-transport",
    )
    assert digest_evidence(first) == digest_evidence(second)


def test_changed_observed_state_changes_digest():
    assert digest_evidence(_evidence(10)) != digest_evidence(_evidence(11))


def test_changed_source_changes_digest():
    first = _evidence()
    second = UnrealEvidence(
        first.operation_name,
        first.entity_ids,
        first.observed_state,
        "different-source",
        first.verified,
    )
    assert digest_evidence(first) != digest_evidence(second)


def test_ledger_order_is_significant():
    first = _evidence(10)
    second = _evidence(20)
    assert digest_evidence_ledger((first, second)) != digest_evidence_ledger((second, first))


def test_non_finite_float_is_rejected():
    evidence = UnrealEvidence(
        "inspect_target_actors",
        ("FIELD_SURFACE",),
        {"FIELD_SURFACE": {"x": float("nan")}},
        "unreal-editor-atlas-transport",
    )
    with pytest.raises(UnrealEvidenceDigestError, match="non-finite floats"):
        digest_evidence(evidence)


def test_non_string_mapping_key_is_rejected():
    evidence = UnrealEvidence(
        "inspect_target_actors",
        ("FIELD_SURFACE",),
        {"FIELD_SURFACE": {1: "invalid"}},
        "unreal-editor-atlas-transport",
    )
    with pytest.raises(UnrealEvidenceDigestError, match="mapping keys"):
        digest_evidence(evidence)


def test_digest_requires_unreal_evidence():
    with pytest.raises(TypeError):
        digest_evidence("not evidence")
