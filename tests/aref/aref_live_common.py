"""A-REF staged live driver — shared (bpy-free) protocol: markers, digests, handoff, categories.

Design authority: R4F sections 22 (second slice: harness-only live drivers, two-phase topology),
24 (probe launch / controller verification / execution launch), 16.5 (recording delegate),
16.4 (evidence instrumentation), 9.10 (plan artifact executed by BOTH paths).

This module is imported by BOTH the controller (headless pytest process) and the in-Blender stage
scripts, so it MUST stay free of bpy and of any production-module import that needs bpy.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------------------------
# Marker-delimited evidence transport (R4F 24 step 11; established w1 pattern).
# ---------------------------------------------------------------------------------------------

AREF_DIR = Path(__file__).resolve().parent

PROBE_BEGIN = "ATLAS_AREF_PROBE_EVIDENCE_BEGIN"
PROBE_END = "ATLAS_AREF_PROBE_EVIDENCE_END"
EXEC_BEGIN = "ATLAS_AREF_EXECUTION_EVIDENCE_BEGIN"
EXEC_END = "ATLAS_AREF_EXECUTION_EVIDENCE_END"

#: Refusal / failure categories (R4F 24; 10.1/10.8 dispositions). These are A-REF evidence
#: categories, never production codes.
CATEGORIES = frozenset({
    "FIXTURE-CONSTRUCTION-FAILURE",   # step 3 raw assertions failed (OC8-family)
    "FIXTURE-BINDING-MISMATCH",       # controller step 6 or in-process step 7 mismatch
    "STALE-HANDOFF",                  # stage-2 input identity/digest does not match the verified set
    "MALFORMED-EVIDENCE",             # unparseable/truncated/incomplete stage record
    "TRANSPORT-FAILURE",              # process exit, capture failure, missing marker (OC8)
    "GRAPH-MUTATED-BY-EXECUTION",     # step 10: names/references/slots changed
})

#: Controller-side tamper modes for the FX-BIND-* binding negatives (R4F 16.6(7)(ii)).
#: "withheld" modes stop the controller from launching the execution at all (the strongest
#: pre-mutation evidence); "in_process" modes tamper the handoff the execution launch consumes.
TAMPER_MODES = frozenset({
    "NONE",
    "WRONG_ARTIFACT_SHA",             # withheld at controller step 6
    "WRONG_PLAN_ID",                  # withheld at controller step 6
    "WRONG_SOURCE_DIGEST",            # withheld at controller step 6
    "TAMPERED_PROBE_ARTIFACT",        # execution-side: the written probe record is altered
    "TRUNCATED_EVIDENCE",             # withheld at controller step 6 (malformed probe record)
    "WRONG_PARAMETER_IN_HANDOFF",     # execution launch consumes a tampered plan (step 7 refusal)
})


class LiveError(Exception):
    """A stage-contract failure carrying an A-REF category (never a production code)."""

    def __init__(self, category: str, detail: str) -> None:
        if category not in CATEGORIES:
            raise ValueError(f"unknown A-REF category {category!r}")
        self.category = category
        self.detail = detail
        super().__init__(f"{category}: {detail}")


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_digest(obj: Any) -> str:
    return sha256_hex(canonical_bytes(obj))


def artifact(kind: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    """A digest-pinned A-REF evidence artifact (section 18 shape; authority is always 'none')."""
    body = {"artifact_kind": kind, "authority": "none", "receipt_authority": "none", **fields}
    return {"artifact_sha256": canonical_digest(body), "body": body}


def emit_marker(begin: str, end: str, payload: Dict[str, Any]) -> None:
    """Emit ONE marker-delimited JSON record (R4F 24 step 11)."""
    print(begin)
    print(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    print(end)
    import sys

    sys.stdout.flush()


def parse_marker(stdout: str, begin: str, end: str) -> Dict[str, Any]:
    """Parse the marker record out of captured stdout; malformed output is a transport failure."""
    lines = stdout.splitlines()
    try:
        i = lines.index(begin)
        j = lines.index(end, i + 1)
    except ValueError as exc:
        raise LiveError("TRANSPORT-FAILURE", f"evidence marker {begin}/{end} not found in output") from exc
    body = "\n".join(lines[i + 1:j]).strip()
    try:
        payload = json.loads(body)
    except Exception as exc:  # noqa: BLE001
        raise LiveError("MALFORMED-EVIDENCE", f"marker JSON is unparseable: {exc}") from exc
    if not isinstance(payload, dict):
        raise LiveError("MALFORMED-EVIDENCE", "marker JSON is not an object")
    body = payload.get("body") if isinstance(payload.get("body"), dict) else payload
    if "status" not in body or "stage" not in body:
        raise LiveError("MALFORMED-EVIDENCE", "marker JSON is missing status/stage")
    merged = dict(body)
    if "artifact_sha256" in payload:
        merged["artifact_sha256"] = payload["artifact_sha256"]
    return merged


# ---------------------------------------------------------------------------------------------
# Fixture-spec identity (EV-FixtureSpec; R4F 24 step 1/6): computed identically in both processes.
# ---------------------------------------------------------------------------------------------

def spec_fingerprint(raw_spec: Dict[str, Any], expected: Dict[str, Any]) -> str:
    """The immutable-spec digest: canonical hash of the FIX literals + declared expected literals."""
    return canonical_digest({"fixture": raw_spec, "expected": expected})


def fixture_spec_sha256(fixture_id: str) -> str:
    """Digest of the ON-DISK fixture declaration files for one case (both processes derive it)."""
    from tests.aref.fixtures import SPECS

    raw = SPECS[fixture_id]
    expected_path = AREF_DIR / "expected" / f"{fixture_id}.expected.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    return spec_fingerprint(raw, expected)


# ---------------------------------------------------------------------------------------------
# Stage handoff (controller -> execution launch) and its verification.
# ---------------------------------------------------------------------------------------------

HANDOFF_KEYS = frozenset({
    "handoff_version", "stage", "fixture_id", "case", "operation",
    "spec_digest", "expected_sha256", "plan_sha256", "plan_path",
    "declared_pre_digest", "declared_report_digest", "declared_plan_id",
    "declared_correction_ids", "probe_artifact_sha256", "probe_record_path", "controller_verified",
})

HANDOFF_VERSION = "aref-live-handoff-v1"


def build_handoff(*, fixture_id: str, case: str, operation: str, spec_digest: str,
                  expected_sha256: str, plan_sha256: str, plan_path: str,
                  declared_pre_digest: str, declared_report_digest: str, declared_plan_id: str,
                  declared_correction_ids: List[str], probe_artifact_sha256: str,
                  probe_record_path: str) -> Dict[str, Any]:
    return {
        "handoff_version": HANDOFF_VERSION, "stage": "EXECUTION", "fixture_id": fixture_id,
        "case": case, "operation": operation, "spec_digest": spec_digest,
        "expected_sha256": expected_sha256, "plan_sha256": plan_sha256, "plan_path": plan_path,
        "declared_pre_digest": declared_pre_digest, "declared_report_digest": declared_report_digest,
        "declared_plan_id": declared_plan_id, "declared_correction_ids": list(declared_correction_ids),
        "probe_artifact_sha256": probe_artifact_sha256,
        "probe_record_path": probe_record_path, "controller_verified": True,
    }


def validate_handoff(handoff: Any) -> Dict[str, Any]:
    """Fail closed on a malformed or incomplete handoff (never launch a tampered execution)."""
    if not isinstance(handoff, dict):
        raise LiveError("MALFORMED-EVIDENCE", "handoff is not an object")
    missing = sorted(HANDOFF_KEYS - set(handoff))
    if missing:
        raise LiveError("MALFORMED-EVIDENCE", f"handoff is missing keys {missing}")
    if handoff.get("handoff_version") != HANDOFF_VERSION or handoff.get("stage") != "EXECUTION":
        raise LiveError("MALFORMED-EVIDENCE", "handoff version/stage mismatch")
    if handoff.get("controller_verified") is not True:
        raise LiveError("FIXTURE-BINDING-MISMATCH", "handoff is not controller-verified")
    for key in ("spec_digest", "expected_sha256", "plan_sha256", "declared_pre_digest",
                "declared_report_digest", "declared_plan_id", "probe_artifact_sha256"):
        value = handoff.get(key)
        if type(value) is not str or len(value) != 64:
            raise LiveError("MALFORMED-EVIDENCE", f"handoff.{key} is not a 64-hex digest")
    ids = handoff.get("declared_correction_ids")
    if not isinstance(ids, list) or not ids or not all(type(i) is str for i in ids):
        raise LiveError("MALFORMED-EVIDENCE", "handoff.declared_correction_ids must be a non-empty str list")
    return handoff


# ---------------------------------------------------------------------------------------------
# Evidence-directory layout (external evidence only; never inside the repo tests tree).
# ---------------------------------------------------------------------------------------------

def load_case_live(fixture_id: str):
    """Load + validate one FIX case WITHOUT importing the harness (executor-free probe path).

    Same merge the Slice-1 loader performs (spec skeleton + generated expected literals), built on
    modules that never import the correction executor.
    """
    import copy

    from tests.aref.aref_fixture import validate_fixture
    from tests.aref.fixtures import SPECS

    if fixture_id not in SPECS:
        raise KeyError(f"unknown fixture {fixture_id!r}")
    spec = copy.deepcopy(SPECS[fixture_id])
    expected = read_json(AREF_DIR / "expected" / f"{fixture_id}.expected.json")
    spec["expected"] = expected["expected"]
    if expected.get("authorization_fixture") is not None:
        spec["authorization_fixture"] = expected["authorization_fixture"]
    return validate_fixture(spec)


def case_dir(evidence_root: Path, fixture_id: str) -> Path:
    return evidence_root / "live" / fixture_id


def write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    path.write_text(data, encoding="utf-8")
    return sha256_hex(data.encode("utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_probe_record_file(path: str, expected_sha256: str, expected_fixture_id: str) -> None:
    """M-d: the execution launch verifies the probe ARTIFACT it depends on (no stale evidence).

    The recorded probe record is the artifact's body plus its artifact_sha256; recomputing the
    digest over the body must reproduce the digest the controller verified.
    """
    import json as _json

    try:
        record = _json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise LiveError("MALFORMED-EVIDENCE", f"probe record unreadable: {exc}") from exc
    if not isinstance(record, dict) or "artifact_sha256" not in record:
        raise LiveError("MALFORMED-EVIDENCE", "probe record is not a digest-pinned artifact")
    body = {k: v for k, v in record.items() if k != "artifact_sha256"}
    if canonical_digest(body) != expected_sha256:
        raise LiveError("FIXTURE-BINDING-MISMATCH",
                        "the probe artifact digest does not match the controller-verified value")
    if record.get("fixture_id") != expected_fixture_id or record.get("status") != "PROBED":
        raise LiveError("FIXTURE-BINDING-MISMATCH",
                        "the probe record does not describe this fixture's completed probe")
