"""A-REF outcome classification, normal form, comparison, and evidence artifacts (R4F section 10).

Outcome classes OC1-OC8 (10.1), the outcome normal form (10.2), the disposition vocabulary
(10.8), and the evidence schema subset used by the conformance harness (18). Classification
uses only: (i) the executor's returned outcome/failure_code, (ii) the witness trace, (iii) the
observed mutator invocation count. No message-text matching anywhere.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from tests.aref.aref_witness import WitnessChannel

DISPOSITIONS = frozenset({
    "POSITIVELY_DEMONSTRATED", "STRUCTURALLY_UNREACHABLE", "NOT_APPLICABLE",
    "ENVIRONMENT_LIMITED", "INSUFFICIENT_EVIDENCE", "NON_COMPARABLE",
})

#: OC4 extraction-stage failures: (result, failure_code) pairs, R4F 10.1 OC4 (:596-598, :652-654).
#: SOURCE_DIGEST_MISMATCH (:602-603) is NOT an OC4 pair: OC4 cites :596-598 only, and the
#: digest-mismatch refusal is a pre-mutation refusal (OC1).
OC4_PAIRS = frozenset({
    ("SOURCE_MISMATCH", "EXTRACTION_FAILED"),
    ("MUTATION_FAILED", "POST_EXTRACTION_FAILED"),
})
#: OC1 outcome tokens (the executor's result field) that mean "refused before mutation"
#: (R4F 10.1 OC1, baseline 90e4d0a: PLAN_INVALID :546-570 incl. the entry-parameter allowlist
#: failure :583-587; UNSAFE :575-576; AUTHORIZATION_REQUIRED :579-580; AUTHORIZATION_INVALID
#: :1129/:1131/:1531/:2849; AUTHORIZATION_SCOPE_MISMATCH :99-102 (WAVE 2 authorization gate);
#: SOURCE_MISMATCH via SOURCE_DIGEST_MISMATCH :602-603; PRECONDITION_FAILED :615-616).
#: PARTIAL_FAILURE is declared in the baseline enum (:99) but has NO emission site at 90e4d0a:
#: a receipt carrying it raises EvidenceError (unclassifiable) — the correct fail-closed signal.
OC1_RESULTS = frozenset({
    "PLAN_INVALID", "UNSAFE", "AUTHORIZATION_REQUIRED", "AUTHORIZATION_INVALID",
    "AUTHORIZATION_SCOPE_MISMATCH", "SOURCE_MISMATCH", "PRECONDITION_FAILED",
})


class EvidenceError(Exception):
    """Inconsistent evidence combination (fails the case as infrastructure evidence)."""


def classify_outcome(receipt: Dict[str, Any], *, invocation_count: int,
                     witness: WitnessChannel, side: str) -> str:
    """Mechanically classify one execution outcome into OC1..OC8 (R4F 10.1)."""
    result = receipt.get("result")
    code = receipt.get("failure_code")

    # Witness discipline (10.4g): a pure-side UNEXPECTED_FAULT is OC7 even if codes match.
    if side == "pure" and witness.has_unexpected_fault("pure"):
        return "OC7"
    if side == "live" and witness.has_unexpected_fault("live"):
        return "OC8"

    if result == "COMPLETED":
        if invocation_count < 1:
            raise EvidenceError("COMPLETED with zero observed mutator invocations is inconsistent evidence")
        return "OC2"
    if (result, code) in OC4_PAIRS:
        # OC4 stage attribution: the extraction-stage pair refuses BEFORE mutation; the
        # post-extraction pair is reported only after the mutator returned (R4F 10.1 OC4, 10.3).
        if result == "SOURCE_MISMATCH" and invocation_count != 0:
            raise EvidenceError("OC4 extraction-stage refusal after an invocation is inconsistent evidence")
        if result == "MUTATION_FAILED" and invocation_count < 1:
            raise EvidenceError("OC4 post-extraction failure without an invocation is inconsistent evidence")
        return "OC4"
    if result in OC1_RESULTS:
        if invocation_count != 0:
            raise EvidenceError(f"pre-mutation refusal {result!r} after an invocation is inconsistent evidence")
        return "OC1"
    if result == "MUTATION_FAILED":
        return "OC3"
    if result == "POSTCONDITION_FAILED":
        return "OC6" if code == "NEW_INVALID_INDEX" else "OC5"
    raise EvidenceError(f"unclassifiable executor result {result!r} (code={code!r})")


def witness_classes_for(receipt: Dict[str, Any], witness: WitnessChannel, *, side: str) -> List[str]:
    """The mutator raise classes observed on a side (ENVELOPE_REFUSAL expected for OC3/OC5-with-raise)."""
    return witness.envelope_refusal_classes(side)


def outcome_normal_form(receipt: Dict[str, Any], *, invocation_count: int,
                        witness: WitnessChannel, side: str) -> Dict[str, Any]:
    """The R4F 10.2 normal form for one path."""
    oc = classify_outcome(receipt, invocation_count=invocation_count, witness=witness, side=side)
    phase = "PRE" if invocation_count == 0 else "POST"
    nf: Dict[str, Any] = {
        "oc_class": oc,
        "executor_outcome": receipt.get("result"),
        "failure_code": receipt.get("failure_code"),
        "phase": phase,
        "invocation_count": invocation_count,
    }
    for key in ("precondition_results", "postcondition_results"):
        if key in receipt:
            nf[key] = receipt[key]
    return nf


@dataclass
class ComparisonResult:
    dimensions: Dict[str, Any]
    verdict: str                 # PARITY | DIVERGENCE | INSUFFICIENT_EVIDENCE
    disposition_notes: List[str] = field(default_factory=list)


def compare_normal_forms(pure_nf: Dict[str, Any], live_nf: Dict[str, Any], *,
                         pure_child_digest: Optional[str] = None,
                         live_child_digest: Optional[str] = None,
                         pure_witness: Optional[WitnessChannel] = None,
                         live_witness: Optional[WitnessChannel] = None) -> ComparisonResult:
    """Compare two normal forms per R4F 10.2/10.5. Any mismatch fails as divergence."""
    dims: Dict[str, Any] = {}
    notes: List[str] = []
    ok = True

    for key in ("oc_class", "executor_outcome", "failure_code", "phase", "invocation_count"):
        same = pure_nf.get(key) == live_nf.get(key)
        dims[key] = same
        ok = ok and same

    for key in ("precondition_results", "postcondition_results"):
        if key in pure_nf or key in live_nf:
            same = pure_nf.get(key) == live_nf.get(key)
            dims[key] = same
            ok = ok and same

    if pure_child_digest is not None or live_child_digest is not None:
        same = pure_child_digest == live_child_digest
        dims["child_digest"] = same
        ok = ok and same

    if pure_witness is not None and live_witness is not None:
        p_cls = witness_classes_for({}, pure_witness, side="pure")
        l_cls = witness_classes_for({}, live_witness, side="live")
        dims["witness_classes_match"] = p_cls == l_cls
        ok = ok and dims["witness_classes_match"]

    if pure_nf.get("oc_class") == "OC3":
        notes.append("OC3 refusal-reason parity is NON_COMPARABLE under the current observable contract (R4F 10.2)")

    verdict = "PARITY" if ok else "DIVERGENCE"
    return ComparisonResult(dimensions=dims, verdict=verdict, disposition_notes=notes)


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def evidence_artifact(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap one case's evidence in a digest-pinned artifact (R4F section 18)."""
    artifact = dict(fields)
    digest = hashlib.sha256(canonical_bytes(artifact)).hexdigest()
    wrapped = {"artifact_sha256": digest, "body": artifact}
    wrapped["authority"] = "none"
    wrapped["receipt_authority"] = "none"
    return wrapped
