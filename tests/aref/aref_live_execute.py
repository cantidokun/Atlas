"""A-REF EXECUTION launch (R4F 24 phase B, steps 7/9/10) — executor reachable ONLY after re-verification.

The execution launch rebuilds the fixture from the SAME spec, re-runs the step 3/4 assertions
in-process against the literals the controller verified, reconstructs the plan from the passed
artifact BYTES through the same contract, and only then invokes the existing executor in-process
via the production bridge runtime with the harness recording delegate (section 16.5a) around the
production mutators. Any mismatch before the executor raises, so zero invocations is a mechanical
fact recorded in the refusal evidence.

Blender-only module (imports bpy via the builder); the controller never imports it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import bpy

from planning.blender import correction_execution_bridge_runtime as bridge_runtime
from planning.blender.bpy_extraction import extract_scene
from planning.blender.extraction_payload import payload_to_scene_model
from planning.blender.kernel import run_scene_health, scene_input_digest, soccer_field_profile_default

from tests.aref.aref_live_builder import (assert_construction, build_scene_from_spec,
                                          raw_graph_witness)
from tests.aref.aref_live_common import (LiveError, artifact, canonical_digest,
                                         fixture_spec_sha256, load_case_live, read_json,
                                         sha256_hex, validate_handoff, verify_probe_record_file)
from tests.aref.aref_plan import plan_identity, raw_to_plan
from tests.aref.aref_witness import WitnessChannel

MUTATOR_NAMES = ("_face_removal_mutator", "_winding_mutator", "_merge_mutator")


def _jsonable(value: Any) -> Any:
    if value is None or type(value) in (bool, int, float, str):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    return {"__class__": f"{type(value).__module__}.{type(value).__qualname__}"}


def execute_stage(handoff_path: str) -> Dict[str, Any]:
    handoff = validate_handoff(read_json(Path(handoff_path)))
    fixture_id = handoff["fixture_id"]
    spec = load_case_live(fixture_id)

    # --- stage handoff verification (R4F 24: stale or mismatched inputs are rejected first) ----
    if fixture_spec_sha256(fixture_id) != handoff["spec_digest"]:
        raise LiveError("STALE-HANDOFF", "the fixture specification changed between the two stages")
    if canonical_digest(spec.expected) != handoff["expected_sha256"]:
        raise LiveError("STALE-HANDOFF", "the declared expected literals changed between the two stages")
    plan_path = Path(handoff["plan_path"])
    plan_bytes = plan_path.read_bytes()
    if sha256_hex(plan_bytes) != handoff["plan_sha256"]:
        raise LiveError("STALE-HANDOFF", "the plan artifact bytes do not match the verified digest")
    # M-d: the execution launch depends on the controller-verified PROBE artifact; verify it too.
    verify_probe_record_file(handoff["probe_record_path"], handoff["probe_artifact_sha256"],
                             fixture_id)

    # --- step 7: re-derivation + in-process re-verification STRICTLY BEFORE the executor call ---
    built = build_scene_from_spec(spec)
    witness = raw_graph_witness()
    passed = assert_construction(spec, witness)

    payload = extract_scene(bpy)
    scene = payload_to_scene_model(payload)
    report = run_scene_health(scene, soccer_field_profile_default())
    scene_digest = scene_input_digest(scene)
    report_digest = report.digest()
    if scene_digest != handoff["declared_pre_digest"]:
        raise LiveError("FIXTURE-BINDING-MISMATCH",
                        f"in-process re-verification: live scene digest {scene_digest} != verified "
                        f"{handoff['declared_pre_digest']}")
    if report_digest != handoff["declared_report_digest"]:
        raise LiveError("FIXTURE-BINDING-MISMATCH",
                        f"in-process re-verification: live report digest {report_digest} != verified "
                        f"{handoff['declared_report_digest']}")

    try:
        plan = raw_to_plan(json.loads(plan_bytes.decode("utf-8")))
    except Exception as exc:  # noqa: BLE001 - a non-self-consistent artifact is a binding refusal
        raise LiveError("FIXTURE-BINDING-MISMATCH",
                        f"the plan artifact bytes are not a self-consistent contract plan: "
                        f"{type(exc).__name__}: {exc}") from exc
    identity = plan_identity(plan)
    if identity.plan_id != handoff["declared_plan_id"]:
        raise LiveError("FIXTURE-BINDING-MISMATCH",
                        f"reconstructed plan_id {identity.plan_id} != verified {handoff['declared_plan_id']}")
    if list(identity.correction_ids) != list(handoff["declared_correction_ids"]):
        raise LiveError("FIXTURE-BINDING-MISMATCH",
                        f"reconstructed correction ids {list(identity.correction_ids)} != verified "
                        f"{list(handoff['declared_correction_ids'])}")

    # --- step 9: the EXECUTOR (reachable only through the checks above), recording delegate ----
    channel = WitnessChannel()
    invocations: List[Dict[str, Any]] = []
    originals = {name: getattr(bridge_runtime, name) for name in MUTATOR_NAMES}

    def recorder(seam_name: str):
        original = originals[seam_name]

        def recording(engine_state: Any, **kwargs: Any) -> Any:
            invocations.append({"ordinal": len(invocations) + 1, "seam": seam_name,
                                "operation": spec.operation,
                                "object_id": kwargs.get("object_id"),
                                "mesh_id": kwargs.get("mesh_id"),
                                "params": _jsonable(kwargs),
                                "outcome": None})
            try:
                result = original(engine_state, **kwargs)
            except BaseException as exc:  # recorded by the witness channel, then re-raised
                invocations[-1]["outcome"] = "raised"
                invocations[-1]["exception_type"] = type(exc).__name__
                raise
            invocations[-1]["outcome"] = "returned"
            return result

        return channel.wrap("live", "mutator", recording)

    request: Dict[str, Any] = {"operation": spec.operation}
    if spec.authorization_fixture is not None:
        request["authorization"] = spec.authorization_fixture
    wrapped = {name: recorder(name) for name in MUTATOR_NAMES}
    try:
        for name, wrapper in wrapped.items():
            setattr(bridge_runtime, name, wrapper)
        result = bridge_runtime._run_executor(plan, request)
    finally:
        for name, original in originals.items():
            setattr(bridge_runtime, name, original)
    receipt = result["receipt"]
    counted = result["mutator_invocations"]
    if counted != len(invocations):
        raise LiveError("MALFORMED-EVIDENCE",
                        f"bridge invocation counter {counted} != recorded {len(invocations)}")

    # --- step 10: post-mutation extraction + observation ---
    child_payload = extract_scene(bpy)
    child_scene = payload_to_scene_model(child_payload)
    child_report = run_scene_health(child_scene, soccer_field_profile_default())
    child_digest = scene_input_digest(child_scene)
    child_report_digest = child_report.digest()
    child_witness = raw_graph_witness()
    graph_unchanged = child_witness == witness

    return artifact("AREF-LIVE-EXECUTION", {
        "status": "EXECUTED",
        "stage": "EXECUTION",
        "fixture_id": fixture_id,
        "case": spec.case,
        "operation": spec.operation,
        "spec_digest": handoff["spec_digest"],
        "plan_sha256": handoff["plan_sha256"],
        "recheck": {"construct_assertions_passed": passed, "scene_digest": scene_digest,
                    "report_digest": report_digest, "plan_id": identity.plan_id,
                    "correction_ids": list(identity.correction_ids), "binding_ok": True},
        "invocations": invocations,
        "invocation_count": len(invocations),
        "receipt": _jsonable(receipt),
        "witness": channel.trace(),
        "child": {"scene_digest": child_digest, "report_digest": child_report_digest,
                  "graph_witness": child_witness, "graph_unchanged": graph_unchanged,
                  "output_report_digest": receipt.get("output_report_digest")},
        "blender": {"version": bpy.app.version_string},
    })
