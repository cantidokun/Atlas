"""A-REF PROBE launch (R4F 24 phase A, steps 1-5) — NO executor invocation is reachable here.

The probe constructs the live fixture from the FIX literals, asserts the raw graph, extracts,
checks the pre-state digests against the declared literals, runs the REAL planner once and
serialises the canonical plan artifact.

Mutation unreachability invariant (recorded, not promised): the executor MODULE is loaded in every
Blender process through planning/blender/__init__.py, so module absence is not the right
invariant. Instead all four executor ENTRY POINTS are guarded (tripwired) for the whole probe
body; a guard firing is a hard failure and zero guards fired is recorded in the evidence
(probe_purity). The probe body itself contains no executor call and imports no bridge module.

Blender-only module (imports bpy); the controller never imports it.
"""

from __future__ import annotations

import sys
from typing import Any, Dict

import bpy

from planning.blender.bpy_extraction import extract_scene
from planning.blender.extraction_payload import payload_to_scene_model
from planning.blender.kernel import run_scene_health, scene_input_digest, soccer_field_profile_default

from tests.aref import aref_plan
from tests.aref.aref_live_builder import (assert_construction, build_scene_from_spec,
                                          raw_graph_witness)
from tests.aref.aref_live_common import (LiveError, artifact, canonical_digest,
                                         fixture_spec_sha256, load_case_live, sha256_hex)
from tests.aref.aref_plan import (canonical_plan_bytes, construct_plan, plan_artifact_digest,
                                  plan_identity, plan_to_raw, repoint_face_ids)

EXECUTOR_MODULE = "planning.blender.correction_executor"
EXECUTOR_ENTRY_POINTS = ("execute_remove_duplicate_face", "execute_remove_degenerate_face",
                         "execute_repair_face_winding", "execute_merge_vertex")


class _ExecutorTripwire:
    """Mechanical proof that the probe cannot invoke the executor (R4F 24 step 5).

    The executor MODULE is loaded in every Blender process through planning/blender/__init__.py
    (package initialisation) — module absence is therefore not the right invariant. The invariant
    is INVOCATION reachability: all four entry points are wrapped with guards for the whole probe
    body; a guard firing is a hard failure, and zero guards fired is recorded evidence.
    """

    def __init__(self) -> None:
        import sys

        import planning.blender.correction_executor as executor

        self.module = executor
        self.touched: list = []
        self.originals = {}
        self.bridge_loaded = "planning.blender.correction_execution_bridge_runtime" in sys.modules
        self.bridge_wrapped: list = []
        for name in EXECUTOR_ENTRY_POINTS:
            original = getattr(executor, name, None)
            if original is None:
                continue
            self.originals[name] = original

            def guard(*args, _name=name, **kwargs):
                self.touched.append(_name)
                raise RuntimeError(f"executor entry point {_name} invoked inside the PROBE launch")

            setattr(executor, name, guard)
        # Defensive coverage (implementation review M-c): the bridge runtime binds the executor
        # functions with ``from ... import`` at module import time, so patching only the executor
        # module would not intercept a call made through the bridge's own bindings. The probe does
        # not import the bridge module; if it ever were loaded, its bindings are guarded too.
        if self.bridge_loaded:
            import planning.blender.correction_execution_bridge_runtime as bridge

            self.bridge_module = bridge
            for name in EXECUTOR_ENTRY_POINTS:
                bound = getattr(bridge, name, None)
                if bound is None:
                    continue
                self.originals[f"bridge.{name}"] = bound

                def guard_bridge(*args, _name=name, **kwargs):
                    self.touched.append(f"bridge.{_name}")
                    raise RuntimeError(f"executor entry point {_name} invoked inside the PROBE launch")

                setattr(bridge, name, guard_bridge)
                self.bridge_wrapped.append(name)

    def restore(self) -> None:
        for key, original in self.originals.items():
            if key.startswith("bridge."):
                setattr(self.bridge_module, key.split(".", 1)[1], original)
            else:
                setattr(self.module, key, original)


def _extract() -> Any:
    payload = extract_scene(bpy)
    scene = payload_to_scene_model(payload)
    report = run_scene_health(scene, soccer_field_profile_default())
    return payload, scene, report


def _plan_from_rule(spec: Any, report: Any, payload: Dict[str, Any]) -> Any:
    """The REAL planner once over the live pre-extraction report + the declared construction rule."""
    pc = spec.plan_construction
    rule = pc.get("rule")
    if rule == "PM":
        outcome = aref_plan.real_merge_plan(report, payload)
        if outcome.refusal_code is not None:
            raise LiveError("FIXTURE-BINDING-MISMATCH",
                            f"the real merge planning pass refused: {outcome.refusal_code} "
                            f"({outcome.refusal_detail})")
        return outcome.plan
    plan = aref_plan.real_plan(report)
    if rule == "P1" and pc.get("repoint"):   # the 16.2(b) documented re-point (declared as P1+repoint)
        # mirror the generator exactly: the BASE is the planner's own recorded pair for the single
        # correction of this operation; the declared re-point names the parameter set to record
        # (w1 :319-345 remap semantics; R4F 16.2(b)).
        target = [int(v) for v in pc["repoint"]["face_ids"]]
        dups = [c for c in plan.corrections if c.correction_type == spec.operation]
        if len(dups) != 1:
            raise LiveError("FIXTURE-BINDING-MISMATCH",
                            f"the planner emitted {len(dups)} corrections for {spec.operation}; "
                            "the re-point rule requires exactly one")
        base = tuple(int(v) for v in dups[0].parameters["face_ids"])
        return repoint_face_ids(plan, spec.operation, base, tuple(target))
    return construct_plan(plan, rule, spec.operation, pc)


def probe(fixture_id: str) -> Dict[str, Any]:
    tripwire = _ExecutorTripwire()
    try:
        return _probe_inner(fixture_id, tripwire)
    finally:
        tripwire.restore()


def _probe_inner(fixture_id: str, tripwire: "_ExecutorTripwire") -> Dict[str, Any]:
    spec = load_case_live(fixture_id)
    spec_digest = fixture_spec_sha256(fixture_id)

    built = build_scene_from_spec(spec)
    witness = raw_graph_witness()
    passed = assert_construction(spec, witness)

    payload, scene, report = _extract()
    scene_digest = scene_input_digest(scene)
    report_digest = report.digest()

    declared_pre = spec.expected["pre_digest"]
    declared_report = spec.expected["plan"]["source_report_digest"]
    if scene_digest != declared_pre:
        raise LiveError("FIXTURE-BINDING-MISMATCH",
                        f"live scene digest {scene_digest} != declared pre_digest {declared_pre}")
    if report_digest != declared_report:
        raise LiveError("FIXTURE-BINDING-MISMATCH",
                        f"live report digest {report_digest} != declared source_report_digest {declared_report}")

    plan = _plan_from_rule(spec, report, payload)
    raw = plan_to_raw(plan)
    identity = plan_identity(plan)
    sha = plan_artifact_digest(raw)
    declared_plan = spec.expected["plan"]
    if sha != declared_plan["artifact_sha256"]:
        raise LiveError("FIXTURE-BINDING-MISMATCH",
                        f"live plan artifact {sha} != declared {declared_plan['artifact_sha256']}")
    if identity.plan_id != declared_plan["plan_id"]:
        raise LiveError("FIXTURE-BINDING-MISMATCH",
                        f"live plan_id {identity.plan_id} != declared {declared_plan['plan_id']}")
    if list(identity.correction_ids) != list(declared_plan["correction_ids"]):
        raise LiveError("FIXTURE-BINDING-MISMATCH",
                        f"live correction ids {list(identity.correction_ids)} != declared "
                        f"{list(declared_plan['correction_ids'])}")

    if tripwire.touched:
        raise LiveError("FIXTURE-CONSTRUCTION-FAILURE",
                        f"the probe invoked executor entry point(s) {tripwire.touched}")

    return artifact("AREF-LIVE-PROBE", {
        "status": "PROBED",
        "stage": "PROBE",
        "fixture_id": fixture_id,
        "case": spec.case,
        "operation": spec.operation,
        "spec_digest": spec_digest,
        "expected_sha256": canonical_digest(spec.expected),
        "construct": {"objects": witness["objects"], "shared": witness["shared"],
                      "material_slots": witness["material_slots"], "order": witness["order"],
                      "assertions_passed": passed},
        "pre": {"live_scene_digest": scene_digest, "live_report_digest": report_digest,
                "declared_pre_digest": declared_pre, "declared_report_digest": declared_report,
                "digest_binding_ok": True},
        "plan": {"sha256": sha, "plan_id": identity.plan_id,
                 "source_report_digest": identity.source_report_digest,
                 "correction_ids": list(identity.correction_ids),
                 "canonical_text_sha256": sha256_hex(canonical_plan_bytes(raw)),
                 "raw": canonical_plan_bytes(raw).decode("utf-8", "strict")},
        "probe_purity": {"executor_entry_points_wrapped": sorted(
                             k for k in tripwire.originals if not k.startswith("bridge.")),
                         "bridge_runtime_loaded": tripwire.bridge_loaded,
                         "bridge_bindings_wrapped": sorted(tripwire.bridge_wrapped),
                         "executor_invocations": len(tripwire.touched),
                         "executor_module_loaded_via_package_init": EXECUTOR_MODULE in sys.modules,
                         "note": "the executor module is loaded by planning/blender/__init__.py in "
                                 "every process; the probe's guarantee is INVOCATION unreachability "
                                 "(all four entry points guarded for the whole probe body)"},
        "blender": {"version": bpy.app.version_string,
                    "scene_name": bpy.context.scene.name},
    })
