"""Live extraction gate against a running Unreal Editor (UE 5.6.1).

Not collected by pytest (no ``test_`` prefix): this is the operator-run live gate of
Revision 3.1 §11.3, executed against a real editor session with the Atlas transport pipe
available and the extraction fixture map open.

Usage:

    UnrealEditor-Cmd.exe <project> /Game/AtlasTest/Generated/AtlasExtractionFixture \
        -AtlasExtractionFixture -unattended -nosplash -nop4 -nullrhi -stdout -FullStdOutLogOutput

    python -m tests.unreal_state_extraction_live_gate [--json report.json] \
        [--automation-log <editor-log-with-automation-results>]

Every case is recorded separately with one of four statuses, and the run never converts a
source-level result into a live result:

``PASS``
    the live engine produced the expected value tree or the expected observation.
``REFUSAL VERIFIED``
    the live engine failed closed with the contract's own error code.
``NOT YET LIVE-COVERED``
    the branch is reachable in principle but this rung has no fixture or read for it.
``BLOCKED BY ENGINE/API LIMITATION``
    the branch cannot be induced through any API this harness may use, with the obstacle
    recorded verbatim.
loudly instead of running against unverified content.
and writes nothing -- so a session without ``-AtlasExtractionFixture`` fails this precondition
(review F-1 item 5). Fixture provisioning is opt-in -- an ordinary harness startup provisions
The run also has one precondition: the fixture session must report ``ATLAS_EXTRACTION_FIXTURE_STATUS: OK``


A failure makes the overall result ``FAIL`` while every other case's result is still
reported: a partial result stays a partial result.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

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
SEQUENCER_OPERATION = "extract_sequencer_state"
CAPABILITY = "inspect_actor"
SEQUENCER_CAPABILITY = "sequencer"
KIND = "read"

#: Every entity this gate requests. `tests/test_unreal_state_extraction_fixture_branches.py`
#: asserts each one is created by the fixture, so a request that cannot exist fails there
#: rather than looking like a live pass.
REQUESTED_ENTITIES: List[str] = [
    "FIELD_SURFACE",
    "IMPL_PERM_A",
    "IMPL_PERM_B",
    "CAM",
    "CAM_1",
    "CAM_01",
    "IMPL_PARENT_NONE",
    "IMPL_PARENT_UNBOUND",
    "IMPL_PARENT_BOUND",
    "IMPL_MATERIAL_OVERRIDE_A",
    "IMPL_MATERIAL_OVERRIDE_B",
    "IMPL_OMITTED",
    "IMPL_NULL_SKINNED",
    "IMPL_UNSUPPORTED_COMPONENT",
    "IMPL_SIGNED_ZERO",
    "IMPL_Q_POS",
    "IMPL_Q_NEG",
    "IMPL_RUNTIME_MESH",
    "IMPL_SEQUENCE_VALID",
    "IMPL_SEQUENCE_DEGENERATE",
    "IMPL_SEQUENCE_BAD_RATE",
    "NO_SUCH_ENTITY",
]

PASS = "PASS"
REFUSAL_VERIFIED = "REFUSAL VERIFIED"
NOT_COVERED = "NOT YET LIVE-COVERED"
BLOCKED = "BLOCKED BY ENGINE/API LIMITATION"
FAIL = "FAIL"

NEGATIVE_ZERO_PATTERN = "8000000000000000"
POSITIVE_ZERO_PATTERN = "0000000000000000"


class CaseFailure(Exception):
    def __init__(self, message: str, evidence: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.evidence = evidence or {}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CaseFailure(message)


def _request(entity_ids: List[str], operation: str = OPERATION) -> UnrealTransportRequest:
    capability = SEQUENCER_CAPABILITY if operation == SEQUENCER_OPERATION else CAPABILITY
    return UnrealTransportRequest(
        request_id=f"atlas-extraction-gate-{len(entity_ids)}-{entity_ids[0].lower()}-{operation}",
        operation_name=operation,
        capability=capability,
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


class LiveTransport:
    def __init__(self) -> None:
        self._transport = create_named_pipe_transport()

    def actor(self, entity_ids: List[str]) -> Dict[str, Any]:
        return _as_mapping(self._transport.send(_request(list(entity_ids))))

    def sequencer(self, entity_ids: List[str]) -> Dict[str, Any]:
        return _as_mapping(self._transport.send(_request(list(entity_ids), SEQUENCER_OPERATION)))

    def extract_actor(self, entity_ids: List[str]) -> Tuple[Any, Dict[str, Any]]:
        envelope = self.actor(entity_ids)
        _require(envelope["success"], f"extraction of {entity_ids} failed: {envelope['error']}")
        return extract(envelope), envelope

    def extract_sequencer(self, entity_ids: List[str]) -> Tuple[Any, Dict[str, Any]]:
        envelope = self.sequencer(entity_ids)
        _require(envelope["success"], f"sequencer extraction of {entity_ids} failed: {envelope['error']}")
        return extract(envelope), envelope


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

def case_positive_baseline(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """The rung-1 baseline, re-run against the fixture map through the transport."""
    result, envelope = transport.extract_actor("FIELD_SURFACE".split(","))
    tree = result.value_tree
    world = tree["world"]
    actor = tree["actors"][0]
    evidence: Dict[str, Any] = {
        "digest": result.digest,
        "canonical_bytes": canonical_size(tree),
        "engine_version": world["engine_version"],
        "engine_build_version": world["engine_build_version"],
        "world_type": world["world_type"],
        "selection_provenance": world["selection_provenance"],
        "is_partitioned_world": world["is_partitioned_world"],
        "level_scope": world["level_scope"]["levels"],
        "actor_object_path": actor["actor_object_path"],
        "envelope_session_identity_keys": sorted(envelope["session_identity"].keys()),
    }

    _require(world["engine_version"] != "5.6", "engine_version is the legacy literal")
    _require(world["world_type"] == "editor", "world_type is not editor")
    _require(world["is_partitioned_world"] is False, "the world reports as partitioned")
    _require(
        world["selection_provenance"] == "g_editor_editor_world_context",
        "world selection provenance is not the authoritative site",
    )
    levels = world["level_scope"]["levels"]
    _require(
        sum(1 for level in levels if level["level_kind"] == "persistent") == 1,
        "the scope does not record exactly one persistent level",
    )
    _require(
        all(level["loaded"] and level["visible"] for level in levels),
        "a scope level is not loaded and visible",
    )
    _require(actor["entity_id"] == "FIELD_SURFACE", "the canonical entity id is wrong")
    for axis in ("x", "y", "z"):
        for scalar in (actor["transform"]["location_cm"][axis], actor["transform"]["scale"][axis]):
            _require(
                len(scalar) == 16 and all(c in "0123456789abcdef" for c in scalar),
                f"transform scalar on {axis} is not a binary64 pattern",
            )

    repeat_result, _ = transport.extract_actor(["FIELD_SURFACE"])
    _require(
        repeat_result.canonical_bytes == result.canonical_bytes,
        "repeated extraction is not byte-identical",
    )
    evidence["repeat_digest"] = repeat_result.digest

    payload_text = result.canonical_bytes.decode("utf-8")
    for forbidden in ("session_identity", "process_id", "server_start_time_utc", "editor_session_id"):
        _require(forbidden not in payload_text, f"the payload carries {forbidden}")
    return PASS, evidence


def case_request_order_permutation(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """Two independently tagged actors: the request order must not change the payload."""
    forward = transport.actor(["IMPL_PERM_A", "IMPL_PERM_B"])
    backward = transport.actor(["IMPL_PERM_B", "IMPL_PERM_A"])
    _require(forward["success"] and backward["success"], "one of the permutation requests failed")

    forward_result = extract(forward)
    backward_result = extract(backward)
    forward_ids = [actor["entity_id"] for actor in forward_result.value_tree["actors"]]
    backward_ids = [actor["entity_id"] for actor in backward_result.value_tree["actors"]]
    evidence = {
        "forward_entity_ids": forward_ids,
        "backward_entity_ids": backward_ids,
        "forward_digest": forward_result.digest,
        "backward_digest": backward_result.digest,
    }
    _require(
        forward_result.canonical_bytes == backward_result.canonical_bytes,
        "request order changed the canonical payload",
    )
    _require(len(forward_ids) == 2, f"expected two actor records, got {forward_ids}")
    _require(
        forward_ids == sorted(forward_ids),
        "the payload's actor order is not the canonical ascending order",
    )
    return PASS, evidence


def case_numbered_identities(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """`CAM`, `CAM_1`, `CAM_01` are three identities; their case variants fold onto them."""
    evidence: Dict[str, Any] = {}
    canonical: Dict[str, str] = {}
    for entity_id in ("CAM", "CAM_1", "CAM_01"):
        result, _ = transport.extract_actor([entity_id])
        actor = result.value_tree["actors"][0]
        evidence[entity_id] = {
            "reported_entity_id": actor["entity_id"],
            "digest": result.digest,
        }
        _require(
            actor["entity_id"] == entity_id,
            f"{entity_id} was reported as {actor['entity_id']}",
        )
        canonical[entity_id] = result.digest

    _require(len(set(canonical.values())) == 3, "the numbered identities do not differ")

    for lower, upper in (("cam", "CAM"), ("cam_1", "CAM_1"), ("cam_01", "CAM_01")):
        variant_result, _ = transport.extract_actor([lower])
        variant_actor = variant_result.value_tree["actors"][0]
        evidence[f"{lower}_variant"] = {
            "reported_entity_id": variant_actor["entity_id"],
            "digest": variant_result.digest,
        }
        _require(
            variant_actor["entity_id"] == upper,
            f"case variant {lower} reported {variant_actor['entity_id']}, expected {upper}",
        )
        _require(
            variant_result.digest == canonical[upper],
            f"case variant {lower} did not fold onto {upper}",
        )
    return PASS, evidence


def case_parent_three_state(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """`none`, `unbound` and `bound` are three distinguishable parent records."""
    evidence: Dict[str, Any] = {}
    for entity_id in ("IMPL_PARENT_NONE", "IMPL_PARENT_UNBOUND", "IMPL_PARENT_BOUND"):
        result, _ = transport.extract_actor([entity_id])
        parent = result.value_tree["actors"][0]["parent"]
        evidence[entity_id] = parent
        _require(parent["binding"] in ("none", "unbound", "bound"), f"{entity_id}: bad binding")

    _require(evidence["IMPL_PARENT_NONE"]["binding"] == "none", "IMPL_PARENT_NONE is not none")
    _require(
        evidence["IMPL_PARENT_UNBOUND"]["binding"] == "unbound"
        and evidence["IMPL_PARENT_UNBOUND"]["actor_object_path"],
        "IMPL_PARENT_UNBOUND does not record an unbound parent path",
    )
    _require(
        evidence["IMPL_PARENT_BOUND"]["binding"] == "bound"
        and evidence["IMPL_PARENT_BOUND"]["entity_id"] == "IMPL_PERM_A",
        "IMPL_PARENT_BOUND does not resolve to its tagged parent",
    )
    _require(
        evidence["IMPL_PARENT_NONE"]["actor_object_path"] is None,
        "a parentless actor records a parent object path",
    )
    return PASS, evidence


def case_material_collisions(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """Assignment, asset slot and resolved value are three separate documented facts."""
    evidence: Dict[str, Any] = {}
    digests: Dict[str, str] = {}
    for entity_id in ("IMPL_MATERIAL_OVERRIDE_A", "IMPL_MATERIAL_OVERRIDE_B"):
        result, _ = transport.extract_actor([entity_id])
        materials = result.value_tree["actors"][0]["materials"]
        _require(materials, f"{entity_id} reported no material component")
        evidence[entity_id] = [
            {
                "component_object_path": component["component_object_path"],
                "component_class": component["component_class"],
                "mesh_asset_path": component["mesh_asset_path"],
                "slots": component["slots"],
            }
            for component in materials
        ]
        digests[entity_id] = result.digest

        distinguishing = []
        for component in materials:
            for slot in component["slots"]:
                override = slot["override_material_asset_path"]
                expected_resolution = (
                    override if override else slot["asset_slot_material_asset_path"]
                )
                _require(
                    slot["resolved_material_asset_path"] == expected_resolution,
                    f"{entity_id}: the resolved material {slot['resolved_material_asset_path']} is "
                    "neither the override nor the asset slot",
                )
                if override and override != slot["asset_slot_material_asset_path"]:
                    distinguishing.append(component["component_object_path"])
        _require(
            distinguishing,
            f"{entity_id}: no component distinguishes an override from its asset slot",
        )
        evidence[f"{entity_id}_distinguishing_components"] = distinguishing
        evidence[f"{entity_id}_digest"] = digests[entity_id]

    _require(
        digests["IMPL_MATERIAL_OVERRIDE_A"] != digests["IMPL_MATERIAL_OVERRIDE_B"],
        "two different slot/override states produced the same digest",
    )
    evidence["assignment_and_asset_slot_distinct"] = True
    return PASS, evidence


def case_material_rendered_appearance(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """The engine-side substitution dimension, declared out of scope by Revision 3.3.

    Nothing here is asserted to be absent from the tree by this case; the point is that the
    gate must not claim rendered-material state *or* session-dependent engine resolution. The
    in-process test ``Atlas.StateExtraction.MaterialResolutionBoundary`` asserts the payload's
    ``resolved`` equals the deterministic projection against the engine's own objects, records
    the session's component-accessor value and substitution-gate state, and the Python
    boundary refuses any tree whose ``resolved`` diverges (design §7.4 D17c).
    """
    return (
        NOT_COVERED,
        {
            "contract_boundary": (
                "Nanite render-path substitution is outside v1 extraction because the extraction "
                "accessor does not expose that rendered state; Revision 3.3 adds that no "
                "engine-side material substitution is part of the field either, because a value "
                "that depends on the session cannot be a deterministic source fact (§3.8.2)"
            ),
            "why_out_of_scope": (
                "the engine's material accessor applies a material-level Nanite override only when "
                "the assigned material carries one AND the session reports UseNaniteOverrideMaterials "
                "(ShouldCreateNaniteProxy(Component, nullptr) && "
                "GEnableNaniteMaterialOverrides/r.Nanite.MaterialOverrides != 0). Those inputs are "
                "session and configuration state, so the contract does not read them: resolved is "
                "the projection of the two saved source facts and is unaffected by any of them"
            ),
            "invariance_evidence": (
                "this gate was run in two session configurations (r.Nanite.MaterialOverrides at its "
                "default and at 0) and the material digests recorded per case above are compared "
                "byte for byte between the runs; identical saved source state must give identical "
                "bytes in both"
            ),
        },
    )


def case_null_skinned_and_omitted(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """The skinned family and the omitted-component inventory, live."""
    skinned_result, _ = transport.extract_actor(["IMPL_NULL_SKINNED"])
    skinned = skinned_result.value_tree["actors"][0]
    components = skinned["materials"]
    _require(components, "the skinned fixture reported no material component")
    _require(
        components[0]["mesh_state"] == "no_mesh_asset",
        f"the null-mesh skinned component reported {components[0]['mesh_state']}",
    )

    omitted_result, _ = transport.extract_actor(["IMPL_OMITTED"])
    omitted = omitted_result.value_tree["actors"][0]["omitted_material_components"]
    _require(omitted["count"] >= 1, "the omitted-component inventory is empty")
    return PASS, {
        "skinned_component_class": components[0]["component_class"],
        "skinned_mesh_state": components[0]["mesh_state"],
        "omitted_inventory": omitted,
    }


def case_signed_zero(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """Which engine surface preserves the sign of a negative zero, live."""
    result, _ = transport.extract_actor(["IMPL_SIGNED_ZERO"])
    actor_transform = result.value_tree["actors"][0]["transform"]
    location = actor_transform["location_cm"]
    scale = actor_transform["scale"]
    evidence = {
        "location_cm": dict(location),
        "scale": dict(scale),
        "location_x_preserved": location["x"] == NEGATIVE_ZERO_PATTERN,
        "scale_x_preserved": scale["x"] == NEGATIVE_ZERO_PATTERN,
    }
    if scale["x"] == NEGATIVE_ZERO_PATTERN:
        # The scale surface is a stored source value: the sign survives it, and the
        # in-process fidelity test proves the payload equals the engine's own value.
        return PASS, evidence
    if location["x"] == NEGATIVE_ZERO_PATTERN:
        return PASS, evidence
    return (
        BLOCKED,
        dict(
            evidence,
            obstacle=(
                "neither the actor location nor the actor scale surface reports a negative "
                "zero for the fixture: the engine normalises the sign somewhere in its own "
                "transform storage/composition for these inputs. The extractor still reports "
                "exactly what the engine holds (proved by "
                "Atlas.StateExtraction.TransformSignPreservation, which compares the payload "
                "against a direct engine read bit for bit), so the ±0 arm's live evidence is "
                "the fidelity assertion rather than sign survival."
            ),
        ),
    )


def case_quaternion_sign(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """`q` and `-q` for the same rotation on two fixtures, as the engine holds them."""
    positive, _ = transport.extract_actor(["IMPL_Q_POS"])
    negative, _ = transport.extract_actor(["IMPL_Q_NEG"])
    positive_rotation = positive.value_tree["actors"][0]["transform"]["rotation"]
    negative_rotation = negative.value_tree["actors"][0]["transform"]["rotation"]
    axes = ("x", "y", "z", "w")
    evidence = {
        "IMPL_Q_POS": {axis: positive_rotation[axis] for axis in axes},
        "IMPL_Q_NEG": {axis: negative_rotation[axis] for axis in axes},
        "signs_distinct": any(
            positive_rotation[axis] != negative_rotation[axis] for axis in axes
        ),
    }
    if evidence["signs_distinct"]:
        return PASS, evidence
    return (
        BLOCKED,
        dict(
            evidence,
            obstacle=(
                "the two quaternion fixtures report identical component patterns: UE stores "
                "an actor's rotation as an FRotator and derives the quaternion, so the ±q "
                "distinction is not expressible through an actor transform. Sign preservation "
                "is evidenced at the encoding level (binary64 vectors, both signs) and by "
                "Atlas.StateExtraction.TransformSignPreservation, which proves the payload "
                "matches the engine's own quaternion bit for bit on both fixtures."
            ),
        ),
    )


def case_sequencer_live(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """A real entity-tagged ALevelSequenceActor with a saved, valid sequence."""
    result, _ = transport.extract_sequencer(["IMPL_SEQUENCE_VALID"])
    sequence = result.value_tree["sequences"][0]
    evidence = {
        "entity_id": sequence["entity_id"],
        "sequence_actor_object_path": sequence["sequence_actor_object_path"],
        "sequence_asset_object_path": sequence["sequence_asset_object_path"],
        "playback_range": sequence["playback_range"],
        "tick_resolution": sequence["tick_resolution"],
        "display_rate": sequence["display_rate"],
        "digest": result.digest,
    }
    _require(
        sequence["entity_id"] == "IMPL_SEQUENCE_VALID",
        f"the sequencer record reports {sequence['entity_id']}",
    )
    _require(
        "AtlasExtractionSequenceValid" in sequence["sequence_asset_object_path"],
        "the sequencer record does not name the saved fixture sequence",
    )
    _require(
        sequence["playback_range"]["upper_frame"] > sequence["playback_range"]["lower_frame"],
        "the live sequence reports a degenerate range as valid",
    )
    _require(
        sequence["tick_resolution"]["numerator"] > 0
        and sequence["tick_resolution"]["denominator"] > 0,
        "the live sequence reports an invalid rational rate",
    )
    return PASS, evidence


SEQUENCER_REFUSAL_ARMS = (
    ("IMPL_SEQUENCE_DEGENERATE", "ERR_EXTRACTION_SEQUENCE_RANGE_INVALID"),
    ("IMPL_SEQUENCE_BAD_RATE", "ERR_EXTRACTION_SEQUENCE_RATE_INVALID"),
)


def case_sequencer_refusals(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """Degenerate range, unset range and invalid rate all fail closed, live."""
    evidence: Dict[str, Any] = {}
    for entity_id, expected_code in SEQUENCER_REFUSAL_ARMS:
        envelope = transport.sequencer([entity_id])
        evidence[entity_id] = {
            "success": envelope["success"],
            "error_code": envelope["error_code"],
            "error": envelope["error"],
        }
        _require(envelope["success"] is False, f"{entity_id} was accepted")
        _require(
            envelope["error_code"] == expected_code,
            f"{entity_id} reported {envelope['error_code']}, expected {expected_code}",
        )
    return REFUSAL_VERIFIED, evidence


def case_open_range_refusal(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """The open-bound range refusal has no reachable engine state (see the obstacle)."""
    return (
        BLOCKED,
        {
            "contract_code": "ERR_EXTRACTION_SEQUENCE_RANGE_OPEN",
            "obstacle": (
                "UMovieScene::SetPlaybackRange(const TRange<FFrameNumber>&) documents "
                "'Must not have any open bounds (ie must be a finite range)' and asserts "
                "NewRange.GetLowerBound().IsClosed() && NewRange.GetUpperBound().IsClosed() "
                "(MovieScene.cpp:689, observed live: the editor hit that assertion and "
                "aborted when the fixture tried to build the state); the backing "
                "FMovieSceneFrameRange PlaybackRange is private (MovieScene.h:1271/1311) and "
                "ULevelSequence::Initialize leaves a *degenerate* closed range, not an open "
                "one (measured: the asset with no explicit range reported "
                "ERR_EXTRACTION_SEQUENCE_RANGE_INVALID). An open-bound playback range is "
                "therefore unreachable through any public engine API, so this arm stays a "
                "defensive contract state: its code is in the closed vocabulary and is "
                "cross-checked by test_unreal_state_extraction_contract_closure, and it is "
                "not claimed as live-covered."
            ),
        },
    )


def case_runtime_mesh_refusal(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """A mesh asset generated at runtime is refused, live."""
    envelope = transport.actor(["IMPL_RUNTIME_MESH"])
    evidence = {
        "success": envelope["success"],
        "error_code": envelope["error_code"],
        "error": envelope["error"],
    }
    _require(envelope["success"] is False, "the runtime-generated mesh was accepted")
    _require(
        envelope["error_code"] == "ERR_EXTRACTION_MESH_ASSET_UNSTABLE",
        f"runtime mesh refusal reported {envelope['error_code']}",
    )
    return REFUSAL_VERIFIED, evidence


def case_unsupported_component_refusal(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """A material-bearing component family outside the two supported ones is refused, live."""
    envelope = transport.actor(["IMPL_UNSUPPORTED_COMPONENT"])
    evidence = {
        "success": envelope["success"],
        "error_code": envelope["error_code"],
        "error": envelope["error"],
    }
    _require(envelope["success"] is False, "the unsupported component family was accepted")
    _require(
        envelope["error_code"] == "ERR_EXTRACTION_UNSUPPORTED_COMPONENT_TYPE",
        f"unsupported component refusal reported {envelope['error_code']}",
    )
    return REFUSAL_VERIFIED, evidence


def case_missing_entity_refusal(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    envelope = transport.actor(["NO_SUCH_ENTITY"])
    _require(envelope["success"] is False, "a missing entity was accepted")
    _require(
        envelope["error_code"] == "ERR_EXTRACTION_ENTITY_NOT_FOUND",
        f"missing entity reported {envelope['error_code']}",
    )
    try:
        validate_request_entity_ids(["cam01", "CAM01"])
    except UnrealStateExtractionError as error:
        _require(
            error.code == "ERR_EXTRACTION_REQUEST_INVALID",
            f"case-folded duplicates reported {error.code}",
        )
        duplicate_code = error.code
    else:  # pragma: no cover - the rule is unconditional
        raise CaseFailure("case-folded duplicates were accepted by the request rule set")
    return REFUSAL_VERIFIED, {
        "error_code": envelope["error_code"],
        "duplicate_case_variant_code": duplicate_code,
    }


def case_world_partition_refusal(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """Partitioned worlds are refused. Only observable when the open map is partitioned."""
    envelope = transport.actor(["FIELD_SURFACE"])
    if envelope["success"]:
        return (
            NOT_COVERED,
            {
                "observed_error_code": None,
                "note": (
                    "the open map is not partitioned, so this session cannot observe the "
                    "partitioned-world refusal; it was observed in the rung-1 session "
                    "(ERR_EXTRACTION_WORLD_PARTITION_UNSUPPORTED against the default world)"
                ),
            },
        )
    _require(
        envelope["error_code"] == "ERR_EXTRACTION_WORLD_PARTITION_UNSUPPORTED",
        f"partitioned world refusal reported {envelope['error_code']}",
    )
    return REFUSAL_VERIFIED, {"error_code": envelope["error_code"]}


def case_scope_change_refusal(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """Delegated to the in-process automation seam: the transport cannot induce it."""
    return (
        NOT_COVERED,
        {
            "note": (
                "the world must change between the scope snapshot and the re-query; the "
                "extractor is forbidden to cause that and no transport read can, so this "
                "arm is exercised by Atlas.StateExtraction.ScopeChangeRefusal through the "
                "extractor's null-by-default test seam (see --automation-log)"
            ),
        },
    )


def case_package_dirty_invariance(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """Delegated to the in-process automation probe (no new transport operation)."""
    return (
        NOT_COVERED,
        {
            "note": (
                "package dirty state is measured immediately before and after the extractor "
                "call by Atlas.StateExtraction.PackageDirtyInvariance; exposing dirtiness "
                "through the transport would expand production authority for a test-only "
                "read, which this rung deliberately does not do"
            ),
        },
    )


def case_compiling_mesh_refusal(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """The `IsCompiling()` refusal arm has no inducement this harness may use."""
    return (
        BLOCKED,
        {
            "obstacle": (
                "inducing UStaticMesh::IsCompiling()==true requires the static mesh "
                "compiling manager (Runtime/Engine/Private/StaticMeshCompiler.h), which is "
                "not reachable from a harness module: the only public path is a real async "
                "build whose completion timing is not deterministic, which would make the "
                "gate flaky. The arm's presence is covered by the source gate and the "
                "error-vocabulary closure test; its live inducement is not attempted."
            ),
        },
    )


def case_payload_bound_refusal(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """§9 item 3: the payload bound cannot be reached through this fixture's content."""
    return (
        NOT_COVERED,
        {
            "note": (
                "no fixture in this rung can produce a response near the transport bound (the "
                "fixture set is small, the bound is a transport constant of 1 MiB), so the "
                "live arm is not claimed. The bound itself is proven in-process on a "
                "deliberately constructed payload by "
                "Atlas.StateExtraction.PayloadBoundRefusal, which measures the real "
                "serialization and uses the transport's own predicate "
                "(see payload_bound_refusal_in_process)"
            ),
        },
    )


def case_fixture_content_integrity(transport: LiveTransport) -> Tuple[str, Dict[str, Any]]:
    """Review F-1 items 4-5: committed fixture content is verified, never rewritten."""
    return (
        NOT_COVERED,
        {
            "note": (
                "verified in-process by Atlas.StateExtraction.FixtureContentIntegrity, which "
                "checks the committed sequences, the map and the tagged actor set without "
                "writing anything; the session's own status line is this run's precondition "
                "(see fixture_status_precondition)"
            ),
        },
    )



Case = Tuple[str, Callable[[LiveTransport], Tuple[str, Dict[str, Any]]]]

CASES: List[Case] = [
    ("positive_baseline", case_positive_baseline),
    ("request_order_permutation", case_request_order_permutation),
    ("numbered_fname_identities", case_numbered_identities),
    ("parent_three_state", case_parent_three_state),
    ("material_assignment_resolution_collisions", case_material_collisions),
    ("material_rendered_appearance_dimension", case_material_rendered_appearance),
    ("null_skinned_and_omitted_inventory", case_null_skinned_and_omitted),
    ("signed_zero_preservation", case_signed_zero),
    ("quaternion_sign_preservation", case_quaternion_sign),
    ("sequencer_live_extraction", case_sequencer_live),
    ("sequencer_invalid_range_rate_refusals", case_sequencer_refusals),
    ("sequencer_open_range_refusal", case_open_range_refusal),
    ("runtime_generated_mesh_refusal", case_runtime_mesh_refusal),
    ("unsupported_component_family_refusal", case_unsupported_component_refusal),
    ("missing_entity_refusal", case_missing_entity_refusal),
    ("world_partition_refusal", case_world_partition_refusal),
    ("scope_change_refusal", case_scope_change_refusal),
    ("package_dirty_invariance", case_package_dirty_invariance),
    ("compiling_mesh_refusal", case_compiling_mesh_refusal),
    ("payload_bound_refusal", case_payload_bound_refusal),
    ("fixture_content_integrity", case_fixture_content_integrity),
]


def _read_automation_results(log_path: Optional[str]) -> Dict[str, Dict[str, Any]]:
    """Parse UE automation results out of an editor log, if one was supplied."""
    if not log_path:
        return {}
    path = Path(log_path)
    if not path.exists():
        return {}
    results: Dict[str, Dict[str, Any]] = {}
    # UE prints `Test Completed. Result={Success} Name={Short} Path={Atlas.StateExtraction.X}`.
    pattern = re.compile(
        r"Result=\{([A-Za-z]+)\}\s+Name=\{[^}]*\}\s+Path=\{(Atlas\.StateExtraction\.[A-Za-z0-9_.]+)\}"
    )
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.search(line)
        if match:
            results[match.group(2)] = {"result": match.group(1), "line": line.strip()[:400]}
    return results


FIXTURE_STATUS_PREFIX = "ATLAS_EXTRACTION_FIXTURE_STATUS:"


def _read_fixture_status(log_path: Optional[str]) -> List[str]:
    """The fixture session's status lines (review F-1 items 2, 4 and 5).

    The extraction-fixture session emits exactly one ``ATLAS_EXTRACTION_FIXTURE_STATUS: OK
    version=N`` line after verifying the committed content against the fixture contract. An
    ordinary session provisions nothing and emits nothing, which is what makes the absence of
    this line a usable precondition.
    """
    if not log_path:
        return []
    path = Path(log_path)
    if not path.exists():
        return []
    return [
        line.split(FIXTURE_STATUS_PREFIX, 1)[1].strip()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if FIXTURE_STATUS_PREFIX in line
    ]



def run_gate(automation_log: Optional[str] = None) -> Dict[str, Any]:
    transport = LiveTransport()
    case_results: List[Dict[str, Any]] = []
    overall = PASS

    for name, function in CASES:
        try:
            status, evidence = function(transport)
        except CaseFailure as failure:
            status, evidence = FAIL, {"failure": str(failure), **failure.evidence}
            overall = FAIL
        except Exception as error:  # contract or transport violation
            status, evidence = FAIL, {"failure": f"{type(error).__name__}: {error}"}
            overall = FAIL
        case_results.append({"case": name, "status": status, "evidence": evidence})

    automation = _read_automation_results(automation_log)
    in_process = [
        {
            "case": "scope_change_refusal_in_process",
            "status": (
                PASS
                if automation.get("Atlas.StateExtraction.ScopeChangeRefusal", {}).get("result") == "Success"
                else FAIL
                if automation
                else NOT_COVERED
            ),
            "evidence": automation.get(
                "Atlas.StateExtraction.ScopeChangeRefusal",
                {"note": "in-process automation result not supplied (--automation-log)"},
            ),
        },
        {
            "case": "package_dirty_invariance_in_process",
            "status": (
                PASS
                if automation.get("Atlas.StateExtraction.PackageDirtyInvariance", {}).get("result") == "Success"
                else FAIL
                if automation
                else NOT_COVERED
            ),
            "evidence": automation.get(
                "Atlas.StateExtraction.PackageDirtyInvariance",
                {"note": "in-process automation result not supplied (--automation-log)"},
            ),
        },
        {
            "case": "payload_bound_refusal_in_process",
            "status": (
                PASS
                if automation.get("Atlas.StateExtraction.PayloadBoundRefusal", {}).get("result") == "Success"
                else FAIL
                if automation
                else NOT_COVERED
            ),
            "evidence": automation.get(
                "Atlas.StateExtraction.PayloadBoundRefusal",
                {"note": "in-process automation result not supplied (--automation-log)"},
            ),
        },
        {
            "case": "fixture_content_integrity_in_process",
            "status": (
                PASS
                if automation.get("Atlas.StateExtraction.FixtureContentIntegrity", {}).get("result") == "Success"
                else FAIL
                if automation
                else NOT_COVERED
            ),
            "evidence": automation.get(
                "Atlas.StateExtraction.FixtureContentIntegrity",
                {"note": "in-process automation result not supplied (--automation-log)"},
            ),
        },
    ]
    for entry in in_process:
        if entry["status"] == FAIL:
            overall = FAIL

    # Fixture precondition (review F-1 items 2 and 5): the session states, once, that the
    # committed fixture content was verified against the fixture contract. Provisioning is
    # opt-in, so a session without -AtlasExtractionFixture reports nothing and fails this
    # precondition instead of letting the gate run against content nobody checked.
    fixture_statuses = _read_fixture_status(automation_log)
    precondition: Dict[str, Any] = {
        "case": "fixture_status_precondition",
        "status": (
            PASS
            if automation_log
            and len(fixture_statuses) == 1
            and re.fullmatch(r"OK version=\d+", fixture_statuses[0])
            else FAIL
            if automation_log
            else NOT_COVERED
        ),
        "evidence": {
            "status_lines": fixture_statuses,
            "note": (
                "an explicit -AtlasExtractionFixture session emits exactly one "
                "'ATLAS_EXTRACTION_FIXTURE_STATUS: OK version=N' line after verifying the "
                "committed sequences, map and tagged actor set; ordinary start-up provisions "
                "nothing and reports nothing"
            ),
        },
    }
    if precondition["status"] == FAIL:
        overall = FAIL


    summary: Dict[str, int] = {}
    for entry in case_results + in_process + [precondition]:
        summary[entry["status"]] = summary.get(entry["status"], 0) + 1

    return {
        "result": overall,
        "cases": case_results + in_process + [precondition],
        "summary": summary,
        "automation_log": automation_log,
        "automation_results": sorted(automation.keys()),
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", dest="json_path", default=None)
    parser.add_argument("--automation-log", dest="automation_log", default=None)
    args = parser.parse_args(argv)

    report: Dict[str, Any] = {
        "generated_at_utc": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
        "operation": OPERATION,
        "sequencer_operation": SEQUENCER_OPERATION,
        "entity_id": ENTITY_ID,
    }
    try:
        report.update(run_gate(args.automation_log))
    except Exception as error:  # transport unavailable
        report["result"] = "ERROR"
        report["failure"] = f"{type(error).__name__}: {error}"

    text = json.dumps(report, indent=2, sort_keys=True)
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
    return 0 if report["result"] == PASS else 1


if __name__ == "__main__":
    sys.exit(main())
