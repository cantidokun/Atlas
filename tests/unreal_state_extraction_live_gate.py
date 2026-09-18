"""Live extraction gate against a running Unreal Editor (UE 5.6.1).

Not collected by pytest (no ``test_`` prefix): this is the operator-run live gate of
Revision 3.1 §11.3, executed against a real editor session with the Atlas transport
pipe available.

Usage (after ``UnrealEditor-Cmd.exe AtlasUnrealHarness.uproject`` is running):

    python -m tests.unreal_state_extraction_live_gate [--json <report-path>]

What it proves, end to end:

* the C++ producer's value tree validates against the Python closed schema;
* engine identity is sourced from the engine, not from the legacy ``"5.6"`` literal;
* the world is the editor world with a non-partitioned, complete loaded-visible scope;
* canonical identity is request-independent (case variants share one digest);
* repeated extraction is byte-identical (determinism);
* envelope session metadata never reaches the canonical bytes;
* the refusal arms are real: a missing entity and a case-folded duplicate both fail
  closed with their contract code.

What it deliberately does not attempt, because no fixture or transport read exists for
it in this rung (recorded instead of worked around): package-dirty invariance needs an
engine-side dirty-state read the frozen transport does not expose; scope-change refusal
needs a world with a manipulable streaming level; the material-collision, numbered-name
and signed-zero arms need richer tagged fixtures.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import json
import sys
from typing import Any, Dict, List

from planning.unreal_state_extraction import (
    UnrealStateExtractionError,
    canonical_size,
    extract,
    validate_request_entity_ids,
)
from planning.unreal_transport_contract import UnrealTransportRequest
from planning.unreal_transport_named_pipe import create_named_pipe_transport

ENTITY_ID = "FIELD_SURFACE"
AUTHORIZATION_ID = "atlas-extraction-live-gate"
OPERATION = "extract_actor_state"
CAPABILITY = "inspect_actor"
KIND = "read"


def _request(entity_ids: List[str]) -> UnrealTransportRequest:
    return UnrealTransportRequest(
        request_id=f"atlas-extraction-gate-{len(entity_ids)}-{entity_ids[0].lower()}",
        operation_name=OPERATION,
        capability=CAPABILITY,
        kind=KIND,
        arguments={"entity_ids": list(entity_ids)},
        entity_ids=tuple(entity_ids),
        authorization_id=AUTHORIZATION_ID,
    )


def _as_mapping(response: Any) -> Dict[str, Any]:
    return {
        "request_id": response.request_id,
        "operation_name": response.operation_name,
        "entity_ids": list(response.entity_ids),
        "success": response.success,
        "observed_state": response.observed_state,
        "error": response.error,
        "source": response.source,
        "schema_version": response.schema_version,
        "error_code": response.error_code,
        "session_identity": dict(response.session_identity),
    }


class GateFailure(Exception):
    pass


def _check(condition: bool, message: str, checks: List[Dict[str, Any]]) -> None:
    checks.append({"check": message, "passed": bool(condition)})
    if not condition:
        raise GateFailure(message)


def run_gate() -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    facts: Dict[str, Any] = {}
    transport = create_named_pipe_transport()

    # 1. Positive extraction with the canonical spelling.
    response = transport.send(_request([ENTITY_ID]))
    envelope = _as_mapping(response)
    _check(response.success, f"extraction of {ENTITY_ID} succeeded", checks)
    result = extract(envelope)
    tree = result.value_tree

    world = tree["world"]
    actor = tree["actors"][0]
    facts["digest"] = result.digest
    facts["canonical_bytes"] = canonical_size(tree)
    facts["engine_version"] = world["engine_version"]
    facts["engine_build_version"] = world["engine_build_version"]
    facts["world_type"] = world["world_type"]
    facts["selection_provenance"] = world["selection_provenance"]
    facts["is_partitioned_world"] = world["is_partitioned_world"]
    facts["level_scope"] = world["level_scope"]["levels"]
    facts["entity_id"] = actor["entity_id"]
    facts["actor_object_path"] = actor["actor_object_path"]
    facts["actor_class"] = actor["actor_class"]
    facts["transform"] = actor["transform"]
    facts["materials"] = actor["materials"]
    facts["omitted_material_components"] = actor["omitted_material_components"]
    facts["editor_visibility"] = actor["editor_visibility"]

    # 2. Engine identity is sourced, not the legacy literal (§3.1.2).
    _check(
        world["engine_version"] != "5.6",
        "engine_version is the engine's own version, not the legacy hardcoded literal",
        checks,
    )
    _check(bool(world["engine_version"]), "engine_version is non-empty", checks)
    _check(bool(world["engine_build_version"]), "engine_build_version is non-empty", checks)

    # 3. World and scope facts (§3.1, §3.2.1, §4.4).
    _check(world["world_type"] == "editor", "world_type is editor", checks)
    _check(world["is_partitioned_world"] is False, "the world is not partitioned", checks)
    _check(
        world["selection_provenance"] == "g_editor_editor_world_context",
        "world selection provenance is the authoritative site",
        checks,
    )
    levels = world["level_scope"]["levels"]
    _check(len(levels) >= 1, "the level scope is non-empty", checks)
    _check(
        sum(1 for level in levels if level["level_kind"] == "persistent") == 1,
        "the scope records exactly one persistent level",
        checks,
    )
    _check(all(level["loaded"] and level["visible"] for level in levels), "every scope level is loaded and visible", checks)

    # 4. Canonical identity and transform facts.
    _check(actor["entity_id"] == ENTITY_ID, "the reported entity_id is the canonical identity", checks)
    for axis in ("x", "y", "z"):
        for scalar in (
            actor["transform"]["location_cm"][axis],
            actor["transform"]["scale"][axis],
        ):
            _check(
                len(scalar) == 16 and all(character in "0123456789abcdef" for character in scalar),
                f"transform scalar on {axis} is a binary64 pattern",
                checks,
            )

    # 5. Determinism: repeat extraction is byte-identical (§7.4 D5).
    repeat = extract(_as_mapping(transport.send(_request([ENTITY_ID]))))
    _check(
        repeat.canonical_bytes == result.canonical_bytes and repeat.digest == result.digest,
        "repeated extraction is byte-identical",
        checks,
    )

    # 6. Canonical identity is request-independent (§3.3.4, §7.4 D14).
    case_variant = extract(_as_mapping(transport.send(_request(["field_surface"]))))
    _check(
        case_variant.canonical_bytes == result.canonical_bytes
        and case_variant.digest == result.digest,
        "a case-variant request yields the identical payload and digest",
        checks,
    )
    facts["case_variant_digest"] = case_variant.digest

    # 7. Session metadata is envelope-only (§4.1, §7.4 D8).
    _check(
        "session_identity" in envelope and bool(envelope["session_identity"]),
        "the envelope carries session identity",
        checks,
    )
    payload_text = result.canonical_bytes.decode("utf-8")
    for forbidden in ("session_identity", "process_id", "server_start_time_utc", "editor_session_id"):
        _check(forbidden not in payload_text, f"the payload carries no {forbidden}", checks)
    facts["envelope_session_identity_keys"] = sorted(envelope["session_identity"].keys())

    # 8. Refusal arms are reachable live.
    missing = _as_mapping(transport.send(_request(["NO_SUCH_ENTITY"])))
    _check(missing["success"] is False, "a missing entity fails", checks)
    _check(
        missing["error_code"] == "ERR_EXTRACTION_ENTITY_NOT_FOUND",
        "a missing entity reports ERR_EXTRACTION_ENTITY_NOT_FOUND",
        checks,
    )
    facts["missing_entity_error_code"] = missing["error_code"]

    try:
        validate_request_entity_ids(["cam01", "CAM01"])
    except UnrealStateExtractionError as error:
        facts["duplicate_case_variant_code"] = error.code
        _check(
            error.code == "ERR_EXTRACTION_REQUEST_INVALID",
            "case-folded duplicates are rejected by the request rule set",
            checks,
        )
    else:  # pragma: no cover - the rule is unconditional
        raise GateFailure("case-folded duplicates were accepted")

    facts["checks"] = checks
    return facts


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", dest="json_path", default=None)
    args = parser.parse_args(argv)

    report: Dict[str, Any] = {
        "generated_at_utc": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
        "operation": OPERATION,
        "entity_id": ENTITY_ID,
    }
    try:
        report["result"] = "PASS"
        report["facts"] = run_gate()
    except GateFailure as failure:
        report["result"] = "FAIL"
        report["failure"] = str(failure)
    except Exception as error:  # transport or contract failure
        report["result"] = "ERROR"
        report["failure"] = f"{type(error).__name__}: {error}"

    text = json.dumps(report, indent=2, sort_keys=True)
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
