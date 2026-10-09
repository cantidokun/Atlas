"""A-REF conformance harness: binding gate, pure-path runner, evidence capture (R4F section 24).

The harness enforces the pre-mutation gate BEFORE invoking the executor, wires the witness
channel around the injected seams (R4F 10.6), records production-style mutator invocations
(harness-only recording delegate, R4F 16.5a), and produces the outcome normal form + evidence
artifact. The executor is invoked UNCHANGED.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from planning.blender.correction_executor import (
    execute_merge_vertex,
    execute_remove_degenerate_face,
    execute_remove_duplicate_face,
    execute_repair_face_winding,
)
from planning.blender.kernel import scene_input_digest

from tests.aref.aref_evidence import ComparisonResult, compare_normal_forms, evidence_artifact, outcome_normal_form
from tests.aref.aref_fixture import (AUTH_GATED_OPS, FixtureSpec, validate_authorization_fixture,
                                    validate_binding_map)
from tests.aref.aref_plan import (BindingError, PlanIdentity, check_plan_binding,
                                  plan_artifact_digest, plan_identity, raw_to_plan)
from tests.aref.aref_pure import PureGraph, fresh_graph, make_pure_extractor, make_pure_mutator
from tests.aref.aref_witness import WitnessChannel

EXECUTORS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "REMOVE_DUPLICATE_FACE": execute_remove_duplicate_face,
    "REMOVE_DEGENERATE_FACE": execute_remove_degenerate_face,
    "REPAIR_FACE_WINDING": execute_repair_face_winding,
    "REPAIR_MERGE_VERTEX": execute_merge_vertex,
}

AUTHORIZATION_READY = ("REPAIR_FACE_WINDING", "REPAIR_MERGE_VERTEX")


@dataclass
class CaseRun:
    case: str
    fixture_id: str
    operation: str
    receipt: Dict[str, Any]
    invocations: List[Dict[str, Any]]
    witness: WitnessChannel
    plan_identity: PlanIdentity
    scene_digest_pre: str
    report_digest_pre: str
    scene_digest_child: str
    report_digest_child: str
    normal_form: Dict[str, Any]
    evidence: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------------------------
# Graph witness (R4F 9.8): recorded independently of the canonical extraction.
# ---------------------------------------------------------------------------------------------

def graph_witness(graph: PureGraph) -> Dict[str, Any]:
    """The graph-level witness: names, types, datablock names, sharing groups, order."""
    objects = []
    for name in graph.object_names_sorted():
        obj = graph.objects[name]
        db_name = None
        if obj.db_key is not None:
            db_name = graph.datablocks[obj.db_key].db_name
        objects.append({"name": name, "type": obj.type, "data_block_name": db_name})
    shared: Dict[str, List[str]] = {}
    for db_key, db in graph.datablocks.items():
        refs = sorted(o.object_id for o in graph.objects.values() if o.db_key == db_key)
        shared[db.db_name] = refs
    slots: List[List[Any]] = []
    for name in graph.object_names_sorted():
        for slot in graph.objects[name].material_slots:
            slots.append([slot[0], slot[1]])
    return {"objects": objects, "shared": shared, "material_slots": slots,
            "order": graph.object_names_sorted()}


def check_graph_witness(spec: FixtureSpec, witness: Dict[str, Any]) -> None:
    expected = spec.expected["graph_witness"]
    for key in ("objects", "shared", "order", "material_slots"):
        if key in expected and witness.get(key) != expected[key]:
            raise BindingError(
                f"graph witness mismatch [{key}]: observed {witness.get(key)!r} != declared {expected.get(key)!r}")


# ---------------------------------------------------------------------------------------------
# The pure-path runner.
# ---------------------------------------------------------------------------------------------

def run_pure_case(spec: FixtureSpec, plan_raw: Dict[str, Any]) -> CaseRun:
    """Execute one conformance case on the PURE path with the pre-mutation gate enforced.

    Order (normative; R4F 24 steps 3-9): fresh graph -> witness -> pre-extraction -> BINDING
    (witness + pre-digests + plan identity; fail closed BEFORE the executor is reachable) ->
    executor invocation with witnessed seams + recording mutator -> post extraction -> normal
    form + evidence.
    """
    graph = fresh_graph(spec)
    witness = WitnessChannel()
    extractor = make_pure_extractor(spec)

    # --- pre-state + binding gate (STRICTLY BEFORE MUTATION) ------------------------------
    scene0, report0 = extractor(graph)
    scene_digest = scene_input_digest(scene0)
    report_digest = report0.digest()
    if scene_digest != spec.expected["pre_digest"]:
        raise BindingError(f"pure pre-state digest {scene_digest} != declared {spec.expected['pre_digest']}")
    check_graph_witness(spec, graph_witness(graph))

    plan = raw_to_plan(plan_raw)
    ident = plan_identity(plan)
    check_plan_binding(plan, plan_raw, spec.expected["plan"])
    if report_digest != spec.expected["plan"]["source_report_digest"]:
        raise BindingError("pure pre-report digest != declared plan source_report_digest")

    # --- executor invocation on the pure path ----------------------------------------------
    recorder: List[Dict[str, Any]] = []
    inner_mutator = make_pure_mutator(spec.operation)

    def recording_mutator(engine_state: Any, **kwargs: Any) -> None:
        recorder.append(dict(kwargs))
        inner_mutator(engine_state, **kwargs)

    w_extractor = witness.wrap("pure", "extractor", extractor)
    w_mutator = witness.wrap("pure", "mutator", recording_mutator)

    # Run-time re-check (fail closed even if a caller mutated a loaded spec after load):
    # the marker refusal must hold at the runner, not only in the loader (R4F 8.2; implementation review m1).
    auth = validate_authorization_fixture(
        spec.authorization_fixture, case_requires_auth=spec.operation in AUTH_GATED_OPS)

    call_kwargs: Dict[str, Any] = {"engine_state": graph, "plan": plan,
                                   "mutator": w_mutator, "extractor": w_extractor}
    if spec.operation in AUTHORIZATION_READY:
        call_kwargs["authorization"] = auth
    receipt = EXECUTORS[spec.operation](**call_kwargs)

    # --- post-mutation observation ----------------------------------------------------------
    child_scene, child_report = extractor(graph)
    child_digest = scene_input_digest(child_scene)
    child_report_digest = child_report.digest()

    nf = outcome_normal_form(receipt, invocation_count=len(recorder), witness=witness, side="pure")
    run = CaseRun(
        case=spec.case, fixture_id=spec.fixture_id, operation=spec.operation,
        receipt=receipt, invocations=recorder, witness=witness, plan_identity=ident,
        scene_digest_pre=scene_digest, report_digest_pre=report_digest,
        scene_digest_child=child_digest, report_digest_child=child_report_digest,
        normal_form=nf,
    )
    run.evidence = evidence_artifact({
        "case": spec.case, "fixture_id": spec.fixture_id, "operation": spec.operation,
        "evidence_class": "CONFORMANCE",
        "oc_class": nf["oc_class"],
        "pre_state": {"spec_pre_digest": spec.expected["pre_digest"],
                      "pure_parent_digest": scene_digest,
                      "pure_report_digest": report_digest,
                      "digest_binding_ok": True},
        "plan_artifact": {"sha256_declared": spec.expected["plan"]["artifact_sha256"],
                          "sha256_computed": plan_artifact_digest(plan_raw),
                          "digest_binding_ok": (plan_artifact_digest(plan_raw)
                                                == spec.expected["plan"]["artifact_sha256"]),
                          "plan_id": ident.plan_id,
                          "source_report_digest": ident.source_report_digest,
                          "correction_ids": list(ident.correction_ids)},
        "outcome": {"pure": receipt.get("result"), "live": None},
        "normal_form": nf,
        "invocation_records": {"pure": recorder, "live": []},
        "witness": {"pure": witness.trace(), "live": []},
        "child": {"pure_digest": child_digest, "live_digest": None,
                  "pure_output_report_digest": receipt.get("output_report_digest")},
        "field_binding": {"class_per_field": validate_binding_map()},   # R4F 9.9 / evidence schema 18
        "authority": "none", "receipt_authority": "none",
    })
    return run


# ---------------------------------------------------------------------------------------------
# Fixture / artifact loading (expected literals computed once at fixture-authoring time).
# ---------------------------------------------------------------------------------------------

AREF_DIR = Path(__file__).resolve().parent
EXPECTED_DIR = AREF_DIR / "expected"
PLAN_DIR = AREF_DIR / "plan_artifacts"


def load_plan_artifact(fixture_id: str) -> Dict[str, Any]:
    path = PLAN_DIR / f"{fixture_id}.plan.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_expected(fixture_id: str) -> Dict[str, Any]:
    path = EXPECTED_DIR / f"{fixture_id}.expected.json"
    return json.loads(path.read_text(encoding="utf-8"))


def compare_runs(pure: CaseRun, live_evidence: Dict[str, Any]) -> ComparisonResult:
    """Compare a pure run against a live evidence record carrying its own normal form.

    The witness-class dimension is ACTIVE: the pure run's channel and the live record's recorded
    trace are both supplied (R4F 10.6; implementation review m4).
    """
    live_channel = WitnessChannel.from_trace(live_evidence.get("witness"))
    return compare_normal_forms(
        pure.normal_form, live_evidence["normal_form"],
        pure_child_digest=pure.scene_digest_child,
        live_child_digest=live_evidence.get("child_digest"),
        pure_witness=pure.witness, live_witness=live_channel,
    )
